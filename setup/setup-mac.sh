#!/usr/bin/env bash
# video-studio setup for macOS (Apple Silicon or Intel). Also works on Linux if you install ffmpeg/node/python
# with your package manager first (the brew steps are skipped when the tools already exist).
#
#   bash setup/setup-mac.sh            # full setup
#   bash setup/setup-mac.sh --no-skills   # skip installing the third-party skills
#
# What it does (nothing outside these places is touched):
#   1. ffmpeg, Node, Python via Homebrew (only if missing)
#   2. a Python venv at $VIDEO_STUDIO_HOME/venv with setup/requirements.txt
#   3. Rhubarb Lip Sync + MediaPipe models into $VIDEO_STUDIO_HOME/tools
#   4. copies the skill to ~/.claude/skills/video-studio (an existing copy is moved to ~/.claude/skills-archive first)
#   5. installs the third-party skills listed in setup/skills.txt with `npx skills add`
#   6. writes ~/.video-studio/config.json and runs the smoke test
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
HOME_DIR="${VIDEO_STUDIO_HOME:-$HOME/video-studio}"
SKILLS="$HOME/.claude/skills"
OS="$(uname -s)"
say() { printf '\n==> %s\n' "$*"; }

say "1/6 Tools (ffmpeg, node, python)"
if [ "$OS" = "Darwin" ]; then
  command -v brew >/dev/null || { echo "Homebrew is needed: https://brew.sh"; exit 1; }
  command -v ffmpeg >/dev/null || brew install ffmpeg
  command -v node   >/dev/null || brew install node
  command -v python3.12 >/dev/null || brew install python@3.12
fi
for t in ffmpeg ffprobe node npx; do command -v "$t" >/dev/null || { echo "missing: $t"; exit 1; }; done
PY="$(command -v python3.12 || command -v python3)"
echo "python: $PY ($("$PY" --version))"

say "2/6 Python venv + packages ($HOME_DIR/venv)"
mkdir -p "$HOME_DIR/tools" "$HOME_DIR/assets"
[ -x "$HOME_DIR/venv/bin/python" ] || "$PY" -m venv "$HOME_DIR/venv"
VPY="$HOME_DIR/venv/bin/python"
"$VPY" -m pip install --upgrade pip >/dev/null
"$VPY" -m pip install -r "$HERE/requirements.txt"

say "3/6 Rhubarb Lip Sync + MediaPipe models"
RB="$HOME_DIR/tools/rhubarb"
if ! ls "$RB"/*/rhubarb >/dev/null 2>&1; then
  mkdir -p "$RB"
  case "$OS" in Darwin) Z=macOS ;; *) Z=Linux ;; esac
  curl -fL -o "$RB/rhubarb.zip" "https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.14.0/Rhubarb-Lip-Sync-1.14.0-$Z.zip"
  (cd "$RB" && unzip -q rhubarb.zip && rm rhubarb.zip)
  [ "$OS" = "Darwin" ] && xattr -dr com.apple.quarantine "$RB" 2>/dev/null || true
fi
RHUBARB="$(ls "$RB"/*/rhubarb | head -1)"; chmod +x "$RHUBARB"
MP="$HOME_DIR/tools/mediapipe"; mkdir -p "$MP"
base=https://storage.googleapis.com/mediapipe-models
[ -s "$MP/face_landmarker.task" ]       || curl -fL -o "$MP/face_landmarker.task"       "$base/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
[ -s "$MP/pose_landmarker_heavy.task" ] || curl -fL -o "$MP/pose_landmarker_heavy.task" "$base/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
[ -s "$MP/hand_landmarker.task" ]       || curl -fL -o "$MP/hand_landmarker.task"       "$base/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"

say "4/6 Skill -> $SKILLS/video-studio"
mkdir -p "$SKILLS"
if [ -d "$SKILLS/video-studio" ]; then
  BK="$HOME/.claude/skills-archive/$(date +%Y-%m-%d-%H%M%S)-video-studio"
  mkdir -p "$(dirname "$BK")"; mv "$SKILLS/video-studio" "$BK"; echo "existing copy moved to $BK"
fi
cp -R "$ROOT/video-studio" "$SKILLS/video-studio"

if [ "${1:-}" != "--no-skills" ]; then
  say "5/6 Third-party skills (setup/skills.txt)"
  grep -v '^#' "$HERE/skills.txt" | grep '|' | while IFS='|' read -r repo skill; do
    repo="$(echo "$repo" | xargs)"; skill="$(echo "$skill" | xargs)"
    echo "  $repo -> $skill"
    npx --yes skills add "$repo" --skill "$skill" -g -y -a claude-code >/dev/null || echo "  (failed: install it later by hand)"
  done
fi

say "6/6 Config + smoke test"
mkdir -p "$HOME/.video-studio"
cat > "$HOME/.video-studio/config.json" <<EOF
{
  "home": "$HOME_DIR",
  "rhubarb": "$RHUBARB",
  "mediapipe_models": "$MP",
  "sound_python": "$VPY"
}
EOF
export HYPERFRAMES_PYTHON="$VPY"
"$VPY" -I "$SKILLS/video-studio/scripts/smoke_test.py" || { echo "Smoke test failed: read the output above."; exit 1; }

cat <<EOF

Done. Two things to remember:
  - Run the skill's Python scripts with:  $VPY -I <script>
  - Kokoro TTS needs:  export HYPERFRAMES_PYTHON="$VPY"   (add it to ~/.zshrc to make it permanent)
Optional: add the Playwright MCP, video-analyzer and mcp-video servers in Claude Code (see references/toolchain.md).
EOF
