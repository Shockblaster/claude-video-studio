# Optional: the beat-sync + pro-sound tools (scripts/score.py, scripts/beatmix.py). Windows.
#   earshot 0.4 (MIT, github.com/Leonxlnx/earshot) in its own venv; lemo-opuscar (MIT) sampler + CC0/CC BY samples (~1.3 GB)
# Usage: powershell -ExecutionPolicy Bypass -File setup\setup-audio.ps1 [-WithModels]
param([switch]$WithModels)
$ErrorActionPreference = "Stop"
$HomeDir = if ($env:VIDEO_STUDIO_HOME) { $env:VIDEO_STUDIO_HOME } else { Join-Path $env:USERPROFILE "video-studio" }
$T = Join-Path $HomeDir "tools"; New-Item -ItemType Directory -Force $T | Out-Null
$E = Join-Path $T "earshot"; $O = Join-Path $T "lemo-opuscar"
if (-not (Test-Path $E)) { git clone --depth 1 https://github.com/Leonxlnx/earshot.git $E }
if (-not (Test-Path $O)) { git clone --depth 1 https://github.com/lemomo-ai/lemo-opuscar.git $O }
python -m venv (Join-Path $E ".venv"); $AP = Join-Path $E ".venv\Scripts\python.exe"
& $AP -m pip install -q --upgrade pip
& $AP -m pip install -q torch --index-url https://download.pytorch.org/whl/cpu
& $AP -m pip install -q -e $E
# fetch.sh is POSIX: run its embedded Python directly. -X utf8: the Windows console is cp1252 and it prints arrows
$fetch = Get-Content (Join-Path $O "tools\fetch.sh") -Raw
$py = ($fetch -split "<<'PY'\r?\n")[1] -split "\r?\nPY" | Select-Object -First 1
$tmp = Join-Path $env:TEMP "opus_fetch.py"; Set-Content $tmp $py -Encoding utf8
Push-Location $O; & $AP -X utf8 $tmp instruments-vsco2ce instruments-vcsl instruments-freepats instruments-salamander; Pop-Location
if ($WithModels) { & $AP -X utf8 -m earshot doctor --fetch }
$CfgDir = Join-Path $env:USERPROFILE ".video-studio"; $Cfg = Join-Path $CfgDir "config.json"
New-Item -ItemType Directory -Force $CfgDir | Out-Null
$c = if (Test-Path $Cfg) { Get-Content $Cfg -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
$c | Add-Member -NotePropertyName audio_python -NotePropertyValue $AP -Force
$c | Add-Member -NotePropertyName opuscar -NotePropertyValue $O -Force
$c | ConvertTo-Json | Out-File $Cfg -Encoding ascii
& $AP -X utf8 -m earshot doctor | Select-Object -Last 3
