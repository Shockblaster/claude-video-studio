  // Shared helpers, prepended to every capture step by wrap.py (each Playwright MCP call runs in a fresh sandbox).
  // __SHOTS_DIR__ and __BASE_URL__ are filled in by wrap.py.
  const DIR = '__SHOTS_DIR__';
  const BASE = '__BASE_URL__';
  // The logged-in tab lives in the MCP browser's other context; the tab can close on its own when memory is low,
  // the context keeps the login.
  const ctx = page.context().browser().contexts().find((c) => c !== page.context()) || page.context();
  const p = ctx.pages()[0] || (await ctx.newPage());
  const prev = await page.evaluate(() => window.__boxes || {});
  const boxes = { ...prev };
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  async function rect(loc, docCoords) {
    const b = await loc.first().boundingBox();
    if (!b) return null;
    const [sx, sy] = docCoords ? await p.evaluate(() => [window.scrollX, window.scrollY]) : [0, 0];
    return [Math.round(b.x + sx), Math.round(b.y + sy), Math.round(b.width), Math.round(b.height)];
  }
  // A viewport shot (scrolled to `scrollY`) or a full-page shot; marks are boxes in the image's CSS pixels.
  // A full-page shot taller than 16,384 device px repeats the top of the page: capture tall pages in slices.
  async function shot(name, marks = {}, opts = {}) {
    const full = !!opts.full;
    if (!full && opts.scrollY !== undefined) await p.evaluate((y) => window.scrollTo(0, y), opts.scrollY);
    if (!full) await wait(250);
    const m = {};
    for (const [k, fn] of Object.entries(marks)) {
      try { m[k] = await rect(fn(), full); } catch (e) { m[k] = null; }
    }
    await p.screenshot({ path: DIR + name + '.png', fullPage: full });
    const height = full ? await p.evaluate(() => document.documentElement.scrollHeight) : 900;
    boxes[name] = { full, height, marks: m };
    await page.evaluate((d) => { window.__boxes = d; }, boxes);
    return boxes[name];
  }
