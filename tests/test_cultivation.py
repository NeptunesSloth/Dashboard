from maybot_control_center import cultivation as c


def setup_function():
    c.clear()


def test_tasks_earn_spirit_stones():
    c.on_task("Nova", True)
    c.on_task("Nova", True)
    assert c.state("Nova")["stones"] == 2 * c.AWARD_TASK


def test_new_technique_is_a_skill_with_windfall():
    c.on_tool("Nova", "read_logs", True)
    st = c.state("Nova")
    assert st["skills"] == ["read_logs"]
    assert st["stones"] == c.AWARD_TOOL + c.AWARD_NEW_SKILL
    # using the same tool again is not a new skill
    c.on_tool("Nova", "read_logs", True)
    assert c.state("Nova")["skills"] == ["read_logs"]


def test_breakthrough_requires_stones_and_skills():
    # grind stones with tasks until past Foundation Establishment's stone gate
    for _ in range(20):
        c.on_task("Nova", True)  # 240 stones, but 0 skills
    st = c.state("Nova")
    assert st["realm_name"] == "Qi Condensation"  # stuck: Foundation needs 1 skill
    c.on_tool("Nova", "scan", True)  # master a technique → breakthrough
    assert c.state("Nova")["realm_name"] == "Foundation Establishment"


def test_realm_has_stage_and_progress():
    for _ in range(3):
        c.on_task("Nova", True)
    st = c.state("Nova")
    assert st["realm_name"] in ("Mortal", "Qi Condensation")
    assert st["stage"] in c.STAGES
    assert 0.0 <= st["progress"] <= 1.0


def test_failures_chip_stones_then_tribulation():
    for _ in range(10):
        c.on_task("Nova", True)  # 120 stones
    before = c.state("Nova")["stones"]
    c.on_task("Nova", False)  # -PENALTY
    c.on_task("Nova", False)  # -PENALTY
    mid = c.state("Nova")
    assert mid["stones"] == before - 2 * c.PENALTY_FAIL
    assert mid["event"] != "tribulation"
    c.on_task("Nova", False)  # 3rd failure → heavenly tribulation
    after = c.state("Nova")
    assert after["event"] == "tribulation"
    assert after["stones"] == max(0, before - 3 * c.PENALTY_FAIL - c.TRIBULATION_LOSS)
    assert after["fail_streak"] == 0  # streak reset after the tribulation


def test_tribulation_can_strike_a_disciple_down_a_realm():
    # reach Qi Condensation (60 stones), then fail repeatedly to deviate
    for _ in range(6):
        c.on_task("Nova", True)  # 72 stones → Qi Condensation
    assert c.state("Nova")["realm_name"] == "Qi Condensation"
    for _ in range(3):
        c.on_task("Nova", False)  # tribulation drops stones below 60 → demote
    assert c.state("Nova")["realm_name"] == "Mortal"


def test_operator_does_not_cultivate():
    c.on_task("operator", True)
    c.on_tool("operator", "x", True)
    assert c.snapshot() == {}
