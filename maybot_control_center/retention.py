"""Data retention & scheduled backups — the sect's "Archivist".

Two background hygiene jobs, both opt-in and no-ops unless configured:

* **Retention** — when ``MAYBOT_RETENTION_DAYS`` (>0) is set *and* persistence is
  enabled (``MAYBOT_DB``), time-series rows (history, transcripts, comms, usage)
  older than the window are periodically pruned so the DB doesn't grow forever.

* **Scheduled backups** — when ``MAYBOT_BACKUP_DIR`` is set, the coordination
  state (via :mod:`backup`) is snapshotted to a timestamped JSON file every
  ``MAYBOT_BACKUP_INTERVAL_HOURS`` (default 24), keeping the most recent
  ``MAYBOT_BACKUP_KEEP`` (default 14) and rotating older ones away.

The same loop drives both; ``tick()`` is pure and testable.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

RETENTION_DAYS = float(os.getenv("MAYBOT_RETENTION_DAYS", "0") or 0)
BACKUP_DIR = os.getenv("MAYBOT_BACKUP_DIR", "").strip()
BACKUP_INTERVAL_HOURS = float(os.getenv("MAYBOT_BACKUP_INTERVAL_HOURS", "24") or 24)
BACKUP_KEEP = max(1, int(os.getenv("MAYBOT_BACKUP_KEEP", "14")))
PRUNE_INTERVAL_HOURS = float(os.getenv("MAYBOT_PRUNE_INTERVAL_HOURS", "6") or 6)

_lock = threading.Lock()
_last_prune: float = 0.0
_last_backup: float = 0.0
_started = False


# ---- retention pruning ----
def prune_now() -> dict:
    """Prune aged time-series rows immediately (no-op unless configured)."""
    from . import store
    if RETENTION_DAYS <= 0 or not store.enabled():
        return {"pruned": False, "reason": "retention disabled or no DB"}
    cutoff_ms = int((time.time() - RETENTION_DAYS * 86400) * 1000)
    removed = store.prune_older_than(cutoff_ms)
    if sum(removed.values()) > 0:
        store.vacuum()
    with _lock:
        global _last_prune
        _last_prune = time.time()
    return {"pruned": True, "cutoff_ms": cutoff_ms, "removed": removed}


# ---- scheduled disk backups ----
def _backup_path(now: float) -> Path:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now))
    return Path(BACKUP_DIR) / f"maybot-backup-{stamp}.json"


def _rotate() -> None:
    d = Path(BACKUP_DIR)
    files = sorted(d.glob("maybot-backup-*.json"))
    for old in files[:-BACKUP_KEEP]:
        try:
            old.unlink()
        except Exception:
            pass


def snapshot_now() -> dict:
    """Write a state backup to ``MAYBOT_BACKUP_DIR`` (no-op unless configured)."""
    from . import backup
    if not BACKUP_DIR:
        return {"backed_up": False, "reason": "MAYBOT_BACKUP_DIR not set"}
    now = time.time()
    try:
        Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
        path = _backup_path(now)
        path.write_text(json.dumps(backup.export()), encoding="utf-8")
        _rotate()
    except Exception as exc:
        return {"backed_up": False, "error": str(exc)}
    with _lock:
        global _last_backup
        _last_backup = now
    return {"backed_up": True, "path": str(path)}


def list_backups() -> list[dict]:
    if not BACKUP_DIR:
        return []
    d = Path(BACKUP_DIR)
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("maybot-backup-*.json")):
        try:
            stat = f.stat()
            out.append({"name": f.name, "bytes": stat.st_size, "mtime": int(stat.st_mtime)})
        except Exception:
            pass
    return out


# ---- scheduler ----
def tick(now: float | None = None) -> dict:
    """Run any due hygiene jobs. Returns what ran (for tests/observability)."""
    now = now if now is not None else time.time()
    ran: dict = {}
    if RETENTION_DAYS > 0:
        with _lock:
            due = (now - _last_prune) >= PRUNE_INTERVAL_HOURS * 3600
        if due:
            ran["prune"] = prune_now()
    if BACKUP_DIR:
        with _lock:
            due = (now - _last_backup) >= BACKUP_INTERVAL_HOURS * 3600
        if due:
            ran["backup"] = snapshot_now()
    return ran


def _loop() -> None:
    while True:
        time.sleep(600)
        try:
            tick()
        except Exception:
            pass


def start() -> bool:
    """Start the archivist loop (no-op unless retention or backups are on)."""
    global _started, _last_prune, _last_backup
    if _started or (RETENTION_DAYS <= 0 and not BACKUP_DIR):
        return False
    _started = True
    with _lock:
        # First runs fire one interval after startup, not at boot.
        _last_prune = time.time()
        _last_backup = time.time()
    threading.Thread(target=_loop, daemon=True).start()
    return True


def snapshot() -> dict:
    """State for the dashboard / API."""
    with _lock:
        return {
            "retention_days": RETENTION_DAYS,
            "backup_dir": BACKUP_DIR or None,
            "backup_interval_hours": BACKUP_INTERVAL_HOURS,
            "backup_keep": BACKUP_KEEP,
            "last_prune": _last_prune or None,
            "last_backup": _last_backup or None,
            "backups": list_backups(),
        }


def clear() -> None:
    global _last_prune, _last_backup, _started
    with _lock:
        _last_prune = 0.0
        _last_backup = 0.0
    _started = False
