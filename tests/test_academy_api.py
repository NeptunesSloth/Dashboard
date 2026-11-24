"""Sect Academy HTTP surface, against the content packs that actually ship."""
import pytest
from fastapi.testclient import TestClient

from maybot_control_center import authz
from maybot_control_center.academy import engine, packs, state
from maybot_control_center.app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setenv("MAYBOT_ACADEMY_FILE", ":memory:")
    monkeypatch.setattr(authz, "USERS_FILE", tmp_path / "users.yaml")
    packs.load_all(force=True)
    state.reset_for_tests()
    yield
    state.reset_for_tests()


def _truth(ex):
    it = packs.item_index()[ex["item"]]
    if ex["mode"] in ("type_l2", "listen"):
        return it["l2"]
    if ex["mode"] == "cloze_type":
        return it["answer"]
    return engine._truth(it, ex["mode"])


def test_pages_and_assets_served():
    for path in ("/", "/study", "/library", "/trials", "/progress"):
        r = client.get(path)
        assert r.status_code == 200 and "Sect Academy" in r.text
    assert client.get("/academy.js").status_code == 200
    assert client.get("/academy.css").status_code == 200
    assert client.get("/command").status_code == 200           # the fleet hall moved, not removed


def test_shipped_courses_cover_the_brief():
    got = {p["id"]: p for p in client.get("/api/academy/packs").json()}
    assert {"french-a1", "spanish-a1", "security-plus", "network-plus", "isc2-cc"} <= set(got)
    assert all(p["items"] >= 100 for p in got.values())
    for p in packs.load_all().values():                         # every pack can build every exercise
        for u in p["units"]:
            for it in u["items"]:
                modes = ["mcq"] if it["type"] == "mcq" else sorted(engine._MODES[it["type"]])
                for mode in modes:
                    ex = engine.build_exercise(it, mode, p, 1)
                    if "choices" in ex:
                        assert len(ex["choices"]) == 4 and len(set(ex["choices"])) == 4, (it["id"], mode, ex["choices"])
                        assert _truth(ex) in ex["choices"], (it["id"], mode)
                    assert engine.check(it, mode, _truth(ex))["correct"], (it["id"], mode)


def test_full_day_over_http():
    ov = client.get("/api/academy/overview?tz=60").json()
    assert not ov["onboarded"] and ov["settings"]["tz_offset_min"] == 60
    ov = client.post("/api/academy/setup", json={"name": "Azure Lantern", "master": "Jay",
                                                 "courses": ["french-a1", "isc2-cc"]}).json()
    assert ov["onboarded"] and ov["game"]["name"] == "Azure Lantern" and ov["today"]["new_left"] == 16
    assert [q["id"] for q in ov["game"]["quests"]][0] == "session"
    s = client.post("/api/academy/session", json={}).json()
    assert s["ok"] and s["new"] == 16 and len(s["notes"]) == 2
    n = 0
    for ex in s["exercises"]:
        if ex["mode"] == "intro":
            continue
        r = client.post("/api/academy/answer", json={"session": s["session"], "item": ex["item"], "mode": ex["mode"],
                                                     "answer": _truth(ex)}).json()
        assert r["correct"] and r["rewards"]["qi"] > 0
        n += 1
    assert client.post("/api/academy/answer", json={"item": "fr-01-bonjour", "mode": "choose_l1", "answer": "x"}).status_code == 422
    fin = client.post("/api/academy/session/finish", json={"session": s["session"], "secs": 420}).json()
    assert fin["counted"] and fin["streak"] == 1 and fin["stones"] >= 40
    again = client.post("/api/academy/session/finish", json={"session": s["session"], "secs": 1}).json()
    assert again["stones"] == 0 and again["already"]             # a replayed finish pays nothing
    ov = client.get("/api/academy/overview").json()
    assert ov["today"]["new_left"] == 0 and ov["game"]["studied_today"] and ov["game"]["quests"][0]["done"]
    # spend the earnings: build the spirit vein, recruit, post the disciple
    r = client.post("/api/academy/game/upgrade", json={"room": "spirit_vein"}).json()
    assert r["ok"] and r["game"]["rate"] > 0
    cands = client.post("/api/academy/game/recruit", json={}).json()["candidates"]
    r = client.post("/api/academy/game/recruit-pick", json={"candidate": cands[0]["id"]}).json()
    did = r["disciple"]["id"]
    r = client.post("/api/academy/game/assign", json={"disciple": did, "room": "tongues_west"}).json()
    assert r["ok"] and did in next(x for x in r["game"]["rooms"] if x["id"] == "tongues_west")["staff"]
    assert client.post("/api/academy/game/nonsense", json={}).status_code == 404
    # library + stats + learn-more
    u = client.get("/api/academy/unit", params={"course": "french-a1", "unit": "fr-01"}).json()
    assert u["notes"] and sum(1 for it in u["items"] if it["state"] != "new") == 8
    assert client.get("/api/academy/stats").json()["cards"] == 16
    assert client.post("/api/academy/learn-more", json={"course": "french-a1", "n": 5}).json()["extra"] == 5
    assert client.post("/api/academy/session", json={"course": "french-a1"}).json()["new"] == 5


