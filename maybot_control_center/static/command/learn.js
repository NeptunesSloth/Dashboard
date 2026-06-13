import { $, api, esc, post, authHeaders, mountRail, initAccount, liveStream, debounce, countUp, starfield } from '/lib.js';

mountRail('learn');
initAccount();
starfield('scene-canvas');

let TRACKS = [];
let curTrack = null;
let curTopic = null;
let chatHistory = [];
let PROG = {};
let examTimer = null;
let muted = localStorage.getItem('learn.mute') === '1';
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const fxOn = () => !muted && !reduced;

/* ---------------- juice: toasts, confetti, sound, modal ---------------- */
function toast(msg, good) {
  const t = document.createElement('div');
  t.className = 'toast' + (good ? ' good' : '');
  t.innerHTML = msg;
  $('toasts').appendChild(t);
  setTimeout(() => { t.style.transition = 'opacity .4s'; t.style.opacity = '0'; setTimeout(() => t.remove(), 400); }, 2600);
}
function beep(freq = 660, dur = 0.12) {
  if (muted) return;
  try {
    const ctx = beep._c || (beep._c = new (window.AudioContext || window.webkitAudioContext)());
    const o = ctx.createOscillator(); const g = ctx.createGain();
    o.frequency.value = freq; o.type = 'triangle'; o.connect(g); g.connect(ctx.destination);
    g.gain.setValueAtTime(0.08, ctx.currentTime); g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
    o.start(); o.stop(ctx.currentTime + dur);
  } catch (_) {}
}
function confetti(n = 90) {
  if (!fxOn()) return;
  const box = $('confetti'); const cols = ['#7c5cff', '#38bdf8', '#34d399', '#fbbf24', '#fb5e7e', '#a78bfa'];
  for (let i = 0; i < n; i++) {
    const b = document.createElement('div'); b.className = 'confetti-bit';
    b.style.left = Math.random() * 100 + 'vw'; b.style.background = cols[i % cols.length];
    b.style.opacity = '0.9'; box.appendChild(b);
    const x = (Math.random() - 0.5) * 240, rot = Math.random() * 720 - 360;
    b.animate([{ transform: 'translate(0,0) rotate(0)' },
      { transform: `translate(${x}px, ${innerHeight + 40}px) rotate(${rot}deg)` }],
      { duration: 1600 + Math.random() * 1200, easing: 'cubic-bezier(.2,.6,.4,1)' })
      .onfinish = () => b.remove();
  }
}
function celebrate(ico, title, sub) {
  beep(880, 0.18); confetti();
  $('modal-card').innerHTML = `<div class='big-ico'>${ico}</div><h2>${esc(title)}</h2>
    <div class='muted'>${esc(sub || '')}</div>
    <button class='btn primary' id='modal-ok' style='margin-top:16px'>Nice!</button>`;
  $('modal').classList.add('show');
  $('modal-ok').onclick = () => $('modal').classList.remove('show');
}
$('modal').onclick = (e) => { if (e.target === $('modal')) $('modal').classList.remove('show'); };

function award(res) {
  if (!res) return;
  if (res.awarded) { toast(`<b>+${res.awarded}</b> spirit stones ◈`, true); beep(); }
  (res.badges || []).forEach((b, i) =>
    setTimeout(() => celebrate('🏅', `Badge unlocked: ${b.name}`, `${b.desc} · +${b.stones} ◈`), i * 400));
}

function setMute() {
  $('mute').textContent = muted ? '🔇' : '🔊';
  $('mute').title = muted ? 'Sound & motion off' : 'Sound & motion on';
}
$('mute').onclick = () => { muted = !muted; localStorage.setItem('learn.mute', muted ? '1' : '0'); setMute(); };
setMute();

/* ---------------- tracks + topics ---------------- */
function renderTracks() {
  $('tracks').innerHTML = TRACKS.map((t) =>
    `<div class='chip ${curTrack && curTrack.id === t.id ? 'active' : ''}' data-t='${esc(t.id)}'>
       ${esc(t.title)}<span class='lvl'>Lv ${t.level.level}</span></div>`).join('') +
    `<div class='chip' data-t='__new'>＋ New track</div>`;
  $('tracks').querySelectorAll('.chip').forEach((c) => c.onclick = () => {
    if (c.dataset.t === '__new') return newTrack();
    selectTrack(c.dataset.t);
  });
}
function selectTrack(id) {
  if (examTimer) { clearInterval(examTimer); examTimer = null; }
  curTrack = TRACKS.find((t) => t.id === id) || null; curTopic = null; chatHistory = [];
  $('chat').innerHTML = '';
  renderTracks(); renderTopics(); renderModes();
  $('work').innerHTML = `<div class='muted'>Choose a topic to begin a lesson${curTrack && curTrack.labs.length ? ', or pick a study mode above.' : '.'}</div>`
    + labButtons();
  bindLabButtons();
  $('work-title').textContent = 'Lesson'; $('work-sub').textContent = curTrack ? curTrack.title : '';
  loadChat();
}
function renderModes() {
  if (!curTrack) { $('modes').innerHTML = ''; return; }
  const due = PROG.reviews_due || 0;
  const labs = curTrack.labs || [];
  const m = [
    ['review', `🔁 Review${due ? `<span class='pill'>${due}</span>` : ''}`],
    ['exam', '📝 Practice Exam'],
  ];
  if (labs.includes('pentest')) m.push(['range', '🎯 Pentest Range']);
  if (labs.includes('ids')) m.push(['incident', '🛡 Incident']);
  if (curTrack.language) m.push(['drill', '✍️ Drills']);
  m.push(['skills', '🗺 Skill Path'], ['infra', '🖧 Cyber Range'], ['plan', '📅 Study Plan'],
    ['stats', '📈 Stats'], ['real', '🖥 Real Log Lab'], ['material', '📎 My Material'],
    ['library', '📂 Library']);
  $('modes').innerHTML = m.map(([k, lbl]) => `<button class='mode-btn' data-mode='${k}'>${lbl}</button>`).join('');
  const handlers = { review: startReview, exam: startExam, plan: openPlan, stats: openStats,
    real: startRealLab, library: openLibrary, range: startRange, incident: startIncident,
    drill: startDrill, material: openMaterial, skills: openSkills, infra: openRangeInfra };
  $('modes').querySelectorAll('.mode-btn').forEach((b) => b.onclick = () => {
    if (examTimer) { clearInterval(examTimer); examTimer = null; }
    (handlers[b.dataset.mode] || (() => {}))();
  });
}
async function loadChat() {
  if (!curTrack) return;
  const r = await api(`/api/learning/chat?track=${encodeURIComponent(curTrack.id)}`);
  chatHistory = (r && r.history) || [];
  $('chat').innerHTML = chatHistory.map((t) => `<div class='bub ${t.role === 'user' ? 'you' : 'ai'}'>${esc(t.content)}</div>`).join('');
  $('chat').scrollTop = $('chat').scrollHeight;
}
function renderTopics() {
  if (!curTrack) { $('topics').innerHTML = ''; return; }
  const mastered = curTrack.mastered_topics || [];
  $('topics').innerHTML = curTrack.topics.map((tp) => {
    const done = curTrack.completed_topics.includes(tp);
    const star = mastered.includes(tp) ? ' ✓' : '';
    return `<span class='topic-wrap'><button class='topic-btn ${done ? 'done' : ''}' data-tp='${esc(tp)}'>${esc(tp)}${star}</button>` +
      `<button class='topic-testout' data-testout='${esc(tp)}' title='Already know this? Test out to skip it.'>⚡</button></span>`;
  }).join('');
  $('topics').querySelectorAll('.topic-btn').forEach((b) => b.onclick = () => loadLesson(b.dataset.tp));
  $('topics').querySelectorAll('[data-testout]').forEach((b) => b.onclick = () => startTestOut(b.dataset.testout));
}
function labButtons() {
  if (!curTrack || !curTrack.labs.length) return '';
  return `<div class='actions'>` + curTrack.labs.map((k) =>
    `<button class='btn' data-lab='${k}'>🧪 ${k === 'ids' ? 'Intrusion-detection lab' : 'Pentest lab'}</button>`).join('') + `</div>`;
}
function bindLabButtons() {
  document.querySelectorAll('[data-lab]').forEach((b) => b.onclick = () => startLab(b.dataset.lab));
}

