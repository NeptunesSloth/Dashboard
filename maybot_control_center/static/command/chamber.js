import { $, api, post, esc, mountRail, initAccount, starfield, liveStream, debounce } from '/lib.js';

mountRail('disciples');
initAccount();
starfield('scene-canvas');

let ROWS = [];
let active = null;
let previewMode = false;
let CAN_MANAGE = false;

/* ====================================================================== *
 *  Deterministic character synthesis
 *  Most RPG fields (age, attributes, traits, relationships, equipment…)
 *  have no backend yet, so we synthesise stable, plausible values from the
 *  member's name and blend in the REAL data we do have (realm, role, skills,
 *  merit, tasks, chronicle). Same name => same character, every load.
 * ====================================================================== */
function hash(s) { let h = 2166136261; s = String(s); for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function rng(seed) { let a = seed >>> 0; return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const pick = (r, arr) => arr[Math.floor(r() * arr.length)];
const rint = (r, a, b) => a + Math.floor(r() * (b - a + 1));
const sample = (r, arr, n) => { const c = arr.slice(); const out = []; while (c.length && out.length < n) out.push(c.splice(Math.floor(r() * c.length), 1)[0]); return out; };

const REALMS = ['Mortal', 'Qi Gathering', 'Foundation Establishment', 'Core Formation', 'Nascent Soul', 'Soul Transformation', 'Ascendant', 'Immortal Ascension'];
const STAGES = ['Early Stage', 'Middle Stage', 'Late Stage', 'Peak Stage'];
const GRADES = ['F', 'E', 'D', 'C', 'B', 'A', 'S', 'SS', 'SSS', 'Heavenly', 'Immortal'];
const ATTRS = ['Strength', 'Agility', 'Endurance', 'Intelligence', 'Perception', 'Willpower', 'Charisma', 'Luck'];
const SKILL_POOL = ['Research', 'Alchemy', 'Trading', 'Diplomacy', 'Leadership', 'Swordsmanship', 'Formation Mastery', 'Crafting', 'Scouting', 'Teaching', 'Administration', 'Beast Taming', 'Talismancy'];
const SPECIALTIES = ['Pill Genius', 'Formation Savant', 'Born Merchant', 'Sword Prodigy', 'Beast Tamer', 'Spirit Farmer', 'Talisman Expert', 'Political Genius', 'Master Negotiator'];
const TRAITS_POS = ['Hardworking', 'Loyal', 'Disciplined', 'Curious', 'Brave', 'Patient', 'Wise', 'Charismatic', 'Perfectionist'];
const TRAITS_NEG = ['Lazy', 'Arrogant', 'Cowardly', 'Greedy', 'Impulsive', 'Jealous', 'Vindictive', 'Wasteful', 'Reckless'];
const TRAITS_NEU = ['Quiet', 'Bookworm', 'Dreamer', 'Competitive', 'Eccentric', 'Collector'];
const GOALS = ['Become Elder', 'Master the Sword Dao', 'Found a Personal Peak', 'Reach Nascent Soul', 'Create Legendary Pills', 'Become Sect Leader', 'Comprehend a Heavenly Dao', 'Forge an Immortal Artifact'];
const WEAPONS = [['Wooden Practice Sword', 0], ['Iron Saber', 1], ['Azure Cloud Sword', 3], ['Frostmoon Glaive', 2], ['Nine-Ring Blade', 2], ['Voidsplitter Spear', 4]];
const ARMORS = [['Cotton Robe', 0], ['Spirit Silk Robe', 2], ['Jade Scale Armor', 3], ['Cloudweave Vestment', 1], ['Dragonhide Mantle', 4]];
const ARTIFACTS = [['Minor Storage Ring', 1], ['Spirit Gathering Pearl', 2], ['Soul Lantern', 3], ['Heaven-Peering Mirror', 4], ['—', 0]];
const ACCESSORIES = [['Jade Pendant', 1], ['Beast-Bone Talisman', 2], ['Meridian Bracelet', 2], ['Luck Coin', 3], ['—', 0]];
const RARITY = ['common', 'uncommon', 'rare', 'epic', 'legendary'];
const HALLS = ['Research Hall', 'Alchemy Hall', 'Commerce Hall', 'Mission Hall', 'Martial Hall', 'Spirit Nexus', 'Sect Hall'];

function modelShort(model) {
  const m = String(model || '').toLowerCase();
  for (const k of ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gpt-4', 'gpt', 'llama3', 'llama', 'mistral', 'qwen', 'gemma', 'phi', 'mixtral', 'hermes', 'deepseek'])
    if (m.includes(k)) return k;
  return (m.split(/[-_/:]/)[0] || '?').slice(0, 7) || '?';
}
function portraitFor(a) {
  const g = a.governance || {}; const role = String(a.role || '').toLowerCase();
  if (g.is_leader) return 'leader';
  if (g.is_elder) return 'elder';
  if (/trad|market|invest|merchant/.test(role)) return 'trader';
  if (/eng|build|forge|deploy/.test(role)) return 'engineer';
  if (/research|scholar|study|scribe/.test(role)) return 'researcher';
  if (/analy|data|quant|strateg/.test(role)) return 'analyst';
  if (/architect|infra|ops|marshal/.test(role)) return 'architect';
  return 'disciple';
}

const TIERS = [
  { key: 'leader', label: 'Sect Leader', rank: 'Sect Leader' },
  { key: 'master', label: 'Sect Masters', rank: 'Sect Master' },
  { key: 'elder', label: 'Elders', rank: 'Elder' },
  { key: 'core', label: 'Core Disciples', rank: 'Core Disciple' },
  { key: 'inner', label: 'Inner Disciples', rank: 'Inner Disciple' },
  { key: 'outer', label: 'Outer Disciples', rank: 'Outer Disciple' },
];
function tierOf(a) {
  const g = a.governance || {}; const realm = (a.cultivation || {}).realm || 0;
  if (g.is_leader) return 'leader';
  if (g.is_master) return 'master';
  if (g.is_elder || realm >= 6) return 'elder';
  if (realm >= 4) return 'core';
  if (realm >= 2) return 'inner';
  return 'outer';
}

/* ---- Spirit Root system: the single most important talent mechanic ---- */
const ELEM = ['Fire', 'Water', 'Wood', 'Metal', 'Earth'];
const SPECIAL_ROOTS = ['Lightning', 'Wind', 'Ice', 'Shadow', 'Light', 'Blood', 'Beast', 'Soul', 'Dream', 'Star', 'Time', 'Space', 'Yin', 'Yang'];
const MYTHIC_ROOTS = ['Heavenly', 'Immortal', 'Chaos', 'Primordial', 'Dragon', 'Phoenix', 'Void', 'Dao'];
const ROOT_QUALITY = ['Trash', 'Common', 'Good', 'Superior', 'Earth Grade', 'Heaven Grade', 'Saint Grade', 'Immortal Grade', 'Dao Grade'];
const CONSTITUTIONS = ['Pure Yang Body', 'Pure Yin Body', 'Heavenly Sword Body', 'Nine Phoenix Body', 'Dragon Blood Body', 'Void Body', 'Saint Body', 'Starborn Physique', 'Chaos Physique'];
const MUTATIONS = { 'Fire|Wind': 'Lightning', 'Water|Wind': 'Ice', 'Shadow|Water': 'Moon', 'Fire|Light': 'Solar', 'Earth|Wood': 'Life' };

function decideTrope(c, willpower) {
  if (c.mythic && c.constitution) return "Heaven's Chosen";
  if (c.constitution === 'Heavenly Sword Body' && c.roots.includes('Metal') && c.roots.some((x) => /Lightning/.test(x))) return 'Sword Saint Candidate';
  if (c.purity >= 85 && c.comprehension >= 80 && c.constitution) return 'Heavenly Genius';
  if (c.roots.includes('Wood') && c.roots.includes('Fire')) return 'Alchemy Prodigy';
  if (c.hidden) return 'Hidden Dragon';
  if (['Trash', 'Common'].includes(c.quality) && willpower >= 80) return 'Trash Root Protagonist';
  if ((c.count >= 4 || c.purity < 35) && willpower >= 70) return 'Late Bloomer';
  if (c.purity >= 80 && c.comprehension >= 70) return 'Heavenly Genius';
  return 'Ordinary Disciple';
}
function rootBonuses(c) {
  const b = [];
  const spd = Math.round((c.purity - 50) / 2 + (c.mythic ? 30 : 0) + (c.perfectFive ? 20 : 0) + (c.mutated ? 15 : 0));
  if (spd) b.push(`${spd > 0 ? '+' : ''}${spd}% Cultivation Speed`);
  if (c.constitution === 'Heavenly Sword Body') b.push('+25% Sword Comprehension');
  if (c.roots.includes('Wood') && c.roots.includes('Fire')) b.push('+20% Alchemy');
  if (c.roots.some((x) => /Lightning/.test(x))) b.push('+15% Breakthrough Chance');
  if (c.trope === 'Late Bloomer') b.push('Scales hard in the higher realms');
  if (c.trope === 'Trash Root Protagonist') b.push('Slowly defies cultivation limits');
  return (b.length ? b : ['No notable bonuses yet']).slice(0, 4);
}
function sectReaction(potential) {
  if (['SS', 'SSS', 'Heavenly', 'Immortal'].includes(potential)) return 'The sect watches with admiration — and quiet jealousy. Elders compete to mentor them.';
  if (['S', 'A'].includes(potential)) return 'Seniors take note; mentorship offers may come.';
  if (['F', 'E', 'D'].includes(potential)) return 'Largely overlooked by the elders — underestimated for now.';
  return 'Regarded as a steady, unremarkable member.';
}
function spiritRoot(seed, comprehension, luck, willpower) {
  const r = rng((seed ^ 0x5c0ffee) >>> 0);
  let roots, count, mythic = false, perfectFive = false, mutated = null;
  const roll = r();
  if (roll < 0.04) { roots = [pick(r, MYTHIC_ROOTS)]; mythic = true; count = 1; }
  else if (roll < 0.10) { roots = ELEM.slice(); perfectFive = true; count = 5; }
  else {
    const cr = r();
    count = cr < 0.12 ? 1 : cr < 0.45 ? 2 : cr < 0.75 ? 3 : cr < 0.92 ? 4 : 5;
    roots = sample(r, r() < 0.65 ? ELEM : [...ELEM, ...SPECIAL_ROOTS], count);
  }
  if (count === 2) { const key = roots.slice().sort().join('|'); if (MUTATIONS[key] && r() < 0.6) { mutated = MUTATIONS[key]; roots = [mutated]; count = 1; } }
  const hidden = !mythic && r() < 0.06;
  let purity;
  if (perfectFive) purity = rint(r, 80, 99);
  else if (mythic || mutated) purity = rint(r, 60, 99);
  else purity = Math.max(3, Math.round(rint(r, 10, 95) * [1, 1, 0.9, 0.75, 0.6, 0.5][Math.min(5, count)]));
  purity = Math.max(1, Math.min(100, purity));
  let qIdx = Math.floor(purity / 100 * (ROOT_QUALITY.length - 2)) + (mythic ? 2 : 0) + (perfectFive || mutated ? 1 : 0);
  const quality = ROOT_QUALITY[Math.max(0, Math.min(ROOT_QUALITY.length - 1, qIdx))];
  const constitution = r() < 0.22 ? pick(r, CONSTITUTIONS) : null;
  const rootScore = mythic ? 95 : perfectFive ? 90 : mutated ? 80 : [70, 70, 55, 40, 28, 18][Math.min(5, count)];
  const potScore = Math.max(0, Math.min(110, rootScore * 0.45 + purity * 0.3 + comprehension * 0.15 + luck * 0.1 + (constitution ? 12 : 0)));
  const potential = GRADES[Math.min(GRADES.length - 1, Math.round(potScore / 100 * (GRADES.length - 1)))];
  const ctx = { roots, count, mythic, perfectFive, mutated, purity, quality, constitution, comprehension, hidden };
  const trope = decideTrope(ctx, willpower);
  return {
    roots, count, mythic, perfectFive, mutated, purity, quality, constitution, potential, trope, hidden,
    display: hidden ? 'Unknown Root' : roots.map((x) => x + ' Root').join(' + '),
    bonuses: rootBonuses({ ...ctx, trope }), reaction: sectReaction(potential),
    qIdx: Math.max(0, Math.min(ROOT_QUALITY.length - 1, qIdx)),
  };
}

function profile(a) {
  const seed = hash(a.name);
  const r = rng(seed);
  const cult = a.cultivation || {}, gov = a.governance || {}, rep = a.reputation || {}, sig = rep.signals || {};
  const tier = tierOf(a);
  const tierLabel = (TIERS.find((t) => t.key === tier) || {}).rank || 'Disciple';
  const realmIdx = Math.min(REALMS.length - 1, cult.realm != null ? cult.realm : rint(r, 0, 4));
  const realm = cult.realm_name || REALMS[realmIdx];
  const stage = cult.stage || pick(r, STAGES);
  const prog = cult.stones_to_next && cult.stones ? Math.min(99, Math.round((cult.stones / (cult.stones + cult.stones_to_next)) * 100)) : rint(r, 8, 96);
  const comprehension = rint(r, 25, 99);
  const qi = rint(r, 20, 99);
  const breakChance = Math.max(5, Math.min(98, Math.round(prog * 0.4 + comprehension * 0.4 + qi * 0.2 - rint(r, 0, 20))));
  const gradeIdx = Math.min(GRADES.length - 1, Math.max(0, Math.round(((comprehension + qi) / 2) / 100 * 8 + rint(r, -1, 2))));
  const attrs = ATTRS.map((name) => ({ name, val: rint(r, 18, 96) }));
  const luck = (attrs.find((x) => x.name === 'Luck') || {}).val || 50;
  const willpower = (attrs.find((x) => x.name === 'Willpower') || {}).val || 50;
  const root = spiritRoot(seed, comprehension, luck, willpower);
  const realSkills = (cult.skills || []).map(String);
  const skillNames = [...new Set([...realSkills, ...sample(r, SKILL_POOL, rint(r, 3, 6))])].slice(0, 8);
  const skills = skillNames.map((name) => { const lv = rint(r, 1, 24); return { name, lv, xp: rint(r, 5, 95) }; }).sort((x, y) => y.lv - x.lv);
  const specs = [gov.specialty, ...sample(r, SPECIALTIES, rint(r, 0, 2))].filter(Boolean);
  const traits = [...sample(r, TRAITS_POS, rint(r, 1, 3)).map((t) => ['pos', t]), ...sample(r, TRAITS_NEG, rint(r, 0, 2)).map((t) => ['neg', t]), ...sample(r, TRAITS_NEU, rint(r, 0, 2)).map((t) => ['neu', t])];
  const [wpn, wr] = pick(r, WEAPONS), [arm, ar] = pick(r, ARMORS), [art, atr] = pick(r, ARTIFACTS), [acc, acr] = pick(r, ACCESSORIES);
  const age = rint(r, 16, 22) + realmIdx * rint(r, 6, 14);
  const goal = pick(r, GOALS);
  return {
    name: a.name, model: a.model, role: a.role || 'Disciple', gender: pick(r, ['Male', 'Female']),
    age, rank: cult.rank_title || tierLabel, tier,
    assignment: (a.status === 'working' && a.current_task) ? a.current_task : pick(r, HALLS),
    realm, stage, prog, breakChance, comprehension, qi, grade: GRADES[gradeIdx],
    attrs, skills, specs, traits, goal, root,
    portrait: portraitFor(a),
    status: a.status || 'idle',
    equip: [['Weapon', wpn, RARITY[wr]], ['Armor', arm, RARITY[ar]], ['Artifact', art, RARITY[atr]], ['Accessory', acc, RARITY[acr]]],
    sect: {
      years: Math.max(1, Math.round(age / 4) - rint(r, 1, 4)),
      contribution: (rep.merit != null ? rep.merit * 13 : 0) + rint(r, 120, 3600),
      missions: a.tasks_done != null ? a.tasks_done : rint(r, 0, 60),
      breakthroughs: cult.breakthroughs != null ? cult.breakthroughs : realmIdx,
      techniques: skillNames.length,
    },
    success: Number.isFinite(Number(sig.success_pct)) ? Number(sig.success_pct) : null,
    seed,
  };
}

/* relationship score between two members — stable, symmetric */
function relScore(a, b) {
  const k = [a, b].sort().join('|');
  const r = rng(hash(k));
  return Math.round((r() * 2 - 1) * 100);
}
function relLabel(s) {
  if (s >= 90) return ['Soulmate', '❤'];
  if (s >= 70) return ['Best Friend', '❤'];
  if (s >= 40) return ['Friend', '★'];
  if (s >= 15) return ['Trusted Ally', '★'];
  if (s > -15) return ['Neutral', '·'];
  if (s > -40) return ['Dislikes', '✕'];
  if (s > -70) return ['Rival', '⚔'];
  if (s > -90) return ['Enemy', '⚔'];
  return ['Sworn Enemy', '☠'];
}
function relationships(name) {
  const others = ROWS.filter((x) => x.name !== name);
  const scored = others.map((x) => ({ name: x.name, s: relScore(name, x.name) }));
  scored.sort((a, b) => Math.abs(b.s) - Math.abs(a.s));
  return scored.slice(0, 5);
}
function mentorship(name) {
  const me = ROWS.find((x) => x.name === name); if (!me) return { master: null, apprentices: [] };
  const myRealm = (me.cultivation || {}).realm || 0;
  const r = rng(hash(name + ':mentor'));
  const seniors = ROWS.filter((x) => x.name !== name && ((x.cultivation || {}).realm || 0) > myRealm);
  const juniors = ROWS.filter((x) => x.name !== name && ((x.cultivation || {}).realm || 0) < myRealm);
  return { master: seniors.length ? pick(r, seniors).name : null, apprentices: sample(r, juniors, Math.min(3, juniors.length)) .map((x) => x.name) };
}
function thoughts(p, rels) {
  const out = [];
  if (p.breakChance >= 70) out.push('Excited about an upcoming breakthrough.');
  if (p.status === 'idle') out.push('Restless — would welcome a new assignment.');
  const foe = rels.find((x) => x.s <= -40), friend = rels.find((x) => x.s >= 40);
  if (foe) out.push(`Dislikes working with ${foe.name}.`);
  if (friend) out.push(`Feels inspired alongside ${friend.name}.`);
  if (p.specs.length) out.push(`Keen to deepen mastery of ${p.specs[0]}.`);
  out.push(`Wants to ${p.goal.toLowerCase()}.`);
  return out.slice(0, 4);
}

/* ====================================================================== *
 *  Pyramid roster
 * ====================================================================== */
const STATUS_DOT = { working: 'dot-working', idle: 'dot-idle', queued: 'dot-working', error: 'dot-error' };

function renderPyramid() {
  $('roster-sub').textContent = ROWS.length
    ? `${ROWS.length} sect member${ROWS.length === 1 ? '' : 's'} — click one to inspect`
    : 'The sect stands empty.';
  const py = $('pyramid');
  if (!ROWS.length) {
    py.innerHTML = `<div class='empty-sect glass'>
      <div class='es-mark'>⛩</div>
      <h2>No sect members yet</h2>
      <p>Add members once an AI backend is set up, then they'll rise here by rank — click any one to open their full dossier.</p>
      <div style='display:flex;gap:8px;justify-content:center;margin-top:8px;flex-wrap:wrap'>
        ${CAN_MANAGE ? `<button class='sa-btn' id='es-add'>＋ Add member</button>` : ''}
        <button class='sa-btn ghost' id='preview-sample'>✨ Preview a sample dossier</button>
      </div>
    </div>`;
    const pb = $('preview-sample'); if (pb) pb.onclick = previewSample;
    const ea = $('es-add'); if (ea) ea.onclick = () => memberForm(null);
    return;
  }
  const byTier = {}; ROWS.forEach((a) => { (byTier[tierOf(a)] = byTier[tierOf(a)] || []).push(a); });
  py.innerHTML = TIERS.filter((t) => (byTier[t.key] || []).length).map((t) => `
    <div class='py-row'>
      <div class='py-tier'>${esc(t.label)}</div>
      <div class='py-members'>${byTier[t.key].map(memberChip).join('')}</div>
    </div>`).join('');
  py.querySelectorAll('.member').forEach((c) => c.onclick = () => openInspect(c.dataset.name));
}
function memberChip(a) {
  const dot = STATUS_DOT[a.status] || 'dot-idle';
  const root = profile(a).root;
  const elite = ['SS', 'SSS', 'Heavenly', 'Immortal'].includes(root.potential);
  return `<button class='member ${a.name === active ? 'sel' : ''}' data-name='${esc(a.name)}'>
    <span class='m-av rq-${root.qIdx}' title='${esc(a.model || '')}'>
      <img src='/assets/sect/portraits/${portraitFor(a)}.png' alt='' onerror="this.style.display='none'">
      <span class='m-dot ${dot}'></span></span>
    <span class='m-name'>${esc(a.name)}</span>
    <span class='m-rank'>${esc((a.cultivation || {}).rank_title || a.role || '')}</span>
    <span class='m-pot ${elite ? 'elite' : ''}' title='Potential'>${esc(root.potential)}</span>
  </button>`;
}

/* ====================================================================== *
 *  Cinematic inspection view
 * ====================================================================== */
function bar(label, val, cls) {
  return `<div class='attr'><span class='attr-l'>${esc(label)}</span>
    <span class='attr-bar'><span class='${cls || ''}' style='width:${Math.max(2, Math.min(100, val))}%'></span></span>
    <span class='attr-v'>${val}</span></div>`;
}
function chip(text, cls) { return `<span class='chip ${cls || ''}'>${esc(text)}</span>`; }

async function openInspect(name) {
  active = name;
  const a = ROWS.find((x) => x.name === name); if (!a) return;
  const p = profile(a);
  const rels = relationships(name);
  const ment = mentorship(name);
  const ths = thoughts(p, rels);

  // dim everyone, spotlight the selected
  $('pyramid').querySelectorAll('.member').forEach((c) => {
    c.classList.toggle('spotlight', c.dataset.name === name);
    c.classList.toggle('dim', c.dataset.name !== name);
  });
  $('stage').classList.add('inspecting');

  const panel = $('inspect-panel');
  panel.innerHTML = `
    <button class='inspect-close' id='inspect-close'>✕</button>
    <div class='dsheet'>
      <header class='ds-head'>
        <div class='ds-portrait'><img src='/assets/sect/portraits/${p.portrait}.png' alt='' onerror="this.style.display='none'"><span class='ds-dot ${STATUS_DOT[p.status] || 'dot-idle'}'></span></div>
        <div class='ds-id'>
          <div class='ds-name'>${esc(p.name)}</div>
          <div class='ds-sub'>Age ${p.age} · ${esc(p.gender)} · ${esc(p.rank)}</div>
          <div class='ds-sub'>${esc(p.realm)} <span class='muted'>(${esc(p.stage)})</span></div>
          <div class='ds-sub muted'>${esc(p.role)} · ${esc(p.assignment)}</div>
          <div class='ds-model'>${esc(p.model || 'no model set')}</div>
        </div>
      </header>

      <section class='ds-block ds-root rq-${p.root.qIdx}'>
        <div class='ds-title'>Spirit Root <span class='root-pot'>Potential ${esc(p.root.potential)}</span></div>
        <div class='root-head'>
          <div class='root-name ${p.root.hidden ? 'hidden-root' : ''}'>${esc(p.root.display)}</div>
          <div class='root-quality'>${esc(p.root.quality)}</div>
        </div>
        <div class='attr'><span class='attr-l'>Purity</span><span class='attr-bar'><span class='rootbar' style='width:${p.root.purity}%'></span></span><span class='attr-v'>${p.root.purity}%</span></div>
        <div class='ds-tris'>
          ${p.root.constitution ? chip(p.root.constitution, 'constitution') : chip('No special constitution', 'muted-chip')}
          ${chip(p.root.trope, 'trope')}
        </div>
        <div class='root-bonuses'>${p.root.bonuses.map((b) => `<span class='bonus'>${esc(b)}</span>`).join('')}</div>
        <div class='root-reaction muted'>${esc(p.root.reaction)}</div>
      </section>

      <section class='ds-block'>
        <div class='ds-title'>Cultivation</div>
        <div class='ds-cult'>
          <div class='cult-row'><b>${esc(p.realm)}</b><span class='muted'>${esc(p.stage)}</span></div>
          <div class='attr'><span class='attr-l'>Progress</span><span class='attr-bar'><span class='jadebar' style='width:${p.prog}%'></span></span><span class='attr-v'>${p.prog}%</span></div>
          <div class='attr'><span class='attr-l'>Breakthrough</span><span class='attr-bar'><span class='goldbar' style='width:${p.breakChance}%'></span></span><span class='attr-v'>${p.breakChance}%</span></div>
          <div class='ds-tris'>${chip('Talent ' + p.grade, 'grade')}${chip('Qi Affinity ' + p.qi)}${chip('Comprehension ' + p.comprehension)}</div>
        </div>
      </section>

      <section class='ds-block'>
        <div class='ds-title'>Attributes</div>
        <div class='ds-attrs'>${p.attrs.map((x) => bar(x.name, x.val, 'azurebar')).join('')}</div>
      </section>

      <section class='ds-block'>
        <div class='ds-title'>Skills</div>
        <div class='ds-skills'>${p.skills.map((s) => `<div class='skill'><span class='sk-name'>${esc(s.name)}</span><span class='sk-lv'>Lv ${s.lv}</span><span class='sk-bar'><span style='width:${s.xp}%'></span></span></div>`).join('')}</div>
      </section>

      ${p.specs.length ? `<section class='ds-block'><div class='ds-title'>Specialties</div><div class='ds-row'>${p.specs.map((s) => chip(s, 'spec')).join('')}</div></section>` : ''}

      <section class='ds-block'>
        <div class='ds-title'>Traits</div>
        <div class='ds-row'>${p.traits.map(([k, t]) => chip(t, 'trait-' + k)).join('')}</div>
      </section>

      <section class='ds-block'>
        <div class='ds-title'>Relationships</div>
        <div class='ds-rels'>${rels.length ? rels.map((x) => { const [lbl, ico] = relLabel(x.s); return `<div class='rel ${x.s >= 15 ? 'good' : x.s <= -15 ? 'bad' : ''}'><span class='rel-ico'>${ico}</span><b>${esc(x.name)}</b><span class='rel-lbl'>${esc(lbl)}</span><span class='rel-score'>${x.s > 0 ? '+' : ''}${x.s}</span></div>`; }).join('') : `<div class='muted'>No bonds formed yet.</div>`}</div>
      </section>

      <section class='ds-block'>
        <div class='ds-title'>Mentorship</div>
        <div class='ds-row'><span class='muted'>Master:</span> ${ment.master ? chip(ment.master) : `<span class='muted'>none</span>`}</div>
        <div class='ds-row'><span class='muted'>Apprentices:</span> ${ment.apprentices.length ? ment.apprentices.map((n) => chip(n)).join('') : `<span class='muted'>none</span>`}</div>
      </section>

      <section class='ds-block'>
        <div class='ds-title'>Sect Status</div>
        <div class='ds-stats'>
          ${stat('Years in Sect', p.sect.years)}${stat('Contribution', p.sect.contribution.toLocaleString())}
          ${stat('Missions', p.sect.missions)}${stat('Breakthroughs', p.sect.breakthroughs)}
          ${stat('Techniques', p.sect.techniques)}${stat('Success', p.success != null ? p.success + '%' : '—')}
        </div>
      </section>

      <section class='ds-block'>
        <div class='ds-title'>Equipment</div>
        <div class='ds-equip'>${p.equip.map(([slot, item, rar]) => `<div class='equip rar-${rar}'><span class='eq-slot'>${esc(slot)}</span><span class='eq-item'>${esc(item)}</span></div>`).join('')}</div>
      </section>

      <section class='ds-block'>
        <div class='ds-title'>Current Thoughts</div>
        <div class='ds-thoughts'>${ths.map((t) => `<div class='thought'>“${esc(t)}”</div>`).join('')}</div>
      </section>

      <section class='ds-block'>
        <div class='ds-title'>Life Goal</div>
        <div class='ds-goal'>${esc(p.goal)}</div>
      </section>

      <section class='ds-block'>
        <div class='ds-title'>Event History</div>
        <div class='ds-events' id='ds-events'><div class='muted'>Loading chronicle…</div></div>
      </section>
    </div>`;

  const ov = $('inspect');
  ov.hidden = false;
  requestAnimationFrame(() => ov.classList.add('show'));
  $('inspect-close').onclick = closeInspect;
  $('inspect-scrim').onclick = closeInspect;
  if (CAN_MANAGE && !previewMode) injectMemberActions(a);

  // real chronicle, blended with synthesised milestones
  const chron = await api('/api/chronicle/' + encodeURIComponent(name));
  const real = ((chron && chron.timeline) || []).slice().reverse().slice(0, 8)
    .map((e) => ({ y: e.kind || '', t: e.detail || e.kind || '' }));
  const r = rng(p.seed + 7);
  const synth = [
    { y: `Year ${Math.max(1, p.sect.years - rint(r, 3, 6))}`, t: `Promoted to ${p.rank}.` },
    { y: `Year ${Math.max(1, p.sect.years - rint(r, 1, 3))}`, t: rels[0] ? `Formed a bond with ${rels[0].name}.` : 'Forged a karmic bond.' },
    { y: `Year ${p.sect.years}`, t: p.breakChance >= 60 ? 'On the cusp of a breakthrough.' : `Mastered ${p.skills[0] ? p.skills[0].name : 'a technique'}.` },
  ];
  const events = (real.length ? real : synth);
  const el = $('ds-events');
  if (el) el.innerHTML = events.map((e) => `<div class='evt'><span class='evt-y'>${esc(e.y)}</span><span class='evt-t'>${esc(e.t)}</span></div>`).join('');
}
function stat(l, v) { return `<div class='ds-stat'><span class='st-v'>${esc(v)}</span><span class='st-l'>${esc(l)}</span></div>`; }

function closeInspect() {
  const ov = $('inspect');
  ov.classList.remove('show');
  $('stage').classList.remove('inspecting');
  $('pyramid').querySelectorAll('.member').forEach((c) => c.classList.remove('dim', 'spotlight'));
  active = null;
  setTimeout(() => { ov.hidden = true; }, 360);
}
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('inspect').hidden) closeInspect(); });

