"""The study engine: enrolment, daily sessions, grading, trials (mock exams).

Design (see docs/superpowers/specs/2026-11-24-sect-academy-design.md):

* Every content item is one FSRS card. The *exercise format* hardens as the
  card matures — recognise, then recall, then type from memory, then dictation —
  because retrieval that takes effort is what builds memory.
* A session is due reviews first, then a paced ration of new items from the next
  unlocked unit. Only the first answer to an item in a session is graded; a
  missed item is re-shown by the client until it is right once.
* Grading is done here, server-side: wrong = Again, right-but-flagged (missing
  accent, small typo) = Hard, right = Good.
* Trials are timed mock exams sampled by the official domain weights (certs) or
  from everything introduced so far (languages).
"""
from __future__ import annotations

import datetime as _dt
import random
import re
import time
import unicodedata
import uuid

from . import colony as game, fsrs, packs, state

MATURE_DAYS = 21.0        # stability at which an item counts as "mastered"
MIN_SESSION_ANSWERS = 8   # answers needed for a session to count for the streak
PRACTICE_SIZE = 12


# ---------------------------------------------------------------------------
# time helpers (the learner's local day)
# ---------------------------------------------------------------------------
def _offset(st: dict) -> int:
    try:
        return int(st["settings"].get("tz_offset_min", 0)) * 60
    except Exception:
        return 0


def day_of(st: dict, now: float) -> str:
    return _dt.datetime.fromtimestamp(now + _offset(st), _dt.timezone.utc).strftime("%Y-%m-%d")


