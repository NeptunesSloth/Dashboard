"""Login validation + Web Push subscription framework."""
from fastapi.testclient import TestClient

from maybot_control_center.app import app
from maybot_control_center import authz, push

client = TestClient(app)


# ---- login ----
def test_login_ok_when_no_auth(monkeypatch):
    monkeypatch.setattr(authz, "load_users", lambda: [])
    monkeypatch.setattr(authz, "CONTROL_CENTER_TOKEN", "")
    r = client.post("/api/login", json={"token": ""})
    assert r.status_code == 200 and r.json()["role"] == "operator"


def test_login_rejects_bad_token(monkeypatch):
    monkeypatch.setattr(authz, "load_users", lambda: [{"name": "a", "token": "good", "role": "operator"}])
    assert client.post("/api/login", json={"token": "bad"}).status_code == 401
    r = client.post("/api/login", json={"token": "good"})
    assert r.status_code == 200 and r.json()["name"] == "a"


# ---- web push ----
def test_subscribe_stores(monkeypatch):
    push.clear()
    out = push.subscribe({"endpoint": "https://push/abc", "keys": {}})
    assert out["subscribed"] is True and push.snapshot()["subscriptions"] == 1


def test_subscribe_requires_endpoint():
    import pytest
    with pytest.raises(ValueError):
        push.subscribe({})


def test_send_noop_without_vapid(monkeypatch):
    monkeypatch.setattr(push, "PUBLIC_KEY", "")
    monkeypatch.setattr(push, "PRIVATE_KEY", "")
    push.clear()
    push.subscribe({"endpoint": "https://push/x"})
    assert push.send("t", "b") == 0          # not configured → no-op


def test_key_endpoint():
    assert "enabled" in client.get("/api/push/key").json()


def test_subscribe_endpoint():
    push.clear()
    r = client.post("/api/push/subscribe", json={"subscription": {"endpoint": "https://push/e"}})
    assert r.status_code == 200 and r.json()["count"] == 1
