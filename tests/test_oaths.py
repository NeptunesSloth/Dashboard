from maybot_control_center import oaths


def setup_function():
    oaths.clear()


def test_claim_and_owner():
    oaths.claim("d:bot", "Nova", "investigating")
    assert oaths.is_claimed("d", "bot") is True
    assert oaths.owner("d", "bot") == "Nova"
    assert oaths.owner("d", "other") is None


def test_release():
    oaths.claim("d:bot", "Nova")
    assert oaths.release("d:bot") is True
    assert oaths.is_claimed("d", "bot") is False
    assert oaths.release("d:bot") is False


def test_recovery_releases():
    oaths.claim("d:bot", "Nova")
    oaths.note_recovery("d", "bot")
    assert oaths.is_claimed("d", "bot") is False


def test_annotate():
    oaths.claim("d:bot", "Nova", "on it")
    p = {"device": "d", "name": "bot"}
    oaths.annotate(p)
    assert p["oath"]["who"] == "Nova" and p["oath"]["note"] == "on it"


def test_snapshot():
    oaths.claim("d:bot", "Nova")
    oaths.claim("d:api", "Forge")
    assert {o["target"] for o in oaths.snapshot()["oaths"]} == {"d:bot", "d:api"}
