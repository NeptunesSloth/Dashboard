"""Sect Advisor — a wise sect-elder briefing on the dashboard state.

Turns a Command Hall ``snapshot()`` (see :mod:`maybot_control_center.command`)
into an in-character operations briefing. When an Anthropic API key is present
and the ``anthropic`` SDK is importable, the briefing is written by Claude in a
wise sect-elder voice. Otherwise a strong, fully-local templated fallback reads
the snapshot directly and produces a genuinely useful natural-language briefing
with real highlights and actionable suggestions — no network, no key, no libs.

Everything is wrapped so this module imports and runs OFFLINE.
"""
from __future__ import annotations

import os


# The Anthropic model used for the LLM path. Override via env. NB: deliberately
# a Sonnet default (not Opus) to keep the advisor briefings cheap/fast.
_DEFAULT_MODEL = "claude-sonnet-4-6"


def _model() -> str:
    """The advisor's Claude model id (env-overridable)."""
    return os.getenv("MAYBOT_ADVISOR_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL


def _llm_enabled() -> bool:
    """True iff the LLM path is usable: a key is set AND the SDK imports."""
    if not os.getenv("ANTHROPIC_API_KEY", "").strip():
        return False
    try:
        import anthropic  # noqa: F401
    except Exception:
        return False
    return True


def available() -> dict:
    """Describe whether the live LLM advisor path is active.

    Returns ``{"llm": bool, "model": str}``.
    """
    return {"llm": _llm_enabled(), "model": _model()}


# ---------------------------------------------------------------------------
# Snapshot helpers — small, defensive readers (the snapshot may be partial).
# ---------------------------------------------------------------------------
def _num(v, default: float = 0.0) -> float:
    """Coerce a value to float, tolerating None / bad input."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _money(v: float) -> str:
    """Format a signed dollar figure, e.g. +$642.38 / -$201.00."""
    sign = "+" if v >= 0 else "-"
    return f"{sign}${abs(v):,.2f}"


def _direction(v: float) -> str:
    """A plain-language direction word for a PnL figure."""
    if v > 0:
        return "in the green"
    if v < 0:
        return "in the red"
    return "flat"


def _best_worst(positions: list[dict]) -> tuple[dict | None, dict | None]:
    """Return the (best, worst) open positions by absolute PnL."""
    ranked = sorted(positions, key=lambda p: _num(p.get("pnl")))
    if not ranked:
        return None, None
    return ranked[-1], ranked[0]


def _struggling_bots(bots: list[dict]) -> list[dict]:
    """Bots that are down today or not actively trading."""
    out = []
    for b in bots:
        status = str(b.get("status", "")).lower()
        down_today = _num(b.get("pnl_today")) < 0
        idle = status in {"throttled", "paused", "stopped", "halted", "down", "error"}
        if down_today or idle:
            out.append(b)
    return out


# ---------------------------------------------------------------------------
# Local (templated) briefing — the always-available fallback.
# ---------------------------------------------------------------------------
def _local_summary(snapshot: dict) -> dict:
    """Compute a natural-language briefing directly from the snapshot."""
    name = snapshot.get("greeting_name") or "Sect Master"
    pnl = snapshot.get("pnl") or {}
    positions = snapshot.get("positions") or []
    bots = snapshot.get("bots") or []
    opportunities = snapshot.get("opportunities") or []
    events = snapshot.get("events") or []

    today = _num(pnl.get("today"))
    total = _num(pnl.get("total"))

    highlights: list[str] = []
    suggestions: list[str] = []

    # --- PnL line --------------------------------------------------------
    if pnl:
        highlights.append(
            f"Today's tally stands at {_money(today)} ({_direction(today)}); "
            f"the treasury totals {_money(total)}."
        )
    else:
        highlights.append("No profit-and-loss figures have reached the hall yet.")

    # --- Positions: best / worst ----------------------------------------
    if positions:
        best, worst = _best_worst(positions)
        if best is not None and _num(best.get("pnl")) > 0:
            highlights.append(
                f"Strongest holding: {best.get('ticker', '?')} at {_money(_num(best.get('pnl')))}."
            )
        if worst is not None and _num(worst.get("pnl")) < 0:
            wt = worst.get("ticker", "?")
            highlights.append(f"Weakest holding: {wt} at {_money(_num(worst.get('pnl')))}.")
            suggestions.append(
                f"Review the {wt} position — it bleeds against the sect; consider trimming or a stop."
            )
        highlights.append(f"{len(positions)} position(s) stand open on the floor.")
    else:
        highlights.append("No positions are open — the disciples hold their hands.")

    # --- Bots: any down or losing ---------------------------------------
    if bots:
        struggling = _struggling_bots(bots)
        for b in struggling:
            bn = b.get("name", "a disciple")
            status = str(b.get("status", "")).lower()
            pt = _num(b.get("pnl_today"))
            descr = []
            if status and status not in {"active", "running", "ok"}:
                descr.append(status)
            if pt < 0:
                descr.append(f"down {_money(pt)} today")
            tail = " and ".join(descr) if descr else "underperforming"
            suggestions.append(f"{bn} is {tail} — consider reviewing or pausing it.")
        if not struggling:
            highlights.append(f"All {len(bots)} disciple(s) are trading in good order.")
    else:
        highlights.append("No trading bots are reporting in.")

    # --- Opportunities ---------------------------------------------------
    if opportunities:
        ready = [o for o in opportunities
                 if str(o.get("status", "")).upper() in {"EXECUTE", "READY"}]
        highlights.append(
            f"{len(opportunities)} opportunity(ies) on the board, "
            f"{len(ready)} ripe to act on."
        )
        if ready:
            tickers = ", ".join(str(o.get("ticker", "?")) for o in ready[:3])
            suggestions.append(f"Edge is calling on {tickers} — weigh an entry while the omen holds.")
    else:
        highlights.append("The opportunity board is quiet.")

    # --- Events ----------------------------------------------------------
    if events:
        highlights.append(f"{len(events)} recent event(s) in the intelligence feed.")

    if not suggestions:
        suggestions.append("Hold the course — the sect's affairs are in order.")

    # --- Prose briefing --------------------------------------------------
    text = (
        f"Greetings, {name}. The sect's ledger reads {_money(today)} for the day, "
        f"{_direction(today)}, upon a treasury of {_money(total)}. "
        + " ".join(highlights[1:])  # the lead line is folded into the opening
        + " May your judgement be steady."
    )

    return {
        "text": text,
        "highlights": highlights,
        "suggestions": suggestions,
        "source": "local",
    }


# ---------------------------------------------------------------------------
# LLM (Claude) briefing — best-effort, always falls back to local.
# ---------------------------------------------------------------------------
def _llm_summary(snapshot: dict) -> dict:
    """Ask Claude for an in-character briefing. Raises on any failure."""
    import json

    import anthropic

    client = anthropic.Anthropic()  # resolves ANTHROPIC_API_KEY from the env

    name = snapshot.get("greeting_name") or "Sect Master"
    system = (
        "You are the Sect Advisor, a wise and composed sect-elder overseeing an "
        "AI trading operation themed as a cultivation sect (agents are 'disciples'). "
        "Given a JSON snapshot of the command center, write a concise operations "
        f"briefing for {name} in a calm, in-character sect-elder voice. "
        "Be specific about PnL direction, the best and worst positions, any bot that "
        "is down or throttled, the count of opportunities, and notable events. "
        "Respond ONLY with a JSON object of the form "
        '{"text": str, "highlights": [str, ...], "suggestions": [str, ...]} — '
        "no markdown, no prose outside the JSON."
    )
    user = "Command center snapshot:\n" + json.dumps(snapshot, default=str)[:8000]

    resp = client.messages.create(
        model=_model(),
        max_tokens=1024,  # modest — this is a short briefing
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    raw = "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    ).strip()

    data = json.loads(raw)
    text = str(data.get("text", "")).strip()
    highlights = [str(h) for h in data.get("highlights", []) if str(h).strip()]
    suggestions = [str(s) for s in data.get("suggestions", []) if str(s).strip()]
    if not text:
        raise ValueError("empty advisor text")
    return {
        "text": text,
        "highlights": highlights,
        "suggestions": suggestions,
        "source": "llm",
    }


def summary(snapshot: dict) -> dict:
    """Summarize the dashboard ``snapshot`` as a sect-elder briefing.

    Returns ``{"text": str, "highlights": [str], "suggestions": [str],
    "source": "llm"|"local"}``. Falls back to the local templated briefing on
    any LLM failure (no key, no SDK, no network, bad response).
    """
    snapshot = snapshot or {}
    if _llm_enabled():
        try:
            return _llm_summary(snapshot)
        except Exception:
            # Any failure (network, auth, parse, rate-limit) → local briefing.
            pass
    return _local_summary(snapshot)
