"""Academy persistence: one JSON file, always on.

Study progress and the sect must survive a restart on a bare install, so the
app always writes one small JSON file:

    SECT_ACADEMY_FILE   explicit path; ``:memory:`` disables disk (tests)
    default             ./academy_state.json

Safety rules:

* writes are atomic (tmp file, fsync, ``os.replace``);
* a ``.bak`` is refreshed at most once a day, and only from a file that parsed;
* a file that exists but cannot be read is **never** overwritten — it is moved
  aside to ``.corrupt-<timestamp>`` and the ``.bak`` is used instead;
* everything loaded from disk or imported is coerced to the expected shapes, so
  a hand-edited or hostile file cannot crash the app or smuggle markup into
  fields the UI treats as numbers;
* a failed save is remembered in ``last_error`` and surfaced by the overview.

The process holds the state in memory: run a single worker.
"""
from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
from pathlib import Path

log = logging.getLogger("sect_academy")

LOCK = threading.RLock()
_state: dict | None = None
_path_loaded: str | None = None
last_error: str = ""

VERSION = 1
MAX_IMPORT_BYTES = 8 * 1024 * 1024


def path() -> str:
    return os.getenv("SECT_ACADEMY_FILE", "").strip() or "academy_state.json"


def blank_settings() -> dict:
    return {
        "courses": [],            # enrolled pack ids
        "new_per_day": 8,         # new items per course per day
        "session_size": 20,       # target exercises per session
        "retention": 0.9,         # FSRS desired retention
        "tz_offset_min": 0,       # learner's UTC offset (minutes east), set by the UI
        "audio": True,
        "handwriting": True,      # glyph items also asked written (hand.py); off for people who only type
    }


def blank() -> dict:
    return {
        "v": VERSION,
        "created": time.time(),
        "settings": blank_settings(),
        "cards": {},                  # item_id -> fsrs card (+ "seen")
        "days": {},                   # YYYY-MM-DD -> activity counters
        "extra_new": {},              # YYYY-MM-DD -> {course: extra new items granted today}
        "trials": [],                 # finished trial summaries (bounded)
        "open_trials": {},            # trial_id -> in-flight trial (with answer key)
        "sessions": {},               # session_id -> issued items + what was answered (bounded)
        "open_placements": {},        # placement_id -> in-flight placement test
        "placements": {},             # course -> last placement result
        "mistakes": {},               # item_id -> {n, ts, given}: what you got wrong and still owe
        "drills": {},                 # kind -> {best, runs}
        "colony": {},                 # the sect (see colony.py)
        "dict_user": {},              # word -> your own dictionary meaning (reader.py)
        "words": {},                  # word -> {l1, form, ctx, ts}: saved to learn ("My words")
        "book_pos": {},               # book id -> reading position (character offset); the books sit beside this file
    }


