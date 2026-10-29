  // EXAMPLE capture step (rename to s02.js). `p` is the logged-in app tab; `shot()` saves a PNG + the boxes
  // of the elements you will ring / click / zoom to in the video. Keep one step per scene.
  await p.goto(BASE + '/notes', { waitUntil: 'networkidle' });
  await shot('02-notes', {
    list: () => p.locator('[data-test="note-list"]'),
    newBtn: () => p.getByRole('button', { name: 'New note' }),
  });
  await p.getByRole('button', { name: 'New note' }).click();
  await shot('03-editor', { title: () => p.getByPlaceholder('Title'), save: () => p.getByRole('button', { name: 'Save' }) });
