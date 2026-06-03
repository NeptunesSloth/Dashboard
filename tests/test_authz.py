from maybot_control_center import authz


def setup_function():
    authz.clear()


def test_open_mode_when_nothing_configured(monkeypatch, tmp_path):
    monkeypatch.setattr(authz, "USERS_FILE", tmp_path / "none.yaml")
    monkeypatch.setattr(authz, "CONTROL_CENTER_TOKEN", "")
    assert authz.role_for("") == "operator"  # no auth → open (legacy behavior)


def test_single_token_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(authz, "USERS_FILE", tmp_path / "none.yaml")
    monkeypatch.setattr(authz, "CONTROL_CENTER_TOKEN", "sekret")
    assert authz.role_for("sekret") == "operator"
    assert authz.role_for("nope") is None
    assert authz.role_for("") is None


def test_rbac_from_users_file(monkeypatch, tmp_path):
    f = tmp_path / "users.yaml"
    f.write_text(
        "users:\n  - {name: a, token: optok, role: operator}\n  - {name: b, token: viewtok, role: viewer}\n",
        encoding="utf-8")
    monkeypatch.setattr(authz, "USERS_FILE", f)
    assert authz.role_for("optok") == "operator"
    assert authz.role_for("viewtok") == "viewer"
    assert authz.role_for("bad") is None   # configured users → unknown token rejected


def test_rate_limit_fixed_window(monkeypatch):
    monkeypatch.setattr(authz, "RATE", 3)
    monkeypatch.setattr(authz, "WINDOW", 60)
    assert [authz.allow_request("k") for _ in range(4)] == [True, True, True, False]
    # a different key has its own budget
    assert authz.allow_request("other") is True


def test_rate_limit_disabled(monkeypatch):
    monkeypatch.setattr(authz, "RATE", 0)
    assert all(authz.allow_request("k") for _ in range(100))
