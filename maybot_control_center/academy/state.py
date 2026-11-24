"""Academy persistence: one JSON file, always on.

Unlike the rest of the dashboard (which only persists with ``MAYBOT_DB``), study
progress must survive a restart on a bare install — losing a streak or a review
schedule makes a daily-use app worthless. So the academy always writes a small
JSON file (atomic replace + a once-a-day ``.bak``):

    MAYBOT_ACADEMY_FILE   explicit path; ``:memory:`` disables disk (tests)
    default               next to MAYBOT_DB when that is a file path,
                          else ./academy_state.json
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

LOCK = threading.RLock()
_state: dict | None = None
_path_loaded: str | None = None

VERSION = 1


def path() -> str:
    explicit = os.getenv("MAYBOT_ACADEMY_FILE", "").strip()
    if explicit:
        return explicit
    db = os.getenv("MAYBOT_DB", "").strip()
    if db and "://" not in db and db != ":memory:":
        return str(Path(db).parent / "academy_state.json")
    return "academy_state.json"


def blank() -> dict:
    return {
        "v": VERSION,
        "created": time.time(),
        "settings": {
            "courses": [],            # enrolled pack ids
            "new_per_day": 8,         # new items per course per day
            "session_size": 20,       # target exercises per session
            "retention": 0.9,         # FSRS desired retention
            "tz_offset_min": 0,       # learner's UTC offset (minutes east), set by the UI
            "audio": True,
        },
        "cards": {},                  # item_id -> fsrs card (+ "seen")
        "days": {},                   # YYYY-MM-DD -> activity counters
        "extra_new": {},              # YYYY-MM-DD -> {course: extra new items granted today}
        "trials": [],                 # finished trial summaries (bounded)
        "open_trials": {},            # trial_id -> in-flight trial (with answer key)
        "game": {},                   # see game.py
    }


def _merge(base: dict, data: dict) -> dict:
    for k, v in data.items():
        if k == "settings" and isinstance(v, dict):
            base["settings"].update(v)
        else:
            base[k] = v
    return base


def get() -> dict:
    """The live state dict (loaded lazily). Mutate under ``LOCK`` then ``save()``."""
    global _state, _path_loaded
    with LOCK:
        p = path()
        if _state is not None and _path_loaded == p:
            return _state
        st = blank()
        if p != ":memory:":
            for candidate in (p, p + ".bak"):
                try:
                    data = json.loads(Path(candidate).read_text(encoding="utf-8"))
                    if isinstance(data, dict) and isinstance(data.get("cards"), dict):
                        st = _merge(blank(), data)
                        break
                except Exception:
                    continue
        _state, _path_loaded = st, p
        return st


def save() -> None:
    with LOCK:
        if _state is None:
            return
        p = path()
        if p == ":memory:":
            return
        try:
            target = Path(p)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Once a day, keep the previous good file as a backup.
            bak = Path(p + ".bak")
            if target.exists() and (not bak.exists() or time.time() - bak.stat().st_mtime > 86400):
                bak.write_bytes(target.read_bytes())
            tmp = Path(p + ".tmp")
            tmp.write_text(json.dumps(_state, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, target)
        except Exception:
            pass      # never let a disk error break a study session


def reset_for_tests() -> dict:
    """Fresh in-memory state (call with MAYBOT_ACADEMY_FILE=:memory:)."""
    global _state, _path_loaded
    with LOCK:
        _state, _path_loaded = blank(), path()
        return _state


def export() -> dict:
    with LOCK:
        return json.loads(json.dumps(get()))


def import_(data: dict) -> bool:
    """Replace state from an exported blob (validated shallowly)."""
    global _state, _path_loaded
    if not isinstance(data, dict) or not isinstance(data.get("cards"), dict):
        return False
    with LOCK:
        _state, _path_loaded = _merge(blank(), data), path()
        save()
        return True
