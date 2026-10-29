# Image and video generation in the user's own browser (Playwright MCP)

Still art (character sheets, pose libraries, backdrop plates) comes from ChatGPT image gen; optional cinematic clips
come from Gemini Omni (Veo underneath). Both run in the user's OWN logged-in accounts through the Playwright MCP.
No image or video API is used.

"Playwright" means the Playwright MCP tools (`browser_navigate`, `browser_click`, `browser_evaluate`,
`browser_file_upload`, `browser_run_code_unsafe`), never a local `playwright-core` script. A script does not count as
having checked something "on Playwright". Click the real controls and LOOK at the result. The user handles logins
and account choice; never type credentials. If tabs appear, close or change under you, the user may be using the
same window: say so and ask them to leave it alone for a few minutes.

## Stills through ChatGPT
- **ONE tab, a new chat per image**: open a new chat, type, Enter, wait for the `/c/<id>` URL, record it, move on.
  Renders keep running server-side in parallel. Never one browser tab per image: 13 parallel tabs froze a 6 GB
  machine for 20 minutes and disconnected the MCP. Never stack every image in one chat either.
  - Queue: `scripts/browser/chatgpt_queue.js`, via `browser_run_code_unsafe` with `filename`. It reads its prompt
    list from a JSON file through a hidden file input (`setInputFiles`), so the Playwright code stays small.
  - Keep chat ids in the page's localStorage for later pulls.
- **Rate limit**: sending a prompt every ~12 s triggered "too many requests" after ~55 sends, and the last 5 came
  back "image generation is temporarily unavailable". Space sends at least **60 s** apart, and check every chat's
  status (IMG / still working / text-only error reply) before pulling.
- **Composer**: `div[contenteditable="true"]` (the old `#prompt-textarea` id is gone). Type with
  `page.keyboard.insertText`. Temporary chats refuse image generation. A long thread degrades, so start fresh
  per series.
- **Chat ids**: the URL right after sending can be a temporary `local-chatgpt:` / `WEB:` id. Read the real ids
  from the sidebar a minute later (`nav a[href*="/c/"]`, newest first, at desktop width) and match by prompt text.
- **Reference photo** (likeness): `browser_evaluate` `document.querySelector('#upload-photos').click()`. The MCP then
  reports a file chooser; answer it with `browser_file_upload` and the absolute path.
- **Prompting a series**: one LOCKED treatment up front (style, lens, light, set, grade, wardrobe, frame ratio,
  "no text, no letters, no numbers, no logos, no watermarks"), then vary only the named element. Leave the caption
  area empty and put text on in code: the generator cannot spell or respect a safe area. For logos and marks,
  generic "app icon" prompts give glossy AI-looking art; name a real craft tradition and ban gradients, gloss, 3D,
  shadows, glow and swooshes.
- **Saving without a download event** (download events closed the whole MCP browser): fetch IN the page and return
  base64 from `browser_evaluate` with its `filename` parameter. Then decode with `python -I scripts/broll/b64save.py
  file.b64`, which detects mp4 vs image and reports size.
  ```js
  async () => { for (let k = 0; k < 20; k++) {
    const im = [...document.querySelectorAll('img')].filter(i => i.naturalWidth > 500);
    if (im.length) { const b = new Uint8Array(await (await fetch(im[im.length - 1].src)).arrayBuffer()); let s = '';
      for (let i = 0; i < b.length; i += 32768) s += String.fromCharCode.apply(null, b.subarray(i, i + 32768)); return btoa(s); }
    await new Promise(r => setTimeout(r, 1500)); } return 'NOIMG'; }
  ```
  Images can be `blob:` URLs; the same fetch works. The image loads long after `domcontentloaded`: poll, never wait a
  fixed 6 s. Budget 3-5 min per render.
- **QA every image of a real person**: reference face crop beside the generated face at the same size, plus a
  full-body band so the hands are in frame. Look hardest where hands hold or touch something. When an image is
  rejected, regenerate rather than patch it.

## Video with Gemini Omni (optional garnish; see `references/ai-broll.md` for when)
- **Image-to-video on the SAME still plate**: the clip then matches the plate's layout, and a failed clip degrades
  to the identical still. Every prompt: "Animate this exact image as a slow, cinematic, seamless loop", "camera
  completely locked off, framing, lighting and colours identical to the image", one sentence of motion inside the
  subject, "No text, no letters, no numbers, no logos, no people, no cuts."
- **Subjects that animate**: liquid, smoke, fire, water, lights, slow vehicles, a glow travelling along a path.
  Chained rigid-body physics (dominoes) failed twice. Some subjects get refused; swap the subject rather than burn
  attempts. Failed and refused attempts still use up quota (~4 usable clips a day per account).
- **The user presses Send** (default once quota is tight):
  - navigate to `gemini.google.com/u/N/videos` (the user says which N);
  - wait until the Videos chip is loaded and the "File upload" button is ENABLED (a disabled button right after
    navigation is usually still loading; poll 10-15 s);
  - `browser_click` File upload, then `browser_file_upload` the plate IN ITS OWN CALL;
  - type the prompt in a SEPARATE call with `keyboard.insertText`;
  - screenshot and STOP. Chaining upload + fill in one script once sent the prompt on its own.
  - The user says "done" / "next"; save the clip from that chat, then set up the next.
- **Signals**: "I'm generating your video" stays on the page even after a failure. The real signals are the stop
  (square) button (`aria-label^="Stop"`, anchored, since a chat titled "Stopwatch" matched `*=`) or a finished
  `<video>`. Enter may no longer submit; the button is "Send message".
- **Retry a failed clip IN PLACE**: the refresh icon under that answer opens a menu, then click "Try again"
  (`getByText('Try again', {exact: true})`). Never open a new chat and re-upload. After a failed send the page can
  bounce to `/app` and drop the plate while the prompt survives: re-attach the plate only.
- **Stay on the tab until the clip is saved**: navigating away while it rendered lost it.
- **Save**: scope to the LAST answer, `[...document.querySelectorAll('model-response')].pop().querySelector('video')`.
  A bare `querySelector('video')` once grabbed an unrelated clip. Fetch `currentSrc` in-page, return base64 as above,
  then `b64save.py`. Extract a frame and look before processing.
- **Clean the clip**: `python -I scripts/broll/process_video.py raw.mp4 out.mp4 --crop`, which does the watermark,
  a seamless loop, silence and a poster.
  - The sparkle mark is a static semi-transparent white overlay at about x 1135-1193, y 575-625 of a 1280x720 frame.
  - `--crop` (cut the left 1120 px, rescale) removed it on 8 of 8 clips. The per-clip scrub (alpha estimated
    from the clip's own frames, negative alpha allowed, exact luma un-blend, chroma from an inpaint) is for when
    the subject sits near the right edge.
  - Check with `python -I scripts/broll/check_watermark.py RAW CLEAN --sheet crops.png` and READ the sheet. The
    texture ratio catches smudges (< 0.40); after `--crop` its GHOST verdict is a false alarm, so judge by the sheet.
  - Positions move after `--crop` (x_clip = x_plate / 0.875): measure overlay anchors on the processed poster.
- Generated footage that looks real gets the platform's AI label.
