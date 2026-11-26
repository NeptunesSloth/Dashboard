// Sect Academy — picture lessons: a painting with numbered pins.
// Three exercises: put the word chips on the pins (drag on a desktop; on a phone tap a
// pin then a word; by keyboard focus a pin, press Enter, then choose a word), tap the
// pin a word names, and type the word for a lit pin (the ordinary typed exercise, with
// the picture above it). Grading and scheduling happen on the server, pin by pin.
// Every string goes through esc() or textContent; numbers through num(); the image
// path must be one of the server's /art/pic_<id>.webp names.

const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
const num = (v) => { const n = Number(v); return Number.isFinite(n) ? n : 0; };
const pct = (v) => Math.min(100, Math.max(0, num(v)));
const SRC = /^\/art\/pic_[a-z][a-z0-9_]{1,31}\.webp$/;

/** The painting with its pins. pins: [{n, x, y, lit?}]; `tag` makes pins buttons (default) or plain marks. */
export function figure(picture, pins, { buttons = true, cls = '' } = {}) {
  const pic = picture || {};
  const src = SRC.test(String(pic.src || '')) ? pic.src : '';
  const pin = (p) => {
    const style = `left:${pct(p.x)}%;top:${pct(p.y)}%`;
    const inner = `<b>${num(p.n)}</b>`;
    return buttons
      ? `<button type="button" class="pin ${p.lit ? 'lit' : ''}" data-pin="${num(p.n)}" style="${style}" aria-label="Place ${num(p.n)}">${inner}</button>`
      : `<span class="pin ${p.lit ? 'lit' : ''}" data-pin="${num(p.n)}" style="${style}">${inner}</span>`;
  };
  // labels are siblings of the pins, drawn above all of them, so a label is never hidden under a neighbouring pin
  const lab = (p) => `<span class="lab" data-lab="${num(p.n)}" style="left:${pct(p.x)}%;top:${pct(p.y)}%" hidden></span>`;
  return `<figure class="pic ${esc(cls)}">${src ? `<img src="${esc(src)}" alt="${esc(pic.title || 'Picture')}" draggable="false">` : '<div class="pic-blank"></div>'}
    ${(pins || []).map(pin).join('')}${(pins || []).map(lab).join('')}</figure>`;
}

/** Write a label under pin n (textContent: never markup). state: '', 'ok' or 'no'. */
export function label(root, n, text, state = '') {
  const el = root.querySelector(`.pic [data-pin="${num(n)}"]`);
  const lab = root.querySelector(`.pic [data-lab="${num(n)}"]`);
  if (!el || !lab) return;
  lab.textContent = text || ''; lab.hidden = !text;
  for (const x of [el, lab]) { x.classList.toggle('ok', state === 'ok'); x.classList.toggle('no', state === 'no'); }
}

/** The introduction: the painting with every new word on it, and the list to read aloud. */
export function introHtml(card, lang, sayBtn) {
  const pins = card.pins || [];
  return `<span class="newtag">New picture</span><h2 style="margin:2px 0 10px">${esc(card.title || '')}</h2>
    ${figure(card.picture, pins, { buttons: false, cls: 'labelled' })}
    <ol class="piclist">${pins.map((p) => `<li value="${num(p.n)}"><span lang="${esc(lang)}"><b>${esc(p.l2)}</b></span> ${sayBtn(p.l2, lang)}
      ${p.rom ? `<span class="rom">${esc(p.rom)}</span>` : ''} <span class="dim">${esc(p.l1)}</span></li>`).join('')}</ol>`;
}

export function labelAll(root, pins) { (pins || []).forEach((p) => label(root, p.n, p.l2)); }

/**
 * Put the words on the picture. ctx: {view, shell, guide, retry, submit(placements) -> Promise<res>, done(res, placements)}.
 * placements: [{item, answer}] (one per pin of the exercise).
 */
