// Sect Academy — handwriting: write a glyph stroke by stroke on a square pad.
// The learner draws with a mouse, finger or pen (pointer events). Each stroke is checked as
// it lands, with the same matcher the server uses (hand.py), only to give hints: a stroke
// that misses shakes red, after two misses the expected stroke flashes, after three it stays
// lit. At the end every stroke drawn (failed ones too) goes to the server, which replays and
// grades them; nothing this page concludes is trusted. "Outline" shows the glyph faintly to
// trace (on by default the first time a glyph is written here), "Show me" animates the stroke
// order, and "I wrote it on paper" is the self-check for keyboard users (Hard at best).
// Everything is built with createElementNS / textContent; numbers are forced through num().

const NS = 'http://www.w3.org/2000/svg';
const num = (v) => { const n = Number(v); return Number.isFinite(n) ? n : 0; };
const SEEN_KEY = 'sect.hw.seen';

// --- the matcher (a port of hand.py: keep the two in step) -------------------------
export const TOL = { samples: 16, end: 0.17, mean: 0.12, lenLo: 0.35, lenHi: 2.4, minLen: 0.06, dirCos: 0.5,
  dirLong: 0.15, dirShort: 0.05, better: 0.6, margin: 0.04, orderFloor: 0.05 };
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const length = (p) => { let s = 0; for (let i = 0; i < p.length - 1; i += 1) s += dist(p[i], p[i + 1]); return s; };

export function resample(pts, n = TOL.samples) {
  if (!pts.length) return [];
  const cum = [0];
  for (let i = 0; i < pts.length - 1; i += 1) cum.push(cum[i] + dist(pts[i], pts[i + 1]));
  const total = cum[cum.length - 1];
  if (total <= 1e-9) return Array.from({ length: n }, () => pts[0]);
  const out = []; let j = 0;
  for (let k = 0; k < n; k += 1) {
    const t = total * k / (n - 1);
    while (j < pts.length - 2 && cum[j + 1] < t) j += 1;
    const seg = cum[j + 1] - cum[j];
    const u = seg <= 1e-12 ? 0 : Math.min(1, Math.max(0, (t - cum[j]) / seg));
    out.push([pts[j][0] + u * (pts[j + 1][0] - pts[j][0]), pts[j][1] + u * (pts[j + 1][1] - pts[j][1])]);
  }
  return out;
}

export function compare(drawn, expected) {
  const d = resample(drawn); const e = resample(expected);
  if (!d.length || !e.length) return { ok: false, mean: 9, why: 'empty' };
  let mean = 0; for (let i = 0; i < e.length; i += 1) mean += dist(d[i], e[i]); mean /= e.length;
  const le = Math.max(length(expected), TOL.minLen); const ld = length(drawn);
  let why = '';
  if (dist(d[0], e[0]) > TOL.end) why = 'start';
  else if (dist(d[d.length - 1], e[e.length - 1]) > TOL.end) why = 'end';
  else if (mean > TOL.mean) why = 'shape';
  else if (!(ld / le >= TOL.lenLo && ld / le <= TOL.lenHi)) why = 'length';
  else {
    const ce = [e[e.length - 1][0] - e[0][0], e[e.length - 1][1] - e[0][1]];
    const cd = [d[d.length - 1][0] - d[0][0], d[d.length - 1][1] - d[0][1]];
    const ne = Math.hypot(...ce); const nd = Math.hypot(...cd);
    if (ne > TOL.dirShort && nd > 1e-6) {
      const cos = (ce[0] * cd[0] + ce[1] * cd[1]) / (ne * nd);
      if (cos < (ne > TOL.dirLong ? TOL.dirCos : 0)) why = 'direction';
    } else if (ne > TOL.dirShort) why = 'direction';
  }
  return { ok: !why, mean, why };
}

export function matchStroke(drawn, strokes, at) {
  const here = compare(drawn, strokes[at]);
  let best = null;
  for (let j = at + 1; j < strokes.length; j += 1) { const c = compare(drawn, strokes[j]); if (c.ok && (best === null || c.mean < best)) best = c.mean; }
  if (here.ok) {
    if (best !== null && here.mean > TOL.orderFloor && best < TOL.better * here.mean && here.mean - best > TOL.margin) return { ok: false, why: 'order' };
    return { ok: true, why: '' };
  }
  return best !== null ? { ok: false, why: 'order' } : { ok: false, why: here.why };
}

