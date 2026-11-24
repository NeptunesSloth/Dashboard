"""FSRS-6 spaced-repetition scheduler (pure Python, no dependencies).

Implements the open Free Spaced Repetition Scheduler, version 6 (the version
py-fsrs 6.x and current Anki ship), with its published default weights. A card's memory is two numbers:

* **stability** ``s`` — days until recall probability falls to 90%;
* **difficulty** ``d`` — 1 (easy) .. 10 (hard).

``review(card, grade, now)`` returns the updated card with its next due time.
Grades: 1 Again, 2 Hard, 3 Good, 4 Easy. Reviews of the same card on the same
day use the short-term stability formula. There are no hand-tuned "learning
steps": a failed or brand-new card simply comes back within the session (the
engine re-queues it) and FSRS schedules the next day-scale review.

References: open-spaced-repetition/fsrs4anki wiki "The Algorithm" (FSRS-6) and
the py-fsrs reference implementation; the evidence for choosing it over SM-2 is
in docs/research/sect-academy-design-inputs.md.
"""
from __future__ import annotations

import math

AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4

# FSRS-6 default parameters (w0..w20), identical in the wiki and py-fsrs.
W = (0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001, 1.8722, 0.1666, 0.796,
     1.4835, 0.0614, 0.2629, 1.6483, 0.6014, 1.8729, 0.5425, 0.0912, 0.0658, 0.1542)
DECAY = -W[20]
FACTOR = 0.9 ** (1 / DECAY) - 1     # makes R(t = s) exactly 0.9
S_MIN = 0.001
MAX_INTERVAL = 36500        # days
DAY = 86400.0


def retrievability(elapsed_days: float, s: float) -> float:
    """Probability of recall ``elapsed_days`` after the last review."""
    if s <= 0:
        return 0.0
    return (1 + FACTOR * max(0.0, elapsed_days) / s) ** DECAY


def next_interval(s: float, retention: float = 0.9) -> int:
    """Days until recall probability decays to ``retention``."""
    ivl = s / FACTOR * (retention ** (1 / DECAY) - 1)
    return int(min(max(round(ivl), 1), MAX_INTERVAL))


def _clamp_d(d: float) -> float:
    return min(max(d, 1.0), 10.0)


def _init_s(grade: int) -> float:
    return max(W[grade - 1], S_MIN)


def _init_d(grade: int) -> float:
    return _clamp_d(W[4] - math.exp(W[5] * (grade - 1)) + 1)


def _next_d(d: float, grade: int) -> float:
    delta = -W[6] * (grade - 3)
    d2 = d + delta * (10 - d) / 9                       # linear damping
    d0_easy = W[4] - math.exp(W[5] * (EASY - 1)) + 1    # unclamped D0(Easy)
    return _clamp_d(W[7] * d0_easy + (1 - W[7]) * d2)   # mean reversion


def _recall_s(d: float, s: float, r: float, grade: int) -> float:
    hard = W[15] if grade == HARD else 1.0
    easy = W[16] if grade == EASY else 1.0
    return s * (1 + math.exp(W[8]) * (11 - d) * s ** -W[9]
                * (math.exp((1 - r) * W[10]) - 1) * hard * easy)


def _forget_s(d: float, s: float, r: float) -> float:
    s2 = W[11] * d ** -W[12] * ((s + 1) ** W[13] - 1) * math.exp((1 - r) * W[14])
    return min(s2, s / math.exp(W[17] * W[18]))     # a lapse never increases stability


def _short_term_s(s: float, grade: int) -> float:
    inc = math.exp(W[17] * (grade - 3 + W[18])) * s ** -W[19]
    if grade >= HARD:
        inc = max(inc, 1.0)         # a same-day pass never lowers stability
    return s * inc


def new_card() -> dict:
    return {"s": 0.0, "d": 0.0, "due": 0.0, "last": 0.0, "reps": 0, "lapses": 0}


def review(card: dict, grade: int, now: float, retention: float = 0.9) -> dict:
    """Apply one graded review at unix time ``now``; returns a new card dict."""
    grade = int(min(max(grade, AGAIN), EASY))
    c = dict(card)
    if not c.get("reps") or c.get("s", 0) <= 0:
        s, d = _init_s(grade), _init_d(grade)
    else:
        elapsed = max(0.0, (now - c["last"]) / DAY)
        s0, d0 = c["s"], c["d"]
        if elapsed < 1.0:
            s = _short_term_s(s0, grade)
        elif grade == AGAIN:
            s = _forget_s(d0, s0, retrievability(elapsed, s0))
        else:
            s = _recall_s(d0, s0, retrievability(elapsed, s0), grade)
        d = _next_d(d0, grade)
    c["s"] = max(s, S_MIN)
    c["d"] = d
    c["reps"] = int(c.get("reps", 0)) + 1
    if grade == AGAIN and card.get("reps"):
        c["lapses"] = int(c.get("lapses", 0)) + 1
    c["last"] = now
    # Again: due right away (the session re-shows it; tomorrow at the latest).
    c["due"] = now if grade == AGAIN else now + next_interval(c["s"], retention) * DAY
    return c
