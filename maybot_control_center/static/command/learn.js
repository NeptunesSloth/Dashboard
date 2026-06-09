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
  const m = [
    ['review', `🔁 Review${due ? `<span class='pill'>${due}</span>` : ''}`],
    ['exam', '📝 Practice Exam'],
    ['real', '🖥 Real Log Lab'],
    ['library', '📂 Library'],
  ];
  $('modes').innerHTML = m.map(([k, lbl]) => `<button class='mode-btn' data-mode='${k}'>${lbl}</button>`).join('');
  $('modes').querySelectorAll('.mode-btn').forEach((b) => b.onclick = () => {
    if (examTimer) { clearInterval(examTimer); examTimer = null; }
    ({ review: startReview, exam: startExam, real: startRealLab, library: openLibrary }[b.dataset.mode])();
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
  $('topics').innerHTML = curTrack.topics.map((tp) =>
    `<button class='topic-btn ${curTrack.completed_topics.includes(tp) ? 'done' : ''}' data-tp='${esc(tp)}'>${esc(tp)}</button>`).join('');
  $('topics').querySelectorAll('.topic-btn').forEach((b) => b.onclick = () => loadLesson(b.dataset.tp));
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
    <textarea class='finding' id='finding' placeholder='${placeholder}'></textarea>
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
    <select id='src' class='finding' style='min-height:auto; height:auto'>
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

/* ---------------- tutor chat ---------------- */
async function sendChat() {
  const inp = $('chat-input'); const q = inp.value.trim();
  if (!q) return;
  if (!curTrack) return toast('Pick a track first.');
  inp.value = '';
  chatHistory.push({ role: 'user', content: q });
  $('chat').insertAdjacentHTML('beforeend', `<div class='bub you'>${esc(q)}</div>`);
  $('chat').insertAdjacentHTML('beforeend', `<div class='bub ai' id='pending'>…</div>`);
  $('chat').scrollTop = $('chat').scrollHeight;
  const res = await post('/api/learning/ask', { track: curTrack.id, question: q, history: chatHistory.slice(0, -1) });
  $('pending')?.remove();
  if (!res || res.error) { $('chat').insertAdjacentHTML('beforeend', `<div class='bub ai'>⚠ ${esc(errText(res))}</div>`); return; }
  chatHistory.push({ role: 'assistant', content: res.answer });
  $('chat').insertAdjacentHTML('beforeend', `<div class='bub ai'>${esc(res.answer)}</div>`);
  $('chat').scrollTop = $('chat').scrollHeight;
  loadProgress();
}
$('chat-send').onclick = sendChat;
$('chat-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendChat(); });

/* ---------------- progress sidebar ---------------- */
async function loadProgress() {
  const p = await api('/api/learning/progress');
  if (!p) { if (window.__needAuth) $('jarvis').innerHTML = `Sign in at <a href='/console' style='color:var(--violet,#a78bfa)'>the console</a> to start learning.`; return; }
  PROG = p;
  if ($('modes').innerHTML) renderModes();
  const r = p.realm || {};
  $('realm-name').textContent = r.realm_name || 'Mortal';
  $('rank-title').textContent = `${r.rank_title || ''} · ${r.layer_label || ''}`;
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
