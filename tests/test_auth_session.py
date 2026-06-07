"""Session tokens (login → time-boxed session) and per-project ACLs."""
import time

import pytest

from maybot_control_center import authz


@pytest.fixture(autouse=True)
def _clean():
    authz.clear()
    yield
    authz.clear()


def test_issue_and_validate_session(monkeypatch):
    monkeypatch.setattr(authz, "load_users",
                        lambda: [{"name": "alice", "token": "secret", "role": "operator"}])
    out = authz.issue_session("secret")
    assert out is not None and out["role"] == "operator" and out["name"] == "alice"
    sid = out["session"]
    # The session token now resolves to the captured role/name.
    assert authz.role_for(sid) == "operator"
    assert authz.name_for(sid) == "alice"


def test_invalid_token_yields_no_session(monkeypatch):
    monkeypatch.setattr(authz, "load_users",
                        lambda: [{"name": "alice", "token": "secret", "role": "operator"}])
    assert authz.issue_session("nope") is None


def test_session_expiry(monkeypatch):
    # Users configured so an unknown/expired token resolves to None (not the
    # no-auth fall-through, which would treat any token as operator).
    monkeypatch.setattr(authz, "load_users",
                        lambda: [{"name": "a", "token": "secret", "role": "operator"}])
    monkeypatch.setattr(authz, "SESSION_TTL_MINUTES", 1)
    sid = authz.issue_session("secret")["session"]
    assert authz.role_for(sid) == "operator"
    # Advance time beyond the TTL — the session is reaped on next lookup.
    monkeypatch.setattr(time, "time", lambda: 10**12)
    assert authz.role_for(sid) is None


def test_revoke_session(monkeypatch):
    monkeypatch.setattr(authz, "load_users",
                        lambda: [{"name": "a", "token": "secret", "role": "operator"}])
    sid = authz.issue_session("secret")["session"]
    assert authz.revoke_session(sid) is True
    assert authz.role_for(sid) is None


def test_project_acl_default_allows(monkeypatch):
    monkeypatch.setattr(authz, "load_users",
                        lambda: [{"name": "a", "token": "t", "role": "operator"}])
    # No `projects` list → access to everything.
    assert authz.can_access_project("t", "dev", "proj") is True


def test_project_acl_restricts(monkeypatch):
    monkeypatch.setattr(authz, "load_users",
                        lambda: [{"name": "a", "token": "t", "role": "operator",
                                  "projects": ["edge:bot1", "lab:*"]}])
    assert authz.can_access_project("t", "edge", "bot1") is True
    assert authz.can_access_project("t", "lab", "anything") is True
    assert authz.can_access_project("t", "prod", "bot1") is False


def test_project_acl_via_session(monkeypatch):
    monkeypatch.setattr(authz, "load_users",
                        lambda: [{"name": "a", "token": "t", "role": "viewer",
                                  "projects": ["edge:*"]}])
    sid = authz.issue_session("t")["session"]
    assert authz.can_access_project(sid, "edge", "x") is True
    assert authz.can_access_project(sid, "prod", "x") is False
