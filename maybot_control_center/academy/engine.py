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

from . import fsrs, game, packs, state

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


def _quest_ctx(st: dict, mine: list[dict]) -> dict:
    """What is feasible today, so daily quests are never impossible."""
    known_lang = any(c["kind"] == "language" and c["seen"] >= 8 for c in mine)
    return {"due": sum(c["due"] for c in mine), "new_left": sum(c["new_left"] for c in mine),
            "courses": len(mine), "typed_possible": known_lang}


def set_settings(patch: dict) -> dict:
    with state.LOCK:
        st = state.get()
        s = st["settings"]
        if "new_per_day" in patch:
            s["new_per_day"] = int(min(max(int(patch["new_per_day"]), 0), 40))
        if "session_size" in patch:
            s["session_size"] = int(min(max(int(patch["session_size"]), 5), 60))
        if "retention" in patch:
            s["retention"] = float(min(max(float(patch["retention"]), 0.8), 0.95))
        if "tz_offset_min" in patch:
            s["tz_offset_min"] = int(min(max(int(patch["tz_offset_min"]), -840), 840))
        if "audio" in patch:
            s["audio"] = bool(patch["audio"])
        state.save()
        return dict(s)


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
    keys = ("id", "type", "l1", "l2", "alt", "note", "ex", "ex_l1", "text", "answer", "term", "def", "q", "why")
    out = {k: it[k] for k in keys if k in it and it[k] not in ("", None, [])}
    if it["type"] == "mcq":
        out["correct"] = it["choices"][it["answer"]]
    if it["type"] == "cloze":
        out["full"] = fill_cloze(it)
    return out


# ---------------------------------------------------------------------------
# answer normalisation + checking
# ---------------------------------------------------------------------------
_PUNCT = re.compile(r"[¿¡?!.,;:\"“”«»()\[\]…]")


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


def check_typed(answer: str, accepted: list[str]) -> dict:
    """Grade a typed answer. Returns {correct, flag, expected}."""
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
        if len(got_plain) >= 4 and got_plain == _strip_accents(n):
            return {"correct": True, "flag": "accent", "expected": a}
    for a, n in zip(accepted, normed):
        plain = _strip_accents(n)
        # One slip is forgiven on longer answers — but never the article (le/la,
        # el/la, un/une): that single letter *is* the thing being learned.
        if len(plain) >= 6 and _edit1(got_plain, plain) and got_plain.split(" ")[0] == plain.split(" ")[0]:
            return {"correct": True, "flag": "typo", "expected": a}
    return {"correct": False, "flag": None, "expected": expected}


def fill_cloze(it: dict) -> str:
    """The cloze sentence with its answer in place (capitalised at sentence start)."""
    ans = it["answer"]
    if it["text"].lstrip().startswith("___"):
        ans = ans[:1].upper() + ans[1:]
    return it["text"].replace("___", ans)


def _accepted(it: dict) -> list[str]:
    if it["type"] == "cloze":
        return [it["answer"], *it.get("alt", [])]
    return [it["l2"], *it.get("alt", [])]


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
        if pack.get("lang") and reps >= 3 and reps % 3 == 0:
            return "listen"
        return "type_l2"
    if t == "cloze":
        return "cloze_choose" if reps == 0 else "cloze_type"
    if t == "concept":
        return "choose_term" if reps % 2 == 0 else "choose_def"
    return "mcq"


def _distractors(it: dict, pack: dict, field: str, rng: random.Random, n: int = 3) -> list[str]:
    """Plausible wrong options: same field from sibling items, same unit first."""
    truth = {_norm(it[field])} | ({_norm(a) for a in _accepted(it)} if field in ("l2", "answer") else set())
    same_unit, others = [], []
    for u in pack["units"]:
        for o in u["items"]:
            if o["id"] == it["id"] or field not in o:
                continue
            if field in ("l1", "l2") and (o["type"] == "phrase") != (it["type"] == "phrase"):
                continue
            (same_unit if u["id"] == it["unit"] else others).append(o[field])
    target = _norm(it[field])

    def clashes(v: str) -> bool:
        # An option that contains the answer (or is contained in it) is a trick, not a test.
        nv = _norm(v)
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
    elif mode == "choose_l2":
        ex.update(prompt=it["l1"], ask=f"Choose the {pack.get('language', 'translation')}", choices=choices("l2", it["l2"]))
    elif mode == "type_l2":
        ex.update(prompt=it["l1"], ask=f"Type it in {pack.get('language', 'the language')}")
    elif mode == "listen":
        ex.update(say=it["l2"], hint=it["l1"], ask="Type what you hear")
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
        ex.update(prompt=it["q"], ask="Choose the best answer", choices=opts)
    return ex


