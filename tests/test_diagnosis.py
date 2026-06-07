from maybot_control_center import diagnosis


def test_analyze_logs_picks_root_cause():
    logs = [
        "2026-06-07 INFO starting",
        "ERROR connection refused to broker at 10.0.0.2:7497",
        "ERROR connection refused to broker at 10.0.0.2:7497",
        "WARNING retrying",
    ]
    f = diagnosis.analyze_logs(logs)
    assert f and f[0]["signal"] == "dependency unreachable" and f[0]["count"] == 2


def test_analyze_logs_exception_type():
    f = diagnosis.analyze_logs(["Traceback (most recent call last):", "ValueError: bad symbol"])
    assert any(x["signal"].startswith("exception: ValueError") for x in f)


def test_analyze_logs_clean():
    assert diagnosis.analyze_logs(["INFO all good", "INFO tick"]) == []
