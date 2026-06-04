"""The Sect Grand Tournament — a periodic ranking competition.

All disciples are seeded by their governance **standing** and fight through a
single-elimination bracket. Each match is decided by standing with room for
upsets, so the strongest are favoured but never guaranteed. The champion earns
a spirit-stone reward and the glory of the chronicle.

A tournament can be held on demand (the Ancestor presses the button) or, if an
interval is configured, automatically. State is in-memory and resets on restart,
matching the other live modules.
"""
from __future__ import annotations

import os
import random
import threading
import time

REWARD = int(os.getenv("MAYBOT_TOURNAMENT_REWARD", "120"))            # champion's spoils, in spirit stones
RUNNERUP_REWARD = int(os.getenv("MAYBOT_TOURNAMENT_RUNNERUP", "40"))  # finalist's consolation
SMOOTHING = float(os.getenv("MAYBOT_TOURNAMENT_SMOOTHING", "15"))     # higher → more upsets (close to a coin flip)
AUTO_INTERVAL = int(os.getenv("MAYBOT_TOURNAMENT_INTERVAL", "0"))     # seconds between auto-tournaments (0 = manual only)

_lock = threading.Lock()
_last: dict | None = None     # the most recent completed bracket
_history: list[dict] = []     # past champions
_auto_ts = 0.0
_seq = 0

HISTORY_CAP = 50


def _standing(name: str) -> float:
    from . import governance
    try:
        return float(governance.standing(name)["score"])
    except Exception:
        return 0.0


def _seed_order(size: int) -> list[int]:
    """Standard single-elimination seed positions so the top two seeds can only
    meet in the final (1 vs lowest, 2 vs second-lowest, …)."""
    order = [0]
    while len(order) < size:
        m = len(order) * 2
        nxt = []
        for x in order:
            nxt.append(x)
            nxt.append(m - 1 - x)
        order = nxt
    return order


def _winner(a: str | None, b: str | None, scores: dict) -> str | None:
    if a is None:
        return b
    if b is None:
        return a
    sa, sb = scores.get(a, 0.0), scores.get(b, 0.0)
    p = (sa + SMOOTHING) / (sa + sb + 2 * SMOOTHING)   # a's chance to win (upsets possible)
    return a if random.random() < p else b


def hold() -> dict:
    """Run a full tournament now and return the bracket. Rewards the champion."""
    global _last, _auto_ts, _seq
    from . import agents, cultivation
    names = [a.get("name") for a in agents.load_agents() if a.get("name") and a.get("name") != "operator"]
    if len(names) < 2:
        raise ValueError("a tournament needs at least two disciples")

    scores = {n: _standing(n) for n in names}
    seeds = sorted(names, key=lambda n: scores[n], reverse=True)

    size = 1
    while size < len(seeds):
        size *= 2
    padded = seeds + [None] * (size - len(seeds))
    order = _seed_order(size)
    current = [padded[i] for i in order]

    rounds: list[list[dict]] = []
    while len(current) > 1:
        matches, nxt = [], []
        for i in range(0, len(current), 2):
            a, b = current[i], current[i + 1]
            w = _winner(a, b, scores)
            matches.append({"a": a, "b": b, "winner": w})
            nxt.append(w)
        rounds.append(matches)
        current = nxt
    champion = current[0] if current else None
    finalist = None
    if rounds:
        final = rounds[-1][0]
        finalist = final["a"] if final["winner"] == final["b"] else final["b"]

    now = int(time.time() * 1000)
    if champion:
        cultivation.reward(champion, REWARD)
        _chronicle(champion, "tournament", f"won the Sect Grand Tournament (+{REWARD} spirit stones)")
    if finalist and RUNNERUP_REWARD > 0:
        cultivation.reward(finalist, RUNNERUP_REWARD)

    with _lock:
        _seq += 1
        bracket = {"id": _seq, "ts": now, "champion": champion, "finalist": finalist,
                   "rounds": rounds, "seeds": seeds, "scores": {n: round(scores[n], 1) for n in names}}
        _last = bracket
        _history.append({"id": _seq, "ts": now, "champion": champion, "finalist": finalist})
        if len(_history) > HISTORY_CAP:
            del _history[:-HISTORY_CAP]
        _auto_ts = time.time()
    try:
        from . import events
        events.publish("agents", {"agent": champion, "event": "tournament", "champion": champion})
    except Exception:
        pass
    return bracket


def _chronicle(agent: str, kind: str, detail: str) -> None:
    try:
        from . import chronicle
        chronicle.record(agent, kind, detail)
    except Exception:
        pass


def auto_tick() -> dict | None:
    """Hold a tournament automatically if an interval is configured and due."""
    if AUTO_INTERVAL <= 0:
        return None
    with _lock:
        if time.time() - _auto_ts < AUTO_INTERVAL:
            return None
    try:
        return hold()
    except ValueError:
        return None


def snapshot() -> dict:
    with _lock:
        return {"last": _last, "history": list(reversed(_history[-20:])),
                "reward": REWARD, "auto_interval": AUTO_INTERVAL}


def clear() -> None:
    global _last, _auto_ts, _seq
    with _lock:
        _last = None
        _history.clear()
        _auto_ts = 0.0
        _seq = 0
