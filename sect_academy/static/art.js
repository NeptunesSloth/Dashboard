// Sect Academy artwork — every picture in the app is drawn here as vector art, so it can
// react to progress: halls appear when built and grow taller as they level up.
// Nothing in this file takes untrusted text: callers pass numbers, ids and known keys only.

const P = (n) => Math.round(n * 10) / 10;

/* Where each room sits on the mountain (viewBox 1000 x 700): cx, base y, footprint width, art height. */
export const SITES = {
  main_hall:   { x: 500, y: 250, w: 190, h: 170 },
  library:     { x: 245, y: 345, w: 130, h: 125 },
  fields:      { x: 755, y: 345, w: 150, h: 70 },
  ward:        { x: 500, y: 415, w: 130, h: 115 },
  dormitory:   { x: 150, y: 480, w: 150, h: 80 },
  market:      { x: 850, y: 480, w: 120, h: 110 },
  alchemy:     { x: 322, y: 540, w: 120, h: 95 },
  training:    { x: 500, y: 590, w: 150, h: 80 },
  storehouse:  { x: 678, y: 540, w: 120, h: 95 },
  spirit_vein: { x: 118, y: 640, w: 130, h: 95 },
  meditation:  { x: 882, y: 640, w: 130, h: 95 },
};

/** Hit-area of a room as percentages of the scene (for the HTML buttons laid over the art). */
export function siteRect(id) {
  const s = SITES[id]; if (!s) return [0, 0, 0, 0];
  const pad = 14;
  return [P((s.x - s.w / 2 - pad) / 10), P((s.y - s.h - pad) / 7), P((s.w + pad * 2) / 10), P((s.h + pad * 2 + 8) / 7)];
}

/* ---------------- building parts ---------------- */
const ROOFS = {
  gold:   { roof: 'var(--a-roof-gold)', trim: 'var(--a-trim-gold)' },
  blue:   { roof: 'var(--a-roof-blue)', trim: 'var(--a-trim-blue)' },
  sun:    { roof: 'var(--a-roof-sun)', trim: 'var(--a-trim-sun)' },
  jade:   { roof: 'var(--a-roof-jade)', trim: 'var(--a-trim-jade)' },
  slate:  { roof: 'var(--a-roof-slate)', trim: 'var(--a-trim-slate)' },
  plum:   { roof: 'var(--a-roof-plum)', trim: 'var(--a-trim-plum)' },
};

function roof(x, y, w, h, c) {
  const l = x - w / 2, r = x + w / 2;
  return `<path d="M${P(l - 13)} ${P(y)} Q${P(l + 8)} ${P(y - 2)} ${P(x - w * 0.2)} ${P(y - h)} L${P(x + w * 0.2)} ${P(y - h)} Q${P(r - 8)} ${P(y - 2)} ${P(r + 13)} ${P(y)} Q${P(x)} ${P(y + 10)} ${P(l - 13)} ${P(y)}Z" fill="${c.roof}"/>`
    + `<path d="M${P(l - 13)} ${P(y)} Q${P(x)} ${P(y + 10)} ${P(r + 13)} ${P(y)}" fill="none" stroke="${c.trim}" stroke-width="3.2" stroke-linecap="round"/>`
    + `<rect x="${P(x - w * 0.2 - 3)}" y="${P(y - h - 4)}" width="${P(w * 0.4 + 6)}" height="6" rx="3" fill="${c.trim}"/>`
    + `<circle cx="${P(l - 13)}" cy="${P(y - 1)}" r="3" fill="${c.trim}"/><circle cx="${P(r + 13)}" cy="${P(y - 1)}" r="3" fill="${c.trim}"/>`;
}