/* a fabricated roster so the dossier can be explored before real members exist */
function previewSample() {
  previewMode = true;
  ROWS = [
    { name: 'Aurelia', role: 'Sect Leader', model: 'claude-opus-4-8', status: 'working', current_task: 'Presiding over the sect',
      governance: { is_leader: true, specialty: 'leadership' }, cultivation: { realm: 6, realm_name: 'Ascendant', stage: 'Peak Stage', rank_title: 'Sect Leader', skills: ['Leadership', 'Formation Mastery'], breakthroughs: 6 }, reputation: { merit: 940, signals: { success_pct: 96 } }, tasks_done: 312 },
    { name: 'Kael', role: 'Sword Cultivator', model: 'llama3', status: 'idle',
      governance: { is_elder: true }, cultivation: { realm: 4, realm_name: 'Core Formation', stage: 'Middle Stage', rank_title: 'Elder', skills: ['Swordsmanship'], breakthroughs: 4 }, reputation: { merit: 410, signals: { success_pct: 81 } }, tasks_done: 88 },
    { name: 'Mira', role: 'Alchemist', model: 'gpt-4o', status: 'queued',
      cultivation: { realm: 2, realm_name: 'Foundation Establishment', stage: 'Late Stage', rank_title: 'Inner Disciple', skills: ['Alchemy', 'Research'], breakthroughs: 2 }, reputation: { merit: 160, signals: { success_pct: 74 } }, tasks_done: 23 },
    { name: 'Pin', role: 'Apprentice', model: 'qwen', status: 'idle',
      cultivation: { realm: 0, realm_name: 'Qi Gathering', stage: 'Early Stage', rank_title: 'Outer Disciple', skills: [], breakthroughs: 0 }, reputation: { merit: 12, signals: { success_pct: 55 } }, tasks_done: 2 },
  ];
  renderPyramid();
  $('roster-sub').textContent = 'Sample preview — these aren’t real members. Add your own in agents.yaml.';
  openInspect('Aurelia');
}

