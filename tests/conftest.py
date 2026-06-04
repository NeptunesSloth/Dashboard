"""Per-test isolation of shared in-memory state.

Many modules keep process-global state (cultivation, governance, usage, the task
board, autopilot, …). Tests that don't own a given module used to inherit
whatever a previous test left behind — which, under CI's randomized
``PYTHONHASHSEED``, made a few tests (e.g. the autonomy budget caps) flaky.

This autouse fixture wipes those cross-module aids before every test so order
can't leak. Each test still sets up the state it needs afterwards.
"""
import pytest

from maybot_control_center import (cultivation, governance, usage, treasury,
                                   traits, lifecycle, taskqueue, oaths,
                                   maintenance, autopilot, skillquest, sectmemory)

_RESETTABLE = (cultivation, governance, usage, treasury, traits, lifecycle,
               taskqueue, oaths, maintenance, autopilot, skillquest, sectmemory)


@pytest.fixture(autouse=True)
def _isolate_shared_state(monkeypatch):
    for mod in _RESETTABLE:
        try:
            mod.clear()
        except Exception:
            pass
    # Never reach the real web during tests — roaming skill-quests use the
    # offline fallback unless a test stubs _search itself.
    monkeypatch.setattr(skillquest, "_search", lambda q: [])
    yield
