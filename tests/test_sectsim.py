import importlib
from pathlib import Path

import pytest


@pytest.fixture
def sim(tmp_path, monkeypatch):
    from maybot_control_center import sectsim
    importlib.reload(sectsim)
    sectsim.SECT_FILE = tmp_path / "sect.json"
    sectsim._state = None
    return sectsim


def _agent(tasks=0, bt=0):
    return {"name": "Nova", "role": "Research Analyst", "model": "hermes", "status": "idle",
            "tasks_done": tasks, "cultivation": {"realm": 3, "realm_name": "Core Formation",
            "breakthroughs": bt, "rank_title": "Inner Disciple"},
            "reputation": {"merit": 80, "signals": {"success_pct": 77}}}


def test_profile_generates_and_persists(sim):
    p = sim.profile(_agent(tasks=10))
    assert p["root"]["display"] and p["root"]["potential"] in sim.GRADES
    assert len(p["attrs"]) == 8 and p["sect"]["missions"] == 10
    assert sim.SECT_FILE.exists()                       # persisted to disk


def test_profile_is_stable_per_member(sim):
    a = _agent(tasks=5)
    r1 = sim.profile(a)["root"]["display"]
    sim._state = None                                   # force reload from disk
    r2 = sim.profile(a)["root"]["display"]
    assert r1 == r2                                     # same soul across loads


def test_profile_evolves_with_activity(sim):
    low = sim.profile(_agent(tasks=2))["sect"]["contribution"]
    high = sim.profile(_agent(tasks=50))["sect"]["contribution"]
    assert high > low


def test_breakthrough_appends_event(sim):
    sim.profile(_agent(tasks=5, bt=0))
    p = sim.profile(_agent(tasks=5, bt=2))
    assert any("Broke through" in e["t"] for e in p["events"])