# ---------------------------------------------------------------------------
# coercion: make any loaded/imported blob safe to use
# ---------------------------------------------------------------------------
def _num(v, default=0.0, lo=None, hi=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return default
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def _int(v, default=0, lo=None, hi=None) -> int:
    return int(_num(v, default, lo, hi))


def _str(v, default="", limit=200) -> str:
    return v[:limit] if isinstance(v, str) else default


def clean_settings(raw) -> dict:
    s = blank_settings()
    if not isinstance(raw, dict):
        return s
    if isinstance(raw.get("courses"), list):
        s["courses"] = list(dict.fromkeys(_str(c, "", 64) for c in raw["courses"] if isinstance(c, str) and c))[:50]
    s["new_per_day"] = _int(raw.get("new_per_day"), 8, 0, 40)
    s["session_size"] = _int(raw.get("session_size"), 20, 5, 60)
    s["retention"] = float(_num(raw.get("retention"), 0.9, 0.8, 0.95))
    s["tz_offset_min"] = _int(raw.get("tz_offset_min"), 0, -840, 840)
    s["audio"] = raw.get("audio") if isinstance(raw.get("audio"), bool) else True
    s["handwriting"] = raw.get("handwriting") if isinstance(raw.get("handwriting"), bool) else True
    return s


def _clean_cards(raw) -> dict:
    out = {}
    if not isinstance(raw, dict):
        return out
    for k, c in raw.items():
        if not isinstance(k, str) or not isinstance(c, dict):
            continue
        reps = _int(c.get("reps"), 0, 0)
        s = float(_num(c.get("s"), 0.0, 0.0, 36500.0))
        if not reps or s <= 0:
            continue
        out[k[:64]] = {"s": s, "d": float(_num(c.get("d"), 5.0, 1.0, 10.0)),
                       "due": float(_num(c.get("due"), 0.0, 0.0)), "last": float(_num(c.get("last"), 0.0, 0.0)),
                       "reps": reps, "lapses": _int(c.get("lapses"), 0, 0),
                       "seen": float(_num(c.get("seen"), 0.0, 0.0)), **({"placed": True} if c.get("placed") is True else {})}
    return out


def _clean_days(raw) -> dict:
    out = {}
    if not isinstance(raw, dict):
        return out
    for k, d in raw.items():
        if not isinstance(k, str) or len(k) != 10 or not isinstance(d, dict):
            continue
        nb = d.get("new_by_course") if isinstance(d.get("new_by_course"), dict) else {}
        out[k] = {"answers": _int(d.get("answers"), 0, 0), "correct": _int(d.get("correct"), 0, 0),
                  "reviews": _int(d.get("reviews"), 0, 0), "new": _int(d.get("new"), 0, 0),
                  "sessions": _int(d.get("sessions"), 0, 0), "secs": _int(d.get("secs"), 0, 0),
                  "typed": _int(d.get("typed"), 0, 0),
                  "new_by_course": {_str(c, "", 64): _int(n, 0, 0) for c, n in nb.items() if isinstance(c, str)},
                  "courses": [_str(c, "", 64) for c in d.get("courses", []) if isinstance(c, str)]
                  if isinstance(d.get("courses"), list) else []}
    return out


def _clean_trials(raw) -> list:
    out = []
    for t in raw if isinstance(raw, list) else []:
        if not isinstance(t, dict):
            continue
        out.append({"id": _str(t.get("id"), "", 32), "course": _str(t.get("course"), "", 64),
                    "ts": float(_num(t.get("ts"), 0.0, 0.0)), "pct": _int(t.get("pct"), 0, 0, 100),
                    "passed": t.get("passed") is True, "right": _int(t.get("right"), 0, 0),
                    "total": _int(t.get("total"), 1, 1), "overtime": t.get("overtime") is True,
                    "full": t.get("full") is True,
                    "domains": [{"id": _str(d.get("id"), "", 64), "title": _str(d.get("title"), "", 120), "right": _int(d.get("right"), 0, 0),
                                 "total": _int(d.get("total"), 1, 1)} for d in (t.get("domains") if isinstance(t.get("domains"), list) else [])
                                if isinstance(d, dict)][:20]})
    return out[-200:]


def _clean_extra(raw) -> dict:
    out = {}
    for day, per in (raw.items() if isinstance(raw, dict) else []):
        if isinstance(day, str) and isinstance(per, dict):
            out[day[:10]] = {_str(c, "", 64): _int(n, 0, 0, 40) for c, n in per.items() if isinstance(c, str)}
    return out


def sanitize(data: dict) -> dict:
    """A well-formed state built from an untrusted blob (unknown keys dropped)."""
    from . import colony, reader     # local import: colony imports nothing from state
    st = blank()
    st["created"] = float(_num(data.get("created"), st["created"], 0.0))
    st["settings"] = clean_settings(data.get("settings"))
    st["cards"] = _clean_cards(data.get("cards"))
    st["days"] = _clean_days(data.get("days"))
    st["extra_new"] = _clean_extra(data.get("extra_new"))
    st["trials"] = _clean_trials(data.get("trials"))
    # In-flight trials/sessions are not worth carrying across a restore.
    st["colony"] = colony.sanitize(data.get("colony"), time.time())
    ms = data.get("mistakes")
    st["mistakes"] = {_str(k, "", 96): {"n": _int(v.get("n"), 1, 1, 9), "ts": float(_num(v.get("ts"), 0.0, 0.0)), "given": _str(v.get("given"), "", 200)}
                      for k, v in list(ms.items() if isinstance(ms, dict) else [])[:5000] if isinstance(k, str) and isinstance(v, dict)}
    dr = data.get("drills")
    st["drills"] = {_str(k, "", 32): {"best": _int(v.get("best"), 0, 0, 100), "runs": _int(v.get("runs"), 0, 0)}
                    for k, v in list(dr.items() if isinstance(dr, dict) else [])[:20] if isinstance(k, str) and isinstance(v, dict)}
    st["dict_user"] = reader.clean_user_entries(data.get("dict_user"))
    st["words"] = reader.clean_words(data.get("words"))
    st["book_pos"] = reader.clean_positions(data.get("book_pos"))
    pl = data.get("placements")
    st["placements"] = {_str(k, "", 64): {x: _int(v.get(x), 0, 0) for x in ("passed_units", "units", "placed", "asked", "right")}
                        for k, v in (pl.items() if isinstance(pl, dict) else []) if isinstance(k, str) and isinstance(v, dict)}
    return st


def _looks_like_state(data) -> bool:
    return isinstance(data, dict) and isinstance(data.get("cards"), dict)


def _read(p: Path):
    """-> (state | None, problem). problem is '' when missing, else why it failed."""
    try:
        raw = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, ""
    except Exception as e:  # noqa: BLE001
        return None, f"unreadable: {e}"
    try:
        data = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        return None, f"not valid JSON: {e}"
    if not _looks_like_state(data):
        return None, "not an academy state file"
    try:
        return sanitize(data), ""
    except Exception as e:  # noqa: BLE001
        return None, f"could not be read as academy state: {e}"


def _atomic_write(target: Path, text: str) -> None:
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)


