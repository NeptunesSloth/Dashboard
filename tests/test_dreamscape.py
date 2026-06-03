import pytest

from maybot_control_center import dreamscape


ROSTER = ["Nova", "Forge"]


# ---- estimate_tokens ----
def test_estimate_tokens():
    assert dreamscape.estimate_tokens(0) == 0
    assert dreamscape.estimate_tokens(4) == 4 * dreamscape.COST_PER_STAGE


# ---- preview happy path ----
def test_preview_round_robin_assignment():
    plan = dreamscape.preview("recon-array", "investigate the outage", roster=ROSTER)
    assert plan["formation"] == "recon-array"
    assert plan["goal"] == "investigate the outage"
    assert [r["stage"] for r in plan["stages"]] == ["scout", "analyze", "propose", "review"]
    # 4 stages across 2 agents → Nova, Forge, Nova, Forge
    assert [r["assignee"] for r in plan["stages"]] == ["Nova", "Forge", "Nova", "Forge"]


def test_preview_totals_and_participants():
    plan = dreamscape.preview("recon-array", "ship it", roster=ROSTER)
    assert plan["stage_count"] == 4
    assert plan["est_tokens_total"] == 4 * dreamscape.COST_PER_STAGE
    assert all(r["est_tokens"] == dreamscape.COST_PER_STAGE for r in plan["stages"])
    # participants deduped, in order
    assert plan["participants"] == ["Nova", "Forge"]


def test_preview_synthetic_string_no_llm():
    plan = dreamscape.preview("recon-array", "ship it", roster=ROSTER)
    row = plan["stages"][0]
    assert row["preview"].startswith("⟨dream⟩ Nova would ")
    assert row["preview"].endswith("for: ship it")
    assert row["assignee"] in row["preview"]


# ---- validation ----
def test_preview_empty_goal_raises():
    with pytest.raises(ValueError):
        dreamscape.preview("recon-array", "", roster=ROSTER)
    with pytest.raises(ValueError):
        dreamscape.preview("recon-array", "   ", roster=ROSTER)


def test_preview_unknown_formation_raises():
    with pytest.raises(ValueError):
        dreamscape.preview("ghost-array", "goal", roster=ROSTER)


def test_preview_empty_roster_raises():
    with pytest.raises(ValueError):
        dreamscape.preview("recon-array", "goal", roster=[])


# ---- explicit pinned agent honoured ----
def test_preview_honours_pinned_agent_in_roster(monkeypatch):
    from maybot_control_center import formations

    custom = {
        "name": "pinned-array",
        "title": "Pinned Array",
        "description": "",
        "stages": [
            {"name": "lead", "role": "drive", "agent": "Forge"},  # pinned, in roster
            {"name": "second", "role": "support"},                # round-robin → roster[1]
        ],
    }
    monkeypatch.setattr(formations, "get", lambda name: custom if name == "pinned-array" else None)
    plan = dreamscape.preview("pinned-array", "do the thing", roster=ROSTER)
    # stage 0 honours pinned Forge (not round-robin Nova); stage 1 → roster[1 % 2] = Forge
    assert [r["assignee"] for r in plan["stages"]] == ["Forge", "Forge"]
    assert plan["participants"] == ["Forge"]


def test_preview_pinned_agent_not_in_roster_falls_back(monkeypatch):
    from maybot_control_center import formations

    custom = {
        "name": "pinned-array",
        "title": "Pinned Array",
        "description": "",
        "stages": [{"name": "lead", "role": "drive", "agent": "Ghost"}],
    }
    monkeypatch.setattr(formations, "get", lambda name: custom if name == "pinned-array" else None)
    plan = dreamscape.preview("pinned-array", "goal", roster=ROSTER)
    # Ghost not in roster → round-robin roster[0]
    assert plan["stages"][0]["assignee"] == "Nova"


# ---- roster auto-loaded from agents ----
def test_preview_loads_roster_from_agents(monkeypatch):
    from maybot_control_center import agents

    monkeypatch.setattr(agents, "load_agents", lambda: [{"name": "Nova"}, {"name": "Forge"}])
    plan = dreamscape.preview("recon-array", "goal")
    assert [r["assignee"] for r in plan["stages"]] == ["Nova", "Forge", "Nova", "Forge"]


def test_preview_empty_agents_roster_raises(monkeypatch):
    from maybot_control_center import agents

    monkeypatch.setattr(agents, "load_agents", lambda: [])
    with pytest.raises(ValueError):
        dreamscape.preview("recon-array", "goal")
