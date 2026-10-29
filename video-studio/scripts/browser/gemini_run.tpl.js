async (page) => {
  // Gemini Omni, ONE call per clip, run AFTER browser_click("File upload") + browser_file_upload(plate).
  // Types the prompt, submits, then STAYS on this page until "Your video is ready!" and saves the mp4.
  // Never navigate away while it renders: a clip whose tab was left mid-render vanished
  // (chat absent from Recents, URL bounced to /app). Generate this file with gemini_make.py.
  const KEY = '__KEY__';
  const PROMPT = __PROMPT__;
  await page.waitForFunction(() => !!document.querySelector('img[src^="blob:"]'), null, {timeout: 30000});
  await page.getByRole('textbox').first().click();
  await page.keyboard.insertText(PROMPT);
  await page.waitForTimeout(800); await page.keyboard.press('Enter');
  let state = 'timeout';
  for (let i = 0; i < 90; i++) {
    await page.waitForTimeout(5000);
    const r = await page.evaluate(() => ({ ready: /Your video is ready/.test(document.body.innerText) && !!document.querySelector('video'),
      tail: document.body.innerText.slice(-400) }));
    if (r.ready) { state = 'ready'; break; }
    if (/out of videos|hard time fulfilling|encountered an error|at full capacity/i.test(r.tail)) { state = 'error: ' + r.tail.slice(-250); break; }
  }
  if (state !== 'ready') return KEY + ' ' + state + ' ' + page.url();
  const src = await page.evaluate(() => { const v = document.querySelector('video'); return v.currentSrc || v.src; });
  const body = await (await page.context().request.get(src)).body();
  const b64 = body.toString('base64');
  await page.evaluate((b64) => { const bin = atob(b64); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); window.__vid = URL.createObjectURL(new Blob([u], {type: 'video/mp4'})); }, b64);
  const dl = page.waitForEvent('download', {timeout: 60000});
  await page.evaluate(() => { const a = document.createElement('a'); a.href = window.__vid; a.download = 'v.mp4'; document.body.appendChild(a); a.click(); a.remove(); });
  await (await dl).saveAs(`__OUTDIR__/${KEY}.mp4`);
  return KEY + ' saved ' + body.length + ' ' + page.url();
}