const WHY = { start: 'That stroke starts somewhere else.', end: 'That stroke ends somewhere else.', shape: 'The shape of that stroke is off.',
  length: 'That stroke is too long or too short.', direction: 'That stroke goes the other way.', order: 'Right stroke, wrong moment: another one comes first.',
  empty: 'Draw a stroke on the pad.' };

// --- drawing helpers -----------------------------------------------------------------
const el = (tag, attrs = {}, parent = null) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  if (parent) parent.appendChild(e);
  return e;
};
const unitStrokes = (c) => (c.m || []).map((flat) => { const p = []; for (let i = 0; i + 1 < flat.length; i += 2) p.push([num(flat[i]) / 1000, num(flat[i + 1]) / 1000]); return p; });
const polyD = (pts) => pts.map((p, i) => `${i ? 'L' : 'M'}${(p[0] * 1000).toFixed(1)} ${(p[1] * 1000).toFixed(1)}`).join(' ');
const OUTLINE_OK = /^[MLQCZ0-9 .-]+$/;          // outlines are numbers and path letters only
let uid = 0;

/** One brush stroke (index k of character c): a filled outline for hanzi, a thick line otherwise. */
function brush(parent, c, k, cls) {
  const g = el('g', { class: cls }, parent);
  const o = c.o && c.o[k] && OUTLINE_OK.test(c.o[k]) ? c.o[k] : '';
  if (o) el('path', { d: o, class: 'hw-fill' }, g);
  else el('path', { d: polyD(unitStrokes(c)[k]), class: 'hw-line' }, g);
  return g;
}

/** Draw stroke k growing from its start (the demo and the hint). */
function animateStroke(parent, c, k, cls, ms) {
  const pts = unitStrokes(c)[k];
  const g = el('g', { class: cls }, parent);
  const d = polyD(pts);
  const o = c.o && c.o[k] && OUTLINE_OK.test(c.o[k]) ? c.o[k] : '';
  const line = el('path', { d, class: o ? 'hw-sweep' : 'hw-line' }, g);
  if (o) {
    const id = `hwclip${uid += 1}`;
    const cp = el('clipPath', { id }, g); el('path', { d: o }, cp);
    line.setAttribute('clip-path', `url(#${id})`);
  }
  const len = Math.max(1, length(pts) * 1000 + 60);
  line.style.strokeDasharray = `${len} ${len}`;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches || !line.animate) return Promise.resolve(g);
  const a = line.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: ms, easing: 'ease-in-out', fill: 'forwards' });
  return a.finished.then(() => g, () => g);
}

function seen() { try { return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || '[]')); } catch (_) { return new Set(); } }
function markSeen(id) {
  try { const s = seen(); s.add(id); localStorage.setItem(SEEN_KEY, JSON.stringify([...s].slice(-2000))); } catch (_) { /* private window: the outline just shows again */ }
}

