"""Write gemini_run.js for one clip:
    python gemini_make.py <key> "<motion sentence>" <outdir> [template]
The prompt wraps the motion sentence in the wording that kept the camera still and the
text area empty on every accepted clip."""
import json, os, sys
key, motion = sys.argv[1], sys.argv[2]
outdir = sys.argv[3].replace("\\", "/") if len(sys.argv) > 3 else "assets/video_raw"
here = os.path.dirname(os.path.abspath(__file__))
tpl = sys.argv[4] if len(sys.argv) > 4 else os.path.join(here, "gemini_run.tpl.js")
prompt = ("Animate this exact image as a slow, cinematic, seamless background loop. Keep the camera "
          "completely locked off, with framing, lighting and colours identical to the image. Motion: "
          + motion + " The dark left side must stay dark. No text, no letters, no numbers, no logos, "
          "no people, no camera movement, no cuts.")
t = open(tpl, encoding="utf-8").read().replace("__KEY__", key).replace("__PROMPT__", json.dumps(prompt)).replace("__OUTDIR__", outdir)
open(os.path.join(os.getcwd(), "gemini_run.js"), "w", encoding="utf-8").write(t)
print("wrote gemini_run.js for", key)
