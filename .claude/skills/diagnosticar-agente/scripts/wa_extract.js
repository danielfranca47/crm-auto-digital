async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 40 && !document.querySelector('#main [data-id]'); i++) await sleep(500);
  const main = document.querySelector('#main');
  if (!main) return 'NO_MAIN';
  const pane = [...main.querySelectorAll('div')].filter(d => d.scrollHeight > d.clientHeight + 50 && /auto|scroll/.test(getComputedStyle(d).overflowY)).sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
  if (!pane) return 'NO_PANE';
  let h = -1;
  for (let i = 0; i < 30 && pane.scrollHeight !== h; i++) { h = pane.scrollHeight; pane.scrollTop = 0; await sleep(1500); }
  const order = [];
  const seen = new Map();
  const grab = () => {
    for (const m of main.querySelectorAll('[data-id]')) {
      const id = m.getAttribute('data-id');
      if (!order.includes(id)) order.push(id);
      if (seen.has(id)) continue;
      const v = m.querySelector('[data-virtualized]');
      if (v && v.getAttribute('data-virtualized') !== 'false') continue;
      const item = m.querySelector('.focusable-list-item');
      if (!item) continue;
      const who = getComputedStyle(item).alignItems === 'flex-end' ? 'EMPRESA' : 'CLIENTE';
      const pre = m.querySelector('[data-pre-plain-text]');
      let txt;
      if (pre) {
        const t = pre.querySelector('.selectable-text');
        txt = `${pre.getAttribute('data-pre-plain-text').replace(/\].*$/, ']')} ${(t ? t.innerText : pre.innerText).trim()}`;
      } else {
        const img = m.querySelector('img[src^="blob:"], img[src^="data:image/jpeg"]');
        const aud = m.querySelector('[data-icon*="audio"], [data-icon*="ptt"], button[aria-label*="Reproduzir"], [aria-label*="voz"]');
        const raw = m.innerText.replace(/\s+/g, ' ').trim();
        if (!raw && !img && !aud) continue;
        txt = `${img ? '<IMAGEM> ' : ''}${aud ? '<AUDIO> ' : ''}${raw.slice(0, 250)}`;
      }
      seen.set(id, `${who}: ${txt}`);
    }
  };
  pane.scrollTop = 0; await sleep(1000); grab();
  for (let i = 0; i < 600; i++) {
    const before = pane.scrollTop;
    pane.scrollTop = before + pane.clientHeight * 0.4;
    await sleep(600);
    grab();
    if (pane.scrollTop === before) { await sleep(800); grab(); break; }
  }
  return order.filter(id => seen.has(id)).map(id => seen.get(id)).join('\n') + `\n--- ${seen.size}/${order.length} mensagens lidas`;
}
