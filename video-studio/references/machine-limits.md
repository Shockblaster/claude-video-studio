# Machine limits: heavy video work on a small laptop

This skill was built on a 6 GB RAM laptop with an integrated GPU, and everything here was learned the hard way.
On a bigger machine the rules still prevent lost renders. Measure your own machine once and write the numbers into
`references/toolchain.md`.

## Before a heavy job
- Check free memory, and on Windows the commit charge too: numpy failed to allocate with 500 MB free and the commit
  limit ~95% full.
  - macOS: `memory_pressure` or Activity Monitor.
  - Windows (PowerShell): `Get-CimInstance Win32_OperatingSystem | select FreePhysicalMemory,FreeVirtualMemory`.
- Close the Playwright MCP browser when you are done with it.
- One heavy job at a time: a render, an avatar track or a browser session, never two.
- Never kill a process you did not start. If memory is short, list the big users and ask the user what to close.
  Restart anything you stopped with their OK when you are done.

## Rendering
- HyperFrames: `--workers 2` (each worker is a headless Chrome, ~256 MB). `--workers 1` for very long 1080p
  walkthroughs.
- Long renders run in the FOREGROUND, chunked:
  - HyperFrames: `HF_SEGMENTED_CAPTURE=true npx hyperframes render ... --resume --keep-segments`. Segments survive
    a crash and are reused.
  - Avatar track: `scripts/pipeline/render_chunks.py --chunk N` (~12 s per chunk), then `--join`.
  - A background job was killed when memory ran low and an idle session's shells were reaped: a 45-min render was
    lost.
- If a tool call times out and moves a render to the background, do not start a second copy. Wait for it to
  finish.
- Draft first (`--quality draft`), QC every frame, then `--quality delivery` once. Compare the delivery render with
  the approved draft by PSNR: every frame should match apart from compression (e.g. >= 35 dB).

## Python
- `export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` (PowerShell: `$env:OPENBLAS_NUM_THREADS=1`) before
  numpy-heavy scripts when memory is tight.
- avatar_track.py loads every pose in its plan up front: give it a plan holding only the poses in its range.
- Keep decoded video frames JPEG-compressed in RAM. Six raw 10 s clips ran a 6 GB machine out of memory.
- Cache expensive per-clip analysis (eye tracking, transcripts) next to the clip.
- Build composites from CROPS, in float32, not full-canvas float64 images.

## What not to run locally on a small laptop
- Blender renders, local music models, voice cloning or lip-sync diffusion models. Use a free cloud GPU notebook
  in the user's own account if needed. Some home routers refuse the notebook's runtime domain; switching the
  machine's DNS to a public resolver fixed it.
- More than one browser tab per AI image: 13 tabs froze the machine for 20 minutes.

## Timings measured on the 6 GB laptop (for planning)
| Job | Time |
|---|---|
| 15 s kinetic-type clip with footage, `--quality looks` | ~2 min 45 s |
| 80 s one-take reel with a placed avatar, draft / delivery | ~10-11 min / ~23 min |
| Avatar track, 12 s chunk (26-pose plan) | ~4 min |
| 4.5 min 1080p30 screen walkthrough, `--workers 1` | ~23 min |
| Rhubarb lip-sync, per line | ~10 s |
| Pace check, 80 s reel | ~1 min |