def _truth(it: dict, mode: str) -> str:
    return {"choose_l1": it.get("l1"), "choose_l2": it.get("l2"), "cloze_choose": it.get("answer"),
            "choose_term": it.get("term"), "choose_def": it.get("def"),
            "mcq": it["choices"][it["answer"]] if it["type"] == "mcq" else None}.get(mode) or ""


_MODES = {"vocab": {"choose_l1", "choose_l2", "type_l2", "listen"},
          "phrase": {"choose_l1", "choose_l2", "type_l2", "listen"},
          "cloze": {"cloze_choose", "cloze_type"},
          "concept": {"choose_term", "choose_def"},
          "mcq": {"mcq"}}


def check(it: dict, mode: str, answer: str) -> dict:
    """Grade one answer for an item in a mode -> {correct, flag, expected}."""
    if mode not in _MODES[it["type"]]:
        return {"correct": False, "flag": None, "expected": "", "error": "bad mode"}
    if mode in ("type_l2", "listen", "cloze_type"):
        return check_typed(answer, _accepted(it))
    truth = _truth(it, mode)
    return {"correct": _norm(answer) == _norm(truth), "flag": None, "expected": truth}


def _explain(it: dict) -> dict:
    out = {}
    if it["type"] == "mcq":
        out["why"] = it.get("why", "")
    elif it["type"] == "concept":
        out["why"] = f"{it['term']} — {it['def']}"
    else:
        for k in ("l1", "l2", "note", "ex", "ex_l1"):
            if it.get(k):
                out[k] = it[k]
        if it["type"] == "cloze":
            out["l2"] = fill_cloze(it)
    return out


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


def build_session(course: str | None = None, size: int | None = None, now: float | None = None) -> dict:
    now = now or time.time()
    with state.LOCK:
        st = state.get()
        ids = [course] if course else _enrolled(st)
        ids = [c for c in ids if packs.get(c)]
        if not ids:
            return {"ok": False, "error": "no course", "exercises": []}
        size = int(size or st["settings"]["session_size"])
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
                if it["type"] != "mcq":
                    new_exs.append((build_exercise(it, "intro", pack, seed),
                                    build_exercise(it, _mode_for(it, None, pack), pack, seed)))
                else:
                    new_exs.append((None, build_exercise(it, "mcq", pack, seed)))
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
        return {"ok": True, "exercises": woven, "notes": unit_notes, "due_total": backlog,
                "reviews": len(reviews), "new": len(new_exs), "courses": ids,
                "session": uuid.uuid4().hex[:12], "practice": False}


def build_practice(course: str | None = None, now: float | None = None) -> dict:
    """Off-schedule practice of the weakest known items. Never reschedules."""
    now = now or time.time()
    with state.LOCK:
        st = state.get()
        ids = [c for c in ([course] if course else _enrolled(st)) if packs.get(c)]
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
        return {"ok": bool(exs), "exercises": exs, "notes": [], "practice": True, "courses": ids,
                "session": uuid.uuid4().hex[:12], "error": None if exs else "nothing learned yet"}


