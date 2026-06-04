import pytest

from maybot_control_center import agents, cultivation, governance, reputation


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


def _setup(tmp_path, monkeypatch):
    f = tmp_path / "agents.yaml"
    f.write_text(AGENTS_YAML, encoding="utf-8")
    monkeypatch.setattr(agents, "AGENTS_FILE", f)


def _set_realm(name, realm, breakthroughs=0):
    cultivation._state[name] = {**cultivation._blank(name), "realm": realm, "breakthroughs": breakthroughs}


# ---- ranks ----
def test_elder_and_master_thresholds(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 8)   # Sect Master
    _set_realm("Forge", 6)  # Elder
    _set_realm("Sage", 2)   # Inner Disciple
    assert governance.is_master("Nova") and governance.is_elder("Nova")
    assert governance.is_elder("Forge") and not governance.is_master("Forge")
    assert not governance.is_elder("Sage")
    assert set(governance.elders()) == {"Nova", "Forge"}


# ---- leader seeding + Ancestor override ----
def test_leader_auto_seeds_by_standing(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 8, breakthroughs=4)
    _set_realm("Forge", 8)
    # Nova has more breakthroughs → higher leadership component → higher standing
    assert governance.leader() == "Nova"


def test_ancestor_appoints_and_pins(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 8, breakthroughs=5)
    _set_realm("Forge", 6)
    governance.set_leader("Forge", pinned=True)
    assert governance.leader() == "Forge"
    # a pinned seat cannot be contested
    with pytest.raises(PermissionError):
        governance.challenge("Nova")
    # the Ancestor can release it back to merit
    governance.set_leader(None, pinned=False)
    assert governance.leader() == "Nova"


