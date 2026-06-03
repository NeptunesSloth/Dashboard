from maybot_control_center import usage


def setup_function():
    usage.clear()


def test_cost_for_known_and_unknown_models():
    # opus 4.8: $5/1M in, $25/1M out → 1000 in + 1000 out = 0.005 + 0.025
    assert usage.cost_for("claude-opus-4-8", 1000, 1000) == 0.03
    assert usage.cost_for("hermes", 1000, 1000) == 0.0  # local = free


def test_record_and_snapshot_aggregate():
    usage.record("Nova", "claude-opus-4-8", True, 120, 1000, 500)
    usage.record("Nova", "claude-opus-4-8", False, 80, 0, 0)
    snap = usage.snapshot()
    row = next(r for r in snap["agents"] if r["agent"] == "Nova")
    assert row["calls"] == 2 and row["errors"] == 1
    assert row["success_pct"] == 50
    assert row["avg_latency_ms"] == 100
    assert row["tokens_in"] == 1000 and row["tokens_out"] == 500
    assert row["cost"] == usage.cost_for("claude-opus-4-8", 1000, 500)
    assert snap["totals"]["calls"] == 2


def test_local_model_is_free():
    usage.record("Forge", "llama3", True, 50, 2000, 1000)
    assert usage.snapshot()["totals"]["cost"] == 0.0