async function newTrack() {
  const title = prompt('Name your new track (e.g. "Spanish", "AWS Cert"):'); if (!title) return;
  const topicsRaw = prompt('Topics, comma-separated:', 'Intro, Basics, Practice') || '';
  const res = await post('/api/learning/tracks', { title, topics: topicsRaw.split(',').map((s) => s.trim()).filter(Boolean) });
  if (res && res.track) { toast('Track created.', true); await loadTracks(); selectTrack(res.track.id); }
  else toast((res && res.error) || 'Could not create track.');
}

/* ---------------- lessons ---------------- */
async function loadLesson(topic) {
  curTopic = topic;
  $('work-title').textContent = topic; $('work-sub').textContent = 'Lesson';
  $('work').innerHTML = `<div class='muted'>✨ Crafting a lesson tailored to you…</div>`;
  const res = await api(`/api/learning/lesson?track=${encodeURIComponent(curTrack.id)}&topic=${encodeURIComponent(topic)}`);
  if (!res || res.error) return showErr(res);
  $('work').innerHTML = `<div class='lesson-body'>${esc(res.body)}</div>
    <div class='actions'>
      <button class='btn primary' id='do-quiz'>📝 Quiz me on this</button>
      ${labButtons()}
    </div>`;
  $('do-quiz').onclick = () => startQuiz(topic);
  bindLabButtons();
  award(res); loadProgress();
}

/* ---------------- quizzes ---------------- */
async function startQuiz(topic) {
  $('work-title').textContent = `Quiz · ${topic}`; $('work-sub').textContent = '';
  $('work').innerHTML = `<div class='muted'>Writing your quiz…</div>`;
  const res = await post('/api/learning/quiz', { track: curTrack.id, topic, n: 5 });
  if (!res || res.error) return showErr(res);
  const qs = res.questions || [];
  $('work').innerHTML = qs.map((q, i) => `<div class='qz-q' data-q='${i}'>
      <div class='stem'>${i + 1}. ${esc(q.q)}</div>
      ${q.choices.map((c, j) => `<label class='qz-opt' data-i='${i}' data-j='${j}'>${esc(c)}</label>`).join('')}
    </div>`).join('') + `<div class='actions'><button class='btn primary' id='submit-quiz'>Submit answers</button></div>`;
  const picks = {};
  $('work').querySelectorAll('.qz-opt').forEach((o) => o.onclick = () => {
    const i = o.dataset.i; picks[i] = +o.dataset.j;
    o.parentElement.querySelectorAll('.qz-opt').forEach((x) => x.classList.remove('sel'));
    o.classList.add('sel'); beep(520, 0.05);
  });
  $('submit-quiz').onclick = async () => {
    const answers = qs.map((_, i) => (i in picks ? picks[i] : -1));
    const g = await post('/api/learning/quiz/grade', { quiz_id: res.quiz_id, answers });
    if (!g || g.error) return showErr(g);
    qs.forEach((q, i) => {
      const row = $('work').querySelector(`.qz-q[data-q='${i}']`);
      const r = g.per_question[i];
      row.querySelectorAll('.qz-opt').forEach((o) => {
        const j = +o.dataset.j;
        if (j === r.answer) o.classList.add('right');
        if (j === r.your_answer && !r.correct) o.classList.add('wrong');
        o.style.pointerEvents = 'none';
      });
      if (r.explanation) row.insertAdjacentHTML('beforeend', `<div class='qz-exp'>${esc(r.explanation)}</div>`);
    });
    $('submit-quiz').remove();
    const head = `<div class='glass' style='padding:14px; margin-bottom:14px; text-align:center'>
      <div style='font-size:24px; font-weight:800'>${g.score}%</div>
      <div class='muted'>${g.correct}/${g.total} correct · +${g.awarded} ◈${g.best_combo >= 3 ? ` · 🔥 best combo ${g.best_combo}` : ''}</div></div>`;
    $('work').insertAdjacentHTML('afterbegin', head);
    if (g.score >= 80) celebrate(g.score === 100 ? '🌟' : '✅', g.score === 100 ? 'Flawless!' : 'Quiz passed!', `${g.score}% · +${g.awarded} ◈`);
    else { toast(`Scored ${g.score}% · +${g.awarded} ◈`); beep(330, 0.1); }
    award({ awarded: 0, badges: g.badges });
    loadProgress(); loadTracks();
  };
}

/* ---------------- labs ---------------- */
async function startLab(kind) {
  $('work-title').textContent = `${kind === 'ids' ? 'Intrusion-Detection' : 'Pentest'} Lab`; $('work-sub').textContent = curTrack.title;
  $('work').innerHTML = `<div class='muted'>🧪 Building your lab environment…</div>`;
  const res = await post('/api/learning/lab', { track: curTrack.id, kind });
  if (!res || res.error) return showErr(res);
  renderLab(res, kind);
}
function renderLab(res, kind) {
  const placeholder = kind === 'pentest'
    ? 'Report the vulnerability, how you would exploit it, and the flag…'
    : 'Describe the intrusion you found and your evidence…';
  $('work').innerHTML = `<div style='font-size:13.5px; margin-bottom:10px'><b>Brief:</b> ${esc(res.brief)}</div>
    ${res.source ? `<div class='muted' style='font-size:11px; margin-bottom:6px'>Real logs from ${esc(res.source)}</div>` : ''}
    <div class='lab-art'>${esc(res.artifact)}</div>
    <textarea class='finding' id='finding' aria-label='Your finding' placeholder='${placeholder}'></textarea>
    <div class='actions'><button class='btn primary' id='submit-lab'>Submit finding</button></div>`;
  $('submit-lab').onclick = async () => {
    const finding = $('finding').value.trim();
    if (!finding) return toast('Write your finding first.');
    $('submit-lab').disabled = true; $('submit-lab').textContent = 'Grading…';
    const g = await post('/api/learning/lab/grade', { lab_id: res.lab_id, finding });
    if (!g || g.error) { $('submit-lab').disabled = false; $('submit-lab').textContent = 'Submit finding'; return showErr(g); }
    $('work').insertAdjacentHTML('afterbegin',
      `<div class='glass' style='padding:14px; margin-bottom:14px'>
        <div style='font-size:22px; font-weight:800'>${g.score}/100 ${g.solved ? '✅' : ''}</div>
        <div class='muted' style='margin-top:4px'>${esc(g.feedback)}</div>
        <details style='margin-top:8px'><summary class='muted' style='cursor:pointer; font-size:12px'>Show expected answer</summary>
          <div class='lab-art' style='margin-top:8px'>${esc(g.expected)}</div></details></div>`);
    $('submit-lab').remove();
    if (g.solved) celebrate('🛡️', 'Lab solved!', `${g.score}/100 · +${g.awarded} ◈`);
    else { toast(`Lab scored ${g.score}/100 · +${g.awarded} ◈`); beep(330, 0.1); }
    award({ awarded: 0, badges: g.badges });
    loadProgress();
  };
}

