import pytest
from fastapi.testclient import TestClient

from maybot_control_center.app import app
from maybot_control_center import authz

client = TestClient(app)


@pytest.fixture(autouse=True)
def temp_users(tmp_path, monkeypatch):
    monkeypatch.setattr(authz, "USERS_FILE", tmp_path / "users.yaml")
    yield


def test_accounts_crud_and_bootstrap():
    # open access until the first account exists
    r = client.get("/api/accounts").json()
    assert r["accounts"] == [] and r["auth_active"] is False

    # first account: returns its token once and flags bootstrap
    r = client.post("/api/accounts", json={"name": "alice", "role": "operator"})
    j = r.json()
    assert r.status_code == 200 and j["first"] is True and len(j["token"]) >= 32
    alice_tok = j["token"]
    assert authz.role_for(alice_tok) == "operator"

    # auth is now active; the token is masked in listings
    lst = client.get("/api/accounts", headers={"x-control-token": alice_tok}).json()
    assert lst["auth_active"] is True
    assert alice_tok not in lst["accounts"][0]["token_masked"]

    # add a viewer (authed as operator)
    h = {"x-control-token": alice_tok}
    r = client.post("/api/accounts", json={"name": "bob", "role": "viewer"}, headers=h)
    assert r.status_code == 200 and r.json()["first"] is False
    assert authz.role_for(r.json()["token"]) == "viewer"

    # editing with a blank token keeps the old one; role can change
    bob_tok = r.json()["token"]
    r = client.post("/api/accounts", json={"name": "bob", "role": "operator", "token": "", "original_name": "bob"}, headers=h)
    assert r.status_code == 200 and authz.role_for(bob_tok) == "operator"

    # duplicate name rejected
    assert client.post("/api/accounts", json={"name": "alice", "role": "viewer"}, headers=h).status_code == 409

    # can't strand the dashboard without an operator
    client.request("DELETE", "/api/accounts/bob", headers=h)  # ok, alice still operator
    assert client.request("DELETE", "/api/accounts/alice", headers=h).status_code == 200  # last user -> open again
    assert authz.load_users() == []


def test_viewer_cannot_manage_accounts():
    op = client.post("/api/accounts", json={"name": "root", "role": "operator"}).json()["token"]
    vw = client.post("/api/accounts", json={"name": "val", "role": "viewer"}, headers={"x-control-token": op}).json()["token"]
    # a viewer is not allowed to create accounts
    assert client.post("/api/accounts", json={"name": "x", "role": "viewer"}, headers={"x-control-token": vw}).status_code in (401, 403)