function storey(x, y, w, h, door) {
  const l = x - w / 2;
  let out = `<rect x="${P(l)}" y="${P(y - h)}" width="${P(w)}" height="${P(h)}" fill="var(--a-wall)"/>`
    + `<rect x="${P(l)}" y="${P(y - h)}" width="${P(w)}" height="${P(Math.min(6, h * 0.22))}" fill="var(--a-beam)"/>`;
  const n = w > 110 ? 5 : w > 70 ? 4 : 3;
  for (let i = 0; i < n; i++) {
    const px = l + (w - 6) * (i / (n - 1));
    out += `<rect x="${P(px)}" y="${P(y - h)}" width="6" height="${P(h)}" fill="var(--a-pillar)"/>`;
  }
  if (door) {
    const dw = Math.min(26, w * 0.2), dh = h * 0.72;
    out += `<path d="M${P(x - dw / 2)} ${P(y)} v${P(-dh + dw / 2)} a${P(dw / 2)} ${P(dw / 2)} 0 0 1 ${P(dw)} 0 v${P(dh - dw / 2)}Z" fill="var(--a-door)"/>`
      + `<circle cx="${P(x)}" cy="${P(y - dh * 0.45)}" r="${P(dw * 0.2)}" fill="var(--a-lamp)" class="lamp"/>`;
  } else {
    out += `<rect x="${P(x - w * 0.16)}" y="${P(y - h * 0.68)}" width="${P(w * 0.32)}" height="${P(h * 0.42)}" rx="3" fill="var(--a-window)"/>`;
  }
  return out;
}

/** A multi-tier hall. Its base sits on y; returns the SVG and the y of the top. */
function hall(x, y, w, tiers, c) {
  let out = `<rect x="${P(x - w / 2 - 8)}" y="${P(y - 5)}" width="${P(w + 16)}" height="7" rx="3" fill="var(--a-stone)"/>`;
  let cy = y - 5, cw = w;
  for (let i = 0; i < tiers; i++) {
    const h = i === 0 ? Math.max(26, cw * 0.27) : Math.max(14, cw * 0.19);
    out += storey(x, cy, cw, h, i === 0);
    cy -= h;
    const rh = Math.max(12, cw * 0.19);
    out += roof(x, cy, cw + 12, rh, c);
    cy -= rh * 0.72;
    cw *= 0.7;
  }
  out += `<path d="M${P(x)} ${P(cy - 2)} v-12" stroke="${c.trim}" stroke-width="3" stroke-linecap="round"/><circle cx="${P(x)}" cy="${P(cy - 16)}" r="4" fill="${c.trim}"/>`;
  return { svg: out, top: cy - 20 };
}

function terrace(x, y, w) {
  const rx = w * 0.62 + 16;
  return `<path d="M${P(x - rx)} ${P(y + 2)} Q${P(x - rx * 0.7)} ${P(y + 46)} ${P(x - rx * 0.2)} ${P(y + 52)} Q${P(x)} ${P(y + 62)} ${P(x + rx * 0.25)} ${P(y + 50)} Q${P(x + rx * 0.75)} ${P(y + 42)} ${P(x + rx)} ${P(y + 2)}Z" fill="var(--a-rock)"/>`
    + `<path d="M${P(x - rx * 0.55)} ${P(y + 20)} q10 14 6 26 M${P(x + rx * 0.4)} ${P(y + 16)} q-6 14 2 26" stroke="var(--a-rock-d)" stroke-width="3" fill="none" stroke-linecap="round" opacity=".6"/>`
    + `<ellipse cx="${P(x)}" cy="${P(y + 2)}" rx="${P(rx)}" ry="15" fill="var(--a-grass)"/>`
    + `<ellipse cx="${P(x)}" cy="${P(y)}" rx="${P(rx - 8)}" ry="10" fill="var(--a-grass-l)"/>`;
}

function plot(x, y, w) {
  // An unbuilt site: a marked-out foundation and a little signpost.
  return `<rect x="${P(x - w * 0.36)}" y="${P(y - 30)}" width="${P(w * 0.72)}" height="28" rx="5" fill="none" stroke="var(--a-plot)" stroke-width="3" stroke-dasharray="7 7"/>`
    + `<path d="M${P(x)} ${P(y - 3)} v-34" stroke="var(--a-wood)" stroke-width="4" stroke-linecap="round"/>`
    + `<rect x="${P(x - 17)}" y="${P(y - 52)}" width="34" height="20" rx="4" fill="var(--a-sign)" stroke="var(--a-wood)" stroke-width="2.5"/>`
    + `<path d="M${P(x - 7)} ${P(y - 42)} h14 M${P(x)} ${P(y - 49)} v14" stroke="var(--a-wood)" stroke-width="3" stroke-linecap="round"/>`;
}

