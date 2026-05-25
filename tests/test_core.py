from maybot_agent.services.command_runner import run_foreground, start_background
from maybot_agent.services.process_status import find_process
from maybot_agent.adapters.trading_bot import adapt as adapt_trading


def test_run_foreground_missing_argv():
    res = run_foreground({}, {})
    assert res["status"] == "unknown"


def test_start_background_requires_flag():
    res = start_background({"argv": ["python", "-c", "print('x')"]}, {})
    assert res["status"] == "error"


def test_process_detection_not_found():
    res = find_process(cmdline_contains="definitely_not_a_real_process_token")
    assert res["running"] is False


def test_trading_adapter_fallback_unknown(tmp_path):
    p = {"name": "t", "type": "trading_bot", "path": str(tmp_path)}
    out = adapt_trading(p)
    assert out["metrics"]["profit_today"] == "unknown"
