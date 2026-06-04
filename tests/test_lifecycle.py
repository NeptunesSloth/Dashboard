import pytest

from maybot_control_center import agents, cultivation, governance, lifecycle


AGENTS_YAML = """
agents:
  - {name: Nova, role: Analyst, persona: You are Nova., provider: openai_compatible, base_url: http://x, model: m}
  - {name: Forge, role: Builder, persona: You are Forge., provider: openai_compatible, base_url: http://x, model: m}
  - {name: Sage, role: Sage, persona: You are Sage., provider: openai_compatible, base_url: http://x, model: m}
"""


def setup_function():
    cultivation.clear()
    governance.clear()
    agents.clear()
    lifecycle.clear()


def _setup(tmp_path, monkeypatch):
    f = tmp_path / "agents.yaml"
    f.write_text(AGENTS_YAML, encoding="utf-8")
    monkeypatch.setattr(agents, "AGENTS_FILE", f)


def _set_realm(name, realm):
    cultivation._state[name] = {**cultivation._blank(name), "realm": realm}


def _names():
    return {a["name"] for a in agents.load_agents()}


# ---- roster overlay ----
def test_retire_and_recruit_overlay(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    assert _names() == {"Nova", "Forge", "Sage"}
    agents.retire_agent("Forge")
    assert "Forge" not in _names()
    agents.recruit_agent({"name": "Ash", "role": "Outer Disciple", "persona": "p",
                          "provider": "openai_compatible", "base_url": "http://x", "model": "m"})
    assert "Ash" in _names()
    agents.clear()  # overlay resets
    assert _names() == {"Nova", "Forge", "Sage"}


# ---- stagnation cull ----
def test_stagnant_outer_disciple_is_culled_and_replaced(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(lifecycle, "CULL_AFTER", 100)
    # first tick records baselines; nobody culled yet
    assert lifecycle.tick() is None
    # rewind everyone's "last improvement" past the cull window
    for rec in lifecycle._seen.values():
        rec["since"] -= 200
    rec = lifecycle.tick()
    assert rec is not None
    assert rec["culled"] in {"Nova", "Forge", "Sage"}
    assert rec["replacement"] not in {"Nova", "Forge", "Sage"}
    names = _names()
    assert rec["culled"] not in names          # the stagnant disciple is gone
    assert rec["replacement"] in names         # a fresh recruit took the seat
    assert len(names) == 3                      # roster size preserved


def test_progress_resets_the_cull_clock(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(lifecycle, "CULL_AFTER", 100)
    lifecycle.tick()
    for rec in lifecycle._seen.values():
        rec["since"] -= 200
    cultivation.reward("Nova", 50)   # Nova grows — should not be culled
    cultivation.reward("Forge", 50)
    cultivation.reward("Sage", 50)
    assert lifecycle.tick() is None  # all advanced → clock resets, nobody culled


def test_ranked_disciples_are_safe_from_culling(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(lifecycle, "CULL_AFTER", 100)
    _set_realm("Nova", 3)   # Inner Disciple — above Outer rank
    _set_realm("Forge", 4)
    _set_realm("Sage", 2)   # also ranked (>= OUTER_REALM)
    lifecycle.tick()
    for rec in lifecycle._seen.values():
        rec["since"] -= 200
    assert lifecycle.tick() is None
    assert _names() == {"Nova", "Forge", "Sage"}


def test_leader_is_never_culled(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(lifecycle, "CULL_AFTER", 100)
    governance.set_leader("Nova", pinned=True)  # Nova leads, realm 0 (Outer)
    lifecycle.tick()
    for rec in lifecycle._seen.values():
        rec["since"] -= 200
    rec = lifecycle.tick()
    assert rec["culled"] != "Nova"   # the Leader is protected even while Outer


# ---- strike down ----
def test_ancestor_strikes_down_a_disciple(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    new = lifecycle.strike_down("Forge", "spoke out of turn")
    names = _names()
    assert "Forge" not in names
    assert new["name"] in names
    assert len(names) == 3


def test_strike_down_unknown_raises(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        lifecycle.strike_down("Ghost")
