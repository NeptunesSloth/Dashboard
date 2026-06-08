"""Disaster recovery — a single portable bundle of the dashboard's whole config
so you can rebuild on a fresh box entirely from inside the app: export →
download → restore.

Bundles the things you'd hate to lose: your hosts (and their tokens), the enroll
token, dashboard accounts, and the persisted coordination state (task board,
agent registry, autopilot, sect memory, audit log, …).

The bundle contains secrets (host API tokens, account password hashes) — it's
your own backup; keep it somewhere safe.
"""
from __future__ import annotations

import time

from . import config, authz, registry, backup

BUNDLE_VERSION = 2


def export_all() -> dict:
    return {
        "version": BUNDLE_VERSION,
        "exported_at": int(time.time() * 1000),
        "hosts": config.load_devices(),
        "accounts": authz.load_users(),
        "enroll_token": registry.REGISTER_TOKEN,
        "store": backup.export(),          # persisted coordination state
    }


def restore_all(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("backup must be a JSON object")
    # A raw store-only backup (legacy backup.export output) has 'state' at the top.
    if "store" not in data and "state" in data:
        res = backup.restore(data)
        return {"restored": [f"state: {res.get('restored_modules')} module(s)"]}
    if data.get("version") not in (1, 2):
        raise ValueError("unrecognized backup bundle")

    restored: list[str] = []
    hosts = data.get("hosts")
    if isinstance(hosts, list):
        config.save_devices(hosts)
        restored.append(f"{len(hosts)} host(s)")
    accounts = data.get("accounts")
    if isinstance(accounts, list):
        authz.save_users(accounts)
        restored.append(f"{len(accounts)} account(s)")
    if "enroll_token" in data:
        registry.set_register_token(data.get("enroll_token") or "")
        restored.append("enroll token")
    store_blob = data.get("store")
    if isinstance(store_blob, dict) and store_blob.get("state") is not None:
        try:
            res = backup.restore(store_blob)
            restored.append(f"state: {res.get('restored_modules')} module(s)")
        except Exception as exc:  # noqa: BLE001 (persistence may be off)
            restored.append(f"state skipped ({exc})")
    return {"restored": restored}
