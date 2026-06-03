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

_lock = threading.Lock()
_buckets: dict[str, tuple[float, int]] = {}


def load_users() -> list[dict]:
    if not USERS_FILE.exists():
        return []
    data = yaml.safe_load(USERS_FILE.read_text(encoding="utf-8")) or {}
    users = data.get("users", [])
    return users if isinstance(users, list) else []


def role_for(token: str) -> str | None:
    """Return 'operator' | 'viewer' | None for a presented token."""
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
