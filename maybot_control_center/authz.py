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
import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path

import yaml

from .config import CONTROL_CENTER_TOKEN
from . import store

log = logging.getLogger(__name__)

# Opt-in Redis-backed shared state for running multiple dashboard replicas.
# When MAYBOT_REDIS_URL is set we store login sessions and rate-limit counters
# in Redis so they are shared across replicas; otherwise everything stays
# process-local and behaves exactly as before. The ``redis`` package is NOT a
# hard dependency — install it separately with ``pip install redis``.
REDIS_URL = os.getenv("MAYBOT_REDIS_URL", "").strip()
REDIS_PREFIX = os.getenv("MAYBOT_REDIS_PREFIX", "maybot").strip() or "maybot"

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


# ---- pluggable backends for session + rate-limit state --------------------
# Default backends are in-memory (process-local). When MAYBOT_REDIS_URL is set
# we swap in Redis-backed equivalents so state is shared across replicas. The
# rest of authz.py only talks to ``_session_store`` / ``_rate_store`` and never
# needs to know which implementation is active.

class _InMemorySessionStore:
    """Process-local session store backed by the ``_sessions`` dict."""

    def get(self, sid: str) -> dict | None:
        """Return a live session record (reaping it if expired), else None."""
        now = time.time()
        with _lock:
            rec = _sessions.get(sid)
            if rec is None:
                return None
            exp = rec.get("expires")
            if exp is not None and now >= exp:
                del _sessions[sid]      # reap expired session
                return None
            return dict(rec)

    def put(self, sid: str, rec: dict) -> None:
        with _lock:
            _sessions[sid] = rec
        _persist_sessions()

    def delete(self, sid: str) -> bool:
        with _lock:
            removed = _sessions.pop(sid, None) is not None
        _persist_sessions()
        return removed

    def load_persisted(self, sessions: dict) -> None:
        now = time.time()
        with _lock:
            for sid, rec in sessions.items():
                exp = rec.get("expires")
                if exp is None or now < exp:        # skip already-expired
                    _sessions[sid] = rec

    def clear(self) -> None:
        with _lock:
            _sessions.clear()


class _RedisSessionStore:
    """Session store backed by Redis keys ``<prefix>:sess:<sid>`` with TTLs."""

    def __init__(self, client, prefix: str):
        self._r = client
        self._prefix = prefix

    def _key(self, sid: str) -> str:
        return f"{self._prefix}:sess:{sid}"

    def get(self, sid: str) -> dict | None:
        # Redis expires keys for us, so a missing key == expired/absent session.
        raw = self._r.get(self._key(sid))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def put(self, sid: str, rec: dict) -> None:
        payload = json.dumps(rec)
        exp = rec.get("expires")
        if exp is not None:
            ttl = max(1, int(exp - time.time()))
            self._r.set(self._key(sid), payload, ex=ttl)
        else:
            self._r.set(self._key(sid), payload)

    def delete(self, sid: str) -> bool:
        return bool(self._r.delete(self._key(sid)))

    def load_persisted(self, sessions: dict) -> None:
        # Redis is the source of truth across replicas; no rehydration needed.
        return

    def clear(self) -> None:
        # Used by tests/clear(); drop only our session keys.
        try:
            keys = list(self._r.scan_iter(match=f"{self._prefix}:sess:*"))
            if keys:
                self._r.delete(*keys)
        except Exception:
            pass


class _InMemoryRateStore:
    """Process-local fixed-window rate limiter backed by ``_buckets``."""

    def allow(self, key: str, rate: int, window: int) -> bool:
        now = time.time()
        with _lock:
            ws, count = _buckets.get(key, (now, 0))
            if now - ws >= window:
                ws, count = now, 0
            if count >= rate:
                _buckets[key] = (ws, count)
                return False
            _buckets[key] = (ws, count + 1)
            return True

    def clear(self) -> None:
        with _lock:
            _buckets.clear()