/* ---------------- spaced-repetition review ---------------- */
async function startReview() {
  $('work-title').textContent = 'Review'; $('work-sub').textContent = 'Spaced repetition';
  $('work').innerHTML = `<div class='muted'>Loading your review deck…</div>`;
  const r = await api('/api/learning/reviews');
  if (!r) return showErr(r);
  if (!r.due || !r.due.length) {
    $('work').innerHTML = `<div class='muted'>🎉 Nothing due right now. Missed quiz questions land here and resurface on a schedule. Deck size: ${r.deck_size}.</div>`;
    return;
  }
  let i = 0; const cards = r.due;
  const showCard = () => {
    if (i >= cards.length) {
      $('work').innerHTML = `<div class='muted'>✅ Review complete — ${cards.length} card${cards.length === 1 ? '' : 's'} done. Come back tomorrow!</div>`;
      loadProgress(); renderModes(); return;
    }
    const c = cards[i];
    $('work-sub').textContent = `${i + 1} / ${cards.length} · ${c.topic || c.track}`;
    $('work').innerHTML = `<div class='qz-q'><div class='stem'>${esc(c.q)}</div>
      ${c.choices.map((ch, j) => `<label class='qz-opt' data-j='${j}'>${esc(ch)}</label>`).join('')}</div>
      <div id='rate'></div>`;
    let picked = -1;
    $('work').querySelectorAll('.qz-opt').forEach((o) => o.onclick = () => {
      if (picked >= 0) return;
      picked = +o.dataset.j; beep(520, 0.05);
      o.classList.add('sel');
      // We learn the correct answer from the grade call; self-rate, then reveal.
      $('rate').innerHTML = `<div class='muted' style='margin:8px 0'>How well did you know it?</div>
        <div class='rate-bar'>
          <button class='btn' data-q='2'>😵 Forgot</button>
          <button class='btn' data-q='3'>😐 Hard</button>
          <button class='btn' data-q='4'>🙂 Good</button>
          <button class='btn' data-q='5'>😎 Easy</button></div>`;
      $('rate').querySelectorAll('[data-q]').forEach((b) => b.onclick = () => rate(c, picked, +b.dataset.q));
    });
  };
  const rate = async (c, picked, quality) => {
    const g = await post('/api/learning/reviews/grade', { card_id: c.id, quality });
    if (!g || g.error) return showErr(g);
    $('work').querySelectorAll('.qz-opt').forEach((o) => { const j = +o.dataset.j;
      if (j === g.correct_answer) o.classList.add('right');
      if (j === picked && picked !== g.correct_answer) o.classList.add('wrong');
      o.style.pointerEvents = 'none'; });
    $('rate').innerHTML = g.explanation ? `<div class='qz-exp'>${esc(g.explanation)}</div>` : '';
    toast(`Next review in ${g.interval_days}d · +${g.awarded} ◈`, true);
    award({ awarded: 0, badges: g.badges });
    i++; setTimeout(showCard, 1100);
  };
  showCard();
}

/* ---------------- practice exam ---------------- */
async function startExam() {
  $('work-title').textContent = 'Practice Exam'; $('work-sub').textContent = curTrack.title;
  $('work').innerHTML = `<div class='muted'>📝 Assembling a full exam across all domains…</div>`;
  const ex = await post('/api/learning/exam', { track: curTrack.id, n: 20 });
  if (!ex || ex.error) return showErr(ex);
  const qs = ex.questions; const started = Date.now();
  $('work-sub').innerHTML = `${curTrack.title} · pass ${ex.pass_mark}% · <span class='exam-timer' id='etimer'></span>`;
  $('work').innerHTML = qs.map((q, i) => `<div class='qz-q' data-q='${i}'>
      <div class='stem'>${i + 1}. ${esc(q.q)} <span class='muted' style='font-size:11px'>[${esc(q.domain)}]</span></div>
      ${q.choices.map((c, j) => `<label class='qz-opt' data-i='${i}' data-j='${j}'>${esc(c)}</label>`).join('')}
    </div>`).join('') + `<div class='actions'><button class='btn primary' id='submit-exam'>Submit exam</button></div>`;
  const picks = {};
  $('work').querySelectorAll('.qz-opt').forEach((o) => o.onclick = () => {
    picks[o.dataset.i] = +o.dataset.j;
    o.parentElement.querySelectorAll('.qz-opt').forEach((x) => x.classList.remove('sel'));
    o.classList.add('sel');
  });
  const submit = async () => {
    if (examTimer) { clearInterval(examTimer); examTimer = null; }
    const answers = qs.map((_, i) => (i in picks ? picks[i] : -1));
    const g = await post('/api/learning/exam/grade', { exam_id: ex.exam_id, answers, elapsed: Math.round((Date.now() - started) / 1000) });
    if (!g || g.error) return showErr(g);
    qs.forEach((q, i) => {
      const row = $('work').querySelector(`.qz-q[data-q='${i}']`); const r = g.per_question[i];
      row.querySelectorAll('.qz-opt').forEach((o) => { const j = +o.dataset.j;
        if (j === r.answer) o.classList.add('right');
        if (j === r.your_answer && !r.correct) o.classList.add('wrong');
        o.style.pointerEvents = 'none'; });
    });
    const ok = $('work').querySelector('#submit-exam'); if (ok) ok.remove();
    const doms = Object.entries(g.per_domain).map(([d, v]) => {
      const pct = v.total ? Math.round(100 * v.correct / v.total) : 0;
      return `<div class='dom-row'><span style='width:42%; ${g.weak_domains.includes(d) ? 'color:#fb5e7e' : ''}'>${esc(d)}</span>
        <div class='dom-bar'><span style='width:${pct}%'></span></div><span>${v.correct}/${v.total}</span></div>`;
    }).join('');
    $('work').insertAdjacentHTML('afterbegin',
      `<div class='glass' style='padding:16px; margin-bottom:14px; text-align:center'>
        <div style='font-size:30px; font-weight:800; color:${g.passed ? '#34d399' : '#fb5e7e'}'>${g.score}%</div>
        <div style='font-weight:700'>${g.passed ? '✅ PASSED' : '❌ Below pass mark'} (${g.pass_mark}%)</div>
        <div class='muted' style='margin-top:4px'>${g.correct}/${g.total} correct · +${g.awarded} ◈</div>
        <div style='text-align:left; margin-top:12px'>${doms}</div></div>`);
    if (g.passed) celebrate('🎓', 'Exam passed!', `${g.score}% · +${g.awarded} ◈`);
    else { toast(`Exam: ${g.score}% · +${g.awarded} ◈`); beep(330, 0.1); }
    award({ awarded: 0, badges: g.badges });
    loadProgress(); loadTracks();
    $('etimer')?.remove();
  };
  $('submit-exam').onclick = submit;
  let left = ex.duration_sec;
  const tick = () => {
    const el = $('etimer'); if (!el) { clearInterval(examTimer); examTimer = null; return; }
    const m = String(Math.floor(left / 60)).padStart(2, '0'), s = String(left % 60).padStart(2, '0');
    el.textContent = `⏱ ${m}:${s}`; el.classList.toggle('low', left <= 60);
    if (left <= 0) { toast('Time! Auto-submitting.'); submit(); return; }
    left--;
  };
  tick(); examTimer = setInterval(tick, 1000);
}

/* ---------------- real log lab ---------------- */
async function startRealLab() {
  $('work-title').textContent = 'Real Log Lab'; $('work-sub').textContent = 'Analyze logs from a live host';
  $('work').innerHTML = `<div class='muted'>Finding hosts you can pull logs from…</div>`;
  const r = await api('/api/learning/lab/sources');
  if (!r) return showErr(r);
  const sources = r.sources || [];
  if (!sources.length) {
    $('work').innerHTML = `<div class='muted'>No connected hosts yet. Enroll a host agent (Ops → Hosts) and its projects will appear here — then you can pull <b>real</b> logs and hunt for intrusions in them.</div>`;
    return;
  }
  $('work').innerHTML = `<div style='font-size:13px; margin-bottom:10px'>Pull recent logs from a live host and hunt for suspicious activity. The AI grades your analysis against the real logs.</div>
    <select id='src' class='finding' aria-label='Select log source' style='min-height:auto; height:auto'>
      ${sources.map((s) => `<option value='${esc(s.device)}|${esc(s.project)}'>${esc(s.device)} / ${esc(s.project)} (${esc(s.type || '')})</option>`).join('')}
    </select>
    <div class='actions'><button class='btn primary' id='pull'>🖥 Pull logs & build lab</button></div>`;
  $('pull').onclick = async () => {
    const [device, project] = $('src').value.split('|');
    $('pull').disabled = true; $('pull').textContent = 'Pulling…';
    const lab = await post('/api/learning/lab/real', { track: curTrack.id, device, project });
    if (!lab || lab.error) { $('pull').disabled = false; $('pull').textContent = '🖥 Pull logs & build lab'; return showErr(lab); }
    renderLab(lab, 'ids');
  };
}

