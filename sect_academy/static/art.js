// Sect Academy artwork. The sect and its people are painted images shipped with the app
// (static/art/*.webp, served from this origin so the app stays fully offline); this module
// places them and lays the live state over them.
// Nothing in this file takes untrusted text: callers pass numbers, ids and known keys only.

/* Where each room sits in the painted cut-away of the sect (percent of the picture): x, y, w, h. */
export const SITES = {
  dormitory:   [2, 3, 31, 19],
  main_hall:   [34, 3, 22, 19],
  fields:      [57, 3, 41, 19],
  market:      [2, 24.5, 96, 14.5],
  storehouse:  [3, 41, 31, 16.5],
  library:     [35, 41, 30, 16.5],
  ward:        [66, 41, 32, 16.5],
  alchemy:     [3, 59, 31, 16.5],
  training:    [35, 59, 30, 16.5],
  spirit_vein: [3, 77.5, 40, 20],
  meditation:  [44, 77.5, 54, 20],
};
export const VAULT = [66, 59, 32, 16.5];        // the treasure vault: opens the World tab

export function siteRect(id) { return SITES[id] || [0, 0, 0, 0]; }

/** A crop of the painted sect centred on one room, as inline CSS for a tile of the given aspect (width / height).
 *  Numbers only: the id picks a known site, anything else gets the middle of the painting. */
export function siteCrop(id, aspect = 1.5) {
  const [x, y, w, h] = SITES[id] || [30, 30, 40, 40];
  const art = 1620 / 971;                              // the painting's own aspect
  const scale = Math.max(100 / Math.max(w, 1), (100 * art) / (aspect * Math.max(h, 1)));   // the room covers the tile: the painting is this many tiles wide
  const imgH = scale / art * aspect;                   // and this many tiles tall
  const cx = (x + w / 2) / 100; const cy = (y + h / 2) / 100;
  const px = scale > 1 ? Math.max(0, Math.min(100, ((scale * cx - 0.5) / (scale - 1)) * 100)) : 50;
  const py = imgH > 1 ? Math.max(0, Math.min(100, ((imgH * cy - 0.5) / (imgH - 1)) * 100)) : 50;
  return `background-image:url(/art/hq.webp);background-size:${(scale * 100).toFixed(1)}% auto;background-position:${px.toFixed(1)}% ${py.toFixed(1)}%`;
}

/** The sect itself: one painting; the page lays rooms, crews and veils over it. */
export function sectScene() {
  return '<img class="art" src="/art/hq.webp" alt="A cut-away painting of your sect: five lantern-lit floors of halls" draggable="false">';
}

const BACKDROPS = new Set(['map', 'seclusion', 'technique', 'treasure', 'leader', 'hall', 'pill', 'mission']);
/** A painted backdrop by known name (falls back to the mountain). */
export function backdrop(name) { return `/art/bg_${BACKDROPS.has(name) ? name : 'map'}.webp`; }

/* Result scenes: each kind has its own painting (static/art/scene_<kind>.webp) once one is painted.
   The server says whether that file exists (scene.painted), so a missing picture is never requested;
   until then the closest backdrop stands in. */
const SCENE_FALLBACK = { raid: 'map', tournament: 'technique', festival: 'hall', funeral: 'leader', tribulation: 'seclusion', breakthrough: 'seclusion', realm: 'treasure',
  sickness: 'pill', blight: 'map', infiltrator: 'leader', theft: 'treasure', incident: 'pill',
  festival_spring: 'hall', festival_moon: 'hall', festival_ghost: 'hall', festival_winter: 'hall' };
/** The backdrop for a result scene of a known kind. */
export function scene(kind, painted = false) {
  if (!Object.prototype.hasOwnProperty.call(SCENE_FALLBACK, kind)) return backdrop('hall');
  return painted === true ? `/art/scene_${kind}.webp` : backdrop(SCENE_FALLBACK[kind]);
}

/* ---------------- characters ---------------- */
function hash(str) { let h = 2166136261; for (const ch of String(str)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619) >>> 0; } return h; }
let FACES = ['disciple', 'analyst', 'architect', 'engineer', 'researcher', 'trader'];
/** The server lists the disciple faces that exist (static/art/p_<name>.webp); known-safe names only. */
export function setFaces(list) {
  const ok = Array.isArray(list) ? list.filter((n) => typeof n === 'string' && /^[a-z0-9_]{1,24}$/.test(n)) : [];
  if (ok.length) FACES = ok;
}
const RING = { Common: 'r0', Good: 'r1', Superior: 'r2', 'Heaven Grade': 'r3', 'Saint Grade': 'r4', 'Heaven-Defying': 'r4', Crippled: 'r0' };

/**
 * A round painted portrait. seed picks the face; root picks the ring colour;
 * kind: 'elder' (the guide) | 'master' (you). mood: 'calm' | 'happy' | 'oops' | 'think'.
 */