def get() -> dict:
    """The live state dict (loaded lazily). Mutate under ``LOCK`` then ``save()``."""
    global _state, _path_loaded, last_error
    with LOCK:
        p = path()
        if _state is not None and _path_loaded == p:
            return _state
        st = None
        if p != ":memory:":
            target, bak = Path(p), Path(p + ".bak")
            st, problem = _read(target)
            if st is not None:
                # A good main file: refresh the daily backup from it (atomically).
                try:
                    if not bak.exists() or time.time() - bak.stat().st_mtime > 86400:
                        _atomic_write(bak, target.read_text(encoding="utf-8"))
                except Exception as e:  # noqa: BLE001
                    log.warning("academy: could not refresh backup: %s", e)
            elif problem:
                # The file exists but is damaged. Never overwrite it: move it aside.
                aside = Path(f"{p}.corrupt-{int(time.time())}")
                n = 1
                while aside.exists():                 # never clobber earlier evidence
                    n += 1
                    aside = Path(f"{p}.corrupt-{int(time.time())}-{n}")
                try:
                    os.replace(target, aside)
                except Exception:  # noqa: BLE001
                    aside = target
                st, bak_problem = _read(bak)
                last_error = (f"Your saved progress file was damaged ({problem}) and was kept at {aside.name}. "
                              + ("Yesterday's backup was restored." if st is not None
                                 else "No usable backup was found, so a new sect was started."))
                log.error("academy: %s %s", last_error, bak_problem)
        _state, _path_loaded = st or blank(), p
        return _state


def save() -> None:
    global last_error
    with LOCK:
        if _state is None:
            return
        p = path()
        if p == ":memory:":
            return
        try:
            target = Path(p)
            target.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(target, json.dumps(_state, ensure_ascii=False))
            if last_error.startswith("Progress could not be saved"):
                last_error = ""
        except Exception as e:  # noqa: BLE001 — never let a disk error break a study session
            last_error = f"Progress could not be saved ({e}). Check disk space and permissions for {p}."
            log.error("academy: %s", last_error)


def take_error() -> str:
    """The pending load/save problem, for the UI to show."""
    return last_error


def reset_for_tests() -> dict:
    """Fresh in-memory state (call with SECT_ACADEMY_FILE=:memory:)."""
    global _state, _path_loaded, last_error
    with LOCK:
        _state, _path_loaded, last_error = blank(), path(), ""
        return _state


def export() -> dict:
    with LOCK:
        out = json.loads(json.dumps(get()))
        for key in ("open_trials", "sessions", "open_placements"):
            out.pop(key, None)
        return out


def import_(data, probe=None) -> bool:
    """Replace state from an exported blob.

    The blob is coerced to the expected shapes, then ``probe`` (the engine's
    overview) is run against it; if anything raises, the previous state stays.
    """
    global _state, _path_loaded
    if not _looks_like_state(data):
        return False
    with LOCK:
        previous = get()
        try:
            candidate = sanitize(data)
            _state, _path_loaded = candidate, path()
            if probe is not None:
                probe()
        except Exception as e:  # noqa: BLE001
            log.warning("academy: import rejected: %s", e)
            _state = previous
            return False
        save()
        return True
