from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from maybot_control_center.app import app
from maybot_control_center import config, tools

client = TestClient(app)


@pytest.fixture(autouse=True)
def temp_devices(tmp_path, monkeypatch):
    """Point the host store at a throwaway file so tests never touch devices.yaml."""
    monkeypatch.setattr(config, "DEVICES_FILE", tmp_path / "devices.yaml")
    yield


def test_hosts_crud_roundtrip():
    assert client.get("/api/hosts").json() == {"hosts": []}

    tok = client.get("/api/hosts/gen-token").json()["token"]
    assert len(tok) == 64

    r = client.post("/api/hosts", json={"name": "trade-server", "url": "http://10.0.0.2:8100", "api_token": tok})
    assert r.status_code == 200 and r.json()["ok"]

    # persisted to the (temp) devices file and reloadable
    assert config.load_devices()[0]["api_token"] == tok

    hosts = client.get("/api/hosts").json()["hosts"]
    assert len(hosts) == 1 and hosts[0]["name"] == "trade-server"
    assert tok not in hosts[0]["token_masked"]            # token is masked in the API
    assert hosts[0]["online"] is False                    # nothing actually listening

    # editing with a blank token keeps the existing one; URL updates
    r = client.post("/api/hosts", json={"name": "trade-server", "url": "http://10.0.0.9:8100",
                                        "api_token": "", "original_name": "trade-server"})
    assert r.status_code == 200
    saved = config.load_devices()[0]
    assert saved["url"] == "http://10.0.0.9:8100" and saved["api_token"] == tok

    r = client.request("DELETE", "/api/hosts/trade-server")
    assert r.status_code == 200 and config.load_devices() == []
    assert client.request("DELETE", "/api/hosts/trade-server").status_code == 404


def test_hosts_validation_and_dupes():
    client.post("/api/hosts", json={"name": "a", "url": "http://1.2.3.4:8100"})
    # duplicate name rejected
    assert client.post("/api/hosts", json={"name": "a", "url": "http://5.6.7.8:8100"}).status_code == 409
    # bad url rejected on save and on test
    assert client.post("/api/hosts", json={"name": "b", "url": "ftp://nope"}).status_code == 400
    assert client.post("/api/hosts/test", json={"url": "ftp://nope"}).status_code == 400


def test_hosts_test_offline():
    j = client.post("/api/hosts/test", json={"url": "http://127.0.0.1:59999", "api_token": "x"}).json()
    assert j["online"] is False and j["projects"] == 0


def test_host_mutations_publish_live_events():
    """Adding/removing a host pushes a 'hosts' SSE event so live dashboards update."""
    import json
    from maybot_control_center import events
    q = events.subscribe()
    try:
        client.post("/api/hosts", json={"name": "ev", "url": "http://1.2.3.4:8100"})
        client.request("DELETE", "/api/hosts/ev")
        kinds = []
        while not q.empty():
            kinds.append(json.loads(q.get_nowait()).get("type"))
        assert kinds.count("hosts") >= 2          # one for save, one for delete
    finally:
        events.unsubscribe(q)


def test_host_projects_proxy_endpoints():
    # Unknown host -> 404.
    assert client.get("/api/hosts/nope/projects").status_code == 404
    # Known but unreachable host -> 502 (agent down), not a crash.
    client.post("/api/hosts", json={"name": "c", "url": "http://127.0.0.1:59998", "api_token": "x"})
    assert client.get("/api/hosts/c/projects").status_code == 502
    assert client.put("/api/hosts/c/projects", json={"projects": []}).status_code == 502
    assert client.get("/api/hosts/c/discover").status_code == 502


def test_enroll_token_in_app(monkeypatch):
    """The self-enrollment token is fully manageable from the dashboard:
    generate → view → use → disable, no env edit / restart."""
    from maybot_control_center import registry
    monkeypatch.setattr(registry, "REGISTER_TOKEN", "")  # auto-restored after the test

    g = client.get("/api/hosts/enroll-token").json()
    assert g["configured"] is False and g["token"] == ""

    # generate one
    r = client.post("/api/hosts/enroll-token", json={"generate": True}).json()
    assert r["ok"] and r["configured"] and len(r["token"]) == 64
    tok = r["token"]
    assert registry.REGISTER_TOKEN == tok
    assert client.get("/api/hosts/enroll-token").json()["token"] == tok

    # set an explicit value
    r = client.post("/api/hosts/enroll-token", json={"token": "my-secret-123"}).json()
    assert r["token"] == "my-secret-123" and r["configured"]

    # the self-enroll endpoint now accepts that token (no operator token needed)
    reg = client.post("/api/agents/register", headers={"x-register-token": "my-secret-123"},
                      json={"name": "edgehost", "url": "http://10.0.0.5:8100", "api_token": "t"})
    assert reg.status_code == 200
    registry.deregister("edgehost")

    # disable
    r = client.post("/api/hosts/enroll-token", json={"clear": True}).json()
    assert r["configured"] is False and r["token"] == ""


def test_builtin_observability_tools_available():
    names = [t["name"] for t in tools.tool_summaries()]
    assert "bot_status" in names and "bot_logs" in names
    assert tools.enabled() is True
    assert "bot_status" in tools.prompt_hint()
    # a built-in runs in-process, auto-approves, and degrades gracefully with no hosts
    snap = tools.request_tool("Nova", "bot_status", {"project": "daybot"})
    assert snap["status"] == "done" and "daybot" in snap["output"]
