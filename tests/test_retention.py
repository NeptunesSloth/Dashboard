"""Data retention pruning + scheduled disk backups (Archivist)."""
import json
import time

import pytest

from maybot_control_center import retention, store


@pytest.fixture
def memdb():
    store._reset_for_tests(":memory:")
    store.init()
    yield
    store._reset_for_tests("")
    retention.clear()


def test_prune_older_than_removes_aged_rows(memdb):
    now_ms = int(time.time() * 1000)
    old = now_ms - 40 * 86400 * 1000     # 40 days old
    store.add_history("d", "p", {"ts": old, "pnl": 1.0, "health": "ok"})
    store.add_history("d", "p", {"ts": now_ms, "pnl": 2.0, "health": "ok"})
    cutoff = now_ms - 30 * 86400 * 1000  # keep last 30 days
    removed = store.prune_older_than(cutoff)
    assert removed["history"] == 1
    remaining = store.load_history()["d:p"]
    assert len(remaining) == 1 and remaining[0]["pnl"] == 2.0


def test_prune_now_disabled_without_retention(memdb, monkeypatch):
    monkeypatch.setattr(retention, "RETENTION_DAYS", 0)
    assert retention.prune_now()["pruned"] is False


def test_prune_now_enabled(memdb, monkeypatch):
    monkeypatch.setattr(retention, "RETENTION_DAYS", 30)
    now_ms = int(time.time() * 1000)
    store.add_history("d", "p", {"ts": now_ms - 40 * 86400 * 1000, "pnl": 1.0, "health": "ok"})
    res = retention.prune_now()
    assert res["pruned"] is True and res["removed"]["history"] == 1


def test_snapshot_now_writes_and_rotates(tmp_path, monkeypatch):
    monkeypatch.setattr(retention, "BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr(retention, "BACKUP_KEEP", 2)
    # Three snapshots with distinct timestamps; only the newest 2 are kept.
    t = [1_700_000_000.0]
    monkeypatch.setattr(time, "time", lambda: t[0])
    for i in range(3):
        t[0] += 1
        out = retention.snapshot_now()
        assert out["backed_up"] is True
        assert json.loads((tmp_path / out["path"].split("/")[-1]).read_text())  # valid JSON
    files = retention.list_backups()
    assert len(files) == 2


def test_snapshot_now_disabled_without_dir(monkeypatch):
    monkeypatch.setattr(retention, "BACKUP_DIR", "")
    assert retention.snapshot_now()["backed_up"] is False


def test_tick_runs_due_jobs(tmp_path, memdb, monkeypatch):
    monkeypatch.setattr(retention, "RETENTION_DAYS", 30)
    monkeypatch.setattr(retention, "BACKUP_DIR", str(tmp_path))
    retention._last_prune = 0.0
    retention._last_backup = 0.0
    ran = retention.tick(now=10**10)
    assert "prune" in ran and "backup" in ran
