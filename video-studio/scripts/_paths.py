"""One place that finds every external tool and data folder, on macOS, Linux and Windows.

Lookup order for each item:
  1. an environment variable (e.g. RHUBARB_PATH)
  2. ~/.video-studio/config.json (written by setup/setup-mac.sh or setup/setup-windows.ps1)
  3. the PATH (for executables)
  4. a default under VIDEO_STUDIO_HOME (default: ~/video-studio)

Use from any script in this folder:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import _paths
    exe = _paths.rhubarb()
"""
import json
import os
import pathlib
import shutil
import sys

IS_WIN = sys.platform == "win32"
CONFIG_FILE = pathlib.Path.home() / ".video-studio" / "config.json"


def _config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def home():
    """VIDEO_STUDIO_HOME: tools, models, fonts and scratch work live here (default ~/video-studio)."""
    p = os.environ.get("VIDEO_STUDIO_HOME") or _config().get("home") or str(pathlib.Path.home() / "video-studio")
    return pathlib.Path(p).expanduser()


def _lookup(env, key, default):
    v = os.environ.get(env) or _config().get(key)
    return pathlib.Path(v).expanduser() if v else default


def npx():
    """`npx` (macOS/Linux) or `npx.cmd` (Windows), as a command list element."""
    return "npx.cmd" if IS_WIN else "npx"


def python():
    """The interpreter running this script: same venv, same packages."""
    return sys.executable


def rhubarb():
    """Rhubarb Lip Sync executable (https://github.com/DanielSWolf/rhubarb-lip-sync, MIT)."""
    p = _lookup("RHUBARB_PATH", "rhubarb", None)
    if p and p.exists():
        return p
    found = shutil.which("rhubarb")
    if found:
        return pathlib.Path(found)
    # setup scripts unpack the release zip under <home>/tools/rhubarb/<release folder>/
    for c in sorted((home() / "tools" / "rhubarb").glob("**/rhubarb" + (".exe" if IS_WIN else ""))):
        return c
    return home() / "tools" / "rhubarb" / ("rhubarb.exe" if IS_WIN else "rhubarb")


def mediapipe_models():
    """Folder holding the MediaPipe .task models (face_landmarker, pose_landmarker, hand_landmarker)."""
    return _lookup("MEDIAPIPE_MODELS", "mediapipe_models", home() / "tools" / "mediapipe")


def fonts_dir():
    """Fonts copied into projects. Default: the OFL fonts bundled with this skill (Inter, Mukta, Noto Sans
    Devanagari). Point VIDEO_STUDIO_FONTS at a brand's own fonts folder to use those instead."""
    return _lookup("VIDEO_STUDIO_FONTS", "fonts", pathlib.Path(__file__).resolve().parent.parent / "assets" / "fonts")


def work_dir(name="scratch"):
    """Scratch folders (smoke test, temp renders)."""
    p = home() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def sound_python():
    """Python with librosa/soundfile/scipy (the sound pass). Defaults to this interpreter."""
    return os.environ.get("VIDEO_STUDIO_SOUND_PY") or _config().get("sound_python") or sys.executable


def audio_python():
    """Python of the AUDIO venv (earshot + soxr + torch-cpu) for score.py / beatmix.py: VIDEO_STUDIO_AUDIO_PY, config
    'audio_python', or <home>/tools/earshot/.venv. Falls back to this interpreter."""
    v = os.environ.get("VIDEO_STUDIO_AUDIO_PY") or _config().get("audio_python")
    if v:
        return v
    d = home() / "tools" / "earshot" / ".venv"
    exe = d / ("Scripts/python.exe" if IS_WIN else "bin/python")
    return str(exe) if exe.exists() else sys.executable


def opuscar_dir():
    """lemo-opuscar reference clone (sampler + sample libraries): LEMO_OPUSCAR_DIR, config 'opuscar', or <home>/tools/lemo-opuscar."""
    return _lookup("LEMO_OPUSCAR_DIR", "opuscar", home() / "tools" / "lemo-opuscar")


if __name__ == "__main__":
    print(json.dumps({"home": str(home()), "rhubarb": str(rhubarb()), "rhubarb_exists": rhubarb().exists(),
                      "mediapipe_models": str(mediapipe_models()), "fonts": str(fonts_dir()), "npx": npx(),
                      "config_file": str(CONFIG_FILE)}, indent=1))
