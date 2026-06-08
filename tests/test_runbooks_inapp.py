"""In-app (persisted, editable) self-healing runbooks layered over file rules."""
import pytest
from fastapi.testclient import TestClient

from maybot_control_center import runbooks
from maybot_control_center.app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean():
    runbooks.clear()
    yield
    runbooks.clear()


def test_save_list_delete_rule():
    rb = runbooks.save_rule({"name": "restart-stalled", "tool": "bot_status",
                             "match": {"type": "trading_bot", "health": "error"}, "auto": True})
    assert rb["name"] == "restart-stalled" and rb["auto"] is True
    assert [r["name"] for r in runbooks.list_rules()] == ["restart-stalled"]
    assert runbooks.delete_rule("restart-stalled") is True
    assert runbooks.list_rules() == []
    assert runbooks.delete_rule("restart-stalled") is False


def test_save_rule_validates():
    with pytest.raises(ValueError):
        runbooks.save_rule({"name": "", "tool": "x"})
    with pytest.raises(ValueError):
        runbooks.save_rule({"name": "n", "tool": ""})


def test_inapp_rule_matches_projects():
    runbooks.save_rule({"name": "r1", "tool": "bot_status", "match": {"health": "error"}})
    assert runbooks.match({"name": "daybot", "health": "error"})["name"] == "r1"
    assert runbooks.match({"name": "daybot", "health": "ok"}) is None


def test_endpoints_roundtrip():
    r = client.post("/api/runbooks", json={"name": "ep", "tool": "bot_status", "match": {"type": "website"}})
    assert r.status_code == 200 and r.json()["ok"]
    cat = client.get("/api/runbooks").json()
    assert any(x["name"] == "ep" for x in cat["editable"])
    assert "tools" in cat and isinstance(cat["tools"], list)
    assert client.request("DELETE", "/api/runbooks/ep").json()["ok"] is True
    # invalid -> 400
    assert client.post("/api/runbooks", json={"name": "", "tool": ""}).status_code == 400
