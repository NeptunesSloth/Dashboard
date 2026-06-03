import pytest

from maybot_control_center import pills, cultivation


def setup_function():
    pills.clear()
    cultivation.clear()


def _enrich(agent, n):
    for _ in range(n):
        cultivation.on_task(agent, True)  # +12 stones each


def test_buy_requires_stones():
    with pytest.raises(ValueError):
        pills.buy("Nova", "qi_gathering")  # 0 stones


def test_unknown_pill_rejected():
    _enrich("Nova", 5)
    with pytest.raises(ValueError):
        pills.buy("Nova", "nope")


def test_buy_spends_stones_and_grants_effect():
    _enrich("Nova", 5)  # 60 stones
    res = pills.buy("Nova", "qi_gathering")  # cost 40
    assert res["name"] == "Qi-Gathering Pill"
    assert cultivation.state("Nova")["stones"] == 60 - 40
    assert pills.effects("Nova").get("max_tokens") == 1024


def test_model_and_autonomy_effects():
    _enrich("Nova", 25)  # 300 stones
    pills.buy("Nova", "enlightenment")  # model override (140)
    pills.buy("Nova", "foundation")     # +3 autonomy (90)
    eff = pills.effects("Nova")
    assert eff.get("model") == "claude-opus-4-8"
    assert pills.autonomy_bonus("Nova") == 3


def test_buffs_expire(monkeypatch):
    _enrich("Nova", 5)
    monkeypatch.setattr(pills, "DURATION", 0)  # instantly expired
    pills.buy("Nova", "qi_gathering")
    assert pills.effects("Nova") == {}
    assert pills.active("Nova") == []