export function dragExercise(ex, ctx) {
  const { view } = ctx;
  const chips = (ex.chips || []).map((c, i) => ({ ...c, i }));
  const targets = ex.pins || [];
  const placed = new Map();           // pin n -> chip index
  let selPin = null; let selChip = null; let locked = false;
  ctx.shell(`<div class="guide">${ctx.guide(ex.retry ? 'think' : 'calm')}<div class="speech">${esc(ex.ask || '')}${ex.retry ? ' <span class="tag gold">once more</span>' : ''}</div></div>
    ${figure(ex.picture, targets)}
    <p class="dim small pic-help">Drag each word onto its number, or tap a number and then a word. Tap a placed word to take it back.</p>
    <div class="bank chips" id="p-chips" aria-label="Words">${chips.map((c) => `<button type="button" class="tile chip" draggable="true" data-chip="${c.i}" lang="${esc(ex.lang)}">${esc(c.l2)}</button>`).join('')}</div>
    <div class="foot" id="s-foot"><button class="btn primary big" id="s-check" disabled>Check</button></div>`);
  const pinEl = (n) => view.querySelector(`.pic [data-pin="${num(n)}"]`);
  const chipEl = (i) => view.querySelector(`[data-chip="${num(i)}"]`);
  const paint = () => {
    targets.forEach((p) => {
      const c = placed.get(p.n);
      label(view, p.n, c == null ? '' : chips[c].l2);
      const el = pinEl(p.n);
      el.classList.toggle('sel', selPin === p.n); el.classList.toggle('full', c != null);
      el.setAttribute('aria-pressed', selPin === p.n ? 'true' : 'false');
      el.setAttribute('aria-label', `Place ${num(p.n)}${c == null ? ', empty' : `: ${chips[c].l2}`}`);
    });
    const used = new Set(placed.values());
    chips.forEach((c) => { const b = chipEl(c.i); b.classList.toggle('used', used.has(c.i)); b.classList.toggle('on', selChip === c.i); b.disabled = locked; });
    $check().disabled = locked || placed.size < targets.length;
  };
  const $check = () => view.querySelector('#s-check');
  const place = (n, i) => {
    for (const [k, v] of placed) if (v === i) placed.delete(k);      // a word sits on one pin only
    placed.set(n, i); selPin = null; selChip = null; paint();
    const nextEmpty = targets.find((p) => !placed.has(p.n));
    if (nextEmpty) pinEl(nextEmpty.n).focus(); else $check().focus();
  };
  targets.forEach((p) => {
    const el = pinEl(p.n);
    el.onclick = () => {
      if (locked) return;
      if (selChip != null) return place(p.n, selChip);
      if (placed.has(p.n)) { placed.delete(p.n); selPin = p.n; paint(); return; }
      selPin = selPin === p.n ? null : p.n; paint();
      if (selPin != null) { const free = chips.find((c) => ![...placed.values()].includes(c.i)); if (free) chipEl(free.i).focus(); }
    };
    el.ondragover = (e) => { if (!locked) { e.preventDefault(); el.classList.add('over'); } };
    el.ondragleave = () => el.classList.remove('over');
    el.ondrop = (e) => {
      e.preventDefault(); el.classList.remove('over');
      const i = Number(e.dataTransfer.getData('text/plain'));
      if (!locked && Number.isInteger(i) && chips[i]) place(p.n, i);
    };
  });
  chips.forEach((c) => {
    const b = chipEl(c.i);
    b.onclick = () => {
      if (locked) return;
      if (selPin != null) return place(selPin, c.i);
      selChip = selChip === c.i ? null : c.i; paint();
    };
    b.ondragstart = (e) => { e.dataTransfer.setData('text/plain', String(c.i)); e.dataTransfer.effectAllowed = 'move'; };
  });
  paint();
  $check().onclick = async () => {
    if (locked || placed.size < targets.length) return;
    locked = true; paint();
    const placements = targets.map((p) => ({ item: p.item, answer: chips[placed.get(p.n)].l2 }));
    const res = await ctx.submit(placements);
    if (!res || res.ok === false) { locked = false; paint(); return; }
    (res.pins || []).forEach((r) => {
      const ex2 = r.explain || {};
      label(view, r.n, r.correct ? (ex2.l2 || r.expected) : `${ex2.l2 || r.expected}`, r.correct ? 'ok' : 'no');
    });
    view.querySelectorAll('.chip').forEach((b) => { b.disabled = true; });
    ctx.done(res, placements);
  };
  const first = targets[0]; if (first) pinEl(first.n).focus();
}

/** Tap the pin a word names. ctx: {view, shell, guide, sayBtn, bindSay, speak, submit(answer, el) -> Promise<res>}. */
export function tapExercise(ex, ctx) {
  const { view } = ctx;
  let locked = false;
  ctx.shell(`<div class="guide">${ctx.guide(ex.retry ? 'think' : 'calm')}<div class="speech">${esc(ex.ask || '')}${ex.retry ? ' <span class="tag gold">once more</span>' : ''}</div></div>
    <div class="prompt" lang="${esc(ex.lang)}">${esc(ex.prompt)} ${ex.say ? ctx.sayBtn(ex.say, ex.lang) : ''}</div>${ex.rom ? `<div class="rom">${esc(ex.rom)}</div>` : ''}
    ${figure(ex.picture, ex.pins)}
    <div class="foot" id="s-foot"></div>`);
  ctx.bindSay();
  if (ex.say) ctx.speak(ex.say, ex.lang);
  view.querySelectorAll('.pic .pin').forEach((el) => {
    el.onclick = async () => {
      if (locked) return; locked = true;
      const res = await ctx.submit(String(num(el.dataset.pin)), el);
      if (!res || res.ok === false) { locked = false; return; }
      const right = (res.explain && res.explain.pin && res.explain.pin.n) || null;
      if (!res.correct) el.classList.add('no');
      if (right != null) label(view, right, (res.explain && res.explain.l2) || ex.prompt, 'ok');
      view.querySelectorAll('.pic .pin').forEach((p) => { p.disabled = true; });
    };
  });
}
