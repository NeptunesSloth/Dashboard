"""Offline tests for the Tier-A signal layer (no ML libs required).

These exercise the pure-python heuristic path only: the model file is never
committed and sklearn/joblib are typically absent in CI, so ``score_symbols``
must degrade to deterministic ``source == "heuristic"`` entries.
"""

from maybot_control_center import signals


def test_enabled_reflects_env(monkeypatch):
    # Unset / not "1" => disabled.
    monkeypatch.delenv("MAYBOT_SIGNALS", raising=False)
    assert signals.enabled() is False

    monkeypatch.setenv("MAYBOT_SIGNALS", "0")
    assert signals.enabled() is False

    monkeypatch.setenv("MAYBOT_SIGNALS", "1")
    assert signals.enabled() is True


def test_score_symbols_empty_when_disabled(monkeypatch):
    monkeypatch.delenv("MAYBOT_SIGNALS", raising=False)
    assert signals.score_symbols(["AAPL", "NVDA"]) == []


def test_score_symbols_wellformed_and_deterministic(monkeypatch):
    monkeypatch.setenv("MAYBOT_SIGNALS", "1")

    first = signals.score_symbols(["AAPL", "NVDA"])
    second = signals.score_symbols(["AAPL", "NVDA"])

    # One dict per symbol, in order.
    assert len(first) == 2
    assert [d["symbol"] for d in first] == ["AAPL", "NVDA"]

    for entry in first:
        assert set(entry) == {"symbol", "score", "direction", "confidence", "source"}
        assert 0.0 <= entry["score"] <= 1.0
        assert 0.0 <= entry["confidence"] <= 1.0
        assert entry["direction"] in {"long", "short", "flat"}
        # No model committed / no ML libs in CI => heuristic path.
        assert entry["source"] == "heuristic"

    # Deterministic across calls (synthetic walk is seeded by symbol only).
    assert first == second


def test_features_from_closes_keys():
    closes = [100.0 + i * 0.5 for i in range(40)]  # gentle uptrend
    feats = signals.features_from_closes(closes)
    assert set(feats) == {
        "ret_1", "ret_5", "ret_10", "momentum", "rsi_14", "realized_vol",
    }
    # RSI is bounded; an uptrend should read above the neutral midpoint.
    assert 0.0 <= feats["rsi_14"] <= 100.0
    assert feats["rsi_14"] > 50.0


def test_features_from_closes_short_series_neutral():
    # Degenerate input must not raise and returns neutral defaults.
    feats = signals.features_from_closes([])
    assert feats["rsi_14"] == 50.0
    assert feats["realized_vol"] == 0.0


def test_model_info_shape(monkeypatch):
    info = signals.model_info()
    assert set(info) == {"loaded", "path", "source"}
    assert isinstance(info["loaded"], bool)
    assert info["source"] in {"model", "heuristic"}
    assert info["path"].endswith("signal_model.joblib")
