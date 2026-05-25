from maybot_control_center.agent_client import _wrap


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
