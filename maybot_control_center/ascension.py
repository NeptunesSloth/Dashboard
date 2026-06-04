"""Ascension — a disciple's realm unlocks a stronger mind (model).

As a disciple breaks through to higher realms it earns the right to think with a
more capable model: the deeper the cultivation, the better the brain it runs on.
Within the Claude family the ladder is Haiku → Sonnet → Opus; ascension only
ever *upgrades* (never downgrades a model you configured), and only within the
same provider family by default so it never breaks an agent's credentials.

Hook: :func:`agents.run_task` calls :func:`model_for` to pick the effective
model for a run. Off → every agent uses its configured model.
"""
from __future__ import annotations

import os

ENABLED = os.getenv("MAYBOT_ASCENSION", "1").strip().lower() not in {"0", "false", "no", ""}
# Realm at which a disciple ascends to each Claude tier.
SONNET_REALM = int(os.getenv("MAYBOT_ASCEND_SONNET_REALM", "4"))
OPUS_REALM = int(os.getenv("MAYBOT_ASCEND_OPUS_REALM", "8"))

_LADDER = {"claude-haiku-4-5": 0, "claude-sonnet-4-6": 1, "claude-opus-4-8": 2}


def _rank(model: str) -> int:
    m = (model or "").lower()
    if "opus" in m:
        return 2
    if "sonnet" in m:
        return 1
    if "haiku" in m:
        return 0
    return -1   # non-Claude / unknown


def target_tier(realm: int) -> str | None:
    if realm >= OPUS_REALM:
        return "claude-opus-4-8"
    if realm >= SONNET_REALM:
        return "claude-sonnet-4-6"
    return None


def model_for(agent: str, base_model: str | None) -> str | None:
    """The effective model for this disciple given its realm — an upgrade, or the
    base model unchanged."""
    if not ENABLED:
        return base_model
    from . import cultivation
    target = target_tier(cultivation.realm_of(agent))
    if not target:
        return base_model
    # Only ascend Claude-family models (so we never swap an agent's provider/creds).
    if _rank(base_model) < 0 and base_model:
        return base_model
    if _rank(base_model) >= _rank(target):
        return base_model
    return target


def status(agent: str, base_model: str | None) -> dict:
    """For the UI: the configured model, the ascended one (if any), and the tier."""
    eff = model_for(agent, base_model)
    return {"base": base_model, "model": eff, "ascended": bool(eff and eff != base_model)}
