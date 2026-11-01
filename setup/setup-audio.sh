#!/bin/sh
# Optional: the beat-sync + pro-sound tools (scripts/score.py, scripts/beatmix.py). macOS / Linux.
#   earshot 0.4 (MIT, github.com/Leonxlnx/earshot): 252 audited code-made SFX, kits, critique  -> its own venv
#   lemo-opuscar (MIT code, github.com/lemomo-ai/lemo-opuscar): sampler + CC0 / CC BY sample libraries (~1.3 GB)
# Usage: sh setup/setup-audio.sh [--with-models]   (--with-models also fetches earshot's 1.1 GB listening models)
set -e
HOME_DIR="${VIDEO_STUDIO_HOME:-$HOME/video-studio}"; T="$HOME_DIR/tools"; mkdir -p "$T"
[ -d "$T/earshot" ] || git clone --depth 1 https://github.com/Leonxlnx/earshot.git "$T/earshot"
[ -d "$T/lemo-opuscar" ] || git clone --depth 1 https://github.com/lemomo-ai/lemo-opuscar.git "$T/lemo-opuscar"
python3 -m venv "$T/earshot/.venv"; AP="$T/earshot/.venv/bin/python"
"$AP" -m pip install -q --upgrade pip
"$AP" -m pip install -q torch --index-url https://download.pytorch.org/whl/cpu
"$AP" -m pip install -q -e "$T/earshot"
( cd "$T/lemo-opuscar" && for lib in vsco2ce vcsl freepats salamander; do sh tools/fetch.sh instruments $lib; done )
[ "${1:-}" = "--with-models" ] && "$AP" -m earshot doctor --fetch
python3 - "$AP" "$T/lemo-opuscar" <<'PY'
import json, pathlib, sys
f = pathlib.Path.home() / ".video-studio" / "config.json"; f.parent.mkdir(exist_ok=True)
c = json.loads(f.read_text()) if f.exists() else {}
c.update(audio_python=sys.argv[1], opuscar=sys.argv[2]); f.write_text(json.dumps(c, indent=1)); print("config:", f)
PY
"$AP" -m earshot doctor | tail -3