/** A glyph_write exercise. ctx: {view, shell, guide, sayBtn, bindSay, speak, submit(body) -> Promise<res>}. */
export function writeExercise(ex, ctx) {
  const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const chars = (ex.chars || []).filter((c) => Array.isArray(c.m) && c.m.length);
  const lang = ex.lang;
  ctx.shell(`<div class="guide">${ctx.guide(ex.retry ? 'think' : 'calm')}<div class="speech">${esc(ex.ask || 'Write it')}${ex.retry ? ' <span class="tag gold">once more</span>' : ''}</div></div>
    <div class="prompt big">${esc(ex.prompt)} ${ex.say ? ctx.sayBtn(ex.say, lang) : ''}</div>${ex.sub ? `<div class="sub">${esc(ex.sub)}</div>` : ''}
    <div class="hw">
      <div class="hw-pad" id="hw-pad" role="img" aria-label="Writing pad: draw the strokes here with a mouse, finger or pen"></div>
      <div class="hw-side">
        <p class="hw-count dim small" id="hw-count"></p>
        <p class="hw-msg" id="hw-msg" role="status" aria-live="polite"></p>
        <div class="hw-tools">
          <button type="button" class="btn" id="hw-outline" aria-pressed="false">Outline</button>
          <button type="button" class="btn" id="hw-demo">Show me</button>
          <button type="button" class="btn quiet" id="hw-paper">I wrote it on paper</button>
        </div>
        <p class="dim small hw-credit">${esc(ex.credit || '')}</p>
      </div>
    </div>
    <div class="foot" id="s-foot"></div>`);
  ctx.bindSay();
  const pad = ctx.view.querySelector('#hw-pad'); const msg = ctx.view.querySelector('#hw-msg'); const count = ctx.view.querySelector('#hw-count');
  const svg = el('svg', { viewBox: '0 0 1000 1000', class: 'hw-svg', 'aria-hidden': 'true' }, pad);
  const grid = el('g', { class: 'hw-grid' }, svg);
  for (const [x1, y1, x2, y2] of [[500, 0, 500, 1000], [0, 500, 1000, 500], [0, 0, 1000, 1000], [1000, 0, 0, 1000]]) el('line', { x1, y1, x2, y2 }, grid);
  const gOutline = el('g', { class: 'hw-outline' }, svg); const gDone = el('g', {}, svg); const gHint = el('g', {}, svg);
  const ink = el('path', { class: 'hw-ink', d: '' }, svg);

  const st = { ci: 0, at: 0, miss: 0, mistakes: 0, attempts: chars.map(() => []), assisted: false, outline: false, busy: false, over: false, wrong: 0 };
  const strokesOf = (ci) => unitStrokes(chars[ci]);
  const say = (text, cls = '') => { msg.textContent = text; msg.className = `hw-msg ${cls}`; };
  const paintOutline = () => {
    gOutline.replaceChildren();
    if (!st.outline || !chars[st.ci]) return;
    strokesOf(st.ci).forEach((_, k) => brush(gOutline, chars[st.ci], k, 'hw-ghost'));
  };
  const setOutline = (on) => {
    st.outline = on;
    const b = ctx.view.querySelector('#hw-outline'); b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.classList.toggle('on', on);
    paintOutline();
  };
  const status = () => {
    const n = strokesOf(st.ci).length;
    count.textContent = `${chars.length > 1 ? `Character ${st.ci + 1} of ${chars.length}. ` : ''}Stroke ${Math.min(st.at + 1, n)} of ${n}.`;
  };
  const startChar = () => { gDone.replaceChildren(); gHint.replaceChildren(); st.at = 0; st.miss = 0; st.mistakes = 0; paintOutline(); status(); };

  if (!chars.length) { say('There is no stroke data for this one.', 'no'); return; }
  if (!seen().has(ex.item)) setOutline(true);
  startChar();
  say(st.outline ? 'Trace the outline, in stroke order. Start with the first stroke.' : 'Write the first stroke.');

  const finish = async () => {
    st.over = true; st.busy = true;
    pad.classList.add('done');
    ctx.view.querySelectorAll('.hw-tools button').forEach((b) => { b.disabled = true; });
    const res = await ctx.submit({ chars: st.attempts, assisted: st.assisted });
    if (res && res.ok !== false) {
      if (res.correct) markSeen(ex.item);
      const h = ctx.view.querySelector('#s-foot .verdict h3');
      if (h) h.textContent = res.correct ? (res.flag ? (st.assisted ? 'Written, with help' : 'Written, with a slip or two') : 'Written cleanly') : 'Not quite yet';
      if (!res.correct) {
        const why = `${st.wrong} wrong stroke${st.wrong === 1 ? '' : 's'}; ${chars.map((c) => num(c.slips)).join(' + ')} allowed. Watch the order: it comes back in a moment.`;
        say(why, 'no');
        const g = ctx.view.querySelector('#s-foot .verdict .grow');
        if (g && h) { const p = document.createElement('p'); p.className = 'dim small'; p.textContent = why; g.insertBefore(p, h.nextSibling); }
        demo();
      }
    } else { st.over = false; st.busy = false; ctx.view.querySelectorAll('.hw-tools button').forEach((b) => { b.disabled = false; }); }
  };

  const judge = (pts) => {
    const strokes = strokesOf(st.ci);
    const flat = []; for (const p of resample(pts, Math.min(48, Math.max(8, pts.length)))) flat.push(+p[0].toFixed(3), +p[1].toFixed(3));
    st.attempts[st.ci].push(flat);
    if (st.outline) st.assisted = true;          // traced over the outline: written with help
    const r = matchStroke(pts, strokes, st.at);
    if (r.ok) {
      gHint.replaceChildren();
      brush(gDone, chars[st.ci], st.at, 'hw-done');
      st.at += 1; st.miss = 0;
      if (st.at >= strokes.length) {
        if (st.ci + 1 < chars.length) { st.ci += 1; setTimeout(() => { startChar(); say('Good. Now the next character.', 'ok'); }, 450); }
        else { say('All strokes written.', 'ok'); finish(); }
        return;
      }
      status(); say(st.mistakes > num(chars[st.ci].slips) ? 'Keep going. Too many slips for this one to count, so it comes back.' : 'Good.', 'ok');
      return;
    }
    st.miss += 1; st.mistakes += 1; st.wrong += 1;
    say(WHY[r.why] || 'Not that stroke.', 'no');
    pad.classList.remove('shake'); void pad.offsetWidth; pad.classList.add('shake');
    if (st.miss >= 2) {
      gHint.replaceChildren();
      animateStroke(gHint, chars[st.ci], st.at, 'hw-hint', 700).then((g) => { if (st.miss < 3) setTimeout(() => g.remove(), 900); });
    }
  };

  // --- pointer input ---
  let cur = null;
  const at = (e) => { const r = svg.getBoundingClientRect(); return [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height]; };
  svg.addEventListener('pointerdown', (e) => {
    if (st.busy || e.button > 0) return;
    e.preventDefault(); svg.setPointerCapture(e.pointerId);
    cur = { id: e.pointerId, pts: [at(e)] }; ink.setAttribute('d', polyD(cur.pts)); ink.classList.remove('bad');
  });
  svg.addEventListener('pointermove', (e) => {
    if (!cur || e.pointerId !== cur.id) return;
    const events = e.getCoalescedEvents ? e.getCoalescedEvents() : [e];
    for (const ce of (events.length ? events : [e])) {
      const p = at(ce); const last = cur.pts[cur.pts.length - 1];
      if (dist(p, last) > 0.004 && cur.pts.length < 2000) cur.pts.push(p);
    }
    ink.setAttribute('d', polyD(cur.pts));
  });
  const up = (e) => {
    if (!cur || e.pointerId !== cur.id) return;
    const pts = cur.pts; cur = null;
    ink.setAttribute('d', '');
    if (length(pts) < 0.012) return;            // a tap, not a stroke
    judge(pts);
  };
  svg.addEventListener('pointerup', up);
  svg.addEventListener('pointercancel', () => { cur = null; ink.setAttribute('d', ''); });

  // --- tools ---
  const demo = async () => {
    if (st.demoing) return; st.demoing = true;
    const ci = st.over ? 0 : st.ci;
    const show = st.over ? chars.map((_, i) => i) : [ci];
    for (const i of show) {
      gHint.replaceChildren(); gOutline.replaceChildren();
      if (st.over) gDone.replaceChildren();
      for (let k = 0; k < chars[i].m.length; k += 1) await animateStroke(gHint, chars[i], k, 'hw-demo', 520);
      if (show.length > 1) await new Promise((r) => setTimeout(r, 500));
    }
    if (!st.over) setTimeout(() => { gHint.replaceChildren(); paintOutline(); }, 700);
    st.demoing = false;
  };
  ctx.view.querySelector('#hw-outline').onclick = () => setOutline(!st.outline);
  ctx.view.querySelector('#hw-demo').onclick = () => { st.assisted = true; say('Watch the order, then write it.'); demo(); };
  ctx.view.querySelector('#hw-paper').onclick = () => paper();

  // "I wrote it on paper": the keyboard fallback. Show the glyph and its order, then the learner says how it went.
  function paper() {
    if (st.busy) return;
    st.busy = true; st.over = true; pad.classList.add('done');
    ctx.view.querySelectorAll('.hw-tools button').forEach((b) => { b.disabled = true; });
    say('Here is the stroke order. Compare it with what you wrote.');
    demo();
    const foot = ctx.view.querySelector('#s-foot');
    foot.innerHTML = `<div class="hw-self panel"><p><b>Self-check.</b> <span class="dim">Your own verdict counts as Hard at best, so a written answer always schedules better.</span></p>
      <div class="row"><button class="btn primary grow" id="hw-right">I wrote it right</button><button class="btn seal grow" id="hw-wrong">I got it wrong</button></div></div>`;
    const send = async (verdict) => {
      foot.querySelectorAll('button').forEach((b) => { b.disabled = true; });
      const res = await ctx.submit({ self: true, verdict });
      if (res && res.ok === false) { foot.querySelectorAll('button').forEach((b) => { b.disabled = false; }); return; }
      const h = ctx.view.querySelector('#s-foot .verdict h3');
      if (h) h.textContent = verdict === 'right' ? 'Marked right (self-check)' : 'Marked to practise again';
    };
    foot.querySelector('#hw-right').onclick = () => send('right');
    foot.querySelector('#hw-wrong').onclick = () => send('wrong');
    foot.querySelector('#hw-right').focus();
  }
  ctx.view.querySelector('#hw-paper').setAttribute('title', 'For keyboard users, or when you practise with a brush and paper');
}