def answer(item_id: str, mode: str, given: str, *, retry: bool = False, practice: bool = False,
           claim: bool = False, now: float | None = None) -> dict:
    """Grade one answer; schedule the card (first attempt only); pay the sect."""
    now = now or time.time()
    it = packs.item_index().get(item_id)
    if not it:
        return {"ok": False, "error": "unknown item"}
    res = check(it, mode, given)
    if res.get("error"):
        return {"ok": False, "error": res["error"]}
    with state.LOCK:
        st = state.get()
        card = st["cards"].get(item_id)
        was_new = not (card or {}).get("reps")
        out = {"ok": True, "correct": res["correct"], "flag": res["flag"], "expected": res["expected"],
               "explain": _explain(it), "rewards": {}, "events": []}
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
        elif claim and was_new and mode in ("type_l2", "cloze_type"):
            grade = fsrs.EASY       # "I already know this" — and proved it by typing it cold
        else:
            grade = fsrs.GOOD
        new_card = fsrs.review(card or fsrs.new_card(), grade, now, float(st["settings"]["retention"]))
        new_card["seen"] = (card or {}).get("seen") or now
        st["cards"][item_id] = new_card
        d = _day(st, now)
        d["answers"] += 1
        d["correct"] += 1 if res["correct"] else 0
        typed = mode in ("type_l2", "listen", "cloze_type")
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


def finish_session(answers: int, correct: int, secs: int = 0, practice: bool = False,
                   now: float | None = None) -> dict:
    """Close a session: counts toward the streak/quests and pays the session reward."""
    now = now or time.time()
    with state.LOCK:
        st = state.get()
        d = _day(st, now)
        # Trust the server's own tally, not the client's, for anything that pays.
        answers = min(int(answers), d["answers"]) if not practice else int(answers)
        d["secs"] = d.get("secs", 0) + int(min(max(secs, 0), 3 * 3600))
        counted = (not practice) and answers >= MIN_SESSION_ANSWERS
        if counted:
            d["sessions"] += 1
        due_left = len(_due_cards(st, _enrolled(st), now))
        res = game.on_session(st, answers=answers, correct=min(int(correct), answers), counted=counted,
                              due_left=due_left, now=now)
        state.save()
        return {"ok": True, "counted": counted, "due_left": due_left, **res}


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


def trial_info(course: str, now: float | None = None) -> dict:
    now = now or time.time()
    pack = packs.get(course)
    if not pack:
        return {"ok": False, "error": "unknown course"}
    with state.LOCK:
        st = state.get()
        if pack["kind"] == "cert":
            pool = sum(1 for u in pack["units"] for it in u["items"] if it["type"] == "mcq")
            ex = pack["exam"]
            n = min(ex["questions"], pool)
            ready, need = pool >= 10, ""
            minutes, pass_pct = ex["minutes"], ex["pass_pct"]
            name = f"{ex['name']} mock trial"
        else:
            seen = sum(1 for u in pack["units"] for it in u["items"] if (st["cards"].get(it["id"]) or {}).get("reps"))
            n = min(20, seen)
            ready = seen >= 20
            need = "" if ready else f"Learn {20 - seen} more items to unlock the checkpoint trial."
            minutes, pass_pct = 10, 80
            name = f"{pack.get('language', pack['title'])} checkpoint trial"
        history = [t for t in st["trials"] if t["course"] == course][-8:]
        return {"ok": True, "course": course, "name": name, "questions": n, "minutes": minutes,
                "pass_pct": pass_pct, "ready": ready, "need": need, "history": history,
                "best": max((t["pct"] for t in history), default=None)}


