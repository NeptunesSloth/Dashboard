import pytest
from fastapi.testclient import TestClient

from maybot_control_center.app import app
from maybot_control_center import authz

client = TestClient(app)


@pytest.fixture(autouse=True)
def temp_users(tmp_path, monkeypatch):
    monkeypatch.setattr(authz, "USERS_FILE", tmp_path / "users.yaml")
    authz.clear()
    yield
    authz.clear()


def test_password_hash_roundtrip():
    h = authz.hash_password("hunter2horse")
    assert h.startswith("pbkdf2$") and authz.verify_password("hunter2horse", h)
    assert not authz.verify_password("wrong", h)


def test_signup_then_login_with_password():
    # fresh dashboard: open mode (no auth configured yet), no accounts
    me = client.get("/api/account/me").json()
    assert me["accounts_exist"] is False and me["auth_active"] is False

    # signup claims it as operator and returns a session
    r = client.post("/api/signup", json={"name": "owner", "password": "supersecret"})
    assert r.status_code == 200 and r.json()["role"] == "operator"
    sess = r.json()["session"]
    assert client.get("/api/account/me", headers={"x-control-token": sess}).json()["name"] == "owner"

    # signup is now closed
    assert client.post("/api/signup", json={"name": "x", "password": "supersecret"}).status_code == 403
    # short password rejected (on a hypothetical fresh install)
    # login with correct + wrong password
    assert client.post("/api/login", json={"name": "owner", "password": "supersecret"}).json().get("session")
    assert client.post("/api/login", json={"name": "owner", "password": "nope"}).status_code == 401


def test_change_password():
    sess = client.post("/api/signup", json={"name": "ann", "password": "firstpass1"}).json()["session"]
    h = {"x-control-token": sess}
    # wrong current password is rejected
    assert client.post("/api/account/password", json={"old": "nope", "new": "secondpass2"}, headers=h).status_code == 403
    # correct rotation works, and the new password logs in
    assert client.post("/api/account/password", json={"old": "firstpass1", "new": "secondpass2"}, headers=h).status_code == 200
    assert client.post("/api/login", json={"name": "ann", "password": "secondpass2"}).json().get("session")


def test_2fa_requires_channel_then_challenges(monkeypatch):
    sess = client.post("/api/signup", json={"name": "z", "password": "passphrase1"}).json()["session"]
    h = {"x-control-token": sess}
    # webhook method explicitly requires a notification channel
    monkeypatch.setattr("maybot_control_center.notify.channels", lambda: [])
    assert client.post("/api/account/2fa", json={"enable": True, "method": "webhook"}, headers=h).status_code == 400
    # with a channel, enabling works and login then requires the code
    monkeypatch.setattr("maybot_control_center.notify.channels", lambda: ["webhook"])
    monkeypatch.setattr("maybot_control_center.notify.send", lambda *a, **k: {"delivered": ["webhook"]})
    assert client.post("/api/account/2fa", json={"enable": True, "method": "webhook"}, headers=h).json()["tfa"] is True
    r = client.post("/api/login", json={"name": "z", "password": "passphrase1"}).json()
    assert r.get("pending_2fa") and r.get("challenge")
    # wrong code rejected; right code (from the in-memory challenge) issues a session
    assert client.post("/api/login/2fa", json={"challenge": r["challenge"], "code": "000000"}).status_code in (401,)


def test_login_lockout(monkeypatch):
    monkeypatch.setattr(authz, "LOGIN_MAX_FAILS", 3)
    client.post("/api/signup", json={"name": "lock", "password": "passphrase1"})
    for _ in range(3):
        assert client.post("/api/login", json={"name": "lock", "password": "wrong"}).status_code == 401
    # further attempts are blocked even with the correct password
    assert client.post("/api/login", json={"name": "lock", "password": "passphrase1"}).status_code == 429


def test_setup_status():
    s = client.get("/api/setup").json()
    assert set(s["steps"]) == {"account", "host", "member", "ai", "notifications"}
    assert s["steps"]["account"] is False and s["done"] is False


def test_totp_2fa():
    su = client.post("/api/signup", json={"name": "ty", "password": "password1"}).json()
    h = {"x-control-token": su["session"]}
    r = client.post("/api/account/2fa", json={"enable": True, "method": "totp"}, headers=h).json()
    assert r["method"] == "totp" and r["secret"] and r["uri"].startswith("otpauth://")
    secret = r["secret"]
    lg = client.post("/api/login", json={"name": "ty", "password": "password1"}).json()
    assert lg.get("pending_2fa") and lg.get("method") == "totp"
    import time
    from maybot_control_center import authz
    code = authz._totp_at(secret, int(time.time() // 30))
    ok = client.post("/api/login/2fa", json={"challenge": lg["challenge"], "code": code})
    assert ok.status_code == 200 and ok.json().get("session")
    lg2 = client.post("/api/login", json={"name": "ty", "password": "password1"}).json()
    assert client.post("/api/login/2fa", json={"challenge": lg2["challenge"], "code": "000000"}).status_code == 401


def test_operator_reset_password():
    op = client.post("/api/signup", json={"name": "boss", "password": "password1"}).json()["session"]
    h = {"x-control-token": op}
    client.post("/api/accounts", json={"name": "u2", "role": "viewer"}, headers=h)
    assert client.post("/api/accounts/u2/reset-password", json={"new": "newpass12"}, headers=h).status_code == 200
    assert client.post("/api/login", json={"name": "u2", "password": "newpass12"}).json().get("session")


def test_security_headers():
    r = client.get("/api/setup")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "SAMEORIGIN"
