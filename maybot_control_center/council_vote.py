"""Merit-weighted council vote — weighted-ensemble decisions with an audit trail.

For ambiguous calls the disciples convene a council: each voting disciple casts
a ballot for one option, and ballots are weighted by the voter's **sect
standing** (the same composite that decides leadership challenges). The option
with the greatest total standing-weight carries the decision, and every
dissenting voice is recorded so the choice — and the disagreement behind it —
stays auditable.

State (the vote history) lives in-memory under a lock, matching the other live
modules; ``governance`` is imported lazily inside :func:`tally` to avoid an
import cycle and to keep tests free of that dependency unless they want it.
"""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_history: list[dict] = []

HISTORY_CAP = 100


def _resolve_weight(agent: str, weights: dict | None) -> float:
    """Weight for one voter.

    When an explicit ``weights`` dict is supplied it is authoritative: an agent
    missing from it, or carrying a non-positive/non-numeric weight, counts as 0.
    When ``weights`` is None the weight is derived from the voter's sect standing
    (``governance.standing(agent)["score"]``), defaulting to 1.0 if that fails.
    """
    if weights is not None:
        if agent not in weights:
            return 0.0  # missing weight counts as no vote
        try:
            w = float(weights[agent])
        except (TypeError, ValueError):
            return 0.0
        return w if w > 0 else 0.0  # negative/zero count as no vote
    # No explicit weights: derive from sect standing (default 1.0 on failure).
    try:
        from . import governance  # lazy sibling import
        score = float(governance.standing(agent)["score"])
        return score if score > 0 else 0.0
    except Exception:
        return 1.0


def tally(question: str, votes: dict, weights: dict | None = None) -> dict:
    """Hold a merit-weighted council vote and record the outcome.

    ``votes`` maps each voting disciple to its chosen option (a string).
    ``weights`` optionally maps agents to explicit float weights; when omitted,
    each voter's weight is its ``governance.standing(agent)["score"]`` (1.0 if
    that lookup fails). Missing or non-positive weights count as zero.

    Returns a copy of the recorded result. Raises ``ValueError`` if ``question``
    is blank or ``votes`` is empty.
    """
    if not question or not question.strip():
        raise ValueError("question must not be blank")
    if not votes:
        raise ValueError("votes must not be empty")

    resolved: dict[str, float] = {}
    tally_by_choice: dict[str, float] = {}
    max_weight_by_choice: dict[str, float] = {}
    for agent, choice in votes.items():
        w = _resolve_weight(agent, weights)
        resolved[agent] = w
        tally_by_choice[choice] = tally_by_choice.get(choice, 0.0) + w
        max_weight_by_choice[choice] = max(max_weight_by_choice.get(choice, 0.0), w)

    # Winner: greatest total weight. Deterministic tie-break: the choice backed
    # by the single highest-weight voter, then alphabetical choice.
    winner = min(
        tally_by_choice,
        key=lambda c: (-tally_by_choice[c], -max_weight_by_choice[c], c),
    )

    dissent = sorted(a for a, c in votes.items() if c != winner)

    weighted = weights is None or any(w != 1 for w in resolved.values())

    result = {
        "question": question,
        "winner": winner,
        "tally": dict(tally_by_choice),
        "votes": dict(votes),
        "weights": resolved,
        "dissent": dissent,
        "weighted": bool(weighted),
        "ts": int(time.time() * 1000),
    }

    with _lock:
        _history.append(result)
        if len(_history) > HISTORY_CAP:
            del _history[: len(_history) - HISTORY_CAP]

    return _copy(result)


def history(limit: int = 50) -> list[dict]:
    """Recent vote results (copies), newest last. ``limit`` caps the count."""
    with _lock:
        items = _history[-limit:] if limit and limit > 0 else list(_history)
        return [_copy(r) for r in items]


def clear() -> None:
    """Reset all council-vote state."""
    with _lock:
        _history.clear()


def _copy(result: dict) -> dict:
    """A deep-enough copy so callers can't mutate stored history."""
    out = dict(result)
    out["tally"] = dict(result["tally"])
    out["votes"] = dict(result["votes"])
    out["weights"] = dict(result["weights"])
    out["dissent"] = list(result["dissent"])
    return out