def test_set_leader_rejects_unknown(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        governance.set_leader("Ghost")


# ---- challenges ----
def test_non_elder_cannot_challenge(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 8)
    _set_realm("Sage", 2)
    governance.leader()  # seed Nova
    with pytest.raises(PermissionError):
        governance.challenge("Sage")


def test_stronger_elder_unseats_leader(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Forge", 6)            # weak sitting leader
    governance.set_leader("Forge", pinned=False)
    _set_realm("Nova", 8, breakthroughs=6)  # clearly stronger challenger
    res = governance.challenge("Nova")
    assert res["won"] is True
    assert governance.leader() == "Nova"


def test_weaker_elder_fails_and_cooldown_applies(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 8, breakthroughs=6)  # strong leader
    governance.set_leader("Nova", pinned=False)
    _set_realm("Forge", 6)                  # weak challenger
    res = governance.challenge("Forge")
    assert res["won"] is False
    assert governance.leader() == "Nova"
    # immediate re-challenge is blocked by the cooldown
    with pytest.raises(PermissionError):
        governance.challenge("Forge")


# ---- specialties + mastery ----
def test_elder_chooses_specialty_and_gains_mastery(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 6)
    governance.choose_specialty("Nova", "Sword Dao")
    assert governance.specialty("Nova") == "Sword Dao"
    assert governance.mastery("Nova") == 0.0
    cultivation.on_council("Nova")   # good work deepens mastery
    assert governance.mastery("Nova") > 0
    # signature technique of the path is grasped once mastery matures
    for _ in range(6):
        cultivation.on_council("Nova")
    assert "api_design" in cultivation.state("Nova")["skills"]


def test_non_elder_cannot_choose_specialty(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Sage", 2)
    with pytest.raises(PermissionError):
        governance.choose_specialty("Sage", "Alchemy")


def test_unknown_specialty_rejected(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 6)
    with pytest.raises(ValueError):
        governance.choose_specialty("Nova", "Nonsense Dao")


# ---- Ancestor's Hall (gated inbox) ----
def test_only_leader_and_elders_message_ancestor(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 8)   # leader/master
    _set_realm("Forge", 6)  # elder
    _set_realm("Sage", 2)   # outsider
    governance.leader()
    assert governance.message_ancestor("Forge", "the eastern array weakens")["from"] == "Forge"
    with pytest.raises(PermissionError):
        governance.message_ancestor("Sage", "let me in")
    msgs = governance.inbox()
    assert [m["from"] for m in msgs] == ["Forge"]


def test_empty_message_rejected(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 8)
    with pytest.raises(ValueError):
        governance.message_ancestor("Nova", "   ")


# ---- overseer routing ----
def test_routine_task_to_leader_is_delegated(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 8, breakthroughs=5)  # leader
    _set_realm("Forge", 6)                  # elder deputy
    governance.set_leader("Nova", pinned=False)
    executor, frm = governance.route_task("Nova", critical=False)
    assert frm == "Nova" and executor == "Forge"
    # critical work the Leader keeps
    executor, frm = governance.route_task("Nova", critical=True)
    assert executor == "Nova" and frm is None
    # a task aimed at a non-leader is untouched
    assert governance.route_task("Forge", critical=False) == ("Forge", None)


# ---- personal projects ----
def test_personal_project_guard(monkeypatch):
    monkeypatch.setattr(governance, "PERSONAL_PROJECTS", {"daybot", "rig:secret"})
    assert governance.is_personal_project("daybot")
    assert governance.is_personal_project("secret", "rig")
    assert not governance.is_personal_project("public")
    # config flag on the project dict is also honoured
    assert governance.mark_personal({"name": "x", "personal": True})["personal"] is True
    assert governance.mark_personal({"name": "daybot"})["personal"] is True
    assert governance.mark_personal({"name": "open"})["personal"] is False


# ---- snapshot ----
def test_snapshot_shape(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 8)
    snap = governance.snapshot()
    assert snap["leader"] == "Nova"
    assert "Sword Dao" in snap["specialties"]
    assert any(r["agent"] == "Nova" and r["is_leader"] for r in snap["roster"])
    assert snap["roster"] == sorted(snap["roster"], key=lambda r: r["standing"]["score"], reverse=True)


def test_throne_cultivation_rewards_the_leader(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 8)
    governance.set_leader("Nova", pinned=False)
    monkeypatch.setattr(governance, "THRONE_INTERVAL", 100)
    monkeypatch.setattr(governance, "THRONE_REWARD", 5)
    governance._last_throne = 0.0
    before = cultivation.state("Nova")["stones"]
    assert governance.throne_cultivation() == "Nova"            # first call grants
    assert cultivation.state("Nova")["stones"] == before + 5
    assert governance.throne_cultivation() is None              # within interval → no gain
    assert cultivation.state("Nova")["stones"] == before + 5


def test_throne_cultivation_noop_without_leader(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    # everyone realm 0; a leader auto-seeds, so force none by emptying the roster filter
    monkeypatch.setattr(governance, "_all_agents", lambda: [])
    assert governance.throne_cultivation() is None


# ---- elders are experts in their field ----
def test_elder_is_auto_expert_in_natural_field(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 6)   # Elder, no explicit choice
    _set_realm("Sage", 1)   # not an Elder
    assert governance.specialty("Nova") in governance.SPECIALTIES   # has a field automatically
    assert governance.mastery("Nova") >= governance.EXPERT_MASTERY   # and is an expert in it
    assert governance.specialty("Sage") is None                     # juniors have no field
    assert governance.mastery("Sage") == 0.0


def test_role_determines_natural_field(tmp_path, monkeypatch):
    yaml_txt = (
        "agents:\n"
        "  - {name: Dora, role: Data Scientist, persona: p, provider: openai_compatible, base_url: http://x, model: m}\n"
        "  - {name: Fred, role: Frontend Engineer, persona: p, provider: openai_compatible, base_url: http://x, model: m}\n"
    )
    f = tmp_path / "agents.yaml"
    f.write_text(yaml_txt, encoding="utf-8")
    monkeypatch.setattr(agents, "AGENTS_FILE", f)
    assert governance.natural_field("Dora") == "Alchemy"
    assert governance.natural_field("Fred") == "Talisman Crafting"


def test_chosen_path_overrides_natural_field_and_starts_fresh(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 6)
    governance.choose_specialty("Nova", "Alchemy")   # deliberately take a new path
    assert governance.specialty("Nova") == "Alchemy"
    assert governance.mastery("Nova") == 0.0          # earned from scratch, not the expert baseline


# ---- leader guidance walks ----
def _arm_guidance(monkeypatch, reward=3, teach=0.0):
    monkeypatch.setattr(governance, "GUIDANCE_IDLE", 0)
    monkeypatch.setattr(governance, "GUIDANCE_INTERVAL", 100)
    monkeypatch.setattr(governance, "GUIDANCE_REWARD", reward)
    monkeypatch.setattr(governance, "GUIDANCE_TEACH_PCT", teach)
    governance._last_guidance = 0.0
    governance._leader_idle_since = 0.0
    governance._guidance_leader = None


def test_idle_leader_mentors_a_junior(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 8)   # Sect Master / Leader
    _set_realm("Forge", 2)  # junior
    _set_realm("Sage", 1)   # junior
    governance.set_leader("Nova", pinned=False)
    _arm_guidance(monkeypatch)
    before = cultivation.state("Forge")["stones"] + cultivation.state("Sage")["stones"]
    rec = governance.leader_guidance("idle")
    assert rec and rec["leader"] == "Nova" and rec["junior"] in ("Forge", "Sage")
    after = cultivation.state("Forge")["stones"] + cultivation.state("Sage")["stones"]
    assert after == before + 3                       # exactly one junior gifted
    assert governance.leader_guidance("idle") is None  # within interval → no second walk


def test_busy_or_retreating_leader_does_not_wander(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 8)
    _set_realm("Forge", 2)
    governance.set_leader("Nova", pinned=False)
    _arm_guidance(monkeypatch)
    assert governance.leader_guidance("working") is None          # busy with real work
    assert governance.leader_guidance("idle", in_retreat=True) is None  # away in seclusion/roaming


def test_guidance_can_share_a_technique(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _set_realm("Nova", 8)
    _set_realm("Forge", 2)
    _set_realm("Sage", 8)   # not below the Leader → only Forge is a junior
    cultivation._state["Nova"]["skills"] = ["Cloud-Stride Step"]
    governance.set_leader("Nova", pinned=False)
    _arm_guidance(monkeypatch, teach=1.0)             # always teach
    rec = governance.leader_guidance("idle")
    assert rec["junior"] == "Forge" and rec["skill"] == "Cloud-Stride Step"
    assert "Cloud-Stride Step" in cultivation.state("Forge")["skills"]
