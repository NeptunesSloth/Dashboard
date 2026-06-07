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

import os
import secrets
import threading
import time
from pathlib import Path

import yaml

from .config import CONTROL_CENTER_TOKEN

USERS_FILE = Path(os.getenv("MAYBOT_USERS_FILE", "users.yaml"))
RATE = int(os.getenv("MAYBOT_RATE_LIMIT", "240"))   # requests per window per key (0 = off)
WINDOW = int(os.getenv("MAYBOT_RATE_WINDOW", "60"))  # seconds
# Login-issued session tokens expire after this many minutes (0 = no expiry).
SESSION_TTL_MINUTES = float(os.getenv("MAYBOT_SESSION_TTL_MINUTES", "720"))

_lock = threading.Lock()
_buckets: dict[str, tuple[float, int]] = {}
# session id -> {"role", "name", "projects", "expires"} (expires=None never lapses)
_sessions: dict[str, dict] = {}


def load_users() -> list[dict]:
    if not USERS_FILE.exists():
        return []
    data = yaml.safe_load(USERS_FILE.read_text(encoding="utf-8")) or {}
    users = data.get("users", [])
    return users if isinstance(users, list) else []


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
        clean.append(e)
    header = ("# users.yaml — dashboard accounts (managed from Ops -> Accounts).\n"
              "# Each token grants its role (operator can mutate, viewer is read-only).\n"
              "# Keep this file secret; never commit real tokens.\n")
    text = header + yaml.safe_dump({"users": clean}, sort_keys=False, allow_unicode=True)
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = USERS_FILE.with_name(USERS_FILE.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(USERS_FILE)


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
    return {"session": sid, "role": role, "name": name, "expires": expires}


def revoke_session(session: str) -> bool:
    with _lock:
        return _sessions.pop(session, None) is not None


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
    return "operator"  # no auth configured at all


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
