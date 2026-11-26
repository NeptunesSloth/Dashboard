// Sect Academy — Read: a book shelf, a paginated reader with tap-to-translate, offline dictionaries and "My words".
// Books are turned into plain text here in the browser (EPUB unzipped by hand, PDF through the vendored
// pdf.js, loaded from this origin only when a PDF is imported), then kept by the server so every device
// sees the same shelf. Lookups and saved words go to the server's offline dictionary.
// Every string from a book, the dictionary or the server goes through esc() before innerHTML.

let C = null;                // context from academy.js: { api, esc, num, toast, go, ICON, ov, setKeys }
const $ = (sel, root = document) => root.querySelector(sel);

/* ---------------- speech (the device's own voices: they work offline) ---------------- */
const synth = window.speechSynthesis;
let voices = [];
const loadVoices = () => { try { voices = synth ? synth.getVoices() : []; } catch (_) { voices = []; } };
if (synth) { loadVoices(); try { synth.addEventListener('voiceschanged', loadVoices); } catch (_) { /* old Safari */ } }
const SPEECH = { es: 'es-ES', fr: 'fr-FR', zh: 'zh-CN', ja: 'ja-JP', ko: 'ko-KR', en: 'en-GB', pt: 'pt-PT', it: 'it-IT', de: 'de-DE' };
let LANG_NAME = { es: 'Spanish', fr: 'French', zh: 'Mandarin Chinese', ja: 'Japanese', ko: 'Korean', en: 'English', pt: 'Portuguese', it: 'Italian', de: 'German', other: 'this language' };
let LOOKUP = ['es'];          // languages the server has a dictionary for (from /api/dict/langs)
let langsLoaded = false;
async function loadLangs() {
  if (langsLoaded) return;
  const r = await C.api('/api/dict/langs');
  if (r.ok !== false && Array.isArray(r.lookup)) {
    LOOKUP = r.lookup.map(String);
    if (r.langs && typeof r.langs === 'object') LANG_NAME = { ...LANG_NAME, ...r.langs };
    langsLoaded = true;
  }
}
const hasLookup = (lang) => LOOKUP.includes(lang);
const noLookupNote = (lang) => `Lookup for ${LANG_NAME[lang] || 'this language'} is coming.`;
function voiceFor(lang) {
  const want = SPEECH[lang]; if (!want) return null;
  loadVoices();
  const norm = (v) => String(v.lang || '').replace('_', '-').toLowerCase();
  const base = want.split('-')[0].toLowerCase();
  const local = voices.filter((v) => v.localService !== false);
  const pool = local.length ? local : voices;
  return pool.find((v) => norm(v) === want.toLowerCase()) || pool.find((v) => norm(v).split('-')[0] === base) || null;
}
function speechNote(lang) {
  if (!synth) return 'This browser cannot speak words aloud.';
  if (!voiceFor(lang)) return `No ${LANG_NAME[lang] || 'matching'} voice is installed on this device, so words cannot be spoken. Add one in your system's speech or language settings.`;
  return '';
}
function speak(text, lang, slow = false) {
  const v = voiceFor(lang); if (!v || !text) return false;
  try { synth.cancel(); const u = new SpeechSynthesisUtterance(String(text)); u.voice = v; u.lang = String(v.lang).replace('_', '-'); u.rate = slow ? 0.55 : 0.9; synth.speak(u); } catch (_) { return false; }
  return true;
}

/* ---------------- turning files into text ---------------- */
const MAX_ENTRY = 32 * 1024 * 1024;           // one file inside an EPUB, unpacked
async function inflate(bytes) {
  if (typeof DecompressionStream === 'undefined') throw new Error('This browser cannot unpack EPUB files.');
  const ds = new DecompressionStream('deflate-raw'); const w = ds.writable.getWriter();
  w.write(bytes).catch(() => {}); w.close().catch(() => {});
  const r = ds.readable.getReader(); const parts = []; let n = 0;
  for (;;) {
    const { done, value } = await r.read(); if (done) break;
    n += value.length; if (n > MAX_ENTRY) { r.cancel().catch(() => {}); throw new Error('A file inside that EPUB is too large.'); }
    parts.push(value);
  }
  const out = new Uint8Array(n); let o = 0; for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}
