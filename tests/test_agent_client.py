from maybot_control_center import agent_client
from maybot_control_center.agent_client import _wrap, _device_timeout


class DummyResp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload


def test_wrap_marks_401_403_as_auth_error_and_not_online():
    r401 = _wrap(DummyResp(401, {"detail": "bad token"}))
    assert r401["online"] is False
    assert r401["auth_error"] is True
    assert r401["status_code"] == 401
    assert "bad token" in (r401["error"] or "")

    r403 = _wrap(DummyResp(403, {"detail": "forbidden"}))
    assert r403["online"] is False
    assert r403["auth_error"] is True
    assert r403["status_code"] == 403


def test_device_timeout_default(monkeypatch):
    monkeypatch.setattr(agent_client, "DEFAULT_TIMEOUT", 5.0)
    assert _device_timeout({}) == 5.0
    assert _device_timeout({"timeout": None}) == 5.0
    assert _device_timeout({"timeout": "bad"}) == 5.0
    assert _device_timeout({"timeout": 0}) == 5.0       # non-positive falls back


def test_device_timeout_override(monkeypatch):
    monkeypatch.setattr(agent_client, "DEFAULT_TIMEOUT", 5.0)
    assert _device_timeout({"timeout": 12}) == 12.0
    assert _device_timeout({"timeout": "2.5"}) == 2.5


def test_call_agent_uses_device_timeout(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["timeout"] = timeout
        return DummyResp(200, {"ok": True})

    monkeypatch.setattr(agent_client._session, "get", fake_get)
    agent_client.call_agent({"url": "http://x", "api_token": "t", "timeout": 9}, "/api/ping")
    assert captured["timeout"] == 9.0
