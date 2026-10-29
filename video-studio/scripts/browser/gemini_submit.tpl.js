async (page) => {
  // Gemini Omni, ONE call per clip, run AFTER browser_click("File upload") + browser_file_upload(plate).
  // Types the prompt, submits, then STAYS on this page until "Your video is ready!" and saves the mp4.
  // Never navigate away while it renders: a clip whose tab was left mid-render vanished
  // (chat absent from Recents, URL bounced to /app). Generate this file with gemini_make.py.
  const KEY = '__KEY__';
  const PROMPT = __PROMPT__;
  await page.waitForFunction(() => !!document.querySelector('img[src^="blob:"]'), null, {timeout: 30000});
  // The Videos tool chip must be on, or the prompt goes to a plain chat (it happened on /u/4).
  const chip = await page.evaluate(() => [...document.querySelectorAll('button, div[role="button"]')].some(b => (b.innerText || '').trim() === 'Videos'));
  if (!chip) return KEY + ' NO VIDEOS CHIP: wait for the page, do not submit';
  await page.getByRole('textbox').first().click();
  await page.keyboard.insertText(PROMPT);
  await page.waitForTimeout(800); await page.keyboard.press('Enter');
  // Enter sometimes clears nothing and sends nothing: confirm the chat exists, else click Send.
  let started = false;
  for (let k = 0; k < 12 && !started; k++) {
    await page.waitForTimeout(2500);
    started = /\/app\/[0-9a-f]{8,}/.test(page.url()) || !!(await page.$('button[aria-label="Stop response"]'));
    if (!started && k === 2) {
      const send = page.locator('button[aria-label*="Send"]').first();
      if (await send.count()) await send.click().catch(() => {});
    }
  }
  if (!started) return KEY + ' NOT STARTED ' + page.url() + ' ' + (await page.evaluate(() => document.body.innerText.slice(-300)));
  let state = 'timeout';
  for (let i = 0; i < 90; i++) {
    await page.waitForTimeout(5000);
    const r = await page.evaluate(() => ({ ready: /Your video is ready/.test(document.body.innerText) && !!document.querySelector('video'),
      tail: document.body.innerText.slice(-400) }));
    if (r.ready) { state = 'ready'; break; }
    if (/out of videos|hard time fulfilling|encountered an error|at full capacity/i.test(r.tail)) { state = 'error: ' + r.tail.slice(-250); break; }
  }
  if (state !== 'ready') return KEY + ' ' + state + ' ' + page.url();
  return KEY + ' READY ' + page.url();
}