function pine(x, y, s = 1) {
  return `<rect x="${P(x - 2 * s)}" y="${P(y - 8 * s)}" width="${P(4 * s)}" height="${P(9 * s)}" fill="var(--a-wood)"/>`
    + [0, 1, 2].map((i) => `<path d="M${P(x - (15 - i * 4) * s)} ${P(y - (6 + i * 11) * s)} L${P(x)} ${P(y - (26 + i * 11) * s)} L${P(x + (15 - i * 4) * s)} ${P(y - (6 + i * 11) * s)}Z" fill="var(--a-pine${i % 2 ? '-l' : ''})"/>`).join('');
}

function blossom(x, y, s = 1) {
  const puffs = [[-18, -34, 15], [0, -46, 18], [19, -36, 15], [-8, -28, 13], [10, -26, 13]];
  return `<path d="M${P(x)} ${P(y)} q-3 -16 0 -30 M${P(x)} ${P(y - 18)} q-8 -6 -14 -12 M${P(x)} ${P(y - 20)} q8 -6 15 -12" stroke="var(--a-wood)" stroke-width="${P(4 * s)}" fill="none" stroke-linecap="round"/>`
    + puffs.map(([dx, dy, r], i) => `<circle cx="${P(x + dx * s)}" cy="${P(y + dy * s)}" r="${P(r * s)}" fill="var(--a-blossom${i % 2 ? '-l' : ''})"/>`).join('');
}

function flag(x, y, h, color) {
  return `<path d="M${P(x)} ${P(y)} v${P(-h)}" stroke="var(--a-wood)" stroke-width="3.5" stroke-linecap="round"/>`
    + `<path class="flag" d="M${P(x + 2)} ${P(y - h + 2)} q14 4 26 0 v20 q-12 4 -26 0Z" fill="${color}"/>`;
}

function person(x, y, robe, skin = 'var(--a-skin)') {
  return `<g class="walker"><ellipse cx="${P(x)}" cy="${P(y)}" rx="8" ry="2.5" fill="#000" opacity=".16"/>`
    + `<path d="M${P(x - 7)} ${P(y)} q-1 -13 7 -15 q8 2 7 15Z" fill="${robe}"/>`
    + `<circle cx="${P(x)}" cy="${P(y - 19)}" r="6.5" fill="${skin}"/>`
    + `<path d="M${P(x - 6.5)} ${P(y - 20)} a6.5 6.5 0 0 1 13 0 q-6 -4 -13 0Z" fill="var(--a-hair)"/><circle cx="${P(x)}" cy="${P(y - 27)}" r="3" fill="var(--a-hair)"/></g>`;
}

/* ---------------- one drawing per room ---------------- */
const ROBES = ['var(--a-robe1)', 'var(--a-robe2)', 'var(--a-robe3)', 'var(--a-robe4)'];

function scaffold(x, y, w) {
  return `<g class="scaffold"><path d="M${P(x - w * 0.3)} ${P(y - 2)} v-44 M${P(x + w * 0.3)} ${P(y - 2)} v-44 M${P(x - w * 0.3)} ${P(y - 22)} h${P(w * 0.6)} M${P(x - w * 0.3)} ${P(y - 44)} h${P(w * 0.6)} M${P(x - w * 0.3)} ${P(y - 2)} l${P(w * 0.6)} -42" stroke="var(--a-wood)" stroke-width="3.5" fill="none" stroke-linecap="round"/></g>`;
}

