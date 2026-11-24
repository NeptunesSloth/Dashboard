"""The HTTP surface, against the courses that actually ship."""
import pytest
from fastapi.testclient import TestClient

from sect_academy import engine, packs, state
from sect_academy.app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    monkeypatch.delenv("SECT_ACADEMY_TOKEN", raising=False)
    packs.load_all(force=True)
    state.reset_for_tests()
    yield
    state.reset_for_tests()


def _truth(ex):
    it = packs.item_index()[ex["item"]]
    if ex["mode"] in ("type_l2", "listen", "build_l2"):
        return it["l2"]
    if ex["mode"] == "cloze_type":
        return it["answer"]
    if ex["mode"] in engine.LIST_MODES:
        return engine.truth_list(it)
    return engine._truth(it, ex["mode"])


def test_shell_is_self_contained_and_offline():
    """Every page and asset is served locally, and nothing references another origin."""
    for path in ("/", "/study", "/library", "/trials", "/progress"):
        r = client.get(path)
        assert r.status_code == 200 and "Sect Academy" in r.text
        assert "default-src 'self'" in r.headers["content-security-policy"]
    for asset in ("/academy.js", "/sect.js", "/art.js", "/academy.css", "/sw.js", "/manifest.webmanifest", "/icon.svg"):
        r = client.get(asset)
        assert r.status_code == 200, asset
        body = r.text.replace("http://www.w3.org/", "")           # the SVG namespace is a name, not a request
        assert "http://" not in body and "https://" not in body and "//fonts." not in body, asset
    assert client.get("/healthz").json()["courses"] >= 7
    assert client.get("/api/overview").headers["cache-control"] == "no-store"
    assert client.get("/command").status_code == 404              # the old dashboard is gone


def test_courses_are_complete_and_every_item_can_be_asked():
    all_packs = packs.load_all()
    assert {"french-a1", "french-a2", "spanish-a1", "spanish-a2", "security-plus", "network-plus", "isc2-cc"} <= set(all_packs)
    for pid, n_units in (("french-a1", 20), ("spanish-a1", 20), ("french-a2", 12), ("spanish-a2", 12)):
        assert len(all_packs[pid]["units"]) == n_units
    for pid in ("security-plus", "network-plus", "isc2-cc"):
        p = all_packs[pid]
        pool = engine._test_pool(p)
        # a full-length mock can be drawn many times over without repeating itself
        assert sum(len(v) for v in pool.values()) >= 2.5 * p["exam"]["full"]["questions"], pid
        assert set(pool) == {str(d["id"]) for d in p["exam"]["domains"]}
        kinds = {it["type"] for u in p["units"] for it in u["items"]}
        assert kinds == {"concept", "mcq", "multi", "order"}, pid
        assert p["exam"]["pass_pct"] >= 85
    for p in all_packs.values():
        for u in p["units"]:
            for it in u["items"]:
                for mode in sorted(engine._MODES[it["type"]]):
                    ex = engine.build_exercise(it, mode, p, 1)
                    if "choices" in ex:
                        assert len(set(ex["choices"])) == len(ex["choices"]) >= 4, (it["id"], mode)
                    assert engine.check(it, mode, _truth(ex))["correct"], (it["id"], mode)