/* ---------------- library (saved lessons) ---------------- */
async function openLibrary() {
  $('work-title').textContent = 'Library'; $('work-sub').textContent = 'Saved lessons';
  $('work').innerHTML = `<div class='muted'>Loading saved lessons…</div>`;
  const r = await api(`/api/learning/lessons?track=${encodeURIComponent(curTrack.id)}`);
  const items = (r && r.lessons) || [];
  if (!items.length) { $('work').innerHTML = `<div class='muted'>No saved lessons yet. Lessons you generate are saved here to revisit anytime.</div>`; return; }
  $('work').innerHTML = items.map((x) => `<div class='lib-item' data-id='${x.id}'>
      <div>${esc(x.topic)}</div><div class='meta'>${new Date(x.created * 1000).toLocaleString()} · ${esc(x.snippet)}…</div></div>`).join('');
  $('work').querySelectorAll('.lib-item').forEach((it) => it.onclick = async () => {
    const full = await api(`/api/learning/lessons/${it.dataset.id}`);
    if (!full || full.error) return showErr(full);
    $('work-title').textContent = full.topic;
    $('work').innerHTML = `<div class='lesson-body'>${esc(full.body)}</div>
      <div class='actions'><button class='btn' id='back-lib'>← Back to library</button>
        <button class='btn primary' id='quiz-saved'>📝 Quiz me on this</button></div>`;
    $('back-lib').onclick = openLibrary;
    $('quiz-saved').onclick = () => startQuiz(full.topic);
  });
}

/* ---------------- study plan ---------------- */
async function openPlan() {
  $('work-title').textContent = 'Study Plan'; $('work-sub').textContent = curTrack.title;
  const r = await api(`/api/learning/plan?track=${encodeURIComponent(curTrack.id)}`);
  const plan = r && r.plan;
  if (!plan) {
    const def = new Date(Date.now() + 21 * 864e5).toISOString().slice(0, 10);
    $('work').innerHTML = `<div style='font-size:13px; margin-bottom:10px'>Set your exam/target date and I'll build a paced day-by-day plan with lessons, spaced reviews and mock exams.</div>
      <div class='actions'><input type='date' id='exam-date' class='finding' style='min-height:auto; height:auto; width:auto' value='${def}'>
        <button class='btn primary' id='make-plan'>Build my plan</button></div>`;
    $('make-plan').onclick = async () => {
      const res = await post('/api/learning/plan', { track: curTrack.id, exam_date: $('exam-date').value });
      if (!res || res.error) return toast(errText(res));
      toast('Plan ready!', true); openPlan();
    };
    return;
  }
  const ICON = { lesson: '📖', review: '🔁', exam: '📝' };
  const today = new Date().toISOString().slice(0, 10);
  $('work').innerHTML = `<div class='glass' style='padding:14px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center'>
      <div><div style='font-size:18px; font-weight:800'>${plan.days_left} days left</div>
        <div class='muted'>exam ${esc(plan.exam_date)} · ${plan.done}/${plan.total} tasks done</div></div>
      <div style='text-align:right'><div style='font-size:15px; font-weight:700; color:${plan.on_track ? '#34d399' : '#fbbf24'}'>${plan.on_track ? '✅ On track' : '⏳ Catch up'}</div>
        <button class='btn' id='replan' style='margin-top:6px; padding:4px 10px; font-size:11px'>change date</button></div></div>`
    + plan.items.map((it, idx) => `<label class='lib-item' style='display:flex; align-items:center; gap:10px; ${it.done ? 'opacity:.6' : ''}'>
        <input type='checkbox' data-idx='${idx}' ${it.done ? 'checked' : ''}>
        <span>${ICON[it.kind] || '•'} <b>${esc(it.ref)}</b>
          <span class='meta'>${it.date}${it.date < today && !it.done ? ' · overdue' : it.date === today ? ' · today' : ''}</span></span></label>`).join('');
  $('work').querySelectorAll('input[type=checkbox]').forEach((cb) => cb.onchange = async () => {
    const g = await post('/api/learning/plan/item', { track: curTrack.id, index: +cb.dataset.idx, done: cb.checked });
    if (g && g.ok) { if (cb.checked) { beep(); toast('+5 ◈', true); } openPlan(); loadProgress(); }
  });
  $('replan').onclick = async () => {
    const d = prompt('New exam/target date (YYYY-MM-DD):', plan.exam_date); if (!d) return;
    const res = await post('/api/learning/plan', { track: curTrack.id, exam_date: d });
    if (!res || res.error) return toast(errText(res));
    openPlan();
  };
}

/* ---------------- analytics ---------------- */
async function openStats() {
  $('work-title').textContent = 'Stats'; $('work-sub').textContent = 'Your learning analytics';
  $('work').innerHTML = `<div class='muted'>Crunching your numbers…</div>`;
  const a = await api('/api/learning/analytics');
  if (!a) return showErr(a);
  // heatmap (last ~17 weeks)
  const cells = a.heatmap.map((d) => {
    const lvl = d.count === 0 ? 0 : d.count < 2 ? 1 : d.count < 4 ? 2 : d.count < 7 ? 3 : 4;
    const col = ['rgba(255,255,255,.05)', '#1e4620', '#2e7d32', '#43a047', '#66bb6a'][lvl];
    return `<span title='${d.date}: ${d.count}' style='width:11px; height:11px; border-radius:2px; background:${col}; display:inline-block'></span>`;
  }).join('');
  const t = a.totals;
  const stat = (lbl, v) => `<div class='glass' style='padding:10px 14px; text-align:center; flex:1'>
    <div style='font-size:20px; font-weight:800'>${v}</div><div class='muted' style='font-size:11px'>${lbl}</div></div>`;
  const mastery = a.mastery.map((m) => {
    const pct = m.topics_total ? Math.round(100 * m.topics_done / m.topics_total) : 0;
    return `<div class='dom-row'><span style='width:40%'>${esc(m.track)}</span>
      <div class='dom-bar'><span style='width:${pct}%'></span></div><span>Lv ${m.level} · ${m.avg_score}%</span></div>`;
  }).join('') || `<div class='muted'>Complete topics to build mastery.</div>`;
  const trend = a.accuracy_trend.slice(-20);
  const spark = trend.length ? trend.map((p) => {
    const h = Math.max(3, Math.round(p.accuracy * 0.4));
    return `<span title='${p.date}: ${p.accuracy}%' style='width:8px; height:${h}px; background:linear-gradient(#38bdf8,#7c5cff); display:inline-block; border-radius:2px'></span>`;
  }).join('') : `<span class='muted'>Take quizzes to see your accuracy trend.</span>`;
  $('work').innerHTML = `
    <div style='display:flex; gap:8px; margin-bottom:14px'>
      ${stat('Active days', a.active_days)}${stat('Streak', a.streak)}${stat('Best', a.max_streak)}${stat('Realm', esc(a.realm || '—'))}</div>
    <div class='panel-title' style='margin-bottom:6px'>Activity</div>
    <div style='display:flex; flex-wrap:wrap; gap:3px; margin-bottom:16px; max-width:100%'>${cells}</div>
    <div style='display:flex; gap:8px; margin-bottom:16px'>
      ${stat('Lessons', t.lessons)}${stat('Quizzes', t.quizzes)}${stat('Labs', t.labs)}${stat('Reviews', t.reviews)}${stat('Exams', t.exams)}</div>
    <div class='panel-title' style='margin-bottom:6px'>Accuracy trend</div>
    <div style='display:flex; align-items:flex-end; gap:3px; height:46px; margin-bottom:16px'>${spark}</div>
    <div class='panel-title' style='margin-bottom:6px'>Track mastery</div>${mastery}
    ${a.skills.length ? `<div class='panel-title' style='margin:14px 0 6px'>Techniques mastered</div>
      <div>${a.skills.map((s) => `<span class='tag'>${esc(s)}</span>`).join('')}</div>` : ''}`;
}

