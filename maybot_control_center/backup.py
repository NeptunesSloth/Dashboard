"""State backup / restore.

Exports the dashboard's persisted coordination state (task board, oaths,
maintenance silences, autopilot, sect memory, audit log, inbound alerts, agent
registry) as one JSON blob, and restores it. Backup/restore operate on the
store's generic ``state`` table, so they require persistence (``MAYBOT_DB``).
"""
from __future__ import annotations

import time

# Modules whose in-memory state is reloaded from the store after a restore.
_RELOAD = ("taskqueue", "oaths", "acks", "maintenance", "autopilot", "sectmemory", "audit", "inbound", "registry")


def export() -> dict:
    from . import store
    return {"version": 1, "exported_at": int(time.time() * 1000),
            "persisted": store.enabled(), "state": store.export_state()}


def restore(data: dict) -> dict:
    from . import store
    if not isinstance(data, dict) or "state" not in data:
        raise ValueError("invalid backup payload (missing 'state')")
    if not store.enabled():
        raise ValueError("restore requires persistence (set MAYBOT_DB)")
    import importlib
    mods = []
    for name in _RELOAD:
        try:
            mods.append(importlib.import_module(f"maybot_control_center.{name}"))
        except Exception:
            pass
    # 1) wipe in-memory (and the store), 2) write the backup, 3) re-hydrate.
    for mod in mods:
        try:
            mod.clear()
        except Exception:
            pass
    written = store.import_state(data.get("state") or {})
    for mod in mods:
        try:
            mod.load_persisted()
        except Exception:
            pass
    return {"restored_modules": written}