def test_first_day_placement_study_and_the_sect():
    assert not client.get("/api/overview?tz=60").json()["onboarded"]
    ov = client.post("/api/setup", json={"name": "Azure Lantern", "master": "Jay", "courses": ["french-a1", "isc2-cc"],
                                         "storyteller": "calm"}).json()
    assert ov["onboarded"] and ov["sect"]["name"] == "Azure Lantern" and ov["sect"]["storyteller"] == "calm"
    assert len(ov["sect"]["pawns"]) == 3 and ov["settings"]["tz_offset_min"] == 60
    # placement: knows unit one, not unit two
    p = client.post("/api/placement/start", json={"course": "french-a1"}).json()
    r = client.post("/api/placement/answer", json={"placement": p["placement"], "answers": [_truth(q) for q in p["questions"]]}).json()
    assert r["passed_unit"] and not r["done"]
    for _ in range(2):
        r = client.post("/api/placement/answer", json={"placement": p["placement"], "answers": ["zzz"] * 3}).json()
    assert r["done"] and r["passed_units"] == 1 and r["placed"] >= 20 and r["start_at"]
    # a session: only issued items, once each
    s = client.post("/api/session", json={"course": "french-a1"}).json()
    assert s["ok"] and s["new"] == 8 and {e["unit"] for e in s["exercises"]} == {"fr-02"}
    n = 0
    for ex in s["exercises"]:
        if ex["mode"] == "intro":
            continue
        r = client.post("/api/answer", json={"session": s["session"], "item": ex["item"], "mode": ex["mode"], "answer": _truth(ex)}).json()
        assert r["correct"] and r["rewards"]["qi"] > 0 and r["rewards"]["insight"] == 1
        n += 1
    assert client.post("/api/answer", json={"item": "fr-01-bonjour", "mode": "choose_l1", "answer": "x"}).status_code == 422
    fin = client.post("/api/session/finish", json={"session": s["session"], "secs": 300}).json()
    assert fin["counted"] and fin["streak"] == 1
    assert client.post("/api/session/finish", json={"session": s["session"], "secs": 1}).json()["already"]
    ov = client.get("/api/overview").json()
    assert ov["sect"]["insight"] == n and ov["sect"]["studied_today"]
    assert any(t["label"].startswith("The Master lectured") for t in ov["sect"]["pawns"][1]["thoughts"])
    # the sect: orders, time, research
    pawn = ov["sect"]["pawns"][1]["id"]
    assert client.post("/api/sect/priority", json={"pawn": pawn, "job": "wood", "level": 1}).json()["ok"]
    assert client.post("/api/sect/research", json={"tech": "irrigation"}).json()["ok"]
    r = client.post("/api/sect/tick", json={"hours": 5}).json()
    assert r["ok"] and r["hours"] >= 1 and r["sect"]["hour"] > ov["sect"]["hour"]
    assert client.post("/api/sect/build", json={"room": "nonsense"}).json()["ok"] is False
    assert client.post("/api/sect/nonsense", json={}).status_code == 404
    assert client.get("/api/stats").json()["cards"] >= 28


def test_full_length_mock_backup_and_token():
    client.post("/api/setup", json={"name": "S", "master": "M", "courses": ["security-plus"]})
    info = client.get("/api/trial", params={"course": "security-plus"}).json()
    assert info["ready"] and info["full"] == {"questions": 90, "minutes": 90} and not info["readiness"]["ready"]
    t = client.post("/api/trial/start", json={"course": "security-plus", "full": True}).json()
    assert len(t["questions"]) == 90 and {q["mode"] for q in t["questions"]} <= {"mcq", "multi", "order"}
    doms = [packs.item_index()[q["item"]]["unit"][3] for q in t["questions"]]
    assert [doms.count(d) for d in "12345"] == [14, 22, 17, 24, 13]             # 16/24/19/27/14% of 90
    res = client.post("/api/trial/submit", json={"trial": t["trial"], "answers": [_truth(q) for q in t["questions"]]}).json()
    assert res["passed"] and res["pct"] == 100 and res["full"]
    t = client.post("/api/trial/start", json={"course": "security-plus"}).json()
    assert client.post("/api/trial/abandon", json={"trial": t["trial"]}).json()["abandoned"]
    blob = client.get("/api/export").json()
    state.reset_for_tests()
    assert not client.get("/api/overview").json()["onboarded"]
    assert client.post("/api/import", json=blob).json()["ok"]
    assert client.get("/api/overview").json()["sect"]["name"] == "S"
    assert client.post("/api/import", json={"nope": 1}).status_code == 400
    assert client.post("/api/import", content=b"{not json").status_code == 400
    assert client.post("/api/import", content=b" " * (state.MAX_IMPORT_BYTES + 1)).status_code == 413
    bad = client.post("/api/import", json={"cards": {}, "days": [], "colony": {"hour": "x", "streak": "<img>"}})
    assert bad.status_code == 200 and not client.get("/api/overview").json()["onboarded"]   # the sect restarts; nothing crashes