/* ---------------- tutor chat ---------------- */
async function sendChat() {
  const inp = $('chat-input'); const q = inp.value.trim();
  if (!q) return;
  if (!curTrack) return toast('Pick a track first.');
  inp.value = '';
  const history = chatHistory.slice();
  chatHistory.push({ role: 'user', content: q });
  $('chat').insertAdjacentHTML('beforeend', `<div class='bub you'>${esc(q)}</div>`);
  const bub = document.createElement('div'); bub.className = 'bub ai'; bub.textContent = '…';
  $('chat').appendChild(bub);
  $('chat').scrollTop = $('chat').scrollHeight;
  let answer = '', errored = null;
  try {
    const resp = await fetch('/api/learning/ask/stream', {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ track: curTrack.id, question: q, history }),
    });
    if (!resp.ok || !resp.body) throw new Error('no stream');
    const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = '';
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf('\n\n')) >= 0) {
        const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 2);
        if (!line.startsWith('data:')) continue;
        let ev; try { ev = JSON.parse(line.slice(5).trim()); } catch (_) { continue; }
        if (ev.type === 'token') { answer += ev.text; bub.textContent = answer; $('chat').scrollTop = $('chat').scrollHeight; }
        else if (ev.type === 'error') { errored = ev.error; }
      }
    }
  } catch (_) {
    // Fallback to the non-streaming endpoint.
    const res = await post('/api/learning/ask', { track: curTrack.id, question: q, history });
    if (res && !res.error) answer = res.answer; else errored = (res && res.error) || 'no response';
  }
  if (!answer) { bub.innerHTML = `⚠ ${esc(errText({ error: errored }))}`; return; }
  bub.textContent = answer;
  chatHistory.push({ role: 'assistant', content: answer });
  speak(answer);
  loadProgress();
}
$('chat-send').onclick = sendChat;
$('chat-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendChat(); });

/* ---------------- voice (TTS + STT) ---------------- */
let speakOn = localStorage.getItem('learn.speak') === '1';
const voiceLang = () => (curTrack && /french|français/i.test(curTrack.title)) ? 'fr-FR' : 'en-US';
function setSpeak() { $('chat-speak').style.opacity = speakOn ? '1' : '.5'; $('chat-speak').textContent = speakOn ? '🔊' : '🔈'; }
function speak(text) {
  if (!speakOn || !window.speechSynthesis || muted) return;
  try {
    const u = new SpeechSynthesisUtterance(String(text).slice(0, 600));
    u.lang = voiceLang(); speechSynthesis.cancel(); speechSynthesis.speak(u);
  } catch (_) {}
}
$('chat-speak').onclick = () => { speakOn = !speakOn; localStorage.setItem('learn.speak', speakOn ? '1' : '0'); setSpeak(); if (speakOn) speak('Voice on.'); };
setSpeak();

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SR) { $('chat-mic').style.display = 'none'; }
else {
  let listening = false; const rec = new SR();
  rec.lang = 'en-US'; rec.interimResults = false; rec.maxAlternatives = 1;
  $('chat-mic').onclick = () => {
    if (listening) { rec.stop(); return; }
    rec.lang = voiceLang();
    try { rec.start(); } catch (_) { return; }
  };
  rec.onstart = () => { listening = true; $('chat-mic').textContent = '🔴'; $('chat-input').placeholder = 'Listening…'; };
  rec.onend = () => { listening = false; $('chat-mic').textContent = '🎙'; $('chat-input').placeholder = 'Ask a question, or tap 🎙 to speak…'; };
  rec.onerror = () => { listening = false; $('chat-mic').textContent = '🎙'; toast('Mic unavailable.'); };
  rec.onresult = (e) => { $('chat-input').value = e.results[0][0].transcript; sendChat(); };
}

/* ---------------- progress sidebar ---------------- */
async function loadProgress() {
  const p = await api('/api/learning/progress');
  if (!p) { if (window.__needAuth) $('jarvis').innerHTML = `Sign in at <a href='/console' style='color:var(--violet,#a78bfa)'>the console</a> to start learning.`; return; }
  PROG = p;
  if ($('modes').innerHTML) renderModes();
  const r = p.realm || {};
  $('realm-name').textContent = r.realm_name || 'Mortal';
  // Job-field rank (junior … head of security) vs cultivation layer.
  const jr = p.rank;
  if (jr) {
    const toNext = jr.next_rank ? ` · ${jr.points_to_next} pts → ${esc(jr.next_rank)}` : ' · top role';
    $('rank-title').innerHTML = `🎖 <b>${esc(jr.rank)}</b> <span class='muted'>(${esc(jr.difficulty)})</span>` +
      `<span class='muted' style='display:block; font-size:10px'>${esc(r.rank_title || '')} · ${esc(r.layer_label || '')}${toNext}</span>`;
  } else {
    $('rank-title').textContent = `${r.rank_title || ''} · ${r.layer_label || ''}`;
  }
  countUp($('stones'), Number(r.stones) || 0, (x) => `${Math.round(x).toLocaleString()} ◈`);
  $('next-realm').textContent = r.next_realm ? `${r.stones_to_next} ◈ to ${r.next_realm}` : 'max realm';
  $('realm-prog').style.width = Math.round((r.progress || 0) * 100) + '%';
  // streak
  const sN = $('streak-n'), sBox = $('streak');
  sN.textContent = `${p.streak || 0}-day streak`;
  sBox.classList.toggle('cold', !p.streak);
  $('streak-sub').textContent = p.streak ? `Best: ${p.max_streak} · ${p.freezes} freeze${p.freezes === 1 ? '' : 's'}` : 'Learn today to start one.';
  // chest
  const chest = $('chest');
  chest.style.display = p.pending_chests ? 'block' : 'none';
  chest.textContent = `🎁 Open ${p.pending_chests} mystery chest${p.pending_chests === 1 ? '' : 's'}`;
  // quests
  $('quests').innerHTML = (p.daily_quests || []).map((q) =>
    `<li class='${q.done ? 'done' : ''}'><span class='box'>${q.done ? '✓' : ''}</span><span>${esc(q.desc)} (+${q.reward} ◈)</span></li>`).join('')
    || `<li class='muted'>No quests today.</li>`;
  // track levels with rings
  $('track-levels').innerHTML = Object.entries(p.track_levels || {}).map(([tid, lv]) => {
    const t = TRACKS.find((x) => x.id === tid); if (!t) return '';
    return `<div class='tlvl-row'><div class='ring2' style='--p:${lv.progress_pct}'><b>${lv.level}</b></div>
      <div><div>${esc(t.title)}</div><div class='muted' style='font-size:11px'>Lv ${lv.level} · avg ${lv.avg_score}%</div></div></div>`;
  }).join('') || `<div class='muted'>Complete lessons to level up tracks.</div>`;
  // per-domain mastery (CORE 6) — web vs AD vs cloud, tracked independently
  const dm = (p.domain_mastery && p.domain_mastery.domains) || [];
  const shown = dm.filter((d) => d.points > 0);
  $('domain-mastery').innerHTML = (shown.length ? shown : dm.slice(0, 4)).map((d) => {
    const pct = Math.min(100, d.points);
    return `<div class='dm-row' title='${esc(d.band)}'><div class='dm-name'>${esc(d.domain)}</div>
      <div class='dm-bar'><span style='width:${pct}%'></span></div>
      <div class='dm-pts'>${d.points}</div></div>`;
  }).join('') || `<div class='muted'>Practice to build domain mastery.</div>`;
  // badges
  $('badge-count').textContent = `${p.earned_badges}/${(p.badges || []).length}`;
  $('badges').innerHTML = (p.badges || []).map((b) =>
    `<div class='badge ${b.earned ? 'earned' : ''}' title='${esc(b.desc)}'><span class='ico'>${b.earned ? '🏅' : '🔒'}</span>${esc(b.name)}</div>`).join('');
  $('chest').onclick = openChest;
}

async function openChest() {
  const res = await post('/api/learning/chest/open', {});
  if (!res || res.error) return toast(errText(res));
  celebrate(res.rarity === 'legendary' ? '💎' : res.rarity === 'rare' ? '🔮' : '🎁',
    `${res.rarity[0].toUpperCase() + res.rarity.slice(1)} chest!`, `+${res.stones} spirit stones ◈`);
  loadProgress();
}

