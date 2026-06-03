import time

from maybot_control_center import treasury, cultivation as c


def setup_function():
    treasury.clear()
    c.clear()


def test_balance_starts_and_withdraw_deposit():
    start = treasury.balance()
    assert start == treasury.START_BALANCE
    assert treasury.withdraw(100) is True
    assert treasury.balance() == start - 100
    treasury.deposit(50)
    assert treasury.balance() == start - 50
    assert treasury.withdraw(10 ** 9) is False  # can't overdraw


def test_spirit_veins_accrue_over_time(monkeypatch):
    treasury.clear()
    monkeypatch.setattr(treasury, "VEIN_RATE", 30)
    monkeypatch.setattr(treasury, "VEIN_SECONDS", 3600)
    before = treasury._balance
    # pretend an hour passed
    treasury._last -= 3600
    assert treasury.status()["balance"] == before + 30


def test_stipend_is_funded_by_treasury(monkeypatch):
    monkeypatch.setattr(c, "STIPEND", 15)
    monkeypatch.setattr(c, "STIPEND_SECONDS", 3600)
    treasury.clear()
    # drain the treasury so it can't pay
    treasury.withdraw(treasury._balance)
    assert c.grant_stipend("Nova") is False     # sect is broke
    assert c.state("Nova")["stones"] == 0
    # endow and try again
    treasury.deposit(100)
    assert c.grant_stipend("Nova") is True
    assert c.state("Nova")["stones"] == 15
    assert treasury.balance() == 100 - 15


def test_tithe_flows_to_the_treasury(monkeypatch):
    monkeypatch.setattr(c, "TITHE", 3)
    before = treasury.balance()
    c.on_task("Nova", True)
    assert treasury.balance() == before + 3