/* ---- member management (add / edit / remove → agents.yaml) ---- */
function setupManage(me) {
  CAN_MANAGE = !!(me && me.authed && (me.role === 'operator' || me.open_mode));
  const slot = $('scene-actions'); if (!slot) return;
  slot.innerHTML = CAN_MANAGE ? `<button class='sa-btn' id='add-member'>＋ Add member</button>` : '';
  const b = $('add-member'); if (b) b.onclick = () => memberForm(null);
}
function memberForm(m) {
  const wrap = $('member-modal');
  wrap.innerHTML = `<div class='acct-modal-box glass' style='width:460px'>
    <h3>${m ? ('Edit ' + esc(m.name)) : 'Add a sect member'}</h3>
    <div class='host-form'>
      <label class='lf-label'>Name</label><input class='lf-input' id='mf-name' value='${m ? esc(m.name) : ''}' placeholder='e.g. Nova'>
      <label class='lf-label'>Role</label><input class='lf-input' id='mf-role' value='${m ? esc(m.role || '') : ''}' placeholder='e.g. Research Analyst'>
      <label class='lf-label'>AI provider</label>
      <select class='lf-input' id='mf-provider'>
        <option value='ollama'>Ollama (local)</option>
        <option value='openai_compatible'>OpenAI-compatible (LM Studio / vLLM)</option>
        <option value='claude'>Claude (needs ANTHROPIC_API_KEY)</option>
      </select>
      <label class='lf-label'>Model</label><input class='lf-input' id='mf-model' value='${m ? esc(m.model || '') : ''}' placeholder='e.g. llama3 · claude-opus-4-8'>
      <label class='lf-label'>Base URL <span class='muted'>(local providers)</span></label><input class='lf-input' id='mf-url' value='${m ? esc(m.base_url || '') : ''}' placeholder='http://127.0.0.1:11434'>
      <label class='lf-label'>Persona <span class='muted'>(optional)</span></label><textarea class='lf-input' id='mf-persona' rows='3' placeholder='How this member thinks and writes…'>${m ? esc(m.persona || '') : ''}</textarea>
      <button class='lf-btn' id='mf-save'>Save member</button>
      <div class='lf-err' id='mf-err'></div>
      <button class='lf-link' id='mf-cancel'>Cancel</button>
    </div></div>`;
  wrap.hidden = false;
  $('mf-provider').value = m ? (m.provider || 'ollama') : 'ollama';
  wrap.onclick = (e) => { if (e.target === wrap) wrap.hidden = true; };
  $('mf-cancel').onclick = () => { wrap.hidden = true; };
  $('mf-save').onclick = async () => {
    const err = $('mf-err'); err.textContent = '';
    const payload = { name: $('mf-name').value.trim(), role: $('mf-role').value.trim() || 'Disciple',
      provider: $('mf-provider').value, model: $('mf-model').value.trim(), base_url: $('mf-url').value.trim(),
      persona: $('mf-persona').value.trim() };
    if (m) payload.original_name = m.name;
    if (!payload.name) { err.textContent = 'Name is required.'; return; }
    if (!payload.model) { err.textContent = 'Model is required.'; return; }
    const r = await post('/api/members', payload);
    if (r && r.ok) { wrap.hidden = true; previewMode = false; load(); } else err.textContent = (r && r.detail) || 'Could not save member.';
  };
}
async function removeMember(name) {
  if (!confirm(`Remove ${name} from the sect?`)) return;
  const tok = localStorage.getItem('maybot.control_token') || '';
  const r = await fetch('/api/members/' + encodeURIComponent(name), { method: 'DELETE', headers: tok ? { 'x-control-token': tok } : {} });
  if (r.ok) { if (active === name) closeInspect(); load(); }
  else { const j = await r.json().catch(() => ({})); alert('Remove failed: ' + (j.detail || r.status)); }
}
function injectMemberActions(a) {
  const head = document.querySelector('#inspect-panel .ds-head');
  if (!head || document.getElementById('ds-edit')) return;
  const row = document.createElement('div'); row.className = 'ds-manage';
  row.innerHTML = `<button class='sa-btn' id='ds-edit'>Edit</button><button class='sa-btn danger' id='ds-del'>Remove</button>`;
  head.appendChild(row);
  $('ds-edit').onclick = async () => { const d = await api('/api/members'); const m = ((d && d.members) || []).find((x) => x.name === a.name); memberForm(m || { name: a.name }); };
  $('ds-del').onclick = () => removeMember(a.name);
}

let _manageInit = false;
async function load() {
  if (previewMode) return;
  if (!_manageInit) { _manageInit = true; try { setupManage(await api('/api/account/me')); } catch (_) {} }
  const data = await api('/api/agents');
  if (window.__needAuth && !data) {
    $('roster-sub').innerHTML = `Authentication required — <a href='/console' style='color:var(--violet)'>sign in</a>.`;
    return;
  }
  ROWS = (data && data.agents) || [];
  renderPyramid();
  // deep-link: /chamber?inspect=<name> (e.g. clicking a character on the Sect Map)
  const want = new URLSearchParams(location.search).get('inspect');
  if (want && !active && ROWS.some((x) => x.name === want)) openInspect(want);
}
load();
setInterval(() => { if (!previewMode && $('inspect').hidden) load(); }, 12000);
liveStream((t) => { if (['agents','tick','tasks'].includes(t) && !previewMode && $('inspect').hidden) debounce(load, 800); });