/* ---------------- profile ---------------- */
async function loadProfile() {
  const p = await api('/api/learning/profile'); if (!p) return;
  const tags = (arr) => (arr || []).map((x) => `<span class='tag'>${esc(x)}</span>`).join('') || `<span class='muted'>—</span>`;
  $('profile').innerHTML = `
    <div>${esc(p.style_summary || 'The AI is still learning how you learn — keep going and it will adapt.')}</div>
    <div style='margin-top:8px'><b>Strengths:</b><br>${tags(p.strengths)}</div>
    <div style='margin-top:6px'><b>Working on:</b><br>${tags(p.gaps)}</div>
    <div style='margin-top:6px'><b>Goals:</b><br>${tags(p.goals)}</div>`;
}
$('edit-profile').onclick = async () => {
  const p = await api('/api/learning/profile') || {};
  const goals = prompt('Your learning goals (comma-separated):', (p.goals || []).join(', '));
  if (goals === null) return;
  const style = prompt('How do you learn best? (a sentence the tutor should follow)', p.style_summary || '');
  const res = await putJson('/api/learning/profile', {
    goals: goals.split(',').map((s) => s.trim()).filter(Boolean),
    style_summary: style || p.style_summary || '',
  });
  if (res) { toast('Profile updated — lessons will adapt.', true); loadProfile(); }
};
// The profile setter is a PUT (operator-gated); lib's post() is POST, so use a small wrapper.
async function putJson(path, body) {
  try { const r = await fetch(path, { method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() }, body: JSON.stringify(body) });
    if (r.status === 401) { window.__needAuth = true; return null; } return await r.json(); } catch (_) { return null; }
}

/* ---------------- test-out / placement ---------------- */
async function startTestOut(topic) {
  $('work-title').textContent = `Test out · ${topic}`; $('work-sub').textContent = 'Pass to skip this topic';
  $('work').innerHTML = `<div class='muted'>Building a challenge to verify your mastery…</div>`;
  const res = await post('/api/learning/placement', { track: curTrack.id, topic, n: 6 });
  if (!res || res.error) return showErr(res);
  const qs = res.questions || []; const picks = {};
  $('work').innerHTML = `<div class='muted' style='margin-bottom:8px'>Score ${res.pass_mark}%+ to test out and skip <b>${esc(topic)}</b>.</div>` +
    qs.map((q, i) => `<div class='qz-q' data-q='${i}'><div class='stem'>${i + 1}. ${esc(q.q)}</div>
      ${q.choices.map((c, j) => `<label class='qz-opt' data-i='${i}' data-j='${j}'>${esc(c)}</label>`).join('')}</div>`).join('') +
    `<div class='actions'><button class='btn primary' id='submit-to'>Submit</button></div>`;
  $('work').querySelectorAll('.qz-opt').forEach((o) => o.onclick = () => {
    picks[o.dataset.i] = +o.dataset.j;
    o.parentElement.querySelectorAll('.qz-opt').forEach((x) => x.classList.remove('sel'));
    o.classList.add('sel');
  });
  $('submit-to').onclick = async () => {
    const answers = qs.map((_, i) => (i in picks ? picks[i] : -1));
    const g = await post('/api/learning/placement/grade', { quiz_id: res.quiz_id, answers });
    if (!g || g.error) return showErr(g);
    const head = g.passed
      ? `<div class='glass' style='padding:14px; text-align:center'><div style='font-size:22px; font-weight:800'>✓ Tested out — ${g.score}%</div><div class='muted'>${esc(topic)} marked mastered · +${g.awarded} ◈</div></div>`
      : `<div class='glass' style='padding:14px; text-align:center'><div style='font-size:22px; font-weight:800'>${g.score}%</div><div class='muted'>Not yet (need ${g.pass_mark}%). Study it, then retry.</div></div>`;
    $('work').innerHTML = head;
    if (g.passed) celebrate('⚡', 'Tested out!', `${esc(topic)} · +${g.awarded} ◈`);
    await loadTracks(); loadProgress();
  };
}

/* ---------------- pentest range ---------------- */
let curRange = null;
async function startRange() {
  $('work-title').textContent = 'Pentest Range'; $('work-sub').textContent = curTrack.title;
  $('work').innerHTML = `<div class='muted'>🎯 Spinning up a simulated network…</div>`;
  const r = await post('/api/learning/range', { track: curTrack.id });
  if (!r || r.error) return showErr(r);
  curRange = r; renderRange();
}
function renderRange() {
  const r = curRange; if (!r) return;
  const obj = r.objective;
  const hostCard = (h) => {
    const tag = h.compromised ? `<span class='pill' style='background:#16341f'>owned · ${esc(h.access_level || '')}</span>`
      : h.reachable ? `<span class='pill'>reachable</span>` : `<span class='pill muted'>locked</span>`;
    let acts = '';
    if (!h.reachable) acts = `<div class='muted' style='font-size:11px'>Compromise a host that pivots here to unlock.</div>`;
    else if (!h.enumerated) acts = `<button class='btn' data-act='enum' data-h='${esc(h.id)}'>🔍 Enumerate</button>`;
    else if (!h.compromised) acts = `<div class='mini-form'><textarea class='finding' data-plan='${esc(h.id)}' placeholder='How would you exploit this host? (vuln + specific path)'></textarea>
      <textarea class='finding' data-evidence='${esc(h.id)}' placeholder='Proof of work: payload/command used, request sent, response observed, data extracted'></textarea>
      <div class='actions'><button class='btn primary' data-act='exploit' data-h='${esc(h.id)}'>💥 Exploit</button>
      <button class='btn' data-act='hint' data-h='${esc(h.id)}'>💡 Hint</button></div></div>`;
    else acts = `<div class='actions'>
        ${h.escalated ? `<span class='pill' style='background:#2a2440'>rooted</span>` : `<button class='btn' data-act='escalate' data-h='${esc(h.id)}'>⬆ Privesc</button>`}
        ${h.persisted ? `<span class='pill' style='background:#2a2440'>persisted</span>` : `<button class='btn' data-act='persist' data-h='${esc(h.id)}'>📌 Persist</button>`}
        <button class='btn' data-act='hint' data-h='${esc(h.id)}'>💡 Hint</button></div>`;
    const svc = h.services ? `<div class='muted' style='font-size:11px'>${h.services.map((s) => `${esc(s.name || '')}:${esc(String(s.port || ''))}`).join(' · ')}</div>` : '';
    const enumHint = h.enum_hint ? `<div class='muted' style='font-size:11px'>📋 ${esc(h.enum_hint)}</div>` : '';
    const loot = h.loot ? `<div style='font-size:11px; color:var(--gold,#e9c46a)'>💰 ${esc(h.loot)}</div>` : '';
    return `<div class='range-host'><div class='section-h'><b>${esc(h.hostname)}</b> ${tag} <span class='muted' style='font-size:11px'>${esc(h.kind)} · ${esc(h.ip || '')}</span></div>
      ${svc}${enumHint}${loot}${acts}</div>`;
  };
  $('work').innerHTML = `<div style='font-size:13px'>${esc(r.scenario || '')}</div>
    ${obj ? `<div class='glass' style='padding:10px; margin:10px 0'>🎯 <b>Objective:</b> ${esc(obj.goal)} ${obj.captured ? '<span class="pill" style="background:#16341f">captured</span>' : ''}</div>` : ''}
    <div class='muted' style='font-size:11px; margin-bottom:8px'>Owned ${r.owned}/${r.total}${r.cleared ? ' · range cleared 🏆' : ''}</div>
    <div class='range-grid'>${r.hosts.map(hostCard).join('')}</div>
    ${obj && !obj.captured ? `<div class='mini-form' style='margin-top:12px'><textarea class='finding' id='cap-sub' placeholder='Extract the objective from ${esc(obj.target_host)} and paste it here'></textarea>
      <div class='actions'><button class='btn gold' id='cap-btn'>🏴 Capture objective</button></div></div>` : ''}`;
  $('work').querySelectorAll('[data-act]').forEach((b) => b.onclick = () => rangeAction(b.dataset.act, b.dataset.h));
  if ($('cap-btn')) $('cap-btn').onclick = rangeCapture;
}
async function rangeAction(act, hostId) {
  if (act === 'enum') {
    const r = await post('/api/learning/range/enumerate', { range_id: curRange.range_id, host_id: hostId });
    if (!r || r.error) return toast(errText(r));
  } else if (act === 'exploit' || act === 'escalate' || act === 'persist') {
    const ta = $('work').querySelector(`[data-plan='${hostId}']`);
    const plan = act === 'exploit' ? (ta ? ta.value.trim() : '') : prompt(act === 'escalate' ? 'How do you escalate to root/admin here?' : 'How do you establish persistence here?') || '';
    if (!plan) return;
    const ep = { exploit: 'exploit', escalate: 'escalate', persist: 'persist' }[act];
    const evEl = $('work').querySelector(`[data-evidence='${hostId}']`);
    const body = act === 'exploit' ? { range_id: curRange.range_id, host_id: hostId, finding: plan, evidence: evEl ? evEl.value.trim() : '' }
      : { range_id: curRange.range_id, host_id: hostId, plan };
    toast('Grading your tradecraft…', true);
    const r = await post(`/api/learning/range/${ep}`, body);
    if (!r || r.error) return toast(errText(r));
    const ok = r.compromised || r.escalated || r.persisted;
    toast(`${r.score}% — ${ok ? 'success' : 'not yet'}. ${r.feedback || ''}`, ok);
    if (r.tradecraft) setTimeout(() => toast('Tradecraft: ' + r.tradecraft), 400);
    loadProgress();
  } else if (act === 'hint') {
    const stage = prompt('What are you stuck on? (enumerate / exploit / privesc / persistence / pivot)', 'exploit') || '';
    const r = await post('/api/learning/range/hint', { range_id: curRange.range_id, host_id: hostId, stage });
    if (!r || r.error) return toast(errText(r));
    return toast('💡 ' + r.hint);
  }
  // refresh range state
  const st = await api(`/api/learning/range/${curRange.range_id}`);
  if (st && !st.error) { curRange = st; renderRange(); }
}
async function rangeCapture() {
  const sub = ($('cap-sub') && $('cap-sub').value.trim()) || '';
  if (!sub) return toast('Paste what you extracted from the target.');
  const r = await post('/api/learning/range/capture', { range_id: curRange.range_id, submission: sub });
  if (!r || r.error) return toast(errText(r));
  if (r.captured) { celebrate('🏴', 'Objective captured!', `+${r.awarded || 0} ◈`); }
  else toast(r.hint || 'Not the objective data — keep looking.');
  const st = await api(`/api/learning/range/${curRange.range_id}`);
  if (st && !st.error) { curRange = st; renderRange(); }
  loadProgress();
}