export function portrait(seed, { root = 'Common', mood = 'calm', kind = '', size = 48 } = {}) {
  const who = kind === 'elder' ? 'elder' : kind === 'master' ? 'leader' : FACES[hash(seed) % FACES.length];
  const px = Math.max(16, Math.min(256, Number(size) || 48));
  const m = ['calm', 'happy', 'oops', 'think'].includes(mood) ? mood : 'calm';
  return `<img class="face ${RING[root] || 'r0'} m-${m}" src="/art/p_${who}.webp" width="${px}" height="${px}" alt="" draggable="false">`;
}

/* ---------------- icons (one visual language for the whole app) ---------------- */
const I = (d, extra = '') => `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true" ${extra}>${d}</svg>`;
export const ICON = {
  sect: I('<path d="M3 10.5 12 4l9 6.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M6 10.5V20h12v-9.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/><path d="M10 20v-5h4v5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/>'),
  study: I('<path d="M4 5.5c2.5-1 5.5-1 8 .5 2.5-1.5 5.5-1.5 8-.5v13c-2.5-1-5.5-1-8 .5-2.5-1.5-5.5-1.5-8-.5z" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/><path d="M12 6v13" stroke="currentColor" stroke-width="2.2"/>'),
  library: I('<rect x="4" y="4" width="4.5" height="16" rx="1.2" fill="none" stroke="currentColor" stroke-width="2.2"/><rect x="10" y="4" width="4.5" height="16" rx="1.2" fill="none" stroke="currentColor" stroke-width="2.2"/><path d="m16.5 7 3.3-1 3 11.5-3.3 1z" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" transform="translate(-2 1)"/>'),
  read: I('<path d="M3 5.5h6a3 3 0 0 1 3 3V20a2.5 2.5 0 0 0-2.5-2.5H3z" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/><path d="M21 5.5h-6a3 3 0 0 0-3 3V20a2.5 2.5 0 0 1 2.5-2.5H21z" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/>'),
  trials: I('<path d="M13 2 5 13.5h6L10 22l9-12.5h-6z" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/>'),
  progress: I('<path d="M4 20V11M10 20V5M16 20v-7M22 20H2" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>'),
  flame: I('<path d="M12 2.5c1 3.5 5.5 5.6 5.5 11A5.5 5.5 0 0 1 12 19a5.500 5.500 0 0 1-5.500-5.500c0-2.300 1.200-3.800 2.300-5 .3 1.700 1.200 2.500 2 2.800C10.300 8 11 5 12 2.500z" fill="#ff8a1f"/><path d="M12 12c.800 1.500 2.300 2.200 2.300 4a2.300 2.300 0 0 1-4.600 0c0-1.500 1.300-2.300 2.300-4z" fill="#ffd34d"/>'),
  stone: I('<path d="M12 2.500 20 9l-3 11H7L4 9z" fill="#4fc3ff"/><path d="M12 2.500 20 9h-5.500z" fill="#a8e4ff"/><path d="M4 9h16l-3 11z" fill="#2796e0" opacity=".55"/>'),
  qi: I('<circle cx="12" cy="12" r="8.500" fill="#b79bff"/><path d="M12 3.500a8.500 8.500 0 0 1 0 17 4.250 4.250 0 0 1 0-8.500 4.250 4.250 0 0 0 0-8.500z" fill="#6d4be0"/><circle cx="12" cy="7.750" r="1.400" fill="#6d4be0"/><circle cx="12" cy="16.250" r="1.400" fill="#e5dbff"/>'),
  pill: I('<circle cx="12" cy="12" r="8" fill="#ff7d6b"/><path d="M6.500 9.500a6 6 0 0 1 5-3.500" stroke="#ffd0c8" stroke-width="2" fill="none" stroke-linecap="round"/>'),
  lock: I('<rect x="5" y="10.500" width="14" height="10" rx="2.500" fill="currentColor"/><path d="M8 10.500V8a4 4 0 0 1 8 0v2.500" fill="none" stroke="currentColor" stroke-width="2.400"/>'),
  check: I('<path d="m5 12.500 4.500 4.500L19 7.500" fill="none" stroke="currentColor" stroke-width="3.200" stroke-linecap="round" stroke-linejoin="round"/>'),
  sound: I('<path d="M4 9.500v5h3.500L12 18V6L7.500 9.500z" fill="currentColor"/><path d="M15 9a4 4 0 0 1 0 6M17.500 6.500a7.500 7.500 0 0 1 0 11" fill="none" stroke="currentColor" stroke-width="2.200" stroke-linecap="round"/>'),
  scroll: I('<path d="M7 4h10a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" fill="none" stroke="currentColor" stroke-width="2.200"/><path d="M9 9h6M9 13h6" stroke="currentColor" stroke-width="2.200" stroke-linecap="round"/>'),
  pause: I('<rect x="6" y="5" width="4.5" height="14" rx="1.5" fill="currentColor"/><rect x="13.5" y="5" width="4.5" height="14" rx="1.5" fill="currentColor"/>'),
  play: I('<path d="M7 4.5v15l12-7.5z" fill="currentColor"/>'),
  fleet: I('<circle cx="12" cy="12" r="3" fill="currentColor"/><circle cx="12" cy="12" r="8.500" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="3 4"/>'),
};
