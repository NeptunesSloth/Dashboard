from maybot_agent.adapters.local_ai_host import adapt
from maybot_control_center.aggregator import aggregate


class DummyResp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload


def test_local_ai_offline_when_unreachable(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("down")
    monkeypatch.setattr("maybot_agent.adapters.local_ai_host.requests.get", boom)
    out = adapt({"name": "llm", "type": "local_ai_host", "provider": "ollama", "base_url": "http://127.0.0.1:11434"})
    assert out["metrics"]["status"] == "offline"


def test_local_ai_unknown_bad_provider():
    out = adapt({"name": "llm", "type": "local_ai_host", "provider": "weird"})
    assert out["metrics"]["status"] == "unknown"


def test_no_generation_call_when_disabled(monkeypatch):
    calls = {"post": 0}

    def fake_get(url, timeout=5):
        return DummyResp(200, {"data": [{"id": "hermes"}]})

    def fake_post(*args, **kwargs):
        calls["post"] += 1
        return DummyResp(200, {})

    monkeypatch.setattr("maybot_agent.adapters.local_ai_host.requests.get", fake_get)
    monkeypatch.setattr("maybot_agent.adapters.local_ai_host.requests.post", fake_post)
    out = adapt({"name": "llm", "type": "local_ai_host", "provider": "openai_compatible", "base_url": "http://127.0.0.1:1234", "test_prompt_enabled": False})
    assert out["metrics"]["status"] == "online"
    assert calls["post"] == 0


def test_aggregator_counts_local_ai_hosts(monkeypatch):
    def fake_call(device, endpoint):
        if endpoint == "/api/ping":
            return {"online": True, "data": {"status": "ok"}}
        return {"online": True, "data": [{"name": "llm", "type": "local_ai_host", "health": "error", "status": "running", "metrics": {"status": "offline"}}]}

    monkeypatch.setattr("maybot_control_center.aggregator.call_agent", fake_call)
    out = aggregate([{"name": "d1", "url": "http://x", "api_token": "t"}])
    s = out["summary"]
    assert s["local_ai_hosts_total"] == 1
    assert s["local_ai_hosts_online"] == 0
    assert s["local_ai_hosts_offline"] == 1
    assert s["local_ai_hosts_with_errors"] == 1
