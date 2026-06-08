"""Authorization: token->role (RBAC) + a simple rate limiter.

Backward compatible: with no ``users.yaml`` the control center behaves exactly
as before — a single ``MAYBOT_CONTROL_CENTER_TOKEN`` grants operator access (or
open access if that's unset). Add a users file to get per-token roles:

    users:
      - {name: alice, token: "<secret>", role: operator}
      - {name: bob,   token: "<secret>", role: viewer}

Viewers can read (GET); operators can also mutate (actions, tasks, missions,
tools, autonomy). Rate limiting is a fixed-window counter per client key.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import threading
import time
from pathlib import Path

import yaml

from .config import CONTROL_CENTER_TOKEN
from . import store

USERS_FILE = Path(os.getenv("MAYBOT_USERS_FILE", "users.yaml"))
RATE = int(os.getenv("MAYBOT_RATE_LIMIT", "240"))   # requests per window per key (0 = off)
WINDOW = int(os.getenv("MAYBOT_RATE_WINDOW", "60"))  # seconds
# Login-issued session tokens expire after this many minutes (0 = no expiry).
SESSION_TTL_MINUTES = float(os.getenv("MAYBOT_SESSION_TTL_MINUTES", "720"))
# Opt-in: when no accounts/token are configured, deny instead of granting open
# operator access (forces creating the first account). Default off (open).
REQUIRE_AUTH = os.getenv("MAYBOT_REQUIRE_AUTH", "").lower() in ("1", "true", "yes", "on")

LOGIN_MAX_FAILS = int(os.getenv("MAYBOT_LOGIN_MAX_FAILS", "8"))   # failed sign-ins before lockout
LOGIN_LOCK_WINDOW = int(os.getenv("MAYBOT_LOGIN_LOCK_WINDOW", "300"))  # seconds

_lock = threading.Lock()
_buckets: dict[str, tuple[float, int]] = {}
_login_fails: dict[str, tuple[float, int]] = {}
# session id -> {"role", "name", "projects", "expires"} (expires=None never lapses)
_sessions: dict[str, dict] = {}
# pending 2FA challenge id -> {"name", "code", "expires", "tries"}
_challenges: dict[str, dict] = {}


# ---- password hashing (PBKDF2-HMAC-SHA256, stdlib only) -------------------
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", (pw or "").encode(), salt, 200_000)
    return "pbkdf2$200000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = (stored or "").split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", (pw or "").encode(), base64.b64decode(salt_b64), int(iters))
        return secrets.compare_digest(dk, base64.b64decode(hash_b64))
    except Exception:
        return False


def load_users() -> list[dict]:
    if not USERS_FILE.exists():
        return []
    try:
        data = yaml.safe_load(USERS_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    users = data.get("users", [])
    return users if isinstance(users, list) else []


def user_by_name(name: str) -> dict | None:
    return next((u for u in load_users() if u.get("name") == name), None)


def save_users(users: list[dict]) -> None:
    """Persist accounts to users.yaml (atomic). Managed from Ops -> Accounts."""
    clean: list[dict] = []
    for u in users:
        if not isinstance(u, dict) or not u.get("name") or not u.get("token"):
            continue
        e = {"name": str(u["name"]), "token": str(u["token"]),
             "role": u.get("role") if u.get("role") in ("operator", "viewer") else "viewer"}
        if u.get("projects"):
            e["projects"] = list(u["projects"])
        if u.get("pw"):
            e["pw"] = str(u["pw"])
        if u.get("tfa"):
            e["tfa"] = True
        if u.get("totp"):
            e["totp"] = str(u["totp"])
        clean.append(e)
    header = ("# users.yaml — dashboard accounts (managed from Ops -> Accounts).\n"
              "# Each token grants its role (operator can mutate, viewer is read-only).\n"
              "# 'pw' is a salted PBKDF2 hash; never store plaintext. Keep this file secret.\n")
    text = header + yaml.safe_dump({"users": clean}, sort_keys=False, allow_unicode=True)
    from .config import _atomic_write
    _atomic_write(USERS_FILE, text)


def set_password(name: str, pw: str) -> bool:
    users = load_users()
    u = next((x for x in users if x.get("name") == name), None)
    if not u:
        return False
    u["pw"] = hash_password(pw)
    save_users(users)
    return True


def set_2fa(name: str, on: bool) -> bool:
    users = load_users()
    u = next((x for x in users if x.get("name") == name), None)
    if not u:
        return False
    u["tfa"] = bool(on)
    save_users(users)
    return True


def current_user(token: str) -> dict | None:
    """Resolve the acting account record from a session id or raw token."""
    sess = _session_lookup(token)
    if sess and sess.get("name"):
        return user_by_name(sess["name"])
    return _user_for(token)


# ---- TOTP (authenticator-app 2FA; works with no notification channel) ------
def gen_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _totp_at(secret: str, counter: int) -> str:
    import hmac, struct
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    h = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    import struct as _s
    return f"{(_s.unpack('>I', h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000:06d}"


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    if not secret or not code:
        return False
    counter = int(time.time() // 30)
    code = code.strip()
    return any(secrets.compare_digest(_totp_at(secret, counter + d), code) for d in range(-window, window + 1))


def totp_uri(name: str, secret: str, issuer: str = "Aegis") -> str:
    from urllib.parse import quote
    return f"otpauth://totp/{quote(issuer)}:{quote(name)}?secret={secret}&issuer={quote(issuer)}&period=30&digits=6"


def set_totp(name: str, secret: str | None) -> bool:
    users = load_users()
    u = next((x for x in users if x.get("name") == name), None)
    if not u:
        return False
    if secret:
        u["totp"] = secret
        u["tfa"] = True
    else:
        u.pop("totp", None)
        u["tfa"] = False
    save_users(users)
    return True


# ---- 2FA challenges (webhook code OR an authenticator-app TOTP) -------------
def create_2fa_challenge(name: str, method: str = "webhook") -> tuple[str, str | None]:
    cid = secrets.token_urlsafe(18)
    code = None if method == "totp" else f"{secrets.randbelow(1000000):06d}"
    with _lock:
        _challenges[cid] = {"name": name, "method": method, "code": code,
                            "expires": time.time() + 300, "tries": 0}
    return cid, code


def verify_2fa(cid: str, code: str) -> str | None:
    now = time.time()
    with _lock:
        rec = _challenges.get(cid)
        if not rec or now >= rec["expires"] or rec["tries"] >= 5:
            _challenges.pop(cid, None)
            return None
        rec["tries"] += 1
        name = rec["name"]
        ok = False
        if rec.get("method") == "totp":
            u = user_by_name(name)
            ok = bool(u) and verify_totp(u.get("totp", ""), code)
        else:
            ok = secrets.compare_digest(code or "", rec.get("code") or "")
        if ok:
            del _challenges[cid]
            return name
        return None


def _user_for(token: str) -> dict | None:
    """Return the matching users.yaml record for a raw token, else None."""
    for u in load_users():
        tok = u.get("token")
        if tok and secrets.compare_digest(token or "", str(tok)):
            return u
    return None


def _session_lookup(token: str) -> dict | None:
    """Return a live session record for ``token`` (a login-issued session id)."""
    if not token:
        return None
    now = time.time()
    with _lock:
        rec = _sessions.get(token)
        if rec is None:
            return None
        exp = rec.get("expires")
        if exp is not None and now >= exp:
            del _sessions[token]      # reap expired session
            return None
        return dict(rec)


def issue_session(token: str) -> dict | None:
    """Exchange a valid user/control token for a time-boxed session token.

    Returns ``{"session", "role", "name", "expires"}`` or ``None`` if the
    presented token is invalid.
    """
    role = role_for(token)
    if role is None:
        return None
    user = _user_for(token)
    projects = user.get("projects") if user else None
    name = name_for(token)            # resolve before locking (name_for locks too)
    sid = secrets.token_urlsafe(32)
    expires = (time.time() + SESSION_TTL_MINUTES * 60) if SESSION_TTL_MINUTES > 0 else None
    with _lock:
        _sessions[sid] = {"role": role, "name": name,
                          "projects": projects, "expires": expires}
    _persist_sessions()
    return {"session": sid, "role": role, "name": name, "expires": expires}


def _persist_sessions() -> None:
    """Save live sessions so a control-center restart doesn't log everyone out."""
    with _lock:
        store.save_state("auth_sessions", {"sessions": dict(_sessions)})


