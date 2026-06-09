import importlib

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


def test_passive_tick_evolves_and_logs_insights(sim):
    a = _agent(tasks=0)
    sim.profile(a)                                  # seed
    import time
    base = time.time()
    sim.tick([a], now=base)                         # establish last_tick
    sim.tick([a], now=base + 6 * 3600)              # 6 hours later -> plenty of xp
    p = sim.profile(a)
    assert p["sect"]["insights"] >= 1
    assert any("insight" in e["t"].lower() for e in p["events"])


def test_relationships_and_promotion(sim):
    import time
    roster = [_agent_named("Nova"), _agent_named("Forge"), _agent_named("Sage")]
    for a in roster:
        sim.profile(a)
    t = time.time()
    for i in range(60):                      # simulate many hours of sect life
        sim.tick(roster, now=t + i * 3600)
    p = sim.profile(roster[0])
    assert isinstance(p["relationships"], list)
    assert p["sim_rank"] in sim.SIM_RANKS
    # someone should have at least one tracked relationship after all that time
    assert any(sim.profile(a)["relationships"] for a in roster)


def _agent_named(n):
    return {"name": n, "role": "Disciple", "model": "nous-hermes", "status": "idle",
            "tasks_done": 20, "cultivation": {"realm": 2, "breakthroughs": 2}, "reputation": {"merit": 200}}
