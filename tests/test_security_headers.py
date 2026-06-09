"""Baseline + opt-in security headers."""
import importlib

from starlette.testclient import TestClient


def _client(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import maybot_control_center.app as app_mod
    importlib.reload(app_mod)
    return TestClient(app_mod.app), app_mod


def test_baseline_headers_always_present(monkeypatch):
    client, _ = _client(monkeypatch)
    h = client.get("/healthz").headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "SAMEORIGIN"
    # CSP/HSTS are opt-in — absent by default.
    assert "content-security-policy" not in h
    assert "strict-transport-security" not in h


def test_csp_and_hsts_opt_in(monkeypatch):
    client, _ = _client(monkeypatch, MAYBOT_CSP="1", MAYBOT_HSTS="1")
    h = client.get("/healthz").headers
    assert h["Content-Security-Policy"].startswith("default-src 'self'")
    assert "max-age=" in h["Strict-Transport-Security"]


def test_custom_csp_string(monkeypatch):
    client, _ = _client(monkeypatch, MAYBOT_CSP="default-src 'none'")
    assert client.get("/healthz").headers["Content-Security-Policy"] == "default-src 'none'"
    # restore module to default env for the rest of the suite
    _client(monkeypatch)