function drawRoom(id, level, extra, building) {
  const s = SITES[id]; const { x, y, w } = s;
  let out = terrace(x, y, w);
  if (!level) return out + plot(x, y, w) + (building ? scaffold(x, y, w) : '');
  const tiersFor = (lv, step, max) => Math.min(max, 1 + Math.floor(lv / step));
  if (id === 'main_hall') {
    const b = hall(x, y, 150, Math.min(4, 1 + level), ROOFS.gold);
    out += blossom(x + 112, y + 2, 1.05) + b.svg + flag(x - 96, y, 62, 'var(--a-banner)') + pine(x - 118, y + 4, 0.9);
  } else if (id === 'library' || id === 'ward') {
    if (id === 'ward') {
      out += `<ellipse class="ward" cx="${x}" cy="${y + 3}" rx="${w * 0.6}" ry="9" fill="none" stroke="var(--a-glow)" stroke-width="3" stroke-dasharray="4 8"/>`;
    }
    out += hall(x, y, 104, Math.min(4, Math.ceil(level / 1.5)), id === 'library' ? ROOFS.blue : ROOFS.jade).svg;
    out += id === 'ward' ? '' : pine(x - 72, y + 3, 0.8);
  } else if (id === 'fields') {
    // rice terraces: stepped paddies, more of them as the fields grow
    const rows = Math.min(4, 1 + Math.floor((level + 1) / 2));
    for (let i = 0; i < rows; i++) {
      const ry = y - 6 - i * 15, rw = 66 - i * 9;
      out += `<path d="M${P(x - rw)} ${P(ry)} q${P(rw)} ${-9 - i} ${P(rw * 2)} 0 q${P(-rw)} 9 ${P(-rw * 2)} 0Z" fill="var(--a-paddy)"/>`
        + `<path d="M${P(x - rw + 8)} ${P(ry - 1)} q${P(rw - 8)} -6 ${P(rw * 2 - 16)} 0" fill="none" stroke="var(--a-rice)" stroke-width="3" stroke-dasharray="2 5" stroke-linecap="round"/>`;
    }
    out += hall(x + 50, y - 2, 34, 1, ROOFS.sun).svg;
  } else if (id === 'dormitory') {
    const n = Math.min(3, 1 + Math.floor(level / 2));
    for (let i = 0; i < n; i++) out += hall(x - 46 + i * 46, y + (i % 2 ? 2 : 0), 40, 1, ROOFS.slate).svg;
  } else if (id === 'market') {
    out += hall(x - 8, y, 86, tiersFor(level, 3, 2), ROOFS.plum).svg + flag(x + 46, y, 78, 'var(--a-banner)');
  } else if (id === 'alchemy') {
    out += hall(x - 14, y, 78, tiersFor(level, 3, 2), ROOFS.jade).svg
      + `<path d="M${x + 30} ${y - 4} q-4 -22 12 -22 q16 0 12 22Z" fill="var(--a-cauldron)"/><rect x="${x + 27}" y="${y - 6}" width="30" height="5" rx="2" fill="var(--a-stone)"/>`
      + `<ellipse cx="${x + 42}" cy="${y - 26}" rx="11" ry="4" fill="var(--a-glow)" opacity=".85"/>`
      + [0, 1, 2].map((i) => `<circle class="smoke s${i}" cx="${x + 42}" cy="${y - 36}" r="${5 + i * 2}" fill="var(--a-smoke)"/>`).join('');
  } else if (id === 'training') {
    out += `<ellipse cx="${x}" cy="${y - 6}" rx="62" ry="17" fill="var(--a-stone)"/><ellipse cx="${x}" cy="${y - 10}" rx="56" ry="14" fill="var(--a-arena)"/>`
      + `<ellipse cx="${x}" cy="${y - 10}" rx="30" ry="7.5" fill="none" stroke="var(--a-banner)" stroke-width="3"/>`
      + `<path d="M${x - 30} ${y - 10} a15 3.75 0 0 0 30 0 a15 3.75 0 0 1 30 0" fill="none" stroke="var(--a-banner)" stroke-width="2.5"/>`
      + flag(x - 66, y - 4, 48, 'var(--a-banner)') + flag(x + 62, y - 4, 48, 'var(--a-banner)');
    for (let i = 0; i < Math.min(4, level - 1); i++) out += `<circle cx="${x - 36 + i * 24}" cy="${y - 30}" r="4.5" fill="var(--a-lamp)" class="lamp"/>`;
  } else if (id === 'storehouse') {
    out += hall(x - 12, y, 82, tiersFor(level, 4, 2), ROOFS.gold).svg;
    const n = Math.min(6, 1 + Math.floor(level * 0.75));
    for (let i = 0; i < n; i++) out += `<rect x="${P(x + 30 + (i % 3) * 11 - Math.floor(i / 3) * 5)}" y="${P(y - 10 - Math.floor(i / 3) * 7)}" width="13" height="7" rx="2" fill="var(--a-ingot)" stroke="var(--a-trim-gold)" stroke-width="1.5"/>`;
  } else if (id === 'spirit_vein') {
    const n = Math.min(6, 2 + Math.floor(level / 2));
    out += `<ellipse class="veinglow" cx="${x}" cy="${y - 6}" rx="${40 + n * 4}" ry="18" fill="var(--a-glow)" opacity=".35"/>`;
    const shards = [[0, 62, 15], [-24, 42, 12], [24, 46, 12], [-44, 26, 9], [44, 30, 9], [8, 34, 9]];
    for (let i = 0; i < n; i++) {
      const [dx, h, hw] = shards[i];
      out += `<path d="M${x + dx - hw} ${y - 4} L${x + dx - hw * 0.5} ${y - h * 0.75} L${x + dx} ${y - h} L${x + dx + hw * 0.5} ${y - h * 0.75} L${x + dx + hw} ${y - 4}Z" fill="var(--a-crystal)"/>`
        + `<path d="M${x + dx} ${y - h} L${x + dx + hw * 0.5} ${y - h * 0.75} L${x + dx + hw} ${y - 4} L${x + dx} ${y - 4}Z" fill="var(--a-crystal-d)"/>`;
    }
  } else if (id === 'meditation') {
    out += `<ellipse cx="${x + 34}" cy="${y + 2}" rx="26" ry="7" fill="var(--a-water)"/>`
      + `<rect x="${x - 46}" y="${y - 6}" width="74" height="6" rx="3" fill="var(--a-stone)"/>`
      + [-40, -16, 8, 22].map((dx) => `<rect x="${x + dx}" y="${y - 44}" width="5" height="39" fill="var(--a-pillar)"/>`).join('')
      + roof(x - 9, y - 44, 84, 20, ROOFS.plum)
      + `<ellipse cx="${x - 9}" cy="${y - 8}" rx="13" ry="4" fill="var(--a-banner)"/>`
      + blossom(x + 52, y, 0.6);
    for (let i = 0; i < Math.min(3, Math.floor(level / 3)); i++) out += `<circle cx="${x - 30 + i * 21}" cy="${y - 50}" r="4" fill="var(--a-lamp)" class="lamp"/>`;
  }
  // disciples posted to this room stand outside it
  if (building && level) out += scaffold(x + w * 0.1, y, w * 0.8);
  (extra || []).slice(0, 4).forEach((robeIdx, i) => { out += person(x - w * 0.42 + i * 17, y + 6, ROBES[robeIdx % ROBES.length]); });
  return out;
}

