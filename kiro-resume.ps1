# kiro-resume.ps1
# Wrapper: launches the Python TUI picker, then execs `kiro-cli chat --resume <id>`

[CmdletBinding()]
param(
    [switch]$List,
    [switch]$Probe
)

$ErrorActionPreference = 'Stop'
$script  = Join-Path $env:USERPROFILE '.kiro\scripts\kiro-resume.py'
$target  = Join-Path $env:USERPROFILE '.kiro\.resume-target'

if (-not (Test-Path $script)) {
    Write-Error "missing $script"
    exit 1
}

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8       = '1'

$prevOut = [Console]::OutputEncoding
$prevIn  = [Console]::InputEncoding
try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
    [Console]::InputEncoding  = [System.Text.UTF8Encoding]::new()
} catch {}

if (-not $env:COLORTERM) { $env:COLORTERM = 'truecolor' }

if (Test-Path $target) { Remove-Item $target -Force }

$pyArgs = @($script)
if ($List)  { $pyArgs += '--list' }
if ($Probe) { $pyArgs += '--probe' }

& python @pyArgs
$code = $LASTEXITCODE

if ($List -or $Probe) { exit $code }

if (-not (Test-Path $target)) { exit 0 }

$sessionId = (Get-Content $target -Raw).Trim()
Remove-Item $target -Force -ErrorAction SilentlyContinue

if (-not $sessionId) { exit 0 }

try { [Console]::OutputEncoding = $prevOut } catch {}
try { [Console]::InputEncoding  = $prevIn  } catch {}

# Print past conversation before resuming
$jsonl = Join-Path $env:USERPROFILE ".kiro\sessions\cli\$sessionId.jsonl"
if (Test-Path $jsonl) {
    Write-Host "`n━━━ 과거 대화 내역 ━━━" -ForegroundColor Yellow
    Get-Content $jsonl -Encoding UTF8 | ForEach-Object {
        try {
            $msg = $_ | ConvertFrom-Json
            $kind = $msg.kind
            if ($kind -eq 'Prompt') {
                $text = $msg.data.content | Where-Object { $_.kind -eq 'text' } | Select-Object -First 1 -ExpandProperty data
                if ($text) {
                    Write-Host "`n나: " -ForegroundColor Cyan -NoNewline
                    Write-Host ($text.Substring(0, [Math]::Min($text.Length, 300)))
                }
            } elseif ($kind -eq 'AssistantMessage') {
                $text = $msg.data.content | Where-Object { $_.kind -eq 'text' } | Select-Object -First 1 -ExpandProperty data
                if ($text) {
                    Write-Host "`nKiro: " -ForegroundColor Green -NoNewline
                    Write-Host ($text.Substring(0, [Math]::Min($text.Length, 300)))
                }
            }
        } catch {}
    }
    Write-Host "`n━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor Yellow
}

& kiro-cli chat --resume-id $sessionId
exit $LASTEXITCODE