function unzip(buf) {
  const u8 = new Uint8Array(buf), dv = new DataView(buf); let e = u8.length - 22;
  while (e >= 0 && dv.getUint32(e, true) !== 0x06054b50) e--;
  if (e < 0) throw new Error('That is not an EPUB (zip) file.');
  const n = dv.getUint16(e + 10, true); let p = dv.getUint32(e + 16, true); const F = new Map();
  const td = new TextDecoder();
  for (let i = 0; i < n && p + 46 <= u8.length; i++) {
    if (dv.getUint32(p, true) !== 0x02014b50) break;
    const m = dv.getUint16(p + 10, true), cs = dv.getUint32(p + 20, true), nl = dv.getUint16(p + 28, true), xl = dv.getUint16(p + 30, true), cl = dv.getUint16(p + 32, true), off = dv.getUint32(p + 42, true);
    F.set(td.decode(u8.subarray(p + 46, p + 46 + nl)), { m, cs, off });
    p += 46 + nl + xl + cl;
  }
  return {
    async get(name) {
      const f = F.get(name); if (!f || f.off + 30 > u8.length) return null;
      const s = f.off + 30 + dv.getUint16(f.off + 26, true) + dv.getUint16(f.off + 28, true), d = u8.subarray(s, s + f.cs);
      if (f.m === 0) return d;
      if (f.m !== 8) return null;
      return inflate(d);
    },
  };
}
function resolvePath(base, href) {
  const parts = base.split('/').slice(0, -1);
  for (const seg of String(href).split('#')[0].split('/')) { if (seg === '..') parts.pop(); else if (seg && seg !== '.') parts.push(seg); }
  const joined = parts.join('/');
  try { return decodeURIComponent(joined); } catch (_) { return joined; }
}
function blockText(doc) {
  doc.querySelectorAll('script,style,rt,rp').forEach((x) => x.remove());      // ruby readings (furigana) are not the text
  const body = doc.body || doc.documentElement; if (!body) return '';
  body.querySelectorAll('p,h1,h2,h3,h4,h5,h6,li,blockquote,div,br,tr').forEach((x) => x.after('\n\n'));
  return body.textContent.replace(/[ \t\r\f ]+/g, ' ').replace(/ ?\n ?/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
}
async function epubText(buf) {
  // DOMParser documents are inert: nothing in them runs or loads; only their text is taken.
  const z = unzip(buf), td = new TextDecoder();
  const read = async (name) => { const d = await z.get(name); return d ? td.decode(d) : null; };
  const xml = (s) => new DOMParser().parseFromString(s || '', 'application/xml');
  const container = xml(await read('META-INF/container.xml')).querySelector('rootfile');
  if (!container) throw new Error('That EPUB has no table of contents.');
  const opfPath = container.getAttribute('full-path') || '';
  const opf = xml(await read(opfPath)); const man = {};
  opf.querySelectorAll('manifest > item').forEach((i) => { man[i.getAttribute('id')] = i.getAttribute('href'); });
  const title = ((opf.getElementsByTagName('dc:title')[0] || {}).textContent || '').trim();
  let out = '';
  for (const r of opf.querySelectorAll('spine > itemref')) {
    const h = man[r.getAttribute('idref')]; if (!h) continue;
    const s = await read(resolvePath(opfPath, h)); if (!s) continue;
    out += blockText(new DOMParser().parseFromString(s, 'text/html')) + '\n\n';
    if (out.length > 4200000) break;
  }
  return { title, text: out };
}
let pdfLoading = null;
function loadPdfJs() {
  if (window.pdfjsLib) return Promise.resolve(window.pdfjsLib);
  if (!pdfLoading) {
    pdfLoading = new Promise((resolve, reject) => {
      const s = document.createElement('script'); s.src = '/vendor/pdfjs/pdf.min.js';
      s.onload = () => (window.pdfjsLib ? resolve(window.pdfjsLib) : reject(new Error('pdf.js did not start.')));
      s.onerror = () => { pdfLoading = null; reject(new Error('pdf.js could not be loaded.')); };
      document.head.appendChild(s);
    });
  }
  return pdfLoading;
}
async function pdfText(buf, progress) {
  const lib = await loadPdfJs();
  lib.GlobalWorkerOptions.workerSrc = '/vendor/pdfjs/pdf.worker.min.js';      // same origin: no blob worker needed
  const doc = await lib.getDocument({ data: new Uint8Array(buf), isEvalSupported: false, disableFontFace: true, useSystemFonts: false,
    disableAutoFetch: true, disableStream: true }).promise;
  let out = '';
  try {
    for (let p = 1; p <= doc.numPages; p++) {
      progress(`Reading PDF page ${p} of ${doc.numPages}…`);
      const t = await (await doc.getPage(p)).getTextContent(); let s = '';
      t.items.forEach((i) => { s += (i.str || '') + (i.hasEOL ? '\n' : ''); });
      // Join the lines of a paragraph; a short line that ends a sentence ends the paragraph (as Aprende did).
      const ls = s.split('\n').map((x) => x.trim()).filter(Boolean); const mx = Math.max(0, ...ls.map((x) => x.length)); let q = '';
      ls.forEach((l) => { if (/\p{L}-$/u.test(l)) q += l.slice(0, -1); else q += l + (/[.!?:»”"]$/.test(l) && l.length < mx * 0.75 ? '\n\n' : ' '); });
      out += q.trim() + '\n\n';
      if (out.length > 4200000) break;
    }
  } finally { doc.destroy(); }
  return out.replace(/ +\n/g, '\n').trim();
}
// A .txt/.html that is not UTF-8: Japanese books are often Shift_JIS (Aozora Bunko) or EUC-JP, Chinese GB18030 or Big5.
const LEGACY = { ja: ['shift_jis', 'euc-jp'], zh: ['gb18030', 'big5'] };
function decodeText(buf, lang) {
  try { return new TextDecoder('utf-8', { fatal: true }).decode(buf); } catch (_) { /* not UTF-8: try the language's old encodings */ }
  for (const label of LEGACY[lang] || []) {
    try { return new TextDecoder(label, { fatal: true }).decode(buf); } catch (_) { /* not this one */ }
  }
  return new TextDecoder().decode(buf);
}
/** Aozora Bunko plain text: ruby 《reading》 and its ｜ base marker, ［＃…］ notes, the symbol key and the colophon go. */
function aozora(text) {
  if (!/《|［＃/.test(text)) return text;
  let t = text.replace(/\r/g, '');
  const dash = /^-{20,}\s*$/gm; const marks = [];
  let m; while ((m = dash.exec(t)) && marks.length < 2) marks.push([m.index, m.index + m[0].length]);
  if (marks.length === 2 && marks[0][0] < 4000) t = t.slice(0, marks[0][0]) + t.slice(marks[1][1]);
  const end = t.search(/\n底本[：:]/);
  if (end > t.length / 2) t = t.slice(0, end);
  return t.replace(/｜([^《\n]+)《[^》\n]*》/g, '$1').replace(/《[^》\n]*》/g, '').replace(/※?［＃[^］\n]*］/g, '').replace(/[ \t]+\n/g, '\n');
}
async function fileText(f, progress, lang = '') {
  let title = f.name.replace(/\.[^.]+$/, ''), text;
  if (/\.epub$/i.test(f.name)) { const r = await epubText(await f.arrayBuffer()); text = r.text; if (r.title) title = r.title; }
  else if (/\.pdf$/i.test(f.name)) text = await pdfText(await f.arrayBuffer(), progress);
  else {
    text = decodeText(await f.arrayBuffer(), lang);
    if (/\.html?$/i.test(f.name)) text = blockText(new DOMParser().parseFromString(text, 'text/html'));
    else if (lang === 'ja') text = aozora(text);
  }
  return { title, text: String(text || '').replace(/\r/g, '') };
}

/* ---------------- pages ---------------- */
const PAGE = 1500;
/** Pages as [start, end) character offsets, so a saved position survives any screen size. */
function paginate(text) {
  const pages = []; const n = text.length; let start = 0;
  while (start < n) {
    let end = Math.min(n, start + PAGE);
    if (end < n) {
      const win = text.slice(start, end); const min = PAGE * 0.4;
      let cut = win.lastIndexOf('\n\n');
      if (cut < min) { let m, last = -1; const re = /[.!?…»”"]\s|[。！？」』]/g; while ((m = re.exec(win))) last = m.index + 1; cut = last; }
      if (cut < min) cut = win.lastIndexOf(' ');
      if (cut > 0) end = start + cut;
    }
    pages.push([start, end]);
    start = end; while (start < n && /\s/.test(text[start])) start++;
  }
  return pages.length ? pages : [[0, 0]];
}
const WORD = /[\p{L}\p{M}](?:[\p{L}\p{M}'’-]*[\p{L}\p{M}])?/gu;
/** Tokens ({t, k}) for a page. The server segments languages it has a dictionary for (Spanish splits on
 *  spaces; Chinese and Japanese will need their dictionary to find word boundaries); anything else is
 *  split on spaces here, so it can still be read and heard. */
async function tokens(text, lang) {
  if (hasLookup(lang)) {
    const r = await C.api('/api/dict/segment', { lang, text });
    if (r.ok !== false && Array.isArray(r.tokens) && r.tokens.map((x) => String(x.t)).join('') === text) return r.tokens;
  }
  const out = []; let last = 0, m; WORD.lastIndex = 0;
  while ((m = WORD.exec(text))) {
    if (m.index > last) out.push({ t: text.slice(last, m.index), k: null });
    out.push({ t: m[0], k: m[0].toLowerCase() }); last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ t: text.slice(last), k: null });
  return out;
}
function pageHtml(toks, base) {
  const esc = C.esc; let off = base, html = '<p>';
  for (const tok of toks) {
    const t = String(tok.t);
    if (tok.k) html += `<span class="w" data-o="${off}">${esc(t)}</span>`;
    else html += esc(t).replace(/\n\s*\n/g, '</p><p>').replace(/\n/g, '<br>');
    off += t.length;
  }
  return `${html}</p>`.replace(/<p>\s*<\/p>/g, '');
}
function sentenceAt(text, at) {
  let a = at, b = at;
  while (a > 0 && !/[.!?…\n。！？]/.test(text[a - 1])) a--;
  while (b < text.length && !/[.!?…\n。！？]/.test(text[b])) b++;
  return text.slice(a, Math.min(text.length, b + 1)).replace(/\s+/g, ' ').trim().slice(0, 240);
}

/* ---------------- the lookup card ---------------- */
const HOW = { form: 'a form of', pronouns: 'a verb with pronouns attached:', ending: 'probably from', accent: 'spelled', exact: '',
  variant: 'a variant of', inflected: 'a form of' };
const SRC = { mine: 'Yours', core: 'Core', wiktionary: 'Wiktionary', cedict: 'CC-CEDICT', jmdict: 'JMdict', number: 'Number', name: 'Name' };
const cache = new Map();
async function lookup(word, lang, around) {
  const pre = around ? String(around.pre || '') : '', post = around ? String(around.post || '') : '';
  const k = `${lang}:${word.toLowerCase()}:${pre}:${post}`;
  if (cache.has(k)) return cache.get(k);
  const ctx = pre || post ? `&pre=${encodeURIComponent(pre)}&post=${encodeURIComponent(post)}` : '';
  const r = await C.api(`/api/dict?lang=${encodeURIComponent(lang)}&w=${encodeURIComponent(word)}${ctx}`);
  if (r.ok !== false) cache.set(k, r);
  return r;
}
let card = null;      // { el, word, lang, ctx }
function closeCard() { if (card) { card.el.hidden = true; card.el.innerHTML = ''; } document.querySelectorAll('.w.on').forEach((x) => x.classList.remove('on')); card = null; }
function cardEl() {
  let el = $('#lk');
  if (!el) { el = document.createElement('aside'); el.id = 'lk'; el.className = 'lookup'; el.setAttribute('aria-live', 'polite'); C.view.appendChild(el); }
  return el;
}
function firstMeaning(r) {
  const s = (r.senses || [])[0]; if (!s) return '';
  return String(s.text).split('; ').slice(0, 2).join('; ').slice(0, 120);
}
async function showCard(word, lang, ctx = '', around = null) {
  const esc = C.esc; const el = cardEl(); card = { el, word, lang, ctx, around };
  el.hidden = false;
  const note = speechNote(lang);
  const sayBtns = note ? '' : `<button class="say tiny" data-say="0" aria-label="Hear it">${C.ICON.sound}</button><button class="btn quiet slow" data-say="1">Slow</button>`;
  const head = (w) => `<div class="lk-head"><b class="lk-word" lang="${esc(lang)}">${esc(w)}</b>${sayBtns}<span class="grow"></span><button class="btn quiet lk-x" data-x aria-label="Close">Close</button></div>
    ${note ? `<p class="dim small lk-note">${esc(note)}</p>` : ''}`;
  if (!hasLookup(lang)) {
    el.innerHTML = `${head(word)}<p class="lk-only">${esc(noLookupNote(lang))}</p>`;
    bindCard(word, lang); return;
  }
  el.innerHTML = `${head(word)}<p class="dim small">Looking it up…</p>`;
  bindCard(word, lang);
  const r = await lookup(word, lang, around);
  if (!card || card.word !== word) return;
  if (r.ok === false) { el.innerHTML = `${head(word)}<p class="dim">${esc(r.error)}</p>`; bindCard(word, lang); return; }
  const L = esc(lang);
  const how = r.how_text ? `${r.how_text} of` : (HOW[r.how] || '');
  const path = (r.path || []).length > 1 ? `<p class="lk-path small"><span class="dim">${esc(how)}</span> ${r.path.slice(1).map((p) => `<b lang="${L}">${esc(p)}</b>`).join(' → ')}</p>` : '';
  // Chinese and Japanese: the reading (pinyin; kana + rōmaji) and the other ways the word is written
  const rd = r.reading ? `<span lang="${L}">${esc(r.reading)}</span>` : '';
  const ro = r.rom && r.rom !== r.reading ? `<i>${esc(r.rom)}</i>` : '';
  const forms = (r.forms || []).length ? `<span class="dim">also written</span> ${r.forms.map((x) => `<span lang="${L}">${esc(x)}</span>`).join(', ')}` : '';
  const reading = rd || ro || forms ? `<p class="lk-read">${[rd, ro, forms].filter(Boolean).join(' · ')}</p>` : '';
  const many = (r.senses || []).filter((s) => s.read).length > 1;
  const senses = (r.senses || []).map((s) => {
    const parts = String(s.text).split('; ');
    const sr = many && s.read ? `<b lang="${L}" class="lk-sr">${esc(s.read)}</b>${s.rom && s.rom !== s.read ? ` <i class="dim">${esc(s.rom)}</i>` : ''} ` : '';
    return `<li><span class="tag ${s.src === 'mine' ? 'jade' : s.src === 'core' ? 'gold' : ''}">${esc(SRC[s.src] || s.src)}</span> ${sr}${esc(parts.slice(0, 4).join('; '))}${parts.length > 4 ? `<details><summary class="small">${parts.length - 4} more</summary>${esc(parts.slice(4).join('; '))}</details>` : ''}${s.src === 'mine' ? ` <button class="btn quiet small" data-unmine="${esc(r.lemma)}">Delete my meaning</button>` : ''}</li>`;
  }).join('');
  const also = (r.also || []).map((a) => `<b lang="${L}">${esc(a.lemma)}</b>${a.reading && a.reading !== a.lemma ? ` <span lang="${L}">${esc(a.reading)}</span>` : ''} <span class="dim">${esc(String((a.senses[0] || {}).text || '').slice(0, 80))}</span>`).join(' · ');
  const target = r.found ? r.lemma : r.word;
  el.innerHTML = `${head(r.word || word)}${reading}${path}
    ${r.found ? `<ol class="lk-senses">${senses}</ol>${r.weak ? '<p class="dim small">The dictionary only knows this spelling as a name; its everyday meaning may be missing. Add your own below.</p>' : ''}`
    : '<p class="lk-only">Not in the dictionary yet.</p>'}
    ${also ? `<p class="small lk-also"><span class="dim">Also:</span> ${also}</p>` : ''}
    ${r.saved ? `<p class="small"><span class="tag jade">Saved</span> in My words. <button class="btn quiet small" data-unsave="${esc(target)}">Remove</button></p>`
    : `<form class="lk-save" data-save><label class="small dim" for="lk-m">${r.found ? `Save <b lang="${L}">${esc(target)}</b> to My words as` : 'Add the English meaning'}</label>
      <div class="row"><input type="text" id="lk-m" maxlength="200" value="${esc(firstMeaning(r))}" autocomplete="off" placeholder="English meaning">
      <button class="btn primary" type="submit">${r.found ? 'Save word' : 'Add and save'}</button></div></form>`}
    <p class="dim tiny">${esc(r.credit || '')}</p>`;
  bindCard(word, lang, r);
}
function bindCard(word, lang, r) {
  const el = card && card.el; if (!el) return;
  el.querySelectorAll('[data-say]').forEach((b) => { b.onclick = () => speak(word, lang, b.dataset.say === '1'); });
  const x = $('[data-x]', el); if (x) x.onclick = closeCard;
  if (!r) return;
  const form = $('[data-save]', el);
  if (form) {
    form.onsubmit = async (e) => {
      e.preventDefault();
      const meaning = $('#lk-m', el).value.trim(); if (!meaning) { $('#lk-m', el).focus(); return; }
      const target = r.found ? r.lemma : r.word;
      if (!r.found) {
        const a = await C.api('/api/dict/entry', { lang, word: target, meaning });
        if (a.ok === false) { C.toast(a.error); return; }
      }
      const s = await C.api('/api/words', { lang, word: target, meaning, form: r.word, ctx: card ? card.ctx : '' });
      if (s.ok === false) { C.toast(s.error); return; }
      cache.clear(); C.toast(`Saved “${target}” to My words.`);
      showCard(word, lang, card ? card.ctx : '', card ? card.around : null);
    };
  }
  const q = `lang=${encodeURIComponent(lang)}&w=`;
  el.querySelectorAll('[data-unsave]').forEach((b) => { b.onclick = async () => { await C.api(`/api/words?${q}${encodeURIComponent(b.dataset.unsave)}`, undefined, 'DELETE'); cache.clear(); showCard(word, lang, card ? card.ctx : '', card ? card.around : null); }; });
  el.querySelectorAll('[data-unmine]').forEach((b) => { b.onclick = async () => { await C.api(`/api/dict/entry?${q}${encodeURIComponent(b.dataset.unmine)}`, undefined, 'DELETE'); cache.clear(); showCard(word, lang, card ? card.ctx : '', card ? card.around : null); }; });
}

/* ---------------- views ---------------- */
const TABS = [['books', 'Books'], ['dict', 'Dictionary'], ['words', 'My words']];
function tabs(on) {
  return `<h1 style="margin-bottom:10px">Read</h1><div class="tabs" role="tablist">${TABS.map(([k, n]) =>
    `<button role="tab" data-rtab="${k}" aria-selected="${k === on}" class="${k === on ? 'on' : ''}">${n}</button>`).join('')}</div>`;
}
function bindTabs() { C.view.querySelectorAll('[data-rtab]').forEach((b) => { b.onclick = () => C.go(b.dataset.rtab === 'books' ? '/read' : `/read?tab=${b.dataset.rtab}`); }); }
const kb = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1e3))} kB`);
const chars = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)} million` : n >= 1e4 ? `${Math.round(n / 1e3)},000` : n.toLocaleString("en-GB"));
/** A language picker over the languages that have a dictionary (one today; more as modules arrive). */
function langPicker(id, cur) {
  const esc = C.esc;
  if (LOOKUP.length < 2) return '';
  return `<select class="in" id="${id}" aria-label="Language" style="width:auto;min-height:40px">${LOOKUP.map((l) => `<option value="${esc(l)}" ${l === cur ? 'selected' : ''}>${esc(LANG_NAME[l] || l)}</option>`).join('')}</select>`;
}

async function renderBooks() {
  const { esc, num } = C;
  C.view.innerHTML = `${tabs('books')}<p class="loading">Taking the books down from the shelf…</p>`;
  bindTabs();
  const r = await C.api('/api/books');
  if (r.ok === false) { C.view.insertAdjacentHTML('beforeend', `<div class="panel">${esc(r.error)}</div>`); return; }
  if (Array.isArray(r.lookup)) LOOKUP = r.lookup.map(String);
  const langs = r.langs || {};
  C.view.innerHTML = `${tabs('books')}
    <section class="panel"><h2>Add a book</h2>
      <p class="dim small">EPUB, PDF, plain text, Markdown or HTML. The text is taken out here on this device and kept by your Sect Academy server, so your phone and your computer share one shelf. Scanned PDFs (pictures of pages) have no text to read.</p>
      <div class="row imp"><label class="field grow" style="margin:0"><span>Language of the book</span>
        <select class="in" id="rb-lang">${Object.entries(langs).map(([k, v]) => `<option value="${esc(k)}" ${k === 'es' ? 'selected' : ''}>${esc(v)}${hasLookup(k) || k === 'other' ? '' : ' (lookup coming)'}</option>`).join('')}</select></label>
      <label class="btn primary">Choose a file<input type="file" id="rb-file" accept=".epub,.pdf,.txt,.md,.html,.htm,application/epub+zip,application/pdf,text/plain" hidden></label></div>
      <p class="small" id="rb-msg" role="status"></p>
      <p class="dim small" style="margin:0">Shelf: ${num(r.books.length)} of ${num(r.max_count)} books, ${kb(num(r.used))} of ${kb(num(r.max_bytes))}.</p></section>
    <section class="panel shelf">${r.books.length ? `<ul class="list">${r.books.map((b) => {
      const pct = Math.min(100, Math.round(100 * num(b.pos) / Math.max(1, num(b.chars))));
      return `<li class="row"><div class="grow"><a href="/read?book=${encodeURIComponent(b.id)}" data-link class="bk-title">${esc(b.title)}</a>
        <div class="dim small">${esc(b.language)} · ${chars(num(b.chars))} characters · ${pct}% read</div>
        <div class="bar thin jade" style="margin-top:6px"><i style="width:${pct}%"></i></div></div>
        <a class="btn" href="/read?book=${encodeURIComponent(b.id)}" data-link>${num(b.pos) ? 'Continue' : 'Open'}</a>
        <button class="btn quiet" data-del="${esc(b.id)}" data-title="${esc(b.title)}">Delete</button></li>`;
    }).join('')}</ul>` : '<p class="dim" style="margin:0">No books yet. Add one above: a short story in Spanish is a good start.</p>'}</section>`;
  bindTabs();
  const msg = $('#rb-msg');
  $('#rb-file').onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const lang = $('#rb-lang').value;
    msg.textContent = `Importing ${f.name}…`;
    try {
      const { title, text } = await fileText(f, (t) => { msg.textContent = t; }, lang);
      if (text.trim().length < 50) throw new Error('No readable text was found in that file. A scanned PDF made of images cannot be read.');
      msg.textContent = 'Saving it to the shelf…';
      const res = await C.api('/api/books', { title, text, lang });
      if (res.ok === false) throw new Error(res.error);
      C.toast(`Added “${res.book.title}”.`);
      C.go(`/read?book=${encodeURIComponent(res.book.id)}`);
    } catch (err) { msg.textContent = (err && err.message) || 'That file could not be read. It may be damaged or protected.'; e.target.value = ''; }
  };
  C.view.querySelectorAll('[data-del]').forEach((b) => {
    b.onclick = async () => {
      if (!confirm(`Delete “${b.dataset.title}” from the shelf? Your saved words stay.`)) return;
      const res = await C.api(`/api/books/${encodeURIComponent(b.dataset.del)}`, undefined, 'DELETE');
      if (res.ok === false) C.toast(res.error); else renderBooks();
    };
  });
}

async function renderBook(id) {
  const { esc, num } = C;
  C.view.innerHTML = '<p class="loading">Opening the book…</p>';
  const r = await C.api(`/api/books/${encodeURIComponent(id)}`);
  if (r.ok === false || !r.book) { C.view.innerHTML = `<div class="panel"><p>${esc(r.error || 'That book is not on the shelf.')}</p><a class="btn" href="/read" data-link>Back to the shelf</a></div>`; return; }
  const b = r.book, text = String(r.text || ''), lang = String(b.lang);
  if (b.lookup && !hasLookup(lang)) LOOKUP = [...LOOKUP, lang];
  const pages = paginate(text);
  let i = 0, drawn = 0; const pos = num(b.pos);
  for (let k = 0; k < pages.length; k++) if (pages[k][0] <= pos) i = k;
  const draw = async () => {
    const mine = ++drawn; const [s, e] = pages[i];
    const toks = await tokens(text.slice(s, e), lang);
    if (mine !== drawn) return;
    closeCard();
    C.view.innerHTML = `<div class="readtop"><a href="/read" data-link class="btn quiet">Shelf</a><b class="grow rt-title">${esc(b.title)}</b><span class="tag">${esc(b.language)}</span></div>
      <article class="page" lang="${esc(lang)}" id="rd">${pageHtml(toks, s)}</article>
      <div class="pager"><button class="btn" id="rd-prev" ${i ? '' : 'disabled'}>Previous</button>
        <span class="dim small num grow" style="text-align:center">Page ${i + 1} of ${pages.length} · ${Math.round(100 * e / Math.max(1, text.length))}%</span>
        <button class="btn primary" id="rd-next" ${i < pages.length - 1 ? '' : 'disabled'}>Next</button></div>
      <p class="dim small" style="text-align:center">${hasLookup(lang) ? 'Tap any word for its meaning.' : `Tap any word to hear it. ${esc(noLookupNote(lang))}`}</p>`;
    $('#rd-prev').onclick = () => turn(-1);
    $('#rd-next').onclick = () => turn(1);
    $('#rd').onclick = (ev) => {
      const w = ev.target.closest('.w'); if (!w) return;
      C.view.querySelectorAll('.w.on').forEach((x) => x.classList.remove('on')); w.classList.add('on');
      const word = w.textContent; const at = num(w.dataset.o);
      const ov = C.ov(); if (ov && ov.settings && ov.settings.audio) speak(word, lang);
      showCard(word, lang, sentenceAt(text, at), { pre: text.slice(Math.max(0, at - 6), at), post: text.slice(at + word.length, at + word.length + 6) });
    };
  };
  const turn = (d) => {
    const n = Math.max(0, Math.min(pages.length - 1, i + d)); if (n === i) return;
    i = n; draw(); window.scrollTo(0, 0);
    C.api(`/api/books/${encodeURIComponent(id)}/pos`, { pos: pages[i][0] }, 'PUT');
  };
  C.setKeys((ev) => {
    if (ev.target && ev.target.closest && ev.target.closest('input,textarea,select')) return;
    if (ev.key === 'ArrowRight') turn(1); else if (ev.key === 'ArrowLeft') turn(-1); else if (ev.key === 'Escape') closeCard();
  });
  await draw();
}

let dictLang = 'es', dictDir = 'from', dictQ = '';
const DICT_HINT = { es: 'Busca una palabra: casas, dímelo, cúrale…', zh: 'Characters or pinyin: 学习, xuéxí, xue2xi2, xuexi…',
  ja: 'Kanji, kana or rōmaji: 食べました, たべる, taberu…' };
const DICT_SIZE = { es: 'About 85,000 Spanish words with their forms, plus your own entries. ',
  zh: 'About 125,000 CC-CEDICT entries, simplified and traditional, plus your own entries. ',
  ja: 'About 210,000 JMdict entries with their conjugations, plus your own entries. ' };
function renderDict() {
  const { esc } = C;
  const name = LANG_NAME[dictLang] || dictLang;
  C.view.innerHTML = `${tabs('dict')}
    <section class="panel"><div class="row" style="margin-bottom:10px">${langPicker('d-lang', dictLang)}<div class="tabs seg" style="margin:0">
      <button data-dir="from" class="${dictDir === 'from' ? 'on' : ''}">${esc(name)} → English</button><button data-dir="en" class="${dictDir === 'en' ? 'on' : ''}">English → ${esc(name)}</button></div></div>
      <input type="text" id="dq" value="${esc(dictQ)}" autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="Search the dictionary"
        placeholder="${dictDir === 'from' ? (DICT_HINT[dictLang] || 'Search a word') : 'Search the English meanings: house, to heal…'}">
      <div id="dr" class="dres"></div>
      <p class="dim tiny" id="d-credit" style="margin:10px 0 0">${esc(DICT_SIZE[dictLang] || '')}</p></section>
    <section class="panel"><h2>Add your own entry</h2><p class="dim small">For a word the dictionary lacks, or a meaning you prefer. Yours is shown first.</p>
      <form class="row" id="da"><input type="text" id="da-w" maxlength="40" placeholder="${esc(name)} word" autocomplete="off" style="flex:1 1 140px;width:auto">
      <input type="text" id="da-m" maxlength="200" placeholder="English meaning" autocomplete="off" style="flex:2 1 200px;width:auto"><button class="btn primary" type="submit">Add</button></form></section>`;
  bindTabs();
  const lp = $('#d-lang'); if (lp) lp.onchange = () => { dictLang = lp.value; dictQ = ''; renderDict(); };
  C.view.querySelectorAll('[data-dir]').forEach((b) => { b.onclick = () => { dictDir = b.dataset.dir; renderDict(); }; });
  let t = null, seq = 0;
  const credit = $('#d-credit'), base = credit.textContent;
  const run = async () => {
    const q = dictQ.trim(); const mine = ++seq;
    if (!q) { $('#dr').innerHTML = ''; return; }
    const r = await C.api(`/api/dict/search?lang=${encodeURIComponent(dictLang)}&q=${encodeURIComponent(q)}&dir=${dictDir}`);
    if (mine !== seq || !$('#dr')) return;
    if (r.ok === false) { $('#dr').innerHTML = `<p class="dim">${esc(r.error)}</p>`; return; }
    credit.textContent = base + (r.credit || '');
    $('#dr').innerHTML = r.results.length ? `<ul class="list">${r.results.map((x) => `<li><button class="dict-row" data-w="${esc(x.w)}"><b lang="${esc(dictLang)}">${esc(x.w)}</b>${x.read ? ` <span lang="${esc(dictLang)}">${esc(x.read)}</span>` : ''}${x.rom ? ` <i>${esc(x.rom)}</i>` : ''}
      ${x.src === 'mine' ? '<span class="tag jade">yours</span>' : ''}<span class="dim">${esc(String(x.en).slice(0, 160))}</span></button></li>`).join('')}</ul>`
      : '<p class="dim" style="margin:10px 0 0">No match. You can add it as your own entry below.</p>';
    $('#dr').querySelectorAll('[data-w]').forEach((b) => { b.onclick = () => showCard(b.dataset.w, dictLang); });
  };
  const inp = $('#dq');
  inp.oninput = () => { dictQ = inp.value; clearTimeout(t); t = setTimeout(run, 180); };
  inp.focus(); run();
  $('#da').onsubmit = async (e) => {
    e.preventDefault();
    const r = await C.api('/api/dict/entry', { lang: dictLang, word: $('#da-w').value, meaning: $('#da-m').value });
    if (r.ok === false) { C.toast(r.error); return; }
    cache.clear(); C.toast(`Added “${r.word}”.`); dictDir = 'from'; dictQ = r.word; renderDict();
  };
  C.setKeys((ev) => { if (ev.key === 'Escape') closeCard(); });
}

let wordsLang = 'es';
async function renderWords() {
  const { esc, num } = C;
  C.view.innerHTML = `${tabs('words')}<p class="loading">Gathering your words…</p>`;
  bindTabs();
  const r = await C.api(`/api/words?lang=${encodeURIComponent(wordsLang)}`);
  if (r.ok === false) { C.view.insertAdjacentHTML('beforeend', `<div class="panel">${esc(r.error)}</div>`); return; }
  const n = r.words.length, name = LANG_NAME[wordsLang] || wordsLang, canHear = !!voiceFor(wordsLang);
  C.view.innerHTML = `${tabs('words')}
    <section class="panel"><div class="row"><div class="grow" style="flex:1 1 260px"><div class="row"><h2>My words (${esc(name)})</h2>${langPicker('w-lang', wordsLang)}</div>
      <p class="dim small" style="margin:2px 0 0">${num(n)} saved. They are a course of their own: reviewed on the same schedule as everything else, and every answer pays qi and insight like any other study.${n && n < 4 ? ' Save a few more and the multiple-choice questions get real choices.' : ''}</p></div>
      ${n ? (r.enrolled ? `<a class="btn primary" href="/study?course=${encodeURIComponent(r.course)}" data-link>Study my words</a>`
    : '<button class="btn primary" id="mw-enrol">Add to my studies</button>') : ''}</div></section>
    <section class="panel">${n ? `<ul class="list">${r.words.map((w) => `<li class="row"><div class="grow"><b lang="${esc(wordsLang)}">${esc(w.word)}</b>${w.rom ? ` <i class="dim">${esc(w.rom)}</i>` : ''}
        <span class="tag ${w.state === 'mastered' ? 'jade' : w.state === 'learning' ? 'blue' : ''}">${esc(w.state)}${w.state !== 'new' ? ` ${num(w.strength)}%` : ''}</span>
        <div>${esc(w.l1)}</div>${w.ctx ? `<div class="dim small" lang="${esc(wordsLang)}">“${esc(w.ctx)}”</div>` : ''}</div>
        <button class="say tiny" data-say="${esc(w.word)}" aria-label="Hear ${esc(w.word)}" ${canHear ? '' : 'disabled'}>${C.ICON.sound}</button>
        <button class="btn quiet" data-del="${esc(w.word)}">Delete</button></li>`).join('')}</ul>`
    : '<p class="dim" style="margin:0">No saved words yet. Tap a word while reading, or look one up in the dictionary, and choose “Save word”.</p>'}
    ${n && !canHear ? `<p class="dim small" style="margin:10px 0 0">${esc(speechNote(wordsLang))}</p>` : ''}</section>`;
  bindTabs();
  const lp = $('#w-lang'); if (lp) lp.onchange = () => { wordsLang = lp.value; renderWords(); };
  const en = $('#mw-enrol');
  if (en) en.onclick = async () => { const res = await C.api('/api/enroll', { course: r.course, on: true }); if (res.ok === false) C.toast(res.error); else { C.toast(`My words (${name}) is now one of your courses.`); renderWords(); } };
  C.view.querySelectorAll('[data-say]').forEach((b) => { b.onclick = () => speak(b.dataset.say, wordsLang); });
  C.view.querySelectorAll('[data-del]').forEach((b) => {
    b.onclick = async () => {
      if (!confirm(`Delete “${b.dataset.del}” from My words? If you save it again later, its progress comes back.`)) return;
      const res = await C.api(`/api/words?lang=${encodeURIComponent(wordsLang)}&w=${encodeURIComponent(b.dataset.del)}`, undefined, 'DELETE');
      if (res.ok === false) C.toast(res.error); else { cache.clear(); renderWords(); }
    };
  });
}

/** Route /read: ?book=<id> opens a book, ?tab=dict|words, else the shelf. */
export async function renderRead(params, ctx) {
  C = ctx; card = null;
  await loadLangs();
  const book = params && params.get('book');
  if (book) return renderBook(book);
  const tab = params && params.get('tab');
  if (tab === 'dict') return renderDict();
  if (tab === 'words') return renderWords();
  return renderBooks();
}
