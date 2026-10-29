async (page) => {
  // Queue a set of ChatGPT still plates from ONE browser tab (Playwright MCP, browser_run_code_unsafe).
  // New chat per plate: type, Enter, wait for the /c/<id> URL, record it, move on. Renders keep
  // running server-side; come back later with chatgpt_download.js. NEVER open one tab per image:
  // 13 parallel tabs froze a 6 GB machine for 20 minutes.
  //
  // 2026-10-08: the box lost its #prompt-textarea id; the ProseMirror div is the fallback.
  // Expect page.url() to return the same temporary local-chatgpt:<uuid> for every plate: the
  // chats still exist, read real ids from the sidebar (newest first) a minute later.
  // Edit ART (the locked art-direction block, shared by every plate) and PLATES (name -> scene).
  const ART = `Generate an image. Wide 16:9 landscape, cinematic photoreal 3D render.
LOCKED ART DIRECTION (identical for the whole series): <ground colour hex>, <key light hex>, <rim light hex>,
ONE small <accent hex> glow only where named; soft haze, shallow depth of field, fine grain.
FORBIDDEN: no text, no letters, no numbers, no logos, no UI with readable content, no watermarks,
no borders, no people, no faces, no hands, no silhouettes of people.`;
  const PLATES = {
    // title: `SCENE: ... COMPOSITION: subject on the RIGHT 45%; the LEFT 55% dark and empty.`,
  };
  const out = {};
  for (const [name, scene] of Object.entries(PLATES)) {
    try { await page.goto('https://chatgpt.com/', {waitUntil: 'domcontentloaded', timeout: 60000}); } catch (e) {}
    const box = page.locator('#prompt-textarea, div.ProseMirror[contenteditable="true"]').first(); await box.waitFor({timeout: 60000});
    await box.click();
    await page.keyboard.insertText(`${ART}\n\n${scene}`);
    await page.keyboard.press('Enter');
    // the first URL is often a temporary /c/WEB:<uuid>; the real id shows in the sidebar later
    try { await page.waitForURL(/\/c\//, {timeout: 60000}); out[name] = page.url(); } catch (e) { out[name] = 'NOURL ' + page.url(); }
    await page.waitForTimeout(1500);
  }
  return out;
}
