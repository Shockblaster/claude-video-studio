# video-studio setup for Windows 10/11 (PowerShell 5.1+).
#
#   powershell -ExecutionPolicy Bypass -File setup\setup-windows.ps1            # full setup
#   powershell -ExecutionPolicy Bypass -File setup\setup-windows.ps1 -NoSkills  # skip third-party skills
#
# What it does (nothing outside these places is touched):
#   1. ffmpeg, Node, Python 3.12 via winget (only if missing)
#   2. a Python venv at $VIDEO_STUDIO_HOME\venv with setup\requirements.txt
#   3. Rhubarb Lip Sync + MediaPipe models into $VIDEO_STUDIO_HOME\tools
#   4. copies the skill to %USERPROFILE%\.claude\skills\video-studio (an existing copy is moved to .claude\skills-archive first)
#   5. installs the third-party skills listed in setup\skills.txt with `npx skills add`
#   6. writes %USERPROFILE%\.video-studio\config.json and runs the smoke test
param([switch]$NoSkills)
$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Here
$HomeDir = if ($env:VIDEO_STUDIO_HOME) { $env:VIDEO_STUDIO_HOME } else { Join-Path $env:USERPROFILE "video-studio" }
$Skills = Join-Path $env:USERPROFILE ".claude\skills"
function Say($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Have($c) { [bool](Get-Command $c -ErrorAction SilentlyContinue) }
function RefreshPath { $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User") }

Say "1/6 Tools (ffmpeg, node, python)"
if (-not (Have "winget")) { throw "winget is needed (App Installer from the Microsoft Store)." }
if (-not (Have "ffmpeg")) { winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements; RefreshPath }
if (-not (Have "node"))   { winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements; RefreshPath }
$Py = $null
try { $Py = (& py -3.12 -c "import sys;print(sys.executable)") 2>$null } catch {}
if (-not $Py) {
  winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements; RefreshPath
  $Py = (& py -3.12 -c "import sys;print(sys.executable)")
}
foreach ($t in "ffmpeg","ffprobe","node","npx") { if (-not (Have $t)) { throw "missing: $t (open a new terminal and run again)" } }
Write-Host "python: $Py"

Say "2/6 Python venv + packages ($HomeDir\venv)"
New-Item -ItemType Directory -Force "$HomeDir\tools", "$HomeDir\assets" | Out-Null
$VPy = Join-Path $HomeDir "venv\Scripts\python.exe"
if (-not (Test-Path $VPy)) { & $Py -m venv (Join-Path $HomeDir "venv") }
& $VPy -m pip install --upgrade pip | Out-Null
& $VPy -m pip install -r (Join-Path $Here "requirements.txt")

Say "3/6 Rhubarb Lip Sync + MediaPipe models"
$Rb = Join-Path $HomeDir "tools\rhubarb"
$RbExe = Get-ChildItem $Rb -Recurse -Filter rhubarb.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $RbExe) {
  New-Item -ItemType Directory -Force $Rb | Out-Null
  $zip = Join-Path $Rb "rhubarb.zip"
  Invoke-WebRequest "https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.14.0/Rhubarb-Lip-Sync-1.14.0-Windows.zip" -OutFile $zip
  Expand-Archive $zip -DestinationPath $Rb -Force; Remove-Item $zip
  $RbExe = Get-ChildItem $Rb -Recurse -Filter rhubarb.exe | Select-Object -First 1
}
$Mp = Join-Path $HomeDir "tools\mediapipe"; New-Item -ItemType Directory -Force $Mp | Out-Null
$base = "https://storage.googleapis.com/mediapipe-models"
$models = @{
  "face_landmarker.task"       = "$base/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
  "pose_landmarker_heavy.task" = "$base/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
  "hand_landmarker.task"       = "$base/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
}
foreach ($k in $models.Keys) { $f = Join-Path $Mp $k; if (-not (Test-Path $f)) { Invoke-WebRequest $models[$k] -OutFile $f } }

Say "4/6 Skill -> $Skills\video-studio"
New-Item -ItemType Directory -Force $Skills | Out-Null
$Dest = Join-Path $Skills "video-studio"
if (Test-Path $Dest) {
  $Bk = Join-Path $env:USERPROFILE (".claude\skills-archive\" + (Get-Date -Format "yyyy-MM-dd-HHmmss") + "-video-studio")
  New-Item -ItemType Directory -Force (Split-Path $Bk) | Out-Null
  Move-Item $Dest $Bk; Write-Host "existing copy moved to $Bk"
}
Copy-Item (Join-Path $Root "video-studio") $Dest -Recurse

if (-not $NoSkills) {
  Say "5/6 Third-party skills (setup\skills.txt)"
  Get-Content (Join-Path $Here "skills.txt") | Where-Object { $_ -match '\|' -and $_ -notmatch '^#' } | ForEach-Object {
    $repo, $skill = $_.Split('|') | ForEach-Object { $_.Trim() }
    Write-Host "  $repo -> $skill"
    & npx --yes skills add $repo --skill $skill -g -y -a claude-code | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Host "  (failed: install it later by hand)" }
  }
}

Say "6/6 Config + smoke test"
$CfgDir = Join-Path $env:USERPROFILE ".video-studio"; New-Item -ItemType Directory -Force $CfgDir | Out-Null
@{ home = $HomeDir; rhubarb = $RbExe.FullName; mediapipe_models = $Mp; sound_python = $VPy } |
  ConvertTo-Json | Out-File (Join-Path $CfgDir "config.json") -Encoding ascii
$env:HYPERFRAMES_PYTHON = $VPy
[Environment]::SetEnvironmentVariable("HYPERFRAMES_PYTHON", $VPy, "User")
& $VPy -I (Join-Path $Dest "scripts\smoke_test.py")
if ($LASTEXITCODE -ne 0) { throw "Smoke test failed: read the output above." }

Write-Host "`nDone. Run the skill's Python scripts with:  $VPy -I <script>"
Write-Host "HYPERFRAMES_PYTHON is set for your user (Kokoro TTS uses it). Open a new terminal to pick it up."
Write-Host "Optional: add the Playwright MCP, video-analyzer and mcp-video servers in Claude Code (see references\toolchain.md)."
