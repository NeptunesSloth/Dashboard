from __future__ import annotations

from maybot_control_center import spirit_root


def setup_function():
    spirit_root.clear()


def test_weights_sum_to_one():
    assert abs(sum(spirit_root.PROBES.values()) - 1.0) < 1e-9


def test_baseline_probes_are_probe_keys():
    assert spirit_root.BASELINE_PROBES == list(spirit_root.PROBES.keys())


def _all(category_oks, latency_ms=0):
    rows = []
    for cat, oks in category_oks.items():
        for ok in oks:
            rows.append({"category": cat, "ok": ok, "latency_ms": latency_ms})
    return rows


def test_perfect_run_is_heavenly():
    results = _all(
        {
            "reasoning": [True, True, True],
            "coding": [True, True, True],
            "reliability": [True, True],
        },
        latency_ms=0,
    )
    p = spirit_root.assess("ace", results)
    assert p["agent"] == "ace"
    assert p["overall"] == 100
    assert p["grade"] == "Heavenly"
    assert p["categories"]["reasoning"] == 100
    assert p["categories"]["latency"] == 100
    assert p["samples"] == len(results)
    assert isinstance(p["ts"], int)


def test_all_fail_is_mortal_dust():
    # Every pass/fail category fails, and latency is catastrophic -> 0.
    results = _all(
        {
            "reasoning": [False, False],
            "coding": [False, False],
            "reliability": [False, False],
        },
        latency_ms=999999,
    )
    # add explicit latency failures
    results += [{"category": "latency", "ok": False, "latency_ms": 999999}]
    p = spirit_root.assess("dud", results)
    assert p["overall"] == 0
    assert p["grade"] == "Mortal Dust"


def test_latency_low_high_and_clamped():
    low = spirit_root.assess("a", [{"category": "latency", "latency_ms": 0}])
    assert low["categories"]["latency"] == 100

    # mean 1000 -> 100 - 1000/20 = 50
    mid = spirit_root.assess("b", [{"category": "latency", "latency_ms": 1000}])
    assert mid["categories"]["latency"] == 50

    # mean 2000 -> exactly 0
    edge = spirit_root.assess("c", [{"category": "latency", "latency_ms": 2000}])
    assert edge["categories"]["latency"] == 0

    # huge latency clamps at 0, never negative
    big = spirit_root.assess("d", [{"category": "latency", "latency_ms": 10**9}])
    assert big["categories"]["latency"] == 0


def test_missing_category_treated_as_100():
    # Only reasoning probed; every other category (incl latency) defaults to 100.
    p = spirit_root.assess("partial", [{"category": "reasoning", "ok": True}])
    assert p["categories"]["reasoning"] == 100
    assert p["categories"]["coding"] == 100
    assert p["categories"]["reliability"] == 100
    assert p["categories"]["latency"] == 100
    assert p["overall"] == 100

    # If the only probed category fails, the untested ones still don't penalize.
    p2 = spirit_root.assess("partial2", [{"category": "reasoning", "ok": False}])
    # overall = 0*0.35 + 100*0.35 + 100*0.20 + 100*0.10 = 65
    assert p2["categories"]["reasoning"] == 0
    assert p2["overall"] == 65


def test_no_results_all_default_100():
    p = spirit_root.assess("empty", [])
    assert p["overall"] == 100
    assert p["grade"] == "Heavenly"
    assert p["samples"] == 0


def test_partial_pass_rate():
    # 2 of 4 reasoning pass -> 50 for that category.
    rows = [
        {"category": "reasoning", "ok": True},
        {"category": "reasoning", "ok": True},
        {"category": "reasoning", "ok": False},
        {"category": "reasoning", "ok": False},
    ]
    p = spirit_root.assess("half", rows)
    assert p["categories"]["reasoning"] == 50


def test_grade_boundaries():
    # Craft overalls hitting each threshold exactly using uniform pass rates.
    # With reasoning+coding+reliability all at rate r and latency 100:
    # overall = r*(0.35+0.35+0.20) + 100*0.10 = 0.9r + 10
    def assess_rate(name, r_pct):
        # rate r_pct% via 100 probes split pass/fail
        npass = r_pct
        rows = []
        for cat in ("reasoning", "coding", "reliability"):
            rows += [{"category": cat, "ok": True}] * npass
            rows += [{"category": cat, "ok": False}] * (100 - npass)
        return spirit_root.assess(name, rows)

    # r=100 -> 0.9*100+10 = 100 -> Heavenly (>=85)
    assert assess_rate("h1", 100)["grade"] == "Heavenly"
    # find r so overall == 85: 0.9r+10=85 -> r=83.33; r=84 -> 85.6 Heavenly
    assert assess_rate("h2", 84)["overall"] == 85.6
    assert assess_rate("h2b", 84)["grade"] == "Heavenly"
    # r=83 -> 84.7 -> Earthly (>=70)
    assert assess_rate("e1", 83)["grade"] == "Earthly"
    # r=70 -> 73 -> Earthly
    assert assess_rate("e2", 70)["grade"] == "Earthly"
    # 0.9r+10=70 -> r=66.67; r=66 -> 69.4 -> Mortal (>=50)
    assert assess_rate("m1", 66)["grade"] == "Mortal"
    # r=45 -> 50.5 -> Mortal
    assert assess_rate("m2", 45)["grade"] == "Mortal"
    # 0.9r+10=50 -> r=44.44; r=44 -> 49.6 -> Mortal Dust
    assert assess_rate("d1", 44)["grade"] == "Mortal Dust"
    # r=0 -> 10 -> Mortal Dust
    assert assess_rate("d2", 0)["grade"] == "Mortal Dust"


def test_profile_and_grade_accessors():
    assert spirit_root.profile("ghost") is None
    assert spirit_root.grade("ghost") is None
    p = spirit_root.assess("seen", [{"category": "reasoning", "ok": True}])
    assert spirit_root.profile("seen") == p
    assert spirit_root.grade("seen") == p["grade"]


def test_assess_overwrites_previous():
    spirit_root.assess("x", [{"category": "reasoning", "ok": True}])
    second = spirit_root.assess("x", [{"category": "reasoning", "ok": False}])
    assert spirit_root.profile("x") == second
    assert spirit_root.profile("x")["categories"]["reasoning"] == 0


def test_snapshot_accumulates_agents():
    spirit_root.assess("a", [{"category": "reasoning", "ok": True}])
    spirit_root.assess("b", [{"category": "coding", "ok": False}])
    snap = spirit_root.snapshot()
    assert set(snap.keys()) == {"a", "b"}
    assert snap["a"]["agent"] == "a"
    # snapshot is a copy: mutating it must not affect stored state
    snap.pop("a")
    assert "a" in spirit_root.snapshot()


def test_unknown_category_ignored():
    rows = [
        {"category": "telepathy", "ok": True},
        {"category": "reasoning", "ok": True},
    ]
    p = spirit_root.assess("weird", rows)
    # unknown category does not appear and does not affect scoring
    assert "telepathy" not in p["categories"]
    assert p["categories"]["reasoning"] == 100
    assert p["samples"] == 2


def test_clear_empties():
    spirit_root.assess("a", [{"category": "reasoning", "ok": True}])
    assert spirit_root.snapshot()
    spirit_root.clear()
    assert spirit_root.snapshot() == {}
    assert spirit_root.profile("a") is None