def test_optional_token(monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_TOKEN", "s3cret")
    assert client.get("/").status_code == 200                                    # the shell itself is public
    assert client.get("/api/overview").status_code == 401
    assert client.post("/api/sect/tick", json={"hours": 1}).status_code == 401
    assert client.get("/api/overview", headers={"x-academy-token": "s3cret"}).status_code == 200


def test_a_conversation_is_rehearsed_line_by_line_and_graded_as_a_whole():
    it = next(i for i in packs.item_index().values() if i["type"] == "dialogue")
    mine = engine.my_lines(it)
    ex = engine.build_exercise(it, "dialogue_build", packs.get(it["pack"]), 1)
    assert [ln["index"] for ln in ex["lines"] if ln["mine"]] == mine
    for ln in ex["lines"]:
        if ln["mine"]:
            assert "l2" not in ln and set(engine._tiles(it["lines"][ln["index"]]["l2"])) <= set(ln["bank"])   # the answer is never sent
            assert not any(w in ".,!?" for w in ln["bank"])
        else:
            assert ln["l2"] == it["lines"][ln["index"]]["l2"]
    good = client.post("/api/line", json={"item": it["id"], "index": mine[0], "answer": it["lines"][mine[0]]["l2"]}).json()
    assert good["correct"] and good["expected"]
    assert not client.post("/api/line", json={"item": it["id"], "index": mine[0], "answer": "zzz"}).json()["correct"]
    partner = next(i for i in range(len(it["lines"])) if i not in mine)
    assert client.post("/api/line", json={"item": it["id"], "index": partner, "answer": "x"}).status_code == 400
    assert client.post("/api/line", json={"item": "nope", "index": 0, "answer": "x"}).status_code == 404
    truth = engine.truth_list(it)
    assert engine.check(it, "dialogue_type", truth)["correct"] and engine.check(it, "dialogue_type", truth)["flag"] is None
    assert not engine.check(it, "dialogue_type", ["zzz"] * len(truth))["correct"]
    one_off = [truth[0]] + ["zzz"] * (len(truth) - 1)
    assert not engine.check(it, "dialogue_type", one_off)["correct"] or len(truth) <= 1
    assert engine.check(it, f"line:{mine[-1]}", truth[-1])["correct"]


def test_best_answer_questions_explain_every_option():
    best = [i for i in packs.item_index().values() if i.get("best")]
    assert len(best) >= 250 and {i["pack"] for i in best} == {"security-plus", "network-plus", "isc2-cc"}
    it = best[0]
    ex = engine.build_exercise(it, "mcq", packs.get(it["pack"]), 3)
    assert ex["best"] and "BEST" in ex["ask"] and "whys" not in ex and sorted(ex["choices"]) == sorted(it["choices"])
    whys = engine._explain(it)["whys"]
    assert set(whys) == set(it["choices"]) and all(len(w) > 10 for w in whys.values())


def test_another_site_cannot_write_and_import_needs_json():
    blob = client.get("/api/export").json()
    assert client.post("/api/import", content=b'{"cards":{}}', headers={"content-type": "text/plain"}).status_code == 400
    assert client.post("/api/import", json=blob, headers={"origin": "http://evil.example"}).status_code == 403
    assert client.post("/api/sect/tick", json={"hours": 1}, headers={"sec-fetch-site": "cross-site"}).status_code == 403
    assert client.post("/api/import", json=blob, headers={"origin": "http://testserver", "sec-fetch-site": "same-origin"}).json()["ok"]


def test_list_answers_come_back_with_the_key_and_choices_are_graded_exactly():
    client.post("/api/setup", json={"name": "S", "master": "M", "courses": ["network-plus"]})
    it = next(i for i in packs.item_index().values() if i["type"] == "multi")
    assert engine.check(it, "multi", engine.truth_list(it))["expected_list"] == engine.truth_list(it)
    v6 = packs.item_index()["np-3-q09"]
    key = v6["choices"][v6["answer"]]
    assert engine.check(v6, "mcq", key)["correct"]
    assert all(not engine.check(v6, "mcq", c)["correct"] for c in v6["choices"] if c != key)


def test_a_cloze_blank_forgives_no_slip_in_the_grammar():
    assert engine.check_typed("hablas", ["hables"])["correct"]                       # a typo, in free typing
    assert not engine.check_typed("hablas", ["hables"], slips=False)["correct"]      # the mood itself, in a blank
    assert not engine.check_typed("hablo", ["habló"], slips=False)["correct"]
    assert engine.check_typed("etudiant", ["étudiant"], slips=False)["flag"] == "accent"


def test_the_paintings_are_served_from_a_fixed_list():
    assert client.get("/art/hq.webp").headers["content-type"] == "image/webp"
    assert client.get("/art/nope.webp").status_code == 404 and client.get("/art/..%2Fapp.py").status_code == 404