def end_of_day(st: dict, now: float) -> float:
    local = now + _offset(st)
    return (int(local // 86400) + 1) * 86400 - _offset(st)


def days_since(st: dict, then: float, now: float) -> int:
    """Whole learner-local calendar days between two instants (0 = same day)."""
    off = _offset(st)
    return max(0, int((now + off) // 86400) - int((then + off) // 86400))


def _review(st: dict, card: dict | None, grade: int, now: float) -> dict:
    """One FSRS review, measuring the gap in the learner's calendar days so an
    early-morning review of yesterday evening's card is not treated as same-day."""
    elapsed = days_since(st, card["last"], now) if card and card.get("reps") else None
    new = fsrs.review(card or fsrs.new_card(), grade, now, float(st["settings"]["retention"]), elapsed_days=elapsed)
    new["seen"] = (card or {}).get("seen") or now
    return new


def _day(st: dict, now: float) -> dict:
    return st["days"].setdefault(day_of(st, now), {
        "answers": 0, "correct": 0, "reviews": 0, "new": 0, "sessions": 0,
        "secs": 0, "new_by_course": {}, "courses": [], "typed": 0})


# ---------------------------------------------------------------------------
# courses
# ---------------------------------------------------------------------------
def _enrolled(st: dict) -> list[str]:
    all_packs = packs.load_all()
    return [c for c in st["settings"].get("courses", []) if c in all_packs]


def enroll(course: str, on: bool = True) -> dict:
    if not packs.get(course):
        return {"ok": False, "error": "unknown course"}
    with state.LOCK:
        st = state.get()
        cur = [c for c in st["settings"].get("courses", []) if c != course]
        if on:
            cur.append(course)
        st["settings"]["courses"] = cur
        game.ensure(st, time.time())
        state.save()
    return {"ok": True, "courses": cur}


def _quest_ctx(st: dict, mine: list[dict], now: float) -> dict:
    """What today can actually supply, so a daily quest is never impossible."""
    due = sum(c["due"] for c in mine)
    held = due > 2 * int(st["settings"]["session_size"])        # review debt holds new items back
    typed_due = 0
    for it, card in _due_cards(st, [c["id"] for c in mine], now):
        if _mode_for(it, card, packs.get(it["pack"])) in ("type_l2", "listen", "cloze_type"):
            typed_due += 1
    return {"due": due, "new_offered": 0 if held else sum(c["new_left"] for c in mine),
            "typed_due": typed_due, "active_courses": sum(1 for c in mine if c["due"] + c["new_left"] > 0)}


def set_settings(patch: dict) -> dict:
    with state.LOCK:
        st = state.get()
        merged = dict(st["settings"])
        for key in ("new_per_day", "session_size", "retention", "tz_offset_min", "audio"):
            if key in patch and patch[key] is not None:
                merged[key] = patch[key]
        clean = state.clean_settings(merged)      # clamps; non-finite/ill-typed values fall back
        clean["courses"] = st["settings"].get("courses", [])
        st["settings"] = clean
        state.save()
        return dict(clean)


def _card_view(card: dict | None, now: float) -> dict:
    if not card or not card.get("reps"):
        return {"state": "new", "strength": 0}
    r = fsrs.retrievability(max(0.0, (now - card["last"]) / fsrs.DAY), card["s"])
    return {"state": "mastered" if card["s"] >= MATURE_DAYS else "learning",
            "strength": round(r * 100), "due": card["due"], "stability": round(card["s"], 1),
            "lapses": card.get("lapses", 0)}


def course_stats(st: dict, pack: dict, now: float) -> dict:
    cards = st["cards"]
    eod = end_of_day(st, now)
    total = seen = mastered = due = 0
    strength_sum = 0.0
    units = []
    unlocked = True
    current = None
    for u in pack["units"]:
        u_seen = u_mast = 0
        for it in u["items"]:
            total += 1
            c = cards.get(it["id"])
            if c and c.get("reps"):
                seen += 1
                u_seen += 1
                strength_sum += fsrs.retrievability(max(0.0, (now - c["last"]) / fsrs.DAY), c["s"])
                if c["s"] >= MATURE_DAYS:
                    mastered += 1
                    u_mast += 1
                if c["due"] <= eod:
                    due += 1
        n = len(u["items"])
        units.append({"id": u["id"], "title": u["title"], "goal": u.get("goal", ""), "items": n,
                      "seen": u_seen, "mastered": u_mast, "unlocked": unlocked,
                      "done": u_seen >= n, "domain": u.get("domain", "")})
        if unlocked and u_seen < n and current is None:
            current = u["id"]
        unlocked = unlocked and u_seen >= n     # next unit opens once this one is fully introduced
    today = _day(st, now)
    quota = int(st["settings"]["new_per_day"]) + int(st.get("extra_new", {}).get(day_of(st, now), {}).get(pack["id"], 0))
    new_left = max(0, min(total - seen, quota - int(today["new_by_course"].get(pack["id"], 0))))
    return {
        "id": pack["id"], "title": pack["title"], "kind": pack["kind"], "blurb": pack.get("blurb", ""),
        "hall": pack.get("hall", ""), "lang": pack.get("lang", ""), "language": pack.get("language", ""),
        "exam": ({k: pack["exam"][k] for k in ("name", "code", "questions", "minutes", "pass_pct")}
                 if pack["kind"] == "cert" else None),
        "total": total, "seen": seen, "mastered": mastered, "due": due, "new_left": new_left,
        "strength": round(100 * strength_sum / seen) if seen else 0,
        "units": units, "current_unit": current,
        "units_done": sum(1 for u in units if u["done"]),
        "enrolled": pack["id"] in st["settings"].get("courses", []),
        "soon": [{"id": u["id"], "title": u["title"], "goal": u.get("goal", "")} for u in pack.get("soon", [])],
    }


def courses(now: float | None = None) -> list[dict]:
    now = now or time.time()
    with state.LOCK:
        st = state.get()
        return [course_stats(st, p, now) for p in packs.load_all().values()]


def unit_detail(course: str, unit_id: str, now: float | None = None) -> dict:
    now = now or time.time()
    pack = packs.get(course)
    unit = next((u for u in (pack or {}).get("units", []) if u["id"] == unit_id), None)
    if not unit:
        return {"ok": False, "error": "unknown unit"}
    with state.LOCK:
        st = state.get()
        items = []
        for it in unit["items"]:
            v = _card_view(st["cards"].get(it["id"]), now)
            items.append({**_public_item(it), **v})
    return {"ok": True, "id": unit["id"], "title": unit["title"], "goal": unit.get("goal", ""),
            "notes": unit.get("notes", ""), "items": items, "lang": pack.get("lang", "")}


def _public_item(it: dict) -> dict:
    keys = ("id", "type", "l1", "l2", "rom", "alt", "note", "ex", "ex_rom", "ex_l1", "text", "answer", "term", "def", "q", "why",
            "title", "scene", "you", "lines", "best", "n", "x", "y")
    out = {k: it[k] for k in keys if k in it and it[k] not in ("", None, [])}
    if it["type"] == "mcq":
        out["correct"] = it["choices"][it["answer"]]
    if it["type"] in ("multi", "order"):
        out["correct"] = (" + " if it["type"] == "multi" else " → ").join(truth_list(it))
    if it["type"] == "cloze":
        out["full"] = fill_cloze(it)
    if it["type"] == "pin":
        out["picture"] = _pic_view(it)
    return out


# ---------------------------------------------------------------------------
# answer normalisation + checking
# ---------------------------------------------------------------------------
_PUNCT = re.compile(r"[¿¡?!.,;:\"“”«»()\[\]…。，、？！：；「」『』（）《》·〜～]")
_TONES = {"a": "āáǎàa", "e": "ēéěèe", "i": "īíǐìi", "o": "ōóǒòo", "u": "ūúǔùu", "ü": "ǖǘǚǜü"}
_PINYIN_NUM = re.compile(r"([a-zü]+?)([1-5])(?![0-9])")


def is_script(s: str) -> bool:
    """True if the text is written in Chinese characters, kana or hangul."""
    return any(ord(ch) >= 0x2E80 for ch in str(s or ""))


def _tone_marks(s: str) -> str:
    """Pinyin typed with tone numbers ("ni3 hao3", "lv4") becomes pinyin with tone marks."""
    def one(m: re.Match) -> str:
        syl, tone = m.group(1).replace("u:", "ü").replace("v", "ü"), int(m.group(2))
        for v in ("a", "e"):
            if v in syl:
                return syl.replace(v, _TONES[v][tone - 1], 1)
        if "ou" in syl:
            return syl.replace("o", _TONES["o"][tone - 1], 1)
        for i in range(len(syl) - 1, -1, -1):
            if syl[i] in _TONES:
                return syl[:i] + _TONES[syl[i]][tone - 1] + syl[i + 1:]
        return syl
    return _PINYIN_NUM.sub(one, s.lower().replace("u:", "ü"))


_ARTICLES = {"le", "la", "les", "un", "une", "des", "du", "el", "los", "las", "unos", "unas", "lo"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFC", str(s or "")).replace("’", "'").replace("‘", "'").replace("`", "'")
    s = _PUNCT.sub(" ", s.lower())
    s = s.replace("-", " ")
    return re.sub(r"\s+", " ", s).strip()


def _strip_accents(s: str) -> str:
    out = "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")
    return out.replace("œ", "oe").replace("æ", "ae").replace("ß", "ss")


def _edit1(a: str, b: str) -> bool:
    """True if a and b differ by exactly one edit (insert/delete/substitute/transpose)."""
    if a == b:
        return False
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = [i for i in range(la) if a[i] != b[i]]
        if len(diff) == 1:
            return True
        return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]
    if la > lb:
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def check_typed(answer: str, accepted: list[str], slips: bool = True) -> dict:
    if any(is_script(a) for a in accepted):
        return _check_script(answer, accepted)
    return _check_typed(answer, accepted, slips)


def _check_script(answer: str, accepted: list[str]) -> dict:
    """Chinese, Japanese, Korean: the answer may be typed in the script itself or in its romanisation
    (the last accepted forms). Spacing never matters. Pinyin may carry tone marks or tone numbers; pinyin
    with no tones at all is accepted on longer answers, marked as a slip so it comes back sooner."""
    expected = accepted[0]
    tight = lambda s: _norm(s).replace(" ", "").replace("'", "")       # noqa: E731
    got = tight(_tone_marks(answer) if not is_script(answer) else answer)
    if not got:
        return {"correct": False, "flag": None, "expected": expected}
    forms = [tight(a) for a in accepted if a]
    if got in forms:
        return {"correct": True, "flag": None, "expected": expected}
    plain = _strip_accents(got)
    for a, f in zip(accepted, forms):
        # no tones typed at all is a slip; the wrong tone is the wrong word
        if not is_script(a) and got == plain and len(plain) >= 4 and plain == _strip_accents(f):
            return {"correct": True, "flag": "tone", "expected": a}
    return {"correct": False, "flag": None, "expected": expected}


def _check_typed(answer: str, accepted: list[str], slips: bool = True) -> dict:
    """Grade a typed answer. Returns {correct, flag, expected}.

    ``slips=False`` (cloze blanks) forgives no typo and no final-letter accent: there one
    letter is usually the grammar being tested (hables/hablas, hablo/habló)."""
    expected = accepted[0]
    got = _norm(answer)
    if not got:
        return {"correct": False, "flag": None, "expected": expected}
    normed = [_norm(a) for a in accepted if a]
    if got in normed:
        return {"correct": True, "flag": None, "expected": expected}
    got_plain = _strip_accents(got)
    # A missing accent is forgiven (with the correction shown) on longer answers.
    # On very short words the accent *is* the word (où/ou, à/a, tú/tu, sí/si).
    for a, n in zip(accepted, normed):
        if len(got_plain) >= 4 and got_plain == _strip_accents(n) and (slips or (n[-1:] == _strip_accents(n)[-1:] and got[-1:] == got_plain[-1:])):
            return {"correct": True, "flag": "accent", "expected": a}
    for a, n in zip(accepted, normed):
        plain = _strip_accents(n)
        # One slip is forgiven on longer answers — but never in the article (le/la,
        # el/la, un/une): that single letter *is* the thing being learned.
        if slips and len(plain) >= 6 and _edit1(got_plain, plain):
            first = plain.split(" ")[0]
            if " " in plain and first in _ARTICLES and got_plain.split(" ")[0] != first:
                continue
            return {"correct": True, "flag": "typo", "expected": a}
    return {"correct": False, "flag": None, "expected": expected}


def _tiles(text: str) -> list[str]:
    """A sentence as word tiles: no loose punctuation, no full stop to give away the last word.
    Chinese and Japanese are written without spaces, so there each character is a tile."""
    text = str(text)
    if is_script(text) and " " not in text.strip():
        return [ch for ch in _PUNCT.sub("", text) if not ch.isspace()]
    out = []
    for w in str(text).split():
        w = w.strip(".,!?;:…«»¿¡\"“”")
        if w:
            out.append(w)
    return out


def fill_cloze(it: dict) -> str:
    """The cloze sentence with its answer in place (capitalised at sentence start)."""
    ans = it["answer"]
    if it["text"].lstrip().startswith("___"):
        ans = ans[:1].upper() + ans[1:]
    return it["text"].replace("___", ans)


def _accepted(it: dict) -> list[str]:
    if it["type"] == "cloze":
        return [it["answer"], *it.get("alt", [])]
    if it["type"] == "glyph":
        return [it["rom"], *it.get("alt", []), it["l2"]]
    return [it["l2"], *it.get("alt", []), *([it["rom"]] if it.get("rom") else [])]


# ---------------------------------------------------------------------------
# exercise construction
# ---------------------------------------------------------------------------
def _mode_for(it: dict, card: dict | None, pack: dict) -> str:
    reps = int((card or {}).get("reps", 0))
    t = it["type"]
    if t in ("vocab", "phrase"):
        if reps == 0:
            return "choose_l1"
        if reps == 1:
            return "choose_l2"
        if reps == 2 and len(_tiles(it["l2"])) >= 3:
            return "build_l2"            # assemble the sentence from tiles before typing it cold
        if pack.get("lang") and reps >= 3 and reps % 3 == 0:
            return "listen"
        return "type_l2"
    if t == "glyph":
        # see it and pick its sound; hear the sound and pick it; then read it cold
        return "glyph_choose" if reps == 0 else "glyph_pick" if reps == 1 else "glyph_type"
    if t == "cloze":
        return "cloze_choose" if reps == 0 else "cloze_type"
    if t == "pin":
        return _pin_mode(reps)
    if t == "concept":
        return "choose_term" if reps % 2 == 0 else "choose_def"
    if t == "dialogue":
        # First rehearsals arrange the words; after that you answer from memory.
        return "dialogue_build" if reps < 2 else "dialogue_type"
    return t          # mcq, multi, order: always the test itself


def _distractors(it: dict, pack: dict, field: str, rng: random.Random, n: int = 3) -> list[str]:
    """Plausible wrong options: same field from sibling items, same unit first."""
    truth = {_norm(it[field])} | ({_norm(a) for a in _accepted(it)} if field in ("l2", "answer") else set())
    same_unit, others = [], []
    for u in pack["units"]:
        for o in u["items"]:
            if o["id"] == it["id"] or field not in o:
                continue
            if (o["type"] == "glyph") != (it["type"] == "glyph"):
                continue                               # characters are only ever confused with characters
            if field in ("l1", "l2") and (o["type"] == "cloze"
                                           or (o["type"] == "phrase") != (it["type"] == "phrase")):
                continue
            (same_unit if u["id"] == it["unit"] else others).append(o[field])
    target = _norm(it[field])

    def clashes(v: str) -> bool:
        # An option that contains the answer (or is contained in it) is a trick, not a test.
        nv = _norm(v)
        if it["type"] == "glyph":
            return nv in truth or not nv              # "a" and "ka" are honest neighbours, not a trick
        return nv in truth or not nv or nv in target or target in nv

    out: list[str] = []
    for pool in (same_unit, others):
        pool = [v for v in dict.fromkeys(pool) if not clashes(v)]
        rng.shuffle(pool)
        # Prefer options of a similar length so the answer does not stand out.
        pool.sort(key=lambda v: abs(len(v) - len(it[field])) > max(8, len(it[field])))
        for v in pool:
            if v not in out and not any(_norm(v) in _norm(o) or _norm(o) in _norm(v) for o in out):
                out.append(v)
            if len(out) >= n:
                return out
    return out


def build_exercise(it: dict, mode: str, pack: dict, seed: int = 0) -> dict:
    rng = random.Random(f"{it['id']}:{mode}:{seed}")
    ex: dict = {"item": it["id"], "course": pack["id"], "mode": mode, "type": it["type"],
                "unit": it["unit"], "lang": pack.get("lang", "")}

    def choices(field: str, truth: str) -> list[str]:
        opts = _distractors(it, pack, field, rng) + [truth]
        rng.shuffle(opts)
        return opts

    if mode == "intro":
        ex["card"] = _public_item(it)
    elif mode == "choose_l1":
        ex.update(prompt=it["l2"], say=it["l2"], ask="What does this mean?", choices=choices("l1", it["l1"]))
        if it.get("rom"):
            ex["rom"] = it["rom"]
    elif mode == "glyph_choose":
        ex.update(prompt=it["l2"], say=it["l2"], ask="How is this read?", choices=choices("rom", it["rom"]), big=True)
    elif mode == "glyph_pick":
        ex.update(prompt=it["rom"], say=it["l2"], sub=it.get("l1", ""), ask="Which one is it?", choices=choices("l2", it["l2"]), big=True)
    elif mode == "glyph_type":
        ex.update(prompt=it["l2"], sub=it.get("l1", ""), ask="Type how it is read", big=True)
    elif mode == "choose_l2":
        ex.update(prompt=it["l1"], ask=f"Choose the {pack.get('language', 'translation')}", choices=choices("l2", it["l2"]))
    elif mode == "type_l2":
        ex.update(prompt=it["l1"], ask=f"Type it in {pack.get('language', 'the language')}"
                  + (" (romanised, or in the script)" if is_script(it["l2"]) else ""))
    elif mode == "build_l2":
        words = _tiles(it["l2"])
        pool = [w for o in next(u for u in pack["units"] if u["id"] == it["unit"])["items"]
                if o["id"] != it["id"] and o.get("l2") for w in _tiles(o["l2"]) if w not in words]
        rng.shuffle(pool)
        bank = words + pool[:3]
        rng.shuffle(bank)
        ex.update(prompt=it["l1"], ask="Build the sentence", bank=bank)
    elif mode == "listen":
        ex.update(say=it["l2"], hint=it["l1"], ask="Type what you hear" + (" (romanised, or in the script)" if is_script(it["l2"]) else ""))
    elif mode == "cloze_choose":
        ex.update(prompt=it["text"], sub=it.get("l1", ""), ask="Fill the blank", choices=choices("answer", it["answer"]))
    elif mode == "cloze_type":
        ex.update(prompt=it["text"], sub=it.get("l1", ""), ask="Type the missing word")
    elif mode == "choose_term":
        ex.update(prompt=it["def"], ask="Which term is this?", choices=choices("term", it["term"]))
    elif mode == "choose_def":
        ex.update(prompt=it["term"], ask="Which definition fits?", choices=choices("def", it["def"]))
    elif mode == "mcq":
        opts = list(it["choices"])
        rng.shuffle(opts)
        ex.update(prompt=it["q"], choices=opts,
                  ask="Every option may be reasonable. Choose the BEST one" if it.get("best") else "Choose the best answer")
        if it.get("best"):
            ex["best"] = True
    elif mode == "multi":
        opts = list(it["choices"])
        rng.shuffle(opts)
        ex.update(prompt=it["q"], ask=f"Choose {len(it['answers'])}", choices=opts, pick=len(it["answers"]))
    elif mode in ("dialogue_build", "dialogue_type"):
        mine = set(my_lines(it))
        lines = []
        for i, ln in enumerate(it["lines"]):
            row = {"who": ln["who"], "l1": ln["l1"], "mine": i in mine, "index": i}
            if i in mine:
                if mode == "dialogue_build":
                    words = _tiles(ln["l2"])
                    # two decoy words from the rest of the conversation keep it honest
                    pool = [w for j, o in enumerate(it["lines"]) if j != i for w in _tiles(o["l2"]) if w not in words]
                    rng.shuffle(pool)
                    bank = words + pool[:2]
                    rng.shuffle(bank)
                    row["bank"] = bank
            else:
                row["l2"] = ln["l2"]
                if ln.get("rom"):
                    row["rom"] = ln["rom"]
            lines.append(row)
        ex.update(title=it["title"], scene=it["scene"], lines=lines,
                  ask="Arrange your reply" if mode == "dialogue_build" else "Reply from memory")
    elif mode.startswith("line:"):
        i = int(mode.split(":", 1)[1])
        prev = it["lines"][i - 1] if i > 0 else None
        ex.update(prompt=it["lines"][i]["l1"], ask=f"Say it in {pack.get('language', 'the language')}",
                  sub=(f"{it['title']}. They said: “{prev['l2']}”" if prev else f"{it['title']}. You speak first."))
    elif mode in PIC_MODES:
        _pic_exercise(ex, it, mode, pack, rng)
    elif mode == "order":
        steps = list(it["steps"])
        for _ in range(8):                       # never hand over the answer already in order
            rng.shuffle(steps)
            if steps != it["steps"]:
                break
        ex.update(prompt=it["q"], ask="Put these in order", steps=steps)
    if it["type"] == "pin" and mode not in PIC_MODES and mode != "intro":
        _pic_lit(ex, it, mode, pack)
    return ex


def _truth(it: dict, mode: str) -> str:
    return {"choose_l1": it.get("l1"), "choose_l2": it.get("l2"), "cloze_choose": it.get("answer"),
            "glyph_choose": it.get("rom"), "glyph_pick": it.get("l2"),
            "choose_term": it.get("term"), "choose_def": it.get("def"),
            "pic_drag": it.get("l2"), "pic_tap": str(it.get("n", "")),
            "mcq": it["choices"][it["answer"]] if it["type"] == "mcq" else None}.get(mode) or ""


LIST_MODES = ("multi", "order", "dialogue_build", "dialogue_type")
_MODES = {"multi": {"multi"}, "order": {"order"}, "dialogue": {"dialogue_build", "dialogue_type"},
          "vocab": {"choose_l1", "choose_l2", "build_l2", "type_l2", "listen"},
          "phrase": {"choose_l1", "choose_l2", "build_l2", "type_l2", "listen"},
          "cloze": {"cloze_choose", "cloze_type"},
          "glyph": {"glyph_choose", "glyph_pick", "glyph_type"},
          "concept": {"choose_term", "choose_def"},
          "mcq": {"mcq"},
          "pin": {"pic_drag", "pic_tap", "type_l2"}}


def my_lines(it: dict) -> list[int]:
    """Indexes of the learner's lines in a dialogue."""
    return [i for i, ln in enumerate(it["lines"]) if ln["who"] == it["you"]]


def check_line(it: dict, index: int, answer: str) -> dict:
    """Grade one of the learner's lines in a dialogue (no scheduling)."""
    if it["type"] != "dialogue" or index not in my_lines(it):
        return {"correct": False, "flag": None, "expected": "", "error": "not one of your lines"}
    ln = it["lines"][index]
    return check_typed(answer if isinstance(answer, str) else "", [ln["l2"], *ln.get("alt", []), *([ln["rom"]] if ln.get("rom") else [])])


def truth_list(it: dict) -> list[str]:
    """The keyed answer of a multi (any order), order (this order) or dialogue (your lines) item."""
    if it["type"] == "dialogue":
        return [it["lines"][i]["l2"] for i in my_lines(it)]
    return [it["choices"][i] for i in it["answers"]] if it["type"] == "multi" else list(it["steps"])


def check(it: dict, mode: str, answer) -> dict:
    """Grade one answer for an item in a mode -> {correct, flag, expected}.

    ``answer`` is a string, or for multi/order items a list of strings."""
    if mode.startswith("line:") and it["type"] == "dialogue":
        # one line of a dialogue asked on its own (placement tests and trials)
        try:
            return check_line(it, int(mode.split(":", 1)[1]), answer)
        except ValueError:
            return {"correct": False, "flag": None, "expected": "", "error": "bad mode"}
    if mode not in _MODES[it["type"]]:
        return {"correct": False, "flag": None, "expected": "", "error": "bad mode"}
    if it["type"] == "dialogue":
        mine = my_lines(it)
        given = list(answer) if isinstance(answer, (list, tuple)) else []
        results = [check_line(it, idx, given[k] if k < len(given) and isinstance(given[k], str) else "") for k, idx in enumerate(mine)]
        right = sum(1 for r in results if r["correct"])
        flagged = any(r["flag"] for r in results)
        # A conversation is passed when every line lands; most of them is a shaky pass.
        ok = right == len(mine) or right / len(mine) >= 0.6
        return {"correct": ok, "flag": None if right == len(mine) and not flagged else ("slips" if ok else None),
                "expected": " / ".join(truth_list(it)), "expected_list": truth_list(it),
                "lines": [{"correct": r["correct"], "expected": r["expected"]} for r in results]}
    if mode in LIST_MODES:
        # Choices come from the server, so they are compared exactly: "a::b" is not "a:b".
        given = [str(a).strip() for a in answer] if isinstance(answer, (list, tuple)) else []
        want = [str(a).strip() for a in truth_list(it)]
        ok = sorted(given) == sorted(want) if mode == "multi" else given == want
        return {"correct": ok, "flag": None, "expected": (" + " if mode == "multi" else " → ").join(truth_list(it)),
                "expected_list": truth_list(it)}
    answer = answer if isinstance(answer, str) else ""
    if mode in ("type_l2", "listen", "cloze_type", "build_l2", "glyph_type"):
        return check_typed(answer, _accepted(it), slips=mode != "cloze_type")
    truth = _truth(it, mode)
    return {"correct": answer.strip() == str(truth).strip(), "flag": None, "expected": truth}


def _explain(it: dict) -> dict:
    out = {}
    if it["type"] in ("mcq", "multi", "order"):
        out["why"] = it.get("why", "")
        if it.get("whys"):
            # per-choice reasons, keyed by the choice text (the choices are shuffled when asked)
            out["whys"] = {str(c): str(w) for c, w in zip(it["choices"], it["whys"])}
    elif it["type"] == "dialogue":
        out["dialogue"] = [{"who": ln["who"], "l2": ln["l2"], "l1": ln["l1"], "rom": ln.get("rom", ""), "mine": ln["who"] == it["you"]} for ln in it["lines"]]
    elif it["type"] == "concept":
        out["why"] = f"{it['term']} — {it['def']}"
    else:
        for k in ("l1", "l2", "rom", "note", "ex", "ex_rom", "ex_l1"):
            if it.get(k):
                out[k] = it[k]
        if it["type"] == "cloze":
            out["l2"] = fill_cloze(it)
        if it["type"] == "pin":
            out["pin"] = {"n": it["n"], "x": it["x"], "y": it["y"]}
    return out


# ---------------------------------------------------------------------------
# picture lessons: each pin of a picture is its own card (type "pin"); a session
# shows a picture's new pins together as one drag-the-words exercise
# ---------------------------------------------------------------------------
PIC_MODES = ("pic_drag", "pic_tap")
PIC_DECOYS = 2          # spare word chips on a drag exercise, when the picture has other pins


def _pin_mode(reps: int) -> str:
    """New: put the words on the picture. Met once: tap the pin a word names. Then type it."""
    return "pic_drag" if reps == 0 else "pic_tap" if reps == 1 else "type_l2"


def _pic_view(it: dict) -> dict:
    """What the client needs to show a pin's picture: a known id only (packs checked the file exists)."""
    return {"id": it["picture"], "src": f"/art/pic_{it['picture']}.webp", "title": it.get("picture_title", "")}


def _pic_siblings(it: dict, pack: dict) -> list[dict]:
    """Every pin of the same picture item, in picture order."""
    unit = next((u for u in pack["units"] if u["id"] == it["unit"]), None)
    return [o for o in (unit or {}).get("items", []) if o["type"] == "pin" and o.get("group") == it["group"]]


def _pic_chips(targets: list[dict], sibs: list[dict], rng: random.Random) -> list[dict]:
    """The word chips: one per target pin, plus a couple of the picture's other words as decoys."""
    ids = {t["id"] for t in targets}
    spare = [o for o in sibs if o["id"] not in ids]
    rng.shuffle(spare)
    chips = [{"l2": o["l2"], **({"rom": o["rom"]} if o.get("rom") else {})} for o in targets + spare[:PIC_DECOYS]]
    rng.shuffle(chips)
    return chips


def _pic_exercise(ex: dict, it: dict, mode: str, pack: dict, rng: random.Random) -> None:
    sibs = _pic_siblings(it, pack) or [it]
    ex["picture"] = _pic_view(it)
    if mode == "pic_tap":
        ex.update(prompt=it["l2"], say=it["l2"], ask="Tap the place this word names",
                  pins=[{"n": o["n"], "x": o["x"], "y": o["y"]} for o in sibs])
        if it.get("rom"):
            ex["rom"] = it["rom"]
    else:       # pic_drag: one pin here; group_pictures() merges a picture's pins into one exercise
        ex.update(ask="Put each word on its place in the picture",
                  pins=[{"item": it["id"], "n": it["n"], "x": it["x"], "y": it["y"]}],
                  chips=_pic_chips([it], sibs, rng))


def _pic_lit(ex: dict, it: dict, mode: str, pack: dict) -> None:
    """A pin asked in a typed form: the picture with that one pin lit."""
    ex["picture"] = _pic_view(it)
    ex["pins"] = [{"n": it["n"], "x": it["x"], "y": it["y"], "lit": True}]
    if mode == "type_l2":
        ex["ask"] = f"Name the lit place in {pack.get('language', 'the language')}" + (
            " (romanised, or in the script)" if is_script(it["l2"]) else "")
        if re.match(r"^(?:(?:el|la|los|las|le|les) |l')", it["l2"]):
            ex["sub"] = "With its article: the article is part of the word."


def group_pictures(exercises: list[dict], seed: int = 0) -> list[dict]:
    """Merge the drag exercises of one picture into a single exercise (where the first one
    was), and its pins' introductions into one labelled picture just before it. Each pin stays
    its own item: the merged exercise lists them in ``pins`` and every pin is answered (and
    scheduled) on its own."""
    index = packs.item_index()
    groups: dict[str, list[dict]] = {}
    for ex in exercises:
        if ex["mode"] == "pic_drag":
            groups.setdefault(index[ex["item"]]["group"], []).append(ex)
    if not groups:
        return exercises
    group_of = {ex["item"]: g for g, exs in groups.items() for ex in exs}
    out: list[dict] = []
    done: set[str] = set()
    for ex in exercises:
        g = group_of.get(ex["item"])
        if g is None:
            out.append(ex)
            continue
        if ex["mode"] == "intro" or g in done:
            continue            # folded into the picture's own intro and exercise
        done.add(g)
        pins = sorted((index[e["item"]] for e in groups[g]), key=lambda o: o["n"])
        first = pins[0]
        pack = packs.get(first["pack"])
        rng = random.Random(f"{g}:pic_drag:{seed}")
        view = _pic_view(first)
        base = {"item": first["id"], "course": pack["id"], "type": "pin", "unit": first["unit"],
                "lang": pack.get("lang", ""), "group": g}
        if any(e.get("new") for e in groups[g]):
            out.append({**base, "mode": "intro", "new": True,
                        "card": {"type": "picture", "picture": view, "title": view["title"],
                                 "pins": [{"n": o["n"], "x": o["x"], "y": o["y"], "l2": o["l2"], "l1": o["l1"],
                                           **({"rom": o["rom"]} if o.get("rom") else {})} for o in pins]}})
        out.append({**base, "mode": "pic_drag", "new": any(e.get("new") for e in groups[g]), "picture": view,
                    "ask": "Put each word on its place in the picture",
                    "pins": [{"item": o["id"], "n": o["n"], "x": o["x"], "y": o["y"]} for o in pins],
                    "chips": _pic_chips(pins, _pic_siblings(first, pack), rng)})
    return out


def issued_items(exercises: list[dict]) -> list[str]:
    """The item ids a list of exercises asks (a merged picture asks each of its pins)."""
    out: list[str] = []
    for ex in exercises:
        if ex["mode"] == "intro":
            continue
        out += [p["item"] for p in ex["pins"]] if ex["mode"] == "pic_drag" and ex.get("pins") else [ex["item"]]
    return out


def answer_picture(placements, *, session: str | None = None, retry: bool = False,
                   now: float | None = None) -> dict:
    """Grade a whole drag-the-words picture: ``placements`` is [{item, answer}], one per pin.
    Each pin goes through ``answer`` on its own, so scheduling and pay are exactly those of
    any other item: only a pin the session issued, and only its first answer, counts."""
    now = now or time.time()
    if not isinstance(placements, list) or not 1 <= len(placements) <= 16:
        return {"ok": False, "error": "a picture has 1-16 pins"}
    index = packs.item_index()
    rows: list[tuple[str, str]] = []
    for p in placements:
        iid = p.get("item") if isinstance(p, dict) else None
        if not isinstance(iid, str) or (index.get(iid) or {}).get("type") != "pin" or any(iid == r[0] for r in rows):
            return {"ok": False, "error": "unknown or repeated pin"}
        given = p.get("answer")
        rows.append((iid, given[:200] if isinstance(given, str) else ""))
    if len({index[i]["group"] for i, _ in rows}) != 1:
        return {"ok": False, "error": "those pins are not one picture"}
    results, rewards, events = [], {"qi": 0, "insight": 0}, []
    for iid, given in rows:
        r = answer(iid, "pic_drag", given, retry=retry, session=session, now=now)
        if not r.get("ok"):
            return r
        results.append({"item": iid, "n": index[iid]["n"], "correct": r["correct"], "expected": r["expected"],
                        "given": given, "explain": r["explain"], "next_days": r.get("next_days")})
        rw = r.get("rewards") or {}
        for k in ("qi", "insight"):
            v = rw.get(k, 0)
            rewards[k] += v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0
        events += rw.get("events") or []
    rewards["events"] = events
    right = sum(1 for r in results if r["correct"])
    return {"ok": True, "pins": results, "right": right, "total": len(results),
            "correct": right == len(results), "rewards": rewards}


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------
def _due_cards(st: dict, course_ids: list[str], now: float) -> list[tuple[dict, dict]]:
    eod = end_of_day(st, now)
    out = []
    for cid in course_ids:
        pack = packs.get(cid)
        for u in pack["units"]:
            for it in u["items"]:
                c = st["cards"].get(it["id"])
                if c and c.get("reps") and c["due"] <= eod:
                    out.append((it, c))
    out.sort(key=lambda p: p[1]["due"])
    return out


def _new_items(st: dict, pack: dict, limit: int) -> list[dict]:
    """Next unseen items, in order, from the first unit that still has any."""
    out: list[dict] = []
    for u in pack["units"]:
        unseen = [it for it in u["items"] if not (st["cards"].get(it["id"]) or {}).get("reps")]
        if unseen:
            # Stay inside one unit per session so its notes frame what is taught.
            return unseen[:limit]
    return out


def _miss(st: dict, iid: str, given, now: float) -> None:
    """Remember a wrong answer until it has been put right."""
    m = st.setdefault("mistakes", {})
    shown = " / ".join(str(g) for g in given) if isinstance(given, (list, tuple)) else str(given or "")
    m[iid] = {"n": min(9, m.get(iid, {}).get("n", 0) + 1), "ts": now, "given": shown[:200]}
    if len(m) > 2000:
        for old in sorted(m, key=lambda k: m[k]["ts"])[:len(m) - 2000]:
            m.pop(old, None)


def _unmiss(st: dict, iid: str) -> None:
    m = st.setdefault("mistakes", {})
    if iid in m:
        m[iid]["n"] -= 1
        if m[iid]["n"] <= 0:
            m.pop(iid, None)


def mistakes(course: str | None = None, limit: int = 40) -> dict:
    """What you have got wrong and not yet put right, worst first."""
    index = packs.item_index()
    with state.LOCK:
        st = state.get()
        rows = []
        for iid, m in st.get("mistakes", {}).items():
            it = index.get(iid)
            if not it or (course and it["pack"] != course):
                continue
            pack = packs.get(it["pack"])
            rows.append({"item": iid, "course": pack["title"], "n": m["n"], "ts": m["ts"], "given": m["given"],
                         "prompt": it.get("q") or it.get("l1") or it.get("term") or it.get("title") or it.get("text", ""),
                         "expected": _explain(it).get("answer") or (it.get("l2") or it.get("def") or it.get("answer") or "")})
        rows.sort(key=lambda r: (-r["n"], -r["ts"]))
        return {"ok": True, "count": len(rows), "items": rows[:limit]}


def build_special(kind: str, course: str | None = None, now: float | None = None) -> dict:
    """An off-schedule session with a purpose: 'mistakes' (put right what you got wrong) or
    'listen' (hear it, type it). Nothing here reschedules a card."""
    now = now or time.time()
    index = packs.item_index()
    with state.LOCK:
        st = state.get()
        enrolled = _enrolled(st)
        ids = [c for c in ([course] if course else enrolled) if c in enrolled]
        seed = int(now // 60)
        rng = random.Random(seed)
        picked: list[tuple[dict, str]] = []
        if kind == "mistakes":
            ms = st.get("mistakes", {})
            for iid in sorted(ms, key=lambda k: (-ms[k]["n"], -ms[k]["ts"])):
                it = index.get(iid)
                if it and it["pack"] in ids:
                    pack = packs.get(it["pack"])
                    card = st["cards"].get(iid)
                    hard = _typed_mode(it, rng) if pack["kind"] == "language" and it["type"] != "dialogue" else _mode_for(it, card, pack)
                    picked.append((it, hard))
                if len(picked) >= 15:
                    break
        elif kind == "listen":
            pool = [(c, index[iid]) for iid, c in st["cards"].items() if iid in index and c.get("reps") and index[iid]["pack"] in ids
                    and index[iid]["type"] in ("vocab", "phrase") and packs.get(index[iid]["pack"])["kind"] == "language"]
            # hardest for the ear first: longer phrases you know least well
            pool.sort(key=lambda t: (fsrs.retrievability(max(0.0, (now - t[0]["last"]) / fsrs.DAY), t[0]["s"]), -len(t[1]["l2"])))
            picked = [(it, "listen") for _, it in pool[:PRACTICE_SIZE]]
        else:
            return {"ok": False, "error": "unknown session"}
        exs = [build_exercise(it, mode, packs.get(it["pack"]), seed) for it, mode in picked]
        rng.shuffle(exs)
        for i, ex in enumerate(exs):
            ex["n"] = i
            ex["new"] = False
        sid = _open_session(st, [ex["item"] for ex in exs], True, now) if exs else ""
        if sid:
            st["sessions"][sid]["kind"] = kind
        state.save()
        return {"ok": bool(exs), "exercises": exs, "notes": [], "practice": True, "kind": kind, "courses": ids, "session": sid,
                "error": None if exs else ("No mistakes are waiting. Well done." if kind == "mistakes" else "Learn some words first; listening practice draws on what you know.")}


def _open_session(st: dict, items: list[str], practice: bool, now: float) -> str:
    """Remember what a session issued, so only those items — once each — are
    scheduled and paid, and the session can be closed exactly once."""
    sessions = st.setdefault("sessions", {})
    for old in sorted(sessions, key=lambda k: sessions[k]["started"])[:-5]:
        sessions.pop(old, None)
    sid = uuid.uuid4().hex[:12]
    sessions[sid] = {"started": now, "practice": practice, "items": {i: 0 for i in items},
                     "n": 0, "c": 0, "done": False}
    return sid


def build_session(course: str | None = None, size: int | None = None, now: float | None = None) -> dict:
    now = now or time.time()
    with state.LOCK:
        st = state.get()
        enrolled = _enrolled(st)
        ids = [c for c in ([course] if course else enrolled) if c in enrolled]
        if not ids:
            return {"ok": False, "error": "no course", "exercises": []}
        size = int(min(max(int(size or st["settings"]["session_size"]), 5), 60))
        due = _due_cards(st, ids, now)
        backlog = len(due)
        reviews = due[:size]
        # Review debt comes first: when the backlog is deep, hold new material back.
        room = size - len(reviews)
        new_budget = 0 if backlog > 2 * size else max(room, min(5, size // 4))
        seed = int(now // 60)
        exercises: list[dict] = []
        for it, card in reviews:
            pack = packs.get(it["pack"])
            exercises.append(build_exercise(it, _mode_for(it, card, pack), pack, seed))
        random.Random(seed).shuffle(exercises)          # interleave courses and units
        new_exs: list[tuple[dict, dict]] = []
        unit_notes: list[dict] = []
        per_course = max(1, new_budget // len(ids)) if new_budget else 0
        for cid in ids:
            pack = packs.get(cid)
            stats = course_stats(st, pack, now)
            for it in _new_items(st, pack, min(per_course, stats["new_left"])):
                if it["type"] not in ("mcq", "multi", "order", "dialogue"):
                    new_exs.append((build_exercise(it, "intro", pack, seed),
                                    build_exercise(it, _mode_for(it, None, pack), pack, seed)))
                else:
                    new_exs.append((None, build_exercise(it, _mode_for(it, None, pack), pack, seed)))
                unit = next(u for u in pack["units"] if u["id"] == it["unit"])
                first_time = not any((st["cards"].get(x["id"]) or {}).get("reps") for x in unit["items"])
                if first_time and not any(n["unit"] == unit["id"] for n in unit_notes):
                    unit_notes.append({"unit": unit["id"], "course": cid, "title": unit["title"],
                                       "goal": unit.get("goal", ""), "notes": unit.get("notes", "")})
        # Weave new items in: a couple of warm-up reviews, then introduce in small
        # batches of 3 (meet three, then get tested on those three, shuffled).
        woven = exercises[:2]
        rest = exercises[2:]
        for i in range(0, len(new_exs), 3):
            batch = new_exs[i:i + 3]
            woven += [intro for intro, _ in batch if intro]
            tests = [test for _, test in batch]
            random.Random(seed + i).shuffle(tests)
            woven += tests
            woven += rest[:2]
            rest = rest[2:]
        woven += rest
        for i, ex in enumerate(woven):
            ex["n"] = i
            ex["new"] = ex["mode"] == "intro" or not (st["cards"].get(ex["item"]) or {}).get("reps")
        woven = group_pictures(woven, seed)
        for i, ex in enumerate(woven):
            ex["n"] = i
        sid = _open_session(st, issued_items(woven), False, now)
        state.save()
        return {"ok": True, "exercises": woven, "notes": unit_notes, "due_total": backlog,
                "reviews": len(reviews), "new": len(new_exs), "courses": ids,
                "session": sid, "practice": False}


def build_practice(course: str | None = None, now: float | None = None) -> dict:
    """Off-schedule practice of the weakest known items. Never reschedules."""
    now = now or time.time()
    with state.LOCK:
        st = state.get()
        enrolled = _enrolled(st)
        ids = [c for c in ([course] if course else enrolled) if c in enrolled]
        index = packs.item_index()
        known = []
        for iid, c in st["cards"].items():
            it = index.get(iid)
            if it and c.get("reps") and it["pack"] in ids:
                known.append((fsrs.retrievability(max(0.0, (now - c["last"]) / fsrs.DAY), c["s"]), it, c))
        known.sort(key=lambda t: t[0])
        seed = int(now // 60)
        exs = []
        for _, it, c in known[:PRACTICE_SIZE]:
            pack = packs.get(it["pack"])
            exs.append(build_exercise(it, _mode_for(it, c, pack), pack, seed))
        random.Random(seed).shuffle(exs)
        for i, ex in enumerate(exs):
            ex["n"] = i
            ex["new"] = False
        sid = _open_session(st, [ex["item"] for ex in exs], True, now) if exs else ""
        state.save()
        return {"ok": bool(exs), "exercises": exs, "notes": [], "practice": True, "courses": ids,
                "session": sid, "error": None if exs else "nothing learned yet"}


def answer(item_id: str, mode: str, given, *, retry: bool = False, practice: bool = False,
           claim: bool = False, session: str | None = None, now: float | None = None) -> dict:
    """Grade one answer; schedule the card (first attempt only); pay the sect.

    With ``session`` (always, over HTTP) the server decides what counts: only an
    item that session issued, and only its first answer, is scheduled and paid.
    Anything else is graded for feedback but changes nothing."""
    now = now or time.time()
    it = packs.item_index().get(item_id)
    if not it:
        return {"ok": False, "error": "unknown item"}
    res = check(it, mode, given)
    if res.get("error"):
        return {"ok": False, "error": res["error"]}
    with state.LOCK:
        st = state.get()
        if session is not None:
            rec = st.get("sessions", {}).get(session)
            if not rec:
                return {"ok": False, "error": "This session has expired. Start a new one."}
            practice = bool(rec["practice"])
            if rec["done"] or rec["items"].get(item_id, 1):
                retry = True                    # not issued, already answered, or session closed
            else:
                rec["items"][item_id] = 1
                rec["n"] += 1
                rec["c"] += 1 if res["correct"] else 0
        card = st["cards"].get(item_id)
        was_new = not (card or {}).get("reps")
        out = {"ok": True, "correct": res["correct"], "flag": res["flag"], "expected": res["expected"],
               "explain": _explain(it), "rewards": {}, "events": []}
        if "expected_list" in res:
            out["expected_list"] = res["expected_list"]
        if not retry:
            if res["correct"]:
                _unmiss(st, item_id)
            elif not practice:
                _miss(st, item_id, given, now)
        if retry or practice:
            if practice and not retry:
                out["rewards"] = game.on_answer(st, it["pack"], correct=res["correct"], is_new=False,
                                                practice=True, typed=False, now=now)
                state.save()
            return out
        if not res["correct"]:
            grade = fsrs.AGAIN
        elif res["flag"]:
            grade = fsrs.HARD
        elif claim and was_new and mode in ("type_l2", "cloze_type", "glyph_type"):
            grade = fsrs.EASY       # "I already know this" — and proved it by typing it cold
        else:
            grade = fsrs.GOOD
        new_card = _review(st, card, grade, now)
        st["cards"][item_id] = new_card
        d = _day(st, now)
        d["answers"] += 1
        d["correct"] += 1 if res["correct"] else 0
        typed = mode in ("type_l2", "listen", "cloze_type", "dialogue_type", "glyph_type")
        d["typed"] = d.get("typed", 0) + (1 if typed and res["correct"] else 0)
        if it["pack"] not in d["courses"]:
            d["courses"].append(it["pack"])
        if was_new:
            d["new"] += 1
            d["new_by_course"][it["pack"]] = d["new_by_course"].get(it["pack"], 0) + 1
        else:
            d["reviews"] += 1
        out["rewards"] = game.on_answer(st, it["pack"], correct=res["correct"], is_new=was_new,
                                        practice=False, typed=typed, now=now)
        out["next_days"] = max(0, round((new_card["due"] - now) / fsrs.DAY))
        state.save()
        return out


def finish_session(answers: int = 0, correct: int = 0, secs: int = 0, practice: bool = False,
                   session: str | None = None, now: float | None = None) -> dict:
    """Close a session: counts toward the streak/quests and pays the session reward.

    A session counts when you answered at least ``MIN_SESSION_ANSWERS`` items,
    or finished everything it offered, however little the schedule had for you."""
    now = now or time.time()
    with state.LOCK:
        st = state.get()
        d = _day(st, now)
        if session is not None:
            rec = st.get("sessions", {}).get(session)
            if not rec:
                return {"ok": False, "error": "This session has expired.", "counted": False, "stones": 0, "events": []}
            if rec["done"]:
                return {"ok": True, "counted": False, "already": True, "stones": 0, "events": [],
                        "due_left": len(_due_cards(st, _enrolled(st), now)), "streak": st.get("colony", {}).get("streak", 0)}
            rec["done"] = True
            answers, correct, practice = rec["n"], rec["c"], bool(rec["practice"])
            complete = answers >= 1 and all(rec["items"].values())      # did everything this session offered
        else:
            # Library callers (tests, scripts): never trust more than the day's own tally.
            answers = min(int(answers), d["answers"]) if not practice else int(answers)
            correct = min(int(correct), answers)
            complete = False
        d["secs"] = d.get("secs", 0) + int(min(max(secs, 0), 3 * 3600))
        enrolled = _enrolled(st)
        due_left = len(_due_cards(st, enrolled, now))
        new_left = sum(course_stats(st, packs.get(c), now)["new_left"] for c in enrolled)
        all_done = answers >= 1 and due_left == 0 and new_left == 0
        counted = (not practice) and (answers >= MIN_SESSION_ANSWERS or complete or all_done)
        if counted:
            d["sessions"] += 1
        res = game.on_session(st, answers=0 if practice else answers, correct=correct, counted=counted,
                              due_left=due_left, now=now)
        state.save()
        return {"ok": True, "counted": counted, "due_left": due_left, "new_left": new_left, **res}


def learn_more(course: str, n: int = 5, now: float | None = None) -> dict:
    """Grant extra new items today for one course (the learner's explicit choice)."""
    now = now or time.time()
    if not packs.get(course):
        return {"ok": False, "error": "unknown course"}
    with state.LOCK:
        st = state.get()
        day = day_of(st, now)
        st["extra_new"] = {day: st.get("extra_new", {}).get(day, {})}      # drop older days
        cur = st["extra_new"][day].get(course, 0)
        st["extra_new"][day][course] = min(cur + int(min(max(n, 1), 20)), 40)
        state.save()
        return {"ok": True, "extra": st["extra_new"][day][course]}


# ---------------------------------------------------------------------------
# trials (mock exams / checkpoints)
# ---------------------------------------------------------------------------
def _apportion(weights: dict[str, float], n: int, available: dict[str, int]) -> dict[str, int]:
    """Largest-remainder split of n questions across domains, capped by supply."""
    total = sum(weights.values()) or 1
    raw = {k: n * w / total for k, w in weights.items()}
    out = {k: min(int(v), available.get(k, 0)) for k, v in raw.items()}
    order = sorted(raw, key=lambda k: raw[k] - int(raw[k]), reverse=True)
    guard = 0
    while sum(out.values()) < n and guard < 10 * len(order) + 10:
        k = order[guard % len(order)]
        if out[k] < available.get(k, 0):
            out[k] += 1
        guard += 1
    return out


TEST_TYPES = ("mcq", "multi", "order")


def _test_pool(pack: dict) -> dict[str, list[dict]]:
    by_dom: dict[str, list[dict]] = {}
    for u in pack["units"]:
        for it in u["items"]:
            if it["type"] in TEST_TYPES:
                by_dom.setdefault(u["domain"], []).append(it)
    return by_dom


def readiness(st: dict, pack: dict, now: float) -> dict:
    """Are you ready for the real exam? Deliberately strict: the whole course
    met, memory holding, and the last three mock trials all above the in-app
    pass mark (which is set above the real exam's)."""
    stats = course_stats(st, pack, now)
    coverage = round(100 * stats["seen"] / max(stats["total"], 1))
    recent = [t for t in st["trials"] if t["course"] == pack["id"]][-3:]
    full = [t for t in st["trials"] if t["course"] == pack["id"] and t.get("full")]
    need = pack["exam"]["pass_pct"]
    checks = [
        {"label": "Met every item in the course", "ok": coverage >= 100, "detail": f"{coverage}% covered"},
        {"label": "Memory strength at 85% or better", "ok": stats["seen"] > 0 and stats["strength"] >= 85,
         "detail": f"{stats['strength']}% now"},
        {"label": f"Last three trials all {need}% or better", "ok": len(recent) == 3 and all(t["pct"] >= need for t in recent),
         "detail": ", ".join(f"{t['pct']}%" for t in recent) or "no trials yet"},
        {"label": "Passed a full-length mock", "ok": any(t["passed"] for t in full),
         "detail": f"best {max((t['pct'] for t in full), default=0)}%" if full else "not attempted"},
    ]
    return {"ready": all(c["ok"] for c in checks), "checks": checks}


def _typed_mode(it: dict, rng: random.Random) -> str:
    """The typed-from-memory form of a language item (one line, for a dialogue)."""
    if it["type"] == "cloze":
        return "cloze_type"
    if it["type"] == "glyph":
        return "glyph_type"
    if it["type"] == "dialogue":
        return f"line:{rng.choice(my_lines(it))}"
    return "type_l2"


def trial_info(course: str, now: float | None = None) -> dict:
    now = now or time.time()
    pack = packs.get(course)
    if not pack:
        return {"ok": False, "error": "unknown course"}
    with state.LOCK:
        st = state.get()
        full = None
        ready_for_exam = None
        if pack["kind"] == "cert":
            pool = sum(len(v) for v in _test_pool(pack).values())
            ex = pack["exam"]
            n = min(ex["questions"], pool)
            ready, need = pool >= 10, ""
            minutes, pass_pct = ex["minutes"], ex["pass_pct"]
            name = f"{ex['name']} mock trial"
            if ex.get("full") and pool >= ex["full"]["questions"]:
                full = {"questions": ex["full"]["questions"], "minutes": ex["full"]["minutes"]}
            ready_for_exam = readiness(st, pack, now)
        else:
            seen = sum(1 for u in pack["units"] for it in u["items"] if (st["cards"].get(it["id"]) or {}).get("reps"))
            n = 20
            ready = seen >= 20
            need = "" if ready else f"Learn {20 - seen} more items to unlock the checkpoint trial."
            minutes, pass_pct = 10, 80
            name = f"{pack['title'].split(' — ')[0]} {pack['title'].split(' — ')[-1].split(' ')[0]} checkpoint trial"
        history = [t for t in st["trials"] if t["course"] == course][-8:]
        # where the marks are being lost, over the last three trials
        agg: dict[str, list] = {}
        for t in history[-3:]:
            for d in t.get("domains", []):
                a = agg.setdefault(d["id"], [d["title"], 0, 0])
                a[1] += d["right"]
                a[2] += d["total"]
        weak = sorted(({"title": v[0], "pct": round(100 * v[1] / v[2]), "total": v[2]} for v in agg.values() if v[2] >= 3), key=lambda x: x["pct"])
        return {"ok": True, "course": course, "name": name, "questions": n, "minutes": minutes,
                "pass_pct": pass_pct, "ready": ready, "need": need, "history": history, "full": full,
                "readiness": ready_for_exam, "best": max((t["pct"] for t in history), default=None), "weak": weak[:3]}


def start_trial(course: str, full: bool = False, now: float | None = None) -> dict:
    now = now or time.time()
    info = trial_info(course, now)
    if not info.get("ok") or not info["ready"]:
        return {"ok": False, "error": info.get("need") or info.get("error") or "not ready"}
    if full and not info.get("full"):
        return {"ok": False, "error": "This course has no full-length mock yet."}
    pack = packs.get(course)
    n_q = info["full"]["questions"] if full else info["questions"]
    minutes = info["full"]["minutes"] if full else info["minutes"]
    rng = random.Random()
    with state.LOCK:
        st = state.get()
        chosen: list[tuple[dict, str]] = []
        if pack["kind"] == "cert":
            by_dom = _test_pool(pack)
            weights = {str(d["id"]): float(d["weight"]) for d in pack["exam"]["domains"]}
            split = _apportion(weights, n_q, {k: len(v) for k, v in by_dom.items()})
            for dom, k in split.items():
                chosen += [(it, it["type"]) for it in rng.sample(by_dom.get(dom, []), k)]
        else:
            seen = [it for u in pack["units"] for it in u["items"] if (st["cards"].get(it["id"]) or {}).get("reps")]
            for it in rng.sample(seen, n_q):
                chosen.append((it, _typed_mode(it, rng)))
        rng.shuffle(chosen)
        tid = uuid.uuid4().hex[:12]
        seed = rng.randrange(1 << 30)
        qs = []
        for i, (it, mode) in enumerate(chosen):
            ex = build_exercise(it, mode, pack, seed)
            ex["n"] = i
            qs.append(ex)
        opens = st["open_trials"]
        for old in sorted(opens, key=lambda k: opens[k]["started"])[:-3]:
            opens.pop(old, None)
        opens[tid] = {"course": course, "started": now, "minutes": minutes, "full": bool(full),
                      "pass_pct": info["pass_pct"], "items": [(it["id"], mode) for it, mode in chosen]}
        state.save()
        return {"ok": True, "trial": tid, "name": info["name"] + (" (full length)" if full else ""), "minutes": minutes,
                "pass_pct": info["pass_pct"], "questions": qs, "full": bool(full)}


def abandon_trial(trial_id: str) -> dict:
    """Drop an in-flight trial without recording or grading anything."""
    with state.LOCK:
        st = state.get()
        found = st["open_trials"].pop(trial_id, None) is not None
        state.save()
        return {"ok": True, "abandoned": found}


def submit_trial(trial_id: str, answers: list, now: float | None = None) -> dict:
    now = now or time.time()
    index = packs.item_index()
    with state.LOCK:
        st = state.get()
        tr = st["open_trials"].pop(trial_id, None)
        if not tr:
            return {"ok": False, "error": "unknown or already submitted trial"}
        pack = packs.get(tr["course"])
        overtime = now - tr["started"] > tr["minutes"] * 60 + 30
        by_dom: dict[str, list[int]] = {}
        review = []
        right = 0
        for i, (iid, mode) in enumerate(tr["items"]):
            it = index.get(iid)
            if not it:
                continue
            raw = answers[i] if i < len(answers) else None
            given = ([str(a) for a in raw] if isinstance(raw, (list, tuple)) else "") if mode in LIST_MODES \
                else (str(raw) if isinstance(raw, str) else "")
            res = check(it, mode, given)
            ok = bool(res["correct"]) and bool(given)
            shown = (" + " if mode == "multi" else " → ").join(given) if isinstance(given, list) else given
            right += ok
            unit = next(u for u in pack["units"] if u["id"] == it["unit"])
            dom = unit.get("domain") or unit["title"]
            by_dom.setdefault(dom, [0, 0])
            by_dom[dom][0] += ok
            by_dom[dom][1] += 1
            review.append({"n": i, "correct": ok, "given": shown, "expected": res["expected"],
                           "prompt": it.get("q") or it.get("l1") or it.get("text", ""), "explain": _explain(it)})
            # A wrong answer on something you have studied sends it back to the review
            # queue. Unanswered questions and items you have not met yet change nothing:
            # a trial must never mark material as learned or punish a timeout.
            card = st["cards"].get(iid)
            if not ok and given and card and card.get("reps"):
                st["cards"][iid] = _review(st, card, fsrs.AGAIN, now)
            if not ok and given:
                _miss(st, iid, given, now)              # the missed-questions bank
        total = len(tr["items"]) or 1
        pct = round(100 * right / total)
        passed = pct >= tr["pass_pct"] and not overtime
        titles = {str(d["id"]): d["title"] for d in (pack.get("exam") or {}).get("domains", [])}
        domains = [{"id": k, "title": titles.get(k, k), "right": v[0], "total": v[1],
                    "pct": round(100 * v[0] / v[1])} for k, v in by_dom.items()]
        summary = {"id": trial_id, "course": tr["course"], "ts": now, "pct": pct, "passed": passed,
                   "right": right, "total": total, "overtime": overtime, "full": bool(tr.get("full")),
                   "domains": [{"id": d["id"], "title": d["title"], "right": d["right"], "total": d["total"]} for d in domains]}
        st["trials"] = (st["trials"] + [summary])[-200:]
        rewards = game.on_trial(st, tr["course"], passed=passed, pct=pct, now=now)
        state.save()
        return {"ok": True, **summary, "domains": sorted(domains, key=lambda d: d["id"]),
                "review": review, "pass_pct": tr["pass_pct"], **rewards}


# ---------------------------------------------------------------------------
# placement: find the learner's level when they start a course, then skip ahead
# ---------------------------------------------------------------------------
PLACEMENT_PER_UNIT = {"language": 3, "cert": 2}
PLACEMENT_MAX_QUESTIONS = 60


def _placement_block(st: dict, pl: dict, pack: dict) -> list[dict]:
    """The next unit's questions: the hardest format for each sampled item."""
    unit = pack["units"][pl["unit"]]
    rng = random.Random(f"{pl['seed']}:{unit['id']}")
    if pack["kind"] == "language":
        pool = list(unit["items"])
    else:
        pool = [it for it in unit["items"] if it["type"] in TEST_TYPES] or list(unit["items"])
    picks = rng.sample(pool, min(PLACEMENT_PER_UNIT[pack["kind"]], len(pool)))
    block = []
    for it in picks:
        if it["type"] in ("cloze", "vocab", "phrase", "dialogue", "pin"):
            mode = _typed_mode(it, rng)
        elif it["type"] == "concept":
            mode = "choose_term"
        else:
            mode = it["type"]
        ex = build_exercise(it, mode, pack, pl["seed"])
        block.append(ex)
    pl["block"] = [(ex["item"], ex["mode"]) for ex in block]
    return block


def placement_start(course: str, now: float | None = None) -> dict:
    now = now or time.time()
    pack = packs.get(course)
    if not pack:
        return {"ok": False, "error": "unknown course"}
    if not pack["units"]:
        return {"ok": False, "error": "This course has nothing to test yet."}     # only pictures still to be painted
    with state.LOCK:
        st = state.get()
        opens = st.setdefault("open_placements", {})
        for old in sorted(opens, key=lambda k: opens[k]["started"])[:-2]:
            opens.pop(old, None)
        pid = uuid.uuid4().hex[:12]
        pl = {"course": course, "started": now, "seed": random.randrange(1 << 30), "unit": 0,
              "fails": 0, "passed": [], "asked": 0, "right": 0}
        opens[pid] = pl
        block = _placement_block(st, pl, pack)
        state.save()
        return {"ok": True, "placement": pid, "units": len(pack["units"]), "unit": 0,
                "unit_title": pack["units"][0]["title"], "questions": block, "kind": pack["kind"]}


def _mark_known(st: dict, pack: dict, unit: dict, proven: set[str], now: float) -> int:
    """A unit tested out of: its unseen items become cards that come back for a
    check over the next two weeks (so a lucky pass is caught by ordinary reviews)."""
    n = 0
    for i, it in enumerate(unit["items"]):
        if (st["cards"].get(it["id"]) or {}).get("reps"):
            continue
        card = fsrs.review(fsrs.new_card(), fsrs.EASY if it["id"] in proven else fsrs.GOOD, now,
                           float(st["settings"]["retention"]))
        card["due"] = now + fsrs.DAY * (2 + (i * 5 + len(unit["items"])) % 12)
        card["seen"] = now
        card["placed"] = True
        st["cards"][it["id"]] = card
        n += 1
    return n


def placement_answer(placement_id: str, answers: list, now: float | None = None, unit: int = -1) -> dict:
    """Grade the current block, then hand back the next one or the result.

    Languages stop after two units in a row are failed (the level is found);
    certifications sample every unit, since their units are not a ladder."""
    now = now or time.time()
    index = packs.item_index()
    with state.LOCK:
        st = state.get()
        pl = st.get("open_placements", {}).get(placement_id)
        if not pl:
            return {"ok": False, "error": "This placement test has expired. Start it again."}
        if unit >= 0 and unit != pl["unit"]:
            return {"ok": False, "error": "That block was already answered."}     # a double tap
        pack = packs.get(pl["course"])
        unit = pack["units"][pl["unit"]]
        right = 0
        proven: set[str] = set()
        feedback = []
        for i, (iid, mode) in enumerate(pl.get("block", [])):
            it = index.get(iid)
            raw = answers[i] if i < len(answers) else None
            given = ([str(a) for a in raw] if isinstance(raw, (list, tuple)) else "") if mode in LIST_MODES \
                else (str(raw) if isinstance(raw, str) else "")
            res = check(it, mode, given)
            ok = bool(res["correct"]) and bool(given)
            right += ok
            if ok:
                proven.add(iid)
            feedback.append({"correct": ok, "expected": res["expected"]})
        n = len(pl.get("block", []))
        pl["asked"] += n
        pl["right"] += right
        passed = n > 0 and right >= (2 if pack["kind"] == "language" else n)
        placed = 0
        if passed:
            pl["passed"].append(unit["id"])
            pl["fails"] = 0
            placed = _mark_known(st, pack, unit, proven, now)
        else:
            pl["fails"] += 1
        pl["placed"] = pl.get("placed", 0) + placed
        pl["unit"] += 1
        stop = pl["unit"] >= len(pack["units"]) or pl["asked"] >= PLACEMENT_MAX_QUESTIONS \
            or (pack["kind"] == "language" and pl["fails"] >= 2)
        if not stop:
            block = _placement_block(st, pl, pack)
            state.save()
            return {"ok": True, "done": False, "feedback": feedback, "unit": pl["unit"], "units": len(pack["units"]),
                    "unit_title": pack["units"][pl["unit"]]["title"], "questions": block, "passed_unit": passed}
        st["open_placements"].pop(placement_id, None)
        stats = course_stats(st, pack, now)
        start = next((u["title"] for u in stats["units"] if not u["done"]), None)
        summary = {"ts": now, "passed_units": len(pl["passed"]), "units": len(pack["units"]), "placed": pl["placed"],
                   "asked": pl["asked"], "right": pl["right"]}
        st.setdefault("placements", {})[pl["course"]] = summary
        state.save()
        return {"ok": True, "done": True, "feedback": feedback, "passed_unit": passed, **summary,
                "start_at": start, "course": pl["course"]}


# ---------------------------------------------------------------------------
# overview + stats
# ---------------------------------------------------------------------------
def overview(now: float | None = None) -> dict:
    now = now or time.time()
    with state.LOCK:
        st = state.get()
        all_courses = [course_stats(st, p, now) for p in packs.load_all().values()]
        mine = [c for c in all_courses if c["enrolled"]]
        events = game.ensure(st, now, _quest_ctx(st, mine, now) if mine else None)
        d = _day(st, now)
        if mine and d["answers"] == 0 and not any(c["due"] or c["new_left"] for c in mine):
            events += game.credit_rest_day(st, now)      # nothing scheduled: the day counts
        out = {
            "events": events,
            "problem": state.take_error(),
            "courses": all_courses,
            "today": {"due": sum(c["due"] for c in mine), "new_left": sum(c["new_left"] for c in mine),
                      "answers": d["answers"], "correct": d["correct"], "sessions": d["sessions"],
                      "new": d["new"], "reviews": d["reviews"], "day": day_of(st, now)},
            "settings": dict(st["settings"]),
            "placements": {k: dict(v) for k, v in st.get("placements", {}).items()},
            "mistakes": sum(1 for iid in st.get("mistakes", {}) if iid in packs.item_index() and packs.item_index()[iid]["pack"] in _enrolled(st)),
            "drills": {k: dict(v) for k, v in st.get("drills", {}).items()},
            "can_listen": any(c["kind"] == "language" and c["enrolled"] and c["seen"] > 0 for c in all_courses),
            "sect": game.view(st, now),
            "onboarded": bool(st.get("colony", {}).get("name")),
        }
        state.save()
        return out


def stats(days: int = 60, now: float | None = None) -> dict:
    now = now or time.time()
    with state.LOCK:
        st = state.get()
        out = []
        for i in range(days - 1, -1, -1):
            key = day_of(st, now - i * 86400)
            d = st["days"].get(key, {})
            out.append({"day": key, "answers": d.get("answers", 0), "correct": d.get("correct", 0),
                        "new": d.get("new", 0), "reviews": d.get("reviews", 0),
                        "secs": d.get("secs", 0), "sessions": d.get("sessions", 0)})
        # forecast: cards falling due on each of the next 14 days
        eod = end_of_day(st, now)
        forecast = [0] * 14
        for c in st["cards"].values():
            if c.get("reps"):
                idx = max(0, int((c["due"] - eod) // 86400) + 1) if c["due"] > eod else 0
                if idx < 14:
                    forecast[idx] += 1
        tot_a = sum(x["answers"] for x in out)
        tot_c = sum(x["correct"] for x in out)
        return {"days": out, "forecast": forecast, "accuracy": round(100 * tot_c / tot_a) if tot_a else None,
                "answers": tot_a, "active_days": sum(1 for x in out if x["answers"]),
                "minutes": round(sum(x["secs"] for x in out) / 60),
                "cards": sum(1 for c in st["cards"].values() if c.get("reps")),
                "mastered": sum(1 for c in st["cards"].values() if c.get("reps") and c["s"] >= MATURE_DAYS)}