def load_persisted() -> None:
    data = store.load_state("auth_sessions") or {}
    sess = data.get("sessions") if isinstance(data, dict) else None
    if not isinstance(sess, dict):
        return
    now = time.time()
    with _lock:
        for sid, rec in sess.items():
            exp = rec.get("expires")
            if exp is None or now < exp:        # skip already-expired
                _sessions[sid] = rec


def revoke_session(session: str) -> bool:
    with _lock:
        removed = _sessions.pop(session, None) is not None
    _persist_sessions()
    return removed


def can_access_project(token: str, device: str, project: str) -> bool:
    """Per-project ACL. A user may restrict access via a ``projects`` list of
    ``device:project`` patterns (``*`` and ``device:*`` wildcards). Absent list,
    legacy single-token mode, or no-auth mode all grant access to everything."""
    sess = _session_lookup(token)
    patterns = sess["projects"] if sess else (_user_for(token) or {}).get("projects")
    if not patterns:               # no restriction declared
        return True
    if not isinstance(patterns, list):
        return True
    candidates = {"*", f"{device}:*", f"{device}:{project}", f"*:{project}"}
    return any(p in candidates for p in patterns)


def name_for(token: str) -> str:
    """A human label for who is acting (for the audit log)."""
    sess = _session_lookup(token)
    if sess:
        return sess.get("name") or sess.get("role") or "user"
    users = load_users()
    if users:
        for u in users:
            tok = u.get("token")
            if tok and secrets.compare_digest(token or "", str(tok)):
                return u.get("name") or u.get("role") or "user"
        return "unknown"
    if CONTROL_CENTER_TOKEN:
        return "operator" if secrets.compare_digest(token or "", CONTROL_CENTER_TOKEN) else "anon"
    return "operator"   # no auth configured


