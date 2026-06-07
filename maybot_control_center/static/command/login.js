import { $, esc, starfield } from '/lib.js';

starfield('scene-canvas');
const TOKEN_KEY = 'maybot.control_token';
const body = $('login-body');

async function post(path, payload) {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const j = await r.json().catch(() => ({}));
  return { ok: r.ok, status: r.status, j };
}
function finish(session) {
  if (session) localStorage.setItem(TOKEN_KEY, session);
  location.href = '/';
}
const field = (id, label, type, ph) =>
  `<label class='lf-label'>${esc(label)}</label><input class='lf-input' id='${id}' type='${type}' placeholder='${esc(ph || '')}' autocomplete='${type === 'password' ? 'current-password' : 'username'}'>`;

function loginView() {
  body.innerHTML = `
    <h2 class='login-h'>Sign in</h2>
    ${field('lf-name', 'Name', 'text', 'your account name')}
    ${field('lf-pass', 'Password', 'password', '••••••••')}
    <button class='lf-btn' id='lf-go'>Sign in</button>
    <div class='lf-err' id='lf-err'></div>`;
  const go = $('lf-go'), err = $('lf-err');
  const submit = async () => {
    err.textContent = ''; go.disabled = true;
    const { ok, j } = await post('/api/login', { name: $('lf-name').value.trim(), password: $('lf-pass').value });
    go.disabled = false;
    if (ok && j.session) return finish(j.session);
    if (j && j.pending_2fa) return twoFAView(j.challenge, j.channel);
    err.textContent = (j && j.detail) || 'Invalid name or password.';
  };
  go.onclick = submit;
  body.querySelectorAll('input').forEach((i) => i.onkeydown = (e) => { if (e.key === 'Enter') submit(); });
  $('lf-name').focus();
}

function twoFAView(challenge, channel) {
  body.innerHTML = `
    <h2 class='login-h'>Two-factor code</h2>
    <p class='muted' style='margin:0 0 10px'>We sent a 6-digit code to your <b>${esc(channel || 'notification')}</b> channel. Enter it to continue.</p>
    ${field('lf-code', 'Code', 'text', '000000')}
    <button class='lf-btn' id='lf-go'>Verify</button>
    <button class='lf-link' id='lf-back'>← back</button>
    <div class='lf-err' id='lf-err'></div>`;
  const go = $('lf-go'), err = $('lf-err');
  const submit = async () => {
    err.textContent = ''; go.disabled = true;
    const { ok, j } = await post('/api/login/2fa', { challenge, code: $('lf-code').value.trim() });
    go.disabled = false;
    if (ok && j.session) return finish(j.session);
    err.textContent = (j && j.detail) || 'Invalid or expired code.';
  };
  go.onclick = submit;
  $('lf-back').onclick = loginView;
  $('lf-code').onkeydown = (e) => { if (e.key === 'Enter') submit(); };
  $('lf-code').focus();
}

function signupView() {
  body.innerHTML = `
    <h2 class='login-h'>Claim your dashboard</h2>
    <p class='muted' style='margin:0 0 12px'>No accounts exist yet. Create the first <b>operator</b> account — you'll own and control the sect.</p>
    ${field('lf-name', 'Name', 'text', 'e.g. you')}
    ${field('lf-pass', 'Password', 'password', 'at least 8 characters')}
    ${field('lf-pass2', 'Confirm password', 'password', 'repeat password')}
    <button class='lf-btn' id='lf-go'>Create account</button>
    <div class='lf-err' id='lf-err'></div>`;
  const go = $('lf-go'), err = $('lf-err');
  const submit = async () => {
    err.textContent = '';
    const pw = $('lf-pass').value, pw2 = $('lf-pass2').value;
    if (pw.length < 8) { err.textContent = 'Password must be at least 8 characters.'; return; }
    if (pw !== pw2) { err.textContent = 'Passwords do not match.'; return; }
    go.disabled = true;
    const { ok, j } = await post('/api/signup', { name: $('lf-name').value.trim(), password: pw });
    go.disabled = false;
    if (ok && j.session) return finish(j.session);
    err.textContent = (j && j.detail) || 'Could not create the account.';
  };
  go.onclick = submit;
  body.querySelectorAll('input').forEach((i) => i.onkeydown = (e) => { if (e.key === 'Enter') submit(); });
  $('lf-name').focus();
}

async function boot() {
  let me = {};
  try { me = await fetch('/api/account/me', { headers: { 'x-control-token': localStorage.getItem(TOKEN_KEY) || '' } }).then((r) => r.json()); } catch (_) {}
  if (me.authed && me.auth_active) { location.href = '/'; return; }   // already signed in
  if (me.accounts_exist) loginView();
  else signupView();                                                   // fresh install → claim it
}
boot();
