from maybot_control_center import store, authz, risk


def _use_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "state.db"))
    store._conn = None
    store.init()


def test_sessions_survive_restart(tmp_path, monkeypatch):
    _use_db(tmp_path, monkeypatch)
    monkeypatch.setattr(authz, "USERS_FILE", tmp_path / "users.yaml")
    authz.clear()
    authz.save_users([{"name": "a", "token": "rawtok1234567890", "role": "operator",
                       "pw": authz.hash_password("password1")}])
    s = authz.issue_session("rawtok1234567890")
    assert s and s["session"]
    sid = s["session"]
    authz._sessions.clear()              # simulate process restart (memory gone)
    assert authz.role_for(sid) is None   # auth active, session id unknown now
    authz.load_persisted()               # restore from store
    assert authz.role_for(sid) == "operator"


def test_kill_switch_survives_restart(tmp_path, monkeypatch):
    _use_db(tmp_path, monkeypatch)
    risk.kill_switch(True, actor="op")
    assert risk.is_halted() is True
    risk._kill.update({"on": False})     # wipe in-memory
    assert risk.is_halted() is False
    risk.load_persisted()
    assert risk.is_halted() is True
    risk.kill_switch(False)              # cleanup
