"""Web Push (VAPID) — alerts reach your phone even when the app is closed.

Stores browser push subscriptions and sends notifications on important events.
Real delivery needs VAPID keys (``MAYBOT_VAPID_PUBLIC`` / ``MAYBOT_VAPID_PRIVATE``
/ ``MAYBOT_VAPID_SUBJECT``) and the optional ``pywebpush`` package; without them
subscriptions are still stored and sends are a safe no-op, so the framework is
always present and lights up once configured.
"""
from __future__ import annotations

import os
import threading

PUBLIC_KEY = os.getenv("MAYBOT_VAPID_PUBLIC", "")
PRIVATE_KEY = os.getenv("MAYBOT_VAPID_PRIVATE", "")
SUBJECT = os.getenv("MAYBOT_VAPID_SUBJECT", "mailto:admin@example.com")

_lock = threading.Lock()
_subs: dict[str, dict] = {}     # endpoint -> subscription


def enabled() -> bool:
    return bool(PUBLIC_KEY and PRIVATE_KEY)


def public_key() -> dict:
    return {"key": PUBLIC_KEY, "enabled": enabled()}


def subscribe(sub: dict) -> dict:
    ep = (sub or {}).get("endpoint")
    if not ep:
        raise ValueError("subscription missing endpoint")
    with _lock:
        _subs[ep] = sub
    _save()
    return {"subscribed": True, "count": len(_subs)}


def unsubscribe(endpoint: str) -> bool:
    with _lock:
        removed = _subs.pop(endpoint, None) is not None
    if removed:
        _save()
    return removed


def send(title: str, body: str, url: str = "/") -> int:
    """Push to every subscriber. Returns how many were delivered (0 if not configured)."""
    if not enabled():
        return 0
    try:
        from pywebpush import webpush, WebPushException
    except Exception:
        return 0
    import json
    payload = json.dumps({"title": title, "body": body, "url": url})
    with _lock:
        subs = list(_subs.items())
    delivered, dead = 0, []
    for ep, sub in subs:
        try:
            webpush(subscription_info=sub, data=payload,
                    vapid_private_key=PRIVATE_KEY, vapid_claims={"sub": SUBJECT})
            delivered += 1
        except Exception as exc:  # 404/410 → subscription gone
            if "410" in str(exc) or "404" in str(exc):
                dead.append(ep)
    if dead:
        with _lock:
            for ep in dead:
                _subs.pop(ep, None)
        _save()
    return delivered


def snapshot() -> dict:
    with _lock:
        return {"enabled": enabled(), "subscriptions": len(_subs)}


def _save() -> None:
    from . import store
    if store.enabled():
        with _lock:
            store.save_state("push", {"subs": _subs})


def load_persisted() -> None:
    from . import store
    data = store.load_state("push")
    if data:
        with _lock:
            _subs.update(data.get("subs") or {})


def clear() -> None:
    with _lock:
        _subs.clear()