def test_cert_trial_over_http_and_backup_roundtrip():
    client.post("/api/academy/setup", json={"name": "S", "master": "M", "courses": ["security-plus"]})
    info = client.get("/api/academy/trial", params={"course": "security-plus"}).json()
    assert info["ready"] and info["questions"] == 30
    t = client.post("/api/academy/trial/start", json={"course": "security-plus"}).json()
    doms = [packs.item_index()[q["item"]]["unit"][3] for q in t["questions"]]
    assert [doms.count(d) for d in "12345"] == [5, 7, 6, 8, 4]         # 16/24/19/27/14% of 30
    res = client.post("/api/academy/trial/submit", json={"trial": t["trial"], "answers": [_truth(q) for q in t["questions"]]}).json()
    assert res["passed"] and res["pct"] == 100 and len(res["domains"]) == 5
    blob = client.get("/api/academy/export").json()
    state.reset_for_tests()
    assert not client.get("/api/academy/overview").json()["onboarded"]
    assert client.post("/api/academy/import", json=blob).json()["ok"]
    assert client.get("/api/academy/overview").json()["game"]["name"] == "S"
    assert client.post("/api/academy/import", json={"nope": 1}).status_code == 400
    assert client.post("/api/academy/import", content=b"{not json").status_code == 400
    assert client.post("/api/academy/import", content=b" " * (state.MAX_IMPORT_BYTES + 1)).status_code == 413
    bad = client.post("/api/academy/import", json={"cards": {}, "days": [], "game": {"step": "x", "streak": "<img>"}})
    assert bad.status_code == 200 and isinstance(client.get("/api/academy/overview").json()["game"]["streak"], int)
    t = client.post("/api/academy/trial/start", json={"course": "security-plus"}).json()
    assert client.post("/api/academy/trial/abandon", json={"trial": t["trial"]}).json()["abandoned"]
    assert not client.post("/api/academy/trial/submit", json={"trial": t["trial"], "answers": []}).json()["ok"]


def test_viewers_can_look_but_not_study():
    op = client.post("/api/accounts", json={"name": "root", "role": "operator"}).json()["token"]
    vw = client.post("/api/accounts", json={"name": "val", "role": "viewer"}, headers={"x-control-token": op}).json()["token"]
    v = {"x-control-token": vw}
    assert client.get("/api/academy/overview").status_code == 401
    assert client.get("/api/academy/overview", headers=v).status_code == 200
    client.get("/api/academy/overview?tz=300", headers=v)        # a viewer's GET must not change settings
    assert state.get()["settings"]["tz_offset_min"] == 0
    client.get("/api/academy/overview?tz=300", headers={"x-control-token": op})
    assert state.get()["settings"]["tz_offset_min"] == 300
    assert client.post("/api/academy/session", json={}, headers=v).status_code == 403
    assert client.post("/api/academy/game/collect", json={}, headers=v).status_code == 403
    assert client.get("/api/academy/export", headers=v).status_code == 403
    assert client.post("/api/academy/setup", json={"name": "x", "courses": []}, headers={"x-control-token": op}).status_code == 200