/* ---------------- blue-team incident ---------------- */
async function startIncident() {
  $('work-title').textContent = 'Incident Investigation'; $('work-sub').textContent = 'Scope the compromise';
  $('work').innerHTML = `<div class='muted'>🛡 Pulling the alert and logs…</div>`;
  const r = await post('/api/learning/incident', { track: curTrack.id });
  if (!r || r.error) return showErr(r);
  $('work').innerHTML = `<div class='glass' style='padding:10px; margin-bottom:10px'>🚨 <b>${esc(r.tool || 'Alert')}:</b> ${esc(r.alert)}</div>
    <div class='muted' style='font-size:12px; margin-bottom:6px'>${esc(r.goal)}</div>
    <div class='lab-art'>${esc(r.artifacts)}</div>
    <div class='mini-form'><textarea class='finding' id='inc-find' placeholder='Entry vector, every compromised device, lateral path, and exactly what was exfiltrated — cite the evidence.'></textarea>
    <div class='actions'><button class='btn primary' id='inc-submit'>Submit investigation</button></div></div>`;
  $('inc-submit').onclick = async () => {
    const findings = $('inc-find').value.trim();
    $('inc-submit').disabled = true; $('inc-submit').textContent = 'Grading…';
    const g = await post('/api/learning/incident/grade', { incident_id: r.incident_id, findings });
    if (!g || g.error) { $('inc-submit').disabled = false; $('inc-submit').textContent = 'Submit investigation'; return showErr(g); }
    const gt = g.ground_truth || {};
    $('work').insertAdjacentHTML('afterbegin', `<div class='glass' style='padding:14px; margin-bottom:12px; text-align:center'>
      <div style='font-size:22px; font-weight:800'>${g.score}% ${g.solved ? '✓' : ''}</div>
      <div class='muted'>${esc(g.feedback || '')} · +${g.awarded} ◈</div></div>`);
    $('work').insertAdjacentHTML('beforeend', `<details style='margin-top:10px'><summary class='muted'>Ground truth</summary>
      <div style='font-size:12px'>Entry: ${esc(gt.entry_vector || '')}<br>Compromised: ${esc((gt.compromised || []).join(', '))}<br>Exfiltration: ${esc(gt.exfiltration || '')}</div></details>`);
    $('inc-submit').remove();
    if (g.solved) celebrate('🛡', 'Scoped it!', `${g.score}% · +${g.awarded} ◈`);
    loadProgress();
  };
}

/* ---------------- language drills ---------------- */
async function startDrill() {
  const kind = (prompt('Drill type: "cloze" (fill-in) or "translate"', 'cloze') || 'cloze').trim();
  const topic = curTopic || (curTrack.topics[0] || 'Vocabulary');
  $('work-title').textContent = `Drill · ${kind}`; $('work-sub').textContent = topic;
  $('work').innerHTML = `<div class='muted'>Writing your ${esc(kind)} drill…</div>`;
  const r = await post('/api/learning/drill', { track: curTrack.id, topic, kind, n: 6 });
  if (!r || r.error) return showErr(r);
  const items = r.items || [];
  $('work').innerHTML = items.map((it, i) => `<div class='qz-q'><div class='stem'>${i + 1}. ${esc(it.prompt)}</div>
      <input class='finding' data-drill='${i}' placeholder='your answer' style='min-height:auto; height:auto' autocomplete='off'>
      ${it.hint ? `<div class='muted' style='font-size:11px'>💡 ${esc(it.hint)}</div>` : ''}</div>`).join('') +
    `<div class='actions'><button class='btn primary' id='drill-submit'>Check answers</button></div>`;
  $('drill-submit').onclick = async () => {
    const answers = items.map((_, i) => { const el = $('work').querySelector(`[data-drill='${i}']`); return el ? el.value : ''; });
    const g = await post('/api/learning/drill/grade', { drill_id: r.drill_id, answers });
    if (!g || g.error) return showErr(g);
    g.per_item.forEach((p, i) => {
      const row = $('work').querySelectorAll('.qz-q')[i];
      const el = row.querySelector(`[data-drill='${i}']`); if (el) el.disabled = true;
      row.insertAdjacentHTML('beforeend', `<div class='qz-exp ${p.correct ? 'right' : 'wrong'}'>${p.correct ? '✓' : '✗ ' + esc(p.answer)} ${esc(p.explain || '')}</div>`);
    });
    $('drill-submit').remove();
    $('work').insertAdjacentHTML('afterbegin', `<div class='glass' style='padding:12px; margin-bottom:10px; text-align:center'><div style='font-size:20px; font-weight:800'>${g.score}%</div><div class='muted'>${g.correct}/${g.total} · +${g.awarded} ◈</div></div>`);
    loadProgress();
  };
}