def role_for(token: str) -> str | None:
    """Return 'operator' | 'viewer' | None for a presented token.

    A login-issued session token resolves to its captured role; otherwise the
    raw user/control token is matched as before."""
    sess = _session_lookup(token)
    if sess:
        return sess.get("role")
    users = load_users()
    if users:
        for u in users:
            tok = u.get("token")
            if tok and secrets.compare_digest(token or "", str(tok)):
                return u.get("role", "viewer")
        return None  # users configured but token didn't match
    # single-token mode (legacy)
    if CONTROL_CENTER_TOKEN:
        return "operator" if secrets.compare_digest(token or "", CONTROL_CENTER_TOKEN) else None
    # no auth configured: open by default; MAYBOT_REQUIRE_AUTH=1 forces sign-in
    return None if REQUIRE_AUTH else "operator"


def login_blocked(key: str) -> bool:
    """True if this client has too many recent failed sign-ins (brute-force guard)."""
    if LOGIN_MAX_FAILS <= 0:
        return False
    now = time.time()
    with _lock:
        ws, n = _login_fails.get(key, (now, 0))
        if now - ws >= LOGIN_LOCK_WINDOW:
            _login_fails.pop(key, None)
            return False
        return n >= LOGIN_MAX_FAILS


def note_login_fail(key: str) -> None:
    now = time.time()
    with _lock:
        ws, n = _login_fails.get(key, (now, 0))
        if now - ws >= LOGIN_LOCK_WINDOW:
            ws, n = now, 0
        _login_fails[key] = (ws, n + 1)


def reset_login(key: str) -> None:
    with _lock:
        _login_fails.pop(key, None)


def allow_request(key: str) -> bool:
    if RATE <= 0:
        return True
    now = time.time()
    with _lock:
        ws, count = _buckets.get(key, (now, 0))
        if now - ws >= WINDOW:
            ws, count = now, 0
        if count >= RATE:
            _buckets[key] = (ws, count)
            return False
        _buckets[key] = (ws, count + 1)
        return True


def clear() -> None:
    with _lock:
        _buckets.clear()
        _sessions.clear()
        _challenges.clear()
        _login_fails.clear()
