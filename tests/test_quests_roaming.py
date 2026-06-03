from maybot_control_center import cultivation as c, quests


def setup_function():
    c.clear()


def test_quest_board_has_rewards():
    cat = quests.catalog()
    assert cat and all("reward_skill" in q and "id" in q for q in cat)


def test_quest_grants_technique_on_success():
    c.assign_quest("Nova", "Far-Sight Art", 40)
    assert c.state("Nova")["pending_quest"]["skill"] == "Far-Sight Art"
    c.on_task("Nova", True)  # quest completed
    st = c.state("Nova")
    assert st["pending_quest"] is None
    assert "Far-Sight Art" in st["skills"]
    assert st["stones"] == 40
    assert st["event"] in ("quest_complete", "breakthrough")


def test_failed_quest_grants_nothing():
    c.assign_quest("Nova", "Far-Sight Art", 40)
    c.on_task("Nova", False)
    st = c.state("Nova")
    assert st["pending_quest"] is None
    assert "Far-Sight Art" not in st["skills"]


def test_roaming_returns_with_a_unique_discovery(monkeypatch):
    monkeypatch.setattr(c, "ROAMING_SECONDS", 1200)
    monkeypatch.setattr(c.random, "choice", lambda seq: seq[0])  # deterministic
    c.enter_roaming("Nova")
    assert c.state("Nova")["in_roaming"] is True
    assert c.tick_roaming("Nova") is None      # not matured yet
    with c._lock:
        c._state["Nova"]["roaming_since"] -= 2000
    found = c.tick_roaming("Nova")
    assert found in c.DISCOVERIES
    st = c.state("Nova")
    assert found in st["skills"]
    assert st["event"] == "discovery"
    assert st["in_roaming"] is True            # keeps wandering for more


def test_seclusion_and_roaming_are_mutually_exclusive():
    c.enter_seclusion("Nova")
    c.enter_roaming("Nova")
    st = c.state("Nova")
    assert st["in_roaming"] is True and st["in_seclusion"] is False