/**
 * The whole sect, drawn for the current state.
 * rooms: [{id, level}]  staff: {roomId: [robeIndex, …]}  building: [roomId under construction]
 */
export function sectScene(rooms, staff = {}, building = []) {
  const cloud = (x, y, s, cls) => `<g class="cloud ${cls}" transform="translate(${x} ${y}) scale(${s})"><ellipse cx="0" cy="0" rx="46" ry="15"/><ellipse cx="-22" cy="-9" rx="22" ry="15"/><ellipse cx="14" cy="-14" rx="26" ry="18"/></g>`;
  const order = ['main_hall', 'library', 'fields', 'ward', 'dormitory', 'market', 'alchemy', 'storehouse', 'training', 'spirit_vein', 'meditation'];
  const level = Object.fromEntries(rooms.map((r) => [r.id, Number(r.level) || 0]));
  const steps = (x1, y1, x2, y2) => `<path d="M${x1} ${y1} Q${(x1 + x2) / 2 + 18} ${(y1 + y2) / 2} ${x2} ${y2}" class="steps"/>`;
  return `<svg class="art" viewBox="0 0 1000 700" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Your sect on its mountain: halls appear here as you build them">
  <defs>
    <linearGradient id="a-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--a-sky1)"/><stop offset=".62" style="stop-color:var(--a-sky2)"/><stop offset="1" style="stop-color:var(--a-sky3)"/></linearGradient>
    <linearGradient id="a-mount" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--a-mount1)"/><stop offset="1" style="stop-color:var(--a-mount2)"/></linearGradient>
  </defs>
  <rect width="1000" height="700" fill="url(#a-sky)"/>
  <circle class="sun" cx="800" cy="112" r="48"/><circle class="sun halo" cx="800" cy="112" r="78"/>
  <g class="stars">${[[90, 60], [210, 110], [330, 50], [470, 90], [610, 40], [700, 150], [930, 70], [150, 170], [560, 150]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2"/>`).join('')}</g>
  ${cloud(170, 110, 1.2, 'c1')}${cloud(620, 80, 0.9, 'c2')}${cloud(930, 190, 1.1, 'c3')}
  <path d="M0 330 Q90 215 180 285 Q250 190 345 275 Q400 235 450 300 L450 700 L0 700Z" fill="var(--a-far)"/>
  <path d="M560 310 Q640 205 730 280 Q820 180 905 262 Q960 225 1000 262 L1000 700 L560 700Z" fill="var(--a-far)"/>
  <path d="M0 400 Q120 320 240 380 Q330 330 420 395 L420 700 L0 700Z" fill="var(--a-mid)"/>
  <path d="M590 395 Q700 320 800 372 Q900 325 1000 380 L1000 700 L590 700Z" fill="var(--a-mid)"/>
  <rect class="mist" x="-40" y="352" width="1080" height="34" rx="17"/>
  <path d="M500 96 Q580 150 640 250 Q760 300 850 400 Q950 480 1000 560 L1000 700 L0 700 L0 560 Q60 470 160 400 Q250 300 360 250 Q420 150 500 96Z" fill="url(#a-mount)"/>
  <path d="M500 96 Q470 150 455 215 Q500 190 520 228 Q545 170 500 96Z" fill="var(--a-snow)"/>
  
  <path class="fall" d="M52 500 q8 60 0 150 h16 q8 -90 0 -150Z"/>
  ${steps(500, 668, 500, 600)}${steps(500, 570, 500, 425)}${steps(500, 380, 500, 262)}
  ${steps(470, 410, 300, 350)}${steps(530, 410, 700, 350)}${steps(455, 585, 345, 548)}${steps(545, 585, 655, 548)}
  ${steps(300, 536, 190, 488)}${steps(700, 536, 810, 488)}${steps(180, 492, 135, 620)}${steps(820, 492, 868, 620)}
  ${pine(60, 470, 1.1)}${pine(940, 452, 1.1)}${pine(395, 490, 0.9)}${pine(610, 492, 0.9)}${pine(232, 610, 1)}${pine(770, 612, 1)}${pine(410, 652, 1.1)}${pine(592, 654, 1.1)}
  ${order.map((id) => `<g class="bld ${level[id] ? 'built' : 'empty'}" data-art="${id}">${drawRoom(id, level[id], staff[id], building.includes(id))}</g>`).join('')}
  <g class="gate"><rect x="446" y="640" width="9" height="50" rx="3" fill="var(--a-pillar)"/><rect x="545" y="640" width="9" height="50" rx="3" fill="var(--a-pillar)"/>
    ${roof(500, 646, 118, 16, ROOFS.gold)}<rect x="458" y="650" width="84" height="15" rx="3" fill="var(--a-banner)"/></g>
  <rect class="mist low" x="-40" y="676" width="1080" height="40" rx="20"/>