class _RedisRateStore:
    """Fixed-window rate limiter shared across replicas via Redis INCR/EXPIRE.

    Each window is its own key (``<prefix>:rl:<key>:<window-index>``) so the
    counter resets automatically when the key TTL lapses — the shared analogue
    of the in-memory fixed window.
    """

    def __init__(self, client, prefix: str):
        self._r = client
        self._prefix = prefix

    def allow(self, key: str, rate: int, window: int) -> bool:
        window = max(1, int(window))
        bucket = int(time.time() // window)
        rkey = f"{self._prefix}:rl:{key}:{bucket}"
        try:
            count = self._r.incr(rkey)
            if count == 1:
                self._r.expire(rkey, window)
            return count <= rate
        except Exception:
            # Never block requests if Redis hiccups mid-flight.
            return True

    def clear(self) -> None:
        try:
            keys = list(self._r.scan_iter(match=f"{self._prefix}:rl:*"))
            if keys:
                self._r.delete(*keys)
        except Exception:
            pass


# Lazily-initialised backend singletons. ``None`` means "not yet selected".
_session_store = None
_rate_store = None
_backend_lock = threading.Lock()


def _redis_client():
    """Build a Redis client from MAYBOT_REDIS_URL, or None on any failure.

    Lazy-imports ``redis`` so it stays an optional dependency. A single warning
    is logged on failure and the caller falls back to the in-memory backend.
    """
    try:
        import redis  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised via monkeypatch
        log.warning(
            "MAYBOT_REDIS_URL is set but the 'redis' package is unavailable "
            "(%s); falling back to in-memory state (single-replica). "
            "Install it with `pip install redis`.", exc)
        return None
    try:
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except Exception as exc:
        log.warning(
            "Could not connect to MAYBOT_REDIS_URL (%s); falling back to "
            "in-memory state (single-replica).", exc)
        return None


def _init_backends() -> None:
    """Pick the Redis backends if configured & reachable, else in-memory."""
    global _session_store, _rate_store
    with _backend_lock:
        if _session_store is not None and _rate_store is not None:
            return
        client = _redis_client() if REDIS_URL else None
        if client is not None:
            _session_store = _RedisSessionStore(client, REDIS_PREFIX)
            _rate_store = _RedisRateStore(client, REDIS_PREFIX)
        else:
            _session_store = _InMemorySessionStore()
            _rate_store = _InMemoryRateStore()


def _sessions_backend():
    if _session_store is None:
        _init_backends()
    return _session_store


def _rate_backend():
    if _rate_store is None:
        _init_backends()
    return _rate_store


def _reset_backends() -> None:
    """Drop the selected backends so the next call re-evaluates MAYBOT_REDIS_URL.

    Used by tests after monkeypatching the env/URL; harmless in production.
    """
    global _session_store, _rate_store
    with _backend_lock:
        _session_store = None
        _rate_store = None


def redis_enabled() -> bool:
    """True when the active session backend is Redis (for diagnostics/tests)."""
    return isinstance(_sessions_backend(), _RedisSessionStore)


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
    return _sessions_backend().get(token)


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
    _sessions_backend().put(sid, {"role": role, "name": name,
                                  "projects": projects, "expires": expires})
    return {"session": sid, "role": role, "name": name, "expires": expires}


def _persist_sessions() -> None:
    """Save live sessions so a control-center restart doesn't log everyone out.

    Only meaningful for the in-memory backend; with Redis the store itself is
    the durable, shared source of truth, so this is a no-op there.
    """
    if isinstance(_sessions_backend(), _RedisSessionStore):
        return
    with _lock:
        store.save_state("auth_sessions", {"sessions": dict(_sessions)})


def load_persisted() -> None:
    data = store.load_state("auth_sessions") or {}
    sess = data.get("sessions") if isinstance(data, dict) else None
    if not isinstance(sess, dict):
        return
    _sessions_backend().load_persisted(sess)


def revoke_session(session: str) -> bool:
    return _sessions_backend().delete(session)


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
    return _rate_backend().allow(key, RATE, WINDOW)


def clear() -> None:
    _sessions_backend().clear()
    _rate_backend().clear()
    with _lock:
        _buckets.clear()
        _sessions.clear()
        _challenges.clear()
        _login_fails.clear()
