"""Observability: cheap Prometheus exposition + opt-in JSON logging."""
import io
import json
import logging

from fastapi.testclient import TestClient

from maybot_control_center import obs
from maybot_control_center.app import app

client = TestClient(app)


def test_render_prometheus_is_str_with_help_and_type():
    text = obs.render_prometheus()
    assert isinstance(text, str)
    assert "# HELP" in text
    assert "# TYPE" in text
    # at least one concrete metric name is exposed
    assert "maybot_obs_process_up" in text


def test_metrics_obs_endpoint_ok_and_plain_text():
    r = client.get("/metrics/obs")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    body = r.text
    assert "# HELP" in body and "# TYPE" in body
    assert "maybot_obs_process_up 1" in body


def test_root_metrics_still_serves_plain_text():
    # The pre-existing comprehensive /metrics route is untouched.
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "# HELP" in r.text


def test_metrics_obs_gated_when_not_public(monkeypatch):
    # With public scraping off and no metrics token, the route falls back to the
    # standard control-token gate. Configure users so that gate actually rejects
    # an absent token (the default open-auth env would otherwise allow it).
    from maybot_control_center import authz
    monkeypatch.setenv("MAYBOT_METRICS_PUBLIC", "0")
    monkeypatch.delenv("MAYBOT_METRICS_TOKEN", raising=False)
    monkeypatch.setattr(authz, "load_users",
                        lambda: [{"name": "alice", "token": "t1", "role": "operator"}])
    r = client.get("/metrics/obs")
    assert r.status_code == 401  # invalid/absent control token

    ok = client.get("/metrics/obs", headers={"x-control-token": "t1"})
    assert ok.status_code == 200
    assert "maybot_obs_process_up" in ok.text


def test_metrics_obs_token_unlocks_when_not_public(monkeypatch):
    monkeypatch.setenv("MAYBOT_METRICS_PUBLIC", "0")
    monkeypatch.setenv("MAYBOT_METRICS_TOKEN", "scrape-secret")
    r = client.get("/metrics/obs", headers={"x-control-token": "scrape-secret"})
    assert r.status_code == 200
    assert "maybot_obs_process_up" in r.text


def test_setup_logging_noop_when_unset(monkeypatch):
    monkeypatch.delenv("MAYBOT_JSON_LOGS", raising=False)
    assert obs.setup_logging() is False


def test_setup_logging_emits_json(monkeypatch):
    monkeypatch.setenv("MAYBOT_JSON_LOGS", "1")
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    try:
        # Replace handlers with a single capture handler so we read exactly one line.
        buf = io.StringIO()
        capture = logging.StreamHandler(buf)
        root.handlers = [capture]
        assert obs.setup_logging() is True
        logging.getLogger("test.obs").warning("hello %s", "world")
        capture.flush()
        line = buf.getvalue().strip().splitlines()[-1]
        rec = json.loads(line)
        assert rec["level"] == "WARNING"
        assert rec["logger"] == "test.obs"
        assert rec["msg"] == "hello world"
        assert "ts" in rec
    finally:
        root.handlers = saved_handlers
        root.setLevel(saved_level)