/* ---------------- skill path (DAG) ---------------- */
async function openSkills() {
  $('work-title').textContent = 'Skill Path'; $('work-sub').textContent = 'Prerequisites unlock as you master domains';
  $('work').innerHTML = `<div class='muted'>Loading the skill graph…</div>`;
  const r = await api('/api/learning/skills');
  const nodes = (r && r.skills) || [];
  if (!nodes.length) { $('work').innerHTML = `<div class='muted'>No skill graph configured.</div>`; return; }
  $('work').innerHTML = `<div class='muted' style='margin-bottom:8px'>${r.mastered}/${r.total} skills mastered. No skipping prerequisites — locked skills need the ones they depend on first.</div>` +
    nodes.map((n) => {
      const state = n.mastered ? '✅' : n.available ? '🔓' : '🔒';
      const cls = n.mastered ? 'sk-done' : n.available ? 'sk-open' : 'sk-locked';
      const need = (!n.unlocked && n.missing_prereqs.length) ? `<div class='muted' style='font-size:11px'>needs: ${esc(n.missing_prereqs.join(', '))}</div>` : '';
      return `<div class='sk-node ${cls}'><div>${state} <b>${esc(n.name)}</b> <span class='muted' style='font-size:11px'>${esc(n.domain)}</span></div>${need}</div>`;
    }).join('');
}

/* ---------------- cyber range (VM control plane) ---------------- */
async function openRangeInfra() {
  $('work-title').textContent = 'Cyber Range'; $('work-sub').textContent = 'Launch real VM labs (when infrastructure is connected)';
  $('work').innerHTML = `<div class='muted'>Checking infrastructure…</div>`;
  const r = await api('/api/range-infra/labs');
  if (!r) return showErr(r);
  const infra = r.infrastructure || {};
  const live = r.live;
  // Honest banner: green only when a real provider reports ok.
  const banner = live
    ? `<div class='glass' style='padding:10px; margin-bottom:10px; border-left:3px solid #34d399'>✅ Infrastructure connected (${esc(infra.provider || '')}).</div>`
    : `<div class='glass' style='padding:12px; margin-bottom:10px; border-left:3px solid #fbbf24'>
        ⚠ <b>Infrastructure not connected yet.</b> ${esc(infra.detail || '')}<br>
        <span class='muted' style='font-size:11px'>The control plane is ready; connect a hypervisor (see docs/CYBER_RANGE_DEPLOYMENT.md) to launch real VMs. Labs below are definitions — launching reports an honest "unavailable" until a provider is live.</span></div>`;
  const labs = r.labs || [];
  $('work').innerHTML = banner + (labs.length ? labs.map((l) => `
    <div class='range-host'>
      <div class='section-h'><b>${esc(l.name)}</b> <span class='pill ${live ? '' : 'muted'}'>${esc(l.difficulty || '')}</span></div>
      <div class='muted' style='font-size:11px'>attacker: ${esc(l.attacker_vm || '')} · targets: ${esc((l.target_vms || []).join(', '))} · ${l.duration_minutes || '?'} min</div>
      <div class='actions'><button class='btn ${live ? 'primary' : ''}' data-launch='${esc(l.lab_id)}'>${live ? '▶ Launch' : '▶ Launch (unavailable)'}</button></div>
      <div class='muted' id='ll-${esc(l.lab_id)}' style='font-size:11px'></div>
    </div>`).join('') : `<div class='muted'>No labs defined.</div>`)
    + `<div class='muted' style='font-size:11px; margin-top:8px'>Active sessions: <span id='infra-sessions'>—</span></div>`;
  $('work').querySelectorAll('[data-launch]').forEach((b) => b.onclick = async () => {
    const id = b.dataset.launch;
    const out = $('ll-' + id); out.textContent = 'Requesting… (provisioning VMs can take a while)';
    const res = await post('/api/range-infra/launch', { lab_id: id });
    // Honest rendering: success only when a real session is returned; otherwise show the reason.
    if (res && res.ok && res.session) {
      const s = res.session;
      let html = `✅ session ${esc(s.id)} · ${esc(s.status)}`;
      if (s.connect_url) {
        // A real Guacamole connection exists — offer to open it (no raw VM IPs).
        html += ` <button class='btn primary' data-open='${esc(s.connect_url)}'>🖥 Open Browser Lab</button>`;
      } else {
        html += ` <span class='muted'>· running, no browser console (${esc(res.detail || 'Guacamole not configured')})</span>`;
      }
      out.innerHTML = html;
      const ob = out.querySelector('[data-open]');
      if (ob) ob.onclick = () => openBrowserLab(ob.dataset.open, out);
    } else {
      out.innerHTML = `⚠ ${esc((res && res.detail) || 'unavailable')} <span class='muted'>(no VM launched)</span>`;
    }
    refreshInfraSessions();
  });
  refreshInfraSessions();
}
async function refreshInfraSessions() {
  const el = $('infra-sessions'); if (!el) return;
  const s = await api('/api/range-infra/sessions');
  el.textContent = s ? String(s.count || 0) : '—';
}
async function openBrowserLab(connectUrl, out) {
  // Resolve the signed broker link into real Guacamole console URLs, then open.
  const prev = out.innerHTML; out.innerHTML = 'Opening console…';
  const r = await api(connectUrl);
  if (!r || !r.ok || !(r.connections || []).length) {
    out.innerHTML = prev + ` <span class='muted'>⚠ ${esc((r && r.detail) || 'could not open console')}</span>`;
    return;
  }
  // open the attacker box (or the first connection) in a new tab
  const att = r.connections.find((c) => c.role === 'attacker') || r.connections[0];
  window.open(att.url, '_blank', 'noopener');
  out.innerHTML = prev + ` <span class='muted'>· opened ${esc(att.role)} (${esc(att.protocol)})</span>`;
}

/* ---------------- bring-your-own material (RAG) ---------------- */
async function openMaterial() {
  $('work-title').textContent = 'My Material'; $('work-sub').textContent = 'Ground lessons in your own notes';
  const cur = await api(`/api/learning/material?track=${encodeURIComponent(curTrack.id)}`);
  const present = cur && cur.present;
  $('work').innerHTML = `<div style='font-size:13px; margin-bottom:8px'>Paste your own notes or document text. Lessons, quizzes and exams for <b>${esc(curTrack.title)}</b> will be grounded in it.</div>
    ${present ? `<div class='muted' style='font-size:12px; margin-bottom:6px'>Current: <b>${esc(cur.name)}</b> (${cur.chars} chars) <button class='btn' id='mat-clear' style='padding:2px 8px; font-size:11px'>remove</button></div>` : ''}
    <input id='mat-name' class='finding' placeholder='Name (e.g. "ACME runbook")' style='min-height:auto; height:auto; margin-bottom:6px' autocomplete='off'>
    <textarea class='finding' id='mat-text' placeholder='Paste your material here…' style='min-height:160px'></textarea>
    <div class='actions'><button class='btn primary' id='mat-save'>Save material</button></div>`;
  $('mat-save').onclick = async () => {
    const text = $('mat-text').value.trim(); if (!text) return toast('Paste some text first.');
    const r = await post('/api/learning/material', { track: curTrack.id, text, name: $('mat-name').value.trim() });
    if (!r || r.error) return toast(errText(r));
    toast(`Saved ${r.chars} chars — lessons will use it.`, true); await loadTracks(); openMaterial();
  };
  if ($('mat-clear')) $('mat-clear').onclick = async () => {
    await api(`/api/learning/material?track=${encodeURIComponent(curTrack.id)}`, { method: 'DELETE' });
    toast('Material removed.', true); await loadTracks(); openMaterial();
  };
}

/* ---------------- helpers + boot ---------------- */
function errText(res) {
  const e = res && res.error;
  if (e === 'no_backend') return 'No AI member is configured. Add one (Claude or a local model) in Sect Members to enable the tutor.';
  return e || 'Something went wrong.';
}
function showErr(res) { $('work').innerHTML = `<div class='muted'>⚠ ${esc(errText(res))}</div>`; }

async function loadTracks() {
  const res = await api('/api/learning/tracks');
  if (!res) { if (window.__needAuth) $('jarvis').innerHTML = `Sign in at <a href='/console' style='color:var(--violet,#a78bfa)'>the console</a> to start learning.`; return; }
  TRACKS = res.tracks || [];
  renderTracks();
  if (!curTrack && TRACKS.length) selectTrack(TRACKS[0].id);
}

setInterval(() => { $('clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }, 1000);
$('clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

(async () => { await loadTracks(); loadProgress(); loadProfile(); })();
liveStream((t) => { if (['agents', 'command', 'tick'].includes(t)) debounce(() => loadProgress()); });
