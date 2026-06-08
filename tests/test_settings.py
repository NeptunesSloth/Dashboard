import os

from fastapi.testclient import TestClient

from maybot_control_center.app import app
from maybot_control_center import settings, authz

client = TestClient(app)


def _item(view, key):
    return [it for g in view["groups"] for it in g["items"] if it["key"] == key][0]


def test_settings_view_set_and_apply_at_runtime(monkeypatch):
    from maybot_control_center import sectsim, agents
    monkeypatch.setattr(settings, "_overrides", {})           # isolate overrides
    monkeypatch.setattr(sectsim, "XP_RATE", 1.0, raising=False)
    monkeypatch.setattr(agents, "DELEGATION_GLOBAL", False, raising=False)

    touched = ["MAYBOT_SECT_XP_RATE", "MAYBOT_DELEGATION", "ANTHROPIC_API_KEY"]
    saved = {k: os.environ.get(k) for k in touched}
    try:
        # masked view has the four groups
        v = client.get("/api/settings").json()
        assert {g["id"] for g in v["groups"]} >= {"ai", "notify", "automation", "sim"}

        r = client.post("/api/settings", json={"values": {
            "MAYBOT_SECT_XP_RATE": "2.5", "MAYBOT_DELEGATION": "1", "ANTHROPIC_API_KEY": "sk-test"}})
        assert r.status_code == 200

        # applied to the live process (cached globals + env), not just stored
        assert sectsim.XP_RATE == 2.5
        assert agents.DELEGATION_GLOBAL is True
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-test"

        # secrets are masked on the plain GET, revealed only via /unlock
        masked = _item(client.get("/api/settings").json(), "ANTHROPIC_API_KEY")
        assert masked["set"] is True and masked["value"] == ""
        revealed = _item(client.post("/api/settings/unlock", json={"password": ""}).json(), "ANTHROPIC_API_KEY")
        assert revealed["value"] == "sk-test"
    finally:
        for k in touched:
            if saved[k] is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = saved[k]


def test_settings_password_gate(monkeypatch):
    """When the operator account has a password, viewing/saving secrets requires it."""
    h = authz.hash_password("hunter2")
    monkeypatch.setattr(authz, "current_user", lambda tok: {"name": "op", "role": "operator", "pw": h})

    assert client.post("/api/settings/unlock", json={"password": "nope"}).status_code == 403
    assert client.post("/api/settings/unlock", json={"password": "hunter2"}).status_code == 200
    # saving is gated too
    assert client.post("/api/settings", json={"values": {}, "password": "nope"}).status_code == 403
    assert client.post("/api/settings", json={"values": {}, "password": "hunter2"}).status_code == 200
