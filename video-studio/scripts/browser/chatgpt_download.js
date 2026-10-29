async (page) => {
  // Download finished ChatGPT renders, ONE tab, chat after chat.
  // CHATS: real chat ids (read them from the sidebar: nav a[href*="/c/"], newest first).
  // KEYS: a phrase unique to each plate's scene -> plate name, so the file is named from the
  // prompt itself (ids get mixed up; duplicates happen when a batch is retried).
  // Poll up to 30 s per chat: the image loads long after domcontentloaded, and a fixed 6 s wait
  // reported 11 of 17 finished renders as "pending".
  const CHATS = [/* '6ab9...-....' */];
  const KEYS = [/* ['endless dark field', 'title'], ['chrome stopwatch', 'skim'] */];
  const DIR = '/ABSOLUTE/path/to/project/assets/chatgpt/';
  const out = [];
  for (const id of CHATS) {
    try { await page.goto('https://chatgpt.com/c/' + id, {waitUntil: 'domcontentloaded', timeout: 60000}); } catch (e) {}
    let info;
    for (let k = 0; k < 12; k++) {
      await page.waitForTimeout(2500);
      info = await page.evaluate(() => {
        const u = document.querySelector('[data-message-author-role="user"]');
        const imgs = [...document.querySelectorAll('img')].filter(i => (i.alt || '').startsWith('Generated image') && i.naturalWidth > 500);
        return { prompt: u ? u.innerText : '', srcs: [...new Set(imgs.map(i => i.src))],
                 busy: !!document.querySelector('[data-testid="stop-button"]') };
      });
      if (info.srcs.length && info.prompt) break;
    }
    const k = KEYS.find(([s]) => info.prompt.includes(s));
    const name = k ? k[1] : 'unknown';
    if (!info.srcs.length) { out.push(`${id} ${name} PENDING busy=${info.busy}`); continue; }
    let n = 0;
    for (const src of info.srcs) {
      await page.evaluate(async (src) => {
        const r = await fetch(src, {credentials: 'include'});
        window.__img = URL.createObjectURL(await r.blob());
      }, src);
      const dl = page.waitForEvent('download', {timeout: 30000});
      await page.evaluate(() => { const a = document.createElement('a'); a.href = window.__img; a.download = 'x.png'; document.body.appendChild(a); a.click(); a.remove(); });
      await (await dl).saveAs(`${DIR}${name}__${id.slice(0, 8)}_${n}.png`); n++;
    }
    out.push(`${id} ${name} saved ${n}`);
  }
  return out;
}
