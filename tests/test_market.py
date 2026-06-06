"""Offline tests for the live market layer: quotes + read-only broker.

These must pass with NO network and NO optional libraries installed. The live
provider and broker are only exercised through their graceful-fallback paths,
plus monkeypatched quotes to verify the pnl math.
"""
from maybot_control_center import broker, quotes


# ---- quotes.get_quotes ----
def test_get_quotes_unset_returns_empty_dict(monkeypatch):
    monkeypatch.delenv("MAYBOT_QUOTES_PROVIDER", raising=False)
    out = quotes.get_quotes(["NVDA", "META"])
    assert out == {}
    assert isinstance(out, dict)


def test_get_quotes_empty_input():
    assert quotes.get_quotes([]) == {}


def test_live_false_when_unset(monkeypatch):
    monkeypatch.delenv("MAYBOT_QUOTES_PROVIDER", raising=False)
    assert quotes.live() is False


# ---- quotes.enrich_positions ----
def test_enrich_unchanged_without_quotes(monkeypatch):
    monkeypatch.delenv("MAYBOT_QUOTES_PROVIDER", raising=False)
    positions = [
        {"ticker": "NVDA", "side": "LONG", "qty": 40, "entry": 118.20,
         "last": 124.85, "pnl": 266.00, "pnl_pct": 5.63},
    ]
    out = quotes.enrich_positions(positions)
    assert out == positions  # no live data -> untouched


def test_enrich_recomputes_long(monkeypatch):
    # 10 shares LONG, entry 100, live last 110 -> +10/share -> pnl 100, +10%.
    monkeypatch.setattr(quotes, "get_quotes", lambda syms: {"NVDA": 110.0})
    positions = [
        {"ticker": "NVDA", "side": "LONG", "qty": 10, "entry": 100.0,
         "last": 100.0, "pnl": 0.0, "pnl_pct": 0.0},
    ]
    out = quotes.enrich_positions(positions)
    assert out[0]["last"] == 110.0
    assert out[0]["pnl"] == 100.0
    assert out[0]["pnl_pct"] == 10.0


def test_enrich_recomputes_short(monkeypatch):
    # 5 shares SHORT, entry 200, live last 180 -> +20/share profit -> pnl 100, +10%.
    monkeypatch.setattr(quotes, "get_quotes", lambda syms: {"TSLA": 180.0})
    positions = [
        {"ticker": "TSLA", "side": "SHORT", "qty": 5, "entry": 200.0,
         "last": 200.0, "pnl": 0.0, "pnl_pct": 0.0},
    ]
    out = quotes.enrich_positions(positions)
    assert out[0]["last"] == 180.0
    assert out[0]["pnl"] == 100.0
    assert out[0]["pnl_pct"] == 10.0


def test_enrich_leaves_untracked_position(monkeypatch):
    # Only NVDA has a live quote; AMD must stay byte-for-byte unchanged.
    monkeypatch.setattr(quotes, "get_quotes", lambda syms: {"NVDA": 130.0})
    amd = {"ticker": "AMD", "side": "LONG", "qty": 60, "entry": 162.40,
           "last": 159.05, "pnl": -201.00, "pnl_pct": -2.06}
    positions = [
        {"ticker": "NVDA", "side": "LONG", "qty": 10, "entry": 100.0,
         "last": 100.0, "pnl": 0.0, "pnl_pct": 0.0},
        dict(amd),
    ]
    out = quotes.enrich_positions(positions)
    assert out[1] == amd
    assert out[0]["pnl"] == 300.0  # NVDA recomputed


# ---- broker (read-only, must stay offline without keys) ----
def test_broker_disabled_without_keys(monkeypatch):
    monkeypatch.delenv("MAYBOT_BROKER", raising=False)
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    assert broker.enabled() is False


def test_broker_disabled_with_partial_keys(monkeypatch):
    monkeypatch.setenv("MAYBOT_BROKER", "alpaca")
    monkeypatch.setenv("ALPACA_API_KEY", "key")
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    assert broker.enabled() is False


def test_broker_empty_returns_without_keys(monkeypatch):
    monkeypatch.delenv("MAYBOT_BROKER", raising=False)
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    assert broker.account() == {}
    assert broker.positions() == []
    assert broker.recent_fills() == []
    # Return types stay stable regardless of input.
    assert isinstance(broker.account(), dict)
    assert isinstance(broker.positions(), list)
    assert isinstance(broker.recent_fills(5), list)