</svg>`;
}

/* ---------------- characters ---------------- */
function hash(str) { let h = 2166136261; for (const ch of String(str)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619) >>> 0; } return h; }
const SKINS = ['#f6d3b3', '#eec39a', '#dba77c', '#c68a5e', '#f9dcc4'];
const HAIRS = ['#2b2433', '#3d2b22', '#5a3a2a', '#1d2a3d', '#6b4a8a', '#8b8f9c'];
const ROBE_BY_ROOT = { Common: ['#7d93b3', '#5b7397'], Good: ['#3fbf8f', '#22946a'], Superior: ['#4aa3ff', '#2577d6'], 'Heaven Grade': ['#ffc233', '#d99a00'], 'Saint Grade': ['#a78bfa', '#7c5ce0'] };

/**
 * A round portrait. seed picks the look; root picks the robe colour; mood: 'calm' | 'happy' | 'oops' | 'think'.
 * kind 'elder' draws the white-bearded guide.
 */
export function portrait(seed, { root = 'Common', mood = 'calm', kind = '', size = 48 } = {}) {
  const h = hash(seed); const elder = kind === 'elder';
  const skin = SKINS[h % SKINS.length]; const hair = elder ? '#eef0f4' : HAIRS[(h >> 3) % HAIRS.length];
  const [robe, robeD] = elder ? ['#f3ead8', '#d9c9a6'] : (ROBE_BY_ROOT[root] || ROBE_BY_ROOT.Common);
  const style = (h >> 7) % 4;
  const eyes = mood === 'happy' ? '<path d="M22 31 q3 -4 6 0 M36 31 q3 -4 6 0" stroke="#2b2433" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
    : mood === 'oops' ? '<circle cx="25" cy="31" r="2.6" fill="#2b2433"/><circle cx="39" cy="31" r="2.6" fill="#2b2433"/><path d="M21 25 l7 2 M43 25 l-7 2" stroke="#2b2433" stroke-width="2" stroke-linecap="round"/>'
      : '<circle cx="25" cy="31" r="2.4" fill="#2b2433"/><circle cx="39" cy="31" r="2.4" fill="#2b2433"/>';
  const mouth = mood === 'happy' ? '<path d="M26 37 q6 7 12 0Z" fill="#b5483f"/>' : mood === 'oops' ? '<ellipse cx="32" cy="39" rx="3" ry="2.4" fill="#b5483f"/>'
    : mood === 'think' ? '<path d="M28 39 h8" stroke="#b5483f" stroke-width="2.2" stroke-linecap="round"/>' : '<path d="M27 38 q5 4 10 0" stroke="#b5483f" stroke-width="2.2" fill="none" stroke-linecap="round"/>';
  const hairBack = style === 1 || elder ? `<path d="M15 30 q-3 18 3 26 h28 q6 -8 3 -26Z" fill="${hair}"/>` : '';
  const hairTop = style === 2 ? `<path d="M15 31 q-1 -20 17 -20 q18 0 17 20 q-4 -11 -17 -11 q-13 0 -17 11Z" fill="${hair}"/><path d="M46 20 q10 4 8 18 q-5 -7 -9 -8Z" fill="${hair}"/>`
    : `<path d="M15 31 q-1 -20 17 -20 q18 0 17 20 q-6 -9 -17 -9 q-11 0 -17 9Z" fill="${hair}"/><circle cx="32" cy="9" r="6" fill="${hair}"/><rect x="26" y="12" width="12" height="3.5" rx="1.75" fill="${elder ? '#d9a400' : robeD}"/>`;
  const beard = elder ? '<path d="M22 38 q10 22 20 0 q-2 8 -10 8 q-8 0 -10 -8Z" fill="#eef0f4"/><path d="M19 26 q5 -3 9 0 M36 26 q4 -3 9 0" stroke="#eef0f4" stroke-width="3" stroke-linecap="round" fill="none"/>' : '';
  return `<svg class="face" width="${size}" height="${size}" viewBox="0 0 64 64" aria-hidden="true">
    <circle cx="32" cy="32" r="32" fill="${elder ? '#ffe7a8' : 'var(--face-bg)'}"/>
    <clipPath id="fc${h}"><circle cx="32" cy="32" r="32"/></clipPath>
    <g clip-path="url(#fc${h})">${hairBack}
      <path d="M8 66 q2 -20 24 -20 q22 0 24 20Z" fill="${robe}"/><path d="M26 47 l6 9 l6 -9" fill="none" stroke="${robeD}" stroke-width="3" stroke-linejoin="round"/>
      <circle cx="32" cy="31" r="15" fill="${skin}"/><circle cx="20.5" cy="36" r="3" fill="#ff9a8a" opacity=".45"/><circle cx="43.5" cy="36" r="3" fill="#ff9a8a" opacity=".45"/>
      ${hairTop}${eyes}${elder ? '' : mouth}${beard}</g></svg>`;
}

/* ---------------- icons (one visual language for the whole app) ---------------- */
const I = (d, extra = '') => `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true" ${extra}>${d}</svg>`;
export const ICON = {
  sect: I('<path d="M3 10.5 12 4l9 6.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M6 10.5V20h12v-9.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/><path d="M10 20v-5h4v5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/>'),
  study: I('<path d="M4 5.5c2.5-1 5.5-1 8 .5 2.5-1.5 5.5-1.5 8-.5v13c-2.5-1-5.5-1-8 .5-2.5-1.5-5.5-1.5-8-.5z" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/><path d="M12 6v13" stroke="currentColor" stroke-width="2.2"/>'),
  library: I('<rect x="4" y="4" width="4.5" height="16" rx="1.2" fill="none" stroke="currentColor" stroke-width="2.2"/><rect x="10" y="4" width="4.5" height="16" rx="1.2" fill="none" stroke="currentColor" stroke-width="2.2"/><path d="m16.5 7 3.3-1 3 11.5-3.3 1z" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" transform="translate(-2 1)"/>'),
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
