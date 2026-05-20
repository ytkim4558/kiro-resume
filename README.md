# kiro-resume

Kiro CLI 의 이전 세션을 빠르게 찾아 이어갈 수 있는 인터랙티브 TUI 피커.

`kiro-cli chat --resume` 의 기본 동작은 세션 ID 만 요구하지만, 이 도구는
**좌측에 세션 리스트, 우측에 전체 대화 내용**을 보여주는 두-패널 인터페이스에서
바로 골라 이어갈 수 있게 한다.

## 주요 특징

- **두-패널 TUI** (Textual 기반): 좌측 세션 리스트 ↔ 우측 전체 대화 스크롤
- **세션 메타 자동 파싱**: 제목, 마지막 활동 시각, 작업 경로
- **CMD / PowerShell 양쪽 지원**: `.cmd`, `.ps1` 래퍼 제공
- **한글 안전**: PowerShell ↔ Python ↔ kiro-cli 인코딩 UTF-8 강제

## 요구 사항

- Windows (PowerShell 5.1 또는 7.x, CMD 도 가능)
- Python 3.11 이상
- [Kiro CLI](https://kiro.dev) (`kiro-cli` 가 PATH 에 있어야 함)
- `pip install --user textual`

## 설치

```powershell
# 1. 저장소 클론
git clone https://github.com/ytkim4558/kiro-resume.git "$env:USERPROFILE\.kiro\scripts"

# 2. 의존성 설치
pip install --user textual

# 3. PATH 에 스크립트 디렉터리 추가 (영구)
$scripts = "$env:USERPROFILE\.kiro\scripts"
$current = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($current.Split(';') -notcontains $scripts) {
    [Environment]::SetEnvironmentVariable('Path', "$current;$scripts", 'User')
}
```

새 셸 창을 띄우면 어느 디렉터리에서든 `kiro-resume` 사용 가능.

## 사용법

```powershell
kiro-resume          # TUI 피커 띄우기
kiro-resume -List    # TUI 없이 stdout 리스트 (스크립팅용)
kiro-resume -Probe   # 환경/파싱 진단
```

### 조작

| 키 | 동작 |
|---|---|
| `↑` `↓` | 세션 이동 |
| `Enter` 또는 `s` | 선택해 이어가기 |
| `Tab` | 좌/우 패널 포커스 전환 |
| 마우스 휠 | 우측 패널 스크롤 |
| `q` 또는 `Esc` | 종료 |

선택하면 `kiro-cli chat --resume <session-id>` 가 자동으로 실행된다.

## 동작 원리

1. **세션 위치**: `~/.kiro/sessions/cli/` 의 `.json` + `.jsonl` 파일들이 Kiro CLI 세션 로그.
2. **메타 추출**: `.json` 에서 title, created_at, updated_at, cwd 파싱.
3. **대화 파싱**: `.jsonl` 에서 `Prompt` (user) / `AssistantMessage` kind 추출.
4. **이어가기 핸드오프**: TUI 종료 시 선택된 ID 를 `~/.kiro/.resume-target` 에 쓰고, PowerShell 래퍼가 읽어 `kiro-cli chat --resume <id>` 실행.

## 관련 도구

| 도구 | 대상 CLI | 레포 |
|---|---|---|
| [claude-resume](https://github.com/ytkim4558/claude-resume) | Claude Code | Python + Textual |
| [codex-resume](https://github.com/ytkim4558/codex-resume) | OpenAI Codex | Node.js + blessed |
| **kiro-resume** | Kiro CLI | Python + Textual |

## License

MIT — see [LICENSE](LICENSE).
