"""wrap.py STEP [--base http://127.0.0.1:3000] : writes capture/run/STEP.js = async (page) => { lib.js + steps/STEP.js }
for the Playwright MCP's run-code tool. Screenshots land in assets/shots/ (absolute path filled in here)."""
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("step"); ap.add_argument("--base", default="http://127.0.0.1:3000")
a = ap.parse_args()
shots = (HERE.parent / "assets" / "shots").resolve(); shots.mkdir(parents=True, exist_ok=True)
lib = (HERE / "lib.js").read_text(encoding="utf-8").replace("__SHOTS_DIR__", shots.as_posix() + "/").replace("__BASE_URL__", a.base)
body = (HERE / "steps" / f"{a.step}.js").read_text(encoding="utf-8")
out = HERE / "run" / f"{a.step}.js"
out.parent.mkdir(exist_ok=True)
out.write_text("async (page) => {\n" + lib + "\n" + body + "\n}\n", encoding="utf-8")
print(out)
