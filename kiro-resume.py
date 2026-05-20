#!/usr/bin/env python3
"""Interactive Kiro CLI session picker (v14-enhanced).

Lists past sessions with multi-line raw preview, tool call tracking,
numbered turns, and message counts. On Enter writes the chosen session id
to ~/.kiro/.resume-target so a wrapper script can exec `kiro-cli chat --resume <id>`.

Usage:
  python kiro-resume.py            # interactive TUI
  python kiro-resume.py --list     # plain stdout listing (no TUI)
  python kiro-resume.py --probe    # parsing/setup smoke test
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HOME = Path.home()
SESSIONS_DIR = HOME / ".kiro" / "sessions" / "cli"
RESUME_TARGET_PATH = HOME / ".kiro" / ".resume-target"
INLINE_PREVIEW_LINES = 4


@dataclass
class Session:
    id: str
    title: str
    cwd: str
    created_at: Optional[str]
    updated_at: Optional[str]
    jsonl_path: Path
    user_msg_count: int = 0
    total_msg_count: int = 0
    tool_names: list[str] = field(default_factory=list)


def parse_session(json_path: Path) -> Optional[Session]:
    try:
        data = json.loads(json_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    sid = data.get("session_id", json_path.stem)
    title = data.get("title", "")
    jsonl = json_path.with_suffix(".jsonl")
    if not jsonl.exists():
        return None

    # Quick scan for counts + tool names
    user_count = 0
    total_count = 0
    tools = set()
    try:
        with jsonl.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = obj.get("kind")
                if kind == "Prompt":
                    user_count += 1
                    total_count += 1
                elif kind == "AssistantMessage":
                    total_count += 1
                    for part in obj.get("data", {}).get("content", []):
                        if isinstance(part, dict) and part.get("kind") == "toolUse":
                            tool_data = part.get("data", {})
                            tu = tool_data.get("toolUse", {})
                            name = tu.get("name", "")
                            if name:
                                tools.add(name)
                elif kind == "ToolResults":
                    total_count += 1
    except OSError:
        pass

    if not title and user_count == 0:
        title = "(untitled)"

    return Session(
        id=sid,
        title=title or "(untitled)",
        cwd=data.get("cwd", ""),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
        jsonl_path=jsonl,
        user_msg_count=user_count,
        total_msg_count=total_count,
        tool_names=sorted(tools)[:8],
    )


def find_sessions() -> list[Session]:
    if not SESSIONS_DIR.is_dir():
        return []
    out: list[Session] = []
    for p in SESSIONS_DIR.glob("*.json"):
        s = parse_session(p)
        if s:
            out.append(s)
    out.sort(key=lambda s: s.updated_at or "", reverse=True)
    return out


def relative_time(iso_ts: Optional[str]) -> str:
    if not iso_ts:
        return "?"
    try:
        ts = iso_ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        secs = int((now - dt).total_seconds())
        if secs < 60:
            return "방금 전"
        if secs < 3600:
            return f"{secs // 60}분 전"
        if secs < 86400:
            return f"{secs // 3600}시간 전"
        if secs < 172800:
            return "어제"
        if secs < 604800:
            return f"{secs // 86400}일 전"
        return dt.astimezone().strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return "?"


def read_messages(jsonl_path: Path) -> list[tuple[str, str, Optional[int], list[str]]]:
    """Return [(role, text, timestamp, tool_names), ...] per turn."""
    out: list[tuple[str, str, Optional[int], list[str]]] = []
    try:
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = obj.get("kind")
                if kind not in ("Prompt", "AssistantMessage"):
                    continue
                data = obj.get("data", {})
                content = data.get("content", [])
                texts = []
                turn_tools = []
                for part in content:
                    if isinstance(part, dict):
                        if part.get("kind") == "text":
                            texts.append(part.get("data", ""))
                        elif part.get("kind") == "toolUse":
                            tu = part.get("data", {}).get("toolUse", {})
                            name = tu.get("name", "")
                            if name:
                                turn_tools.append(name)
                text = "\n".join(texts).strip()
                if not text and not turn_tools:
                    continue
                ts = data.get("meta", {}).get("timestamp")
                role = "user" if kind == "Prompt" else "assistant"
                out.append((role, text, ts, turn_tools))
    except OSError:
        pass
    return out


def render_inline(s: Session, lines: int = INLINE_PREVIEW_LINES) -> str:
    """v14-style multi-line raw preview for list item."""
    parts = []
    try:
        with s.jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("kind") == "Prompt":
                    data = obj.get("data", {})
                    for part in data.get("content", []):
                        if isinstance(part, dict) and part.get("kind") == "text":
                            t = part.get("data", "").strip().replace("\n", " ")
                            if t:
                                parts.append(t[:80])
                if len(parts) >= lines:
                    break
    except OSError:
        pass
    return "\n".join(parts[:lines]) if parts else s.title[:80]


# ----------------------------- modes -----------------------------

def mode_list() -> int:
    sessions = find_sessions()
    if not sessions:
        print("(no sessions found)")
        return 0
    for s in sessions:
        rel = relative_time(s.updated_at)
        title = s.title[:60].replace("\n", " ")
        tools_str = f" [{', '.join(s.tool_names[:4])}]" if s.tool_names else ""
        print(f"{rel:>10}  {s.user_msg_count}u/{s.total_msg_count}m  {s.id[:8]}  {title}{tools_str}")
    return 0


def mode_probe() -> int:
    print(f"sessions dir: {SESSIONS_DIR}  exists={SESSIONS_DIR.is_dir()}")
    sessions = find_sessions()
    print(f"sessions: {len(sessions)}")
    for s in sessions[:5]:
        tools_str = f" [{', '.join(s.tool_names[:4])}]" if s.tool_names else ""
        print(f"  - {s.id[:8]}  {s.user_msg_count}u/{s.total_msg_count}m  title={s.title[:40]!r}{tools_str}")
    try:
        import textual
        print(f"textual: {textual.__version__}")
    except ImportError as e:
        print(f"textual: NOT INSTALLED ({e})")
    return 0


def mode_tui() -> int:
    try:
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.containers import Horizontal, VerticalScroll
        from textual.widgets import Footer, Header, Label, ListItem, ListView, Static
    except ImportError:
        print("error: textual not installed. run: pip install --user textual", file=sys.stderr)
        return 2

    sessions = find_sessions()
    if not sessions:
        print("no sessions found", file=sys.stderr)
        return 1

    def make_label(s: Session) -> str:
        rel = relative_time(s.updated_at)
        meta = f"{s.user_msg_count}u/{s.total_msg_count}m"
        title = s.title[:45].replace("\n", " ")
        tools_str = f"[{', '.join(s.tool_names[:3])}]" if s.tool_names else ""
        return f"{rel:>8} {meta:>8}  {title}\n{' ' * 18}{tools_str}"

    class KiroResumeApp(App):
        CSS = """
        #pane { height: 1fr; }
        #list { width: 42%; border-right: solid $primary; }
        #detail-scroll { width: 58%; }
        #detail { padding: 1 2; }
        ListItem { height: 3; }
        """
        BINDINGS = [
            Binding("q", "quit", "종료", priority=True),
            Binding("escape", "quit", "종료", priority=True),
            Binding("s", "resume", "이어가기"),
        ]
        TITLE = "kiro-resume"
        SUB_TITLE = f"Shift+↑/↓ scrolls preview. Enter resumes. | {len(sessions)}/{len(sessions)}"

        msgs_cache: dict[str, list[tuple[str, str, Optional[int], list[str]]]] = {}

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            with Horizontal(id="pane"):
                yield ListView(id="list")
                with VerticalScroll(id="detail-scroll"):
                    yield Static(id="detail", markup=False, expand=True)
            yield Footer()

        def on_mount(self) -> None:
            lv = self.query_one("#list", ListView)
            for s in sessions:
                item = ListItem(Label(make_label(s)))
                lv.append(item)
            if sessions:
                lv.index = 0
                self.show_detail(0)
            lv.focus()

        def on_list_view_selected(self, event) -> None:
            self.action_resume()

        def show_detail(self, idx: int) -> None:
            from rich.text import Text

            if idx < 0 or idx >= len(sessions):
                return
            s = sessions[idx]
            rel = relative_time(s.updated_at)
            absolute = ""
            if s.updated_at:
                try:
                    ts = s.updated_at.replace("Z", "+00:00")
                    absolute = datetime.fromisoformat(ts).astimezone().strftime("%Y-%m-%d %H:%M")
                except Exception:
                    absolute = s.updated_at

            if s.id not in self.msgs_cache:
                self.msgs_cache[s.id] = read_messages(s.jsonl_path)
            msgs = self.msgs_cache[s.id]

            t = Text()
            t.append("제목", style="bold cyan")
            t.append(f"  {s.title[:80]}\n")
            t.append("마지막 활동", style="bold")
            t.append(f"  {rel}  ({absolute})\n")
            t.append("경로", style="bold")
            t.append(f"  {s.cwd}\n")
            t.append("메시지", style="bold")
            t.append(f"  {s.user_msg_count}u / {s.total_msg_count}m\n")
            if s.tool_names:
                t.append("도구", style="bold")
                t.append(f"  {', '.join(s.tool_names)}\n")
            t.append(f"{s.id}\n", style="dim")
            t.append("\n")
            t.append("─── 대화 (USER#/ASSISTANT# 형식) ───", style="bold yellow")
            t.append("\n\n")

            user_num = 0
            asst_num = 0
            for role, text, ts, turn_tools in msgs:
                hm = ""
                if ts:
                    try:
                        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        hm = dt.astimezone().strftime("%m-%d %H:%M")
                    except Exception:
                        pass
                if role == "user":
                    user_num += 1
                    t.append(f"=== USER #{user_num} ===", style="bold cyan")
                else:
                    asst_num += 1
                    t.append(f"=== ASSISTANT #{asst_num} ===", style="bold green")
                if hm:
                    t.append(f"  {hm}", style="dim")
                if turn_tools:
                    t.append(f"  [tools: {', '.join(turn_tools[:5])}]", style="yellow")
                t.append("\n")
                t.append(text[:600])
                t.append("\n\n")

            self.query_one("#detail", Static).update(t)
            try:
                self.query_one("#detail-scroll").scroll_home(animate=False)
            except Exception:
                pass

        def on_list_view_highlighted(self, event) -> None:
            idx = event.list_view.index
            if idx is not None:
                self.show_detail(idx)

        def action_resume(self) -> None:
            lv = self.query_one("#list", ListView)
            idx = lv.index
            if idx is None or idx < 0 or idx >= len(sessions):
                return
            RESUME_TARGET_PATH.parent.mkdir(parents=True, exist_ok=True)
            RESUME_TARGET_PATH.write_text(sessions[idx].id, encoding="utf-8")
            self.exit()

    KiroResumeApp().run()
    return 0


def main(argv: list[str]) -> int:
    if "--list" in argv:
        return mode_list()
    if "--probe" in argv:
        return mode_probe()
    return mode_tui()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