def start_trial(course: str, now: float | None = None) -> dict:
    now = now or time.time()
    info = trial_info(course, now)
    if not info.get("ok") or not info["ready"]:
        return {"ok": False, "error": info.get("need") or info.get("error") or "not ready"}
    pack = packs.get(course)
    rng = random.Random()
    with state.LOCK:
        st = state.get()
        chosen: list[tuple[dict, str]] = []
        if pack["kind"] == "cert":
            by_dom: dict[str, list[dict]] = {}
            for u in pack["units"]:
                for it in u["items"]:
                    if it["type"] == "mcq":
                        by_dom.setdefault(u["domain"], []).append(it)
            weights = {str(d["id"]): float(d["weight"]) for d in pack["exam"]["domains"]}
            split = _apportion(weights, info["questions"], {k: len(v) for k, v in by_dom.items()})
            for dom, k in split.items():
                chosen += [(it, "mcq") for it in rng.sample(by_dom.get(dom, []), k)]
        else:
            seen = [it for u in pack["units"] for it in u["items"] if (st["cards"].get(it["id"]) or {}).get("reps")]
            for it in rng.sample(seen, info["questions"]):
                chosen.append((it, "cloze_type" if it["type"] == "cloze" else "type_l2"))
        rng.shuffle(chosen)
        tid = uuid.uuid4().hex[:12]
        seed = rng.randrange(1 << 30)
        qs = []
        for i, (it, mode) in enumerate(chosen):
            ex = build_exercise(it, mode, pack, seed)
            ex["n"] = i
            qs.append(ex)
        # keep at most a few in-flight trials
        opens = st["open_trials"]
        for old in sorted(opens, key=lambda k: opens[k]["started"])[:-3]:
            opens.pop(old, None)
        opens[tid] = {"course": course, "started": now, "minutes": info["minutes"],
                      "pass_pct": info["pass_pct"], "items": [(it["id"], mode) for it, mode in chosen]}
        state.save()
        return {"ok": True, "trial": tid, "name": info["name"], "minutes": info["minutes"],
                "pass_pct": info["pass_pct"], "questions": qs}


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
            given = str(answers[i]) if i < len(answers) and answers[i] is not None else ""
            res = check(it, mode, given)
            ok = bool(res["correct"]) and bool(given)
            right += ok
            unit = next(u for u in pack["units"] if u["id"] == it["unit"])
            dom = unit.get("domain") or unit["title"]
            by_dom.setdefault(dom, [0, 0])
            by_dom[dom][0] += ok
            by_dom[dom][1] += 1
            review.append({"n": i, "correct": ok, "given": given, "expected": res["expected"],
                           "prompt": it.get("q") or it.get("l1") or it.get("text", ""), "explain": _explain(it)})
            # A miss joins tomorrow's review queue (unseen items become cards).
            if not ok:
                card = st["cards"].get(iid)
                nc = fsrs.review(card or fsrs.new_card(), fsrs.AGAIN, now, float(st["settings"]["retention"]))
                nc["seen"] = (card or {}).get("seen") or now
                nc["due"] = now + fsrs.DAY * 0.5
                st["cards"][iid] = nc
        total = len(tr["items"]) or 1
        pct = round(100 * right / total)
        passed = pct >= tr["pass_pct"] and not overtime
        titles = {str(d["id"]): d["title"] for d in (pack.get("exam") or {}).get("domains", [])}
        domains = [{"id": k, "title": titles.get(k, k), "right": v[0], "total": v[1],
                    "pct": round(100 * v[0] / v[1])} for k, v in by_dom.items()]
        summary = {"id": trial_id, "course": tr["course"], "ts": now, "pct": pct, "passed": passed,
                   "right": right, "total": total, "overtime": overtime}
        st["trials"] = (st["trials"] + [summary])[-200:]
        rewards = game.on_trial(st, tr["course"], passed=passed, pct=pct, now=now)
        state.save()
        return {"ok": True, **summary, "domains": sorted(domains, key=lambda d: d["id"]),
                "review": review, "pass_pct": tr["pass_pct"], **rewards}


# ---------------------------------------------------------------------------
# overview + stats
# ---------------------------------------------------------------------------
def overview(now: float | None = None) -> dict:
    now = now or time.time()
    with state.LOCK:
        st = state.get()
        all_courses = [course_stats(st, p, now) for p in packs.load_all().values()]
        mine = [c for c in all_courses if c["enrolled"]]
        events = game.ensure(st, now, _quest_ctx(st, mine) if mine else None)
        d = _day(st, now)
        out = {
            "events": events,
            "courses": all_courses,
            "today": {"due": sum(c["due"] for c in mine), "new_left": sum(c["new_left"] for c in mine),
                      "answers": d["answers"], "correct": d["correct"], "sessions": d["sessions"],
                      "new": d["new"], "reviews": d["reviews"], "day": day_of(st, now)},
            "settings": dict(st["settings"]),
            "game": game.view(st, now),
            "onboarded": bool(mine),
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
