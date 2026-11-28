"""The sect is optional: study only, toggling it, and nothing in the sect ever blocking study."""
import time

import pytest
from fastapi.testclient import TestClient

from sect_academy import colony, engine, packs, state
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


def _study(course="isc2-cc"):
    s = client.post("/api/session", json={"course": course}).json()
    assert s["ok"] and s["exercises"]
    out = []
    for ex in s["exercises"]:
        if ex["mode"] == "intro":
            continue
        r = client.post("/api/answer", json={"session": s["session"], "item": ex["item"], "mode": ex["mode"], "answer": _truth(ex)})
        assert r.status_code == 200
        out.append(r.json())
    fin = client.post("/api/session/finish", json={"session": s["session"], "secs": 120}).json()
    return out, fin


def test_existing_saves_and_new_ones_default_to_the_sect_on():
    assert state.blank_settings()["sect_enabled"] is True
    old = state.clean_settings({"courses": ["isc2-cc"], "new_per_day": 8})        # a save from before the setting
    assert old["sect_enabled"] is True and old["sect_name"] == ""
    assert state.clean_settings({"sect_enabled": "no", "sect_name": 5})["sect_enabled"] is True
    assert state.clean_settings({"sect_enabled": False, "sect_name": "x" * 99})["sect_name"] == "x" * 40
    assert not client.get("/api/overview").json()["onboarded"]                     # a fresh install still founds a sect
    ov = client.post("/api/setup", json={"name": "Azure Lantern", "courses": ["isc2-cc"]}).json()
    assert ov["settings"]["sect_enabled"] is True and ov["sect"]["founded"]
    # changing other settings keeps it
    assert client.put("/api/settings", json={"new_per_day": 5}).json()["sect_enabled"] is True


def test_setup_study_only_founds_nothing_and_needs_no_name():
    ov = client.post("/api/setup", json={"courses": ["isc2-cc"], "study_only": True}).json()
    assert ov["onboarded"] and ov["settings"]["sect_enabled"] is False
    assert not ov["sect"]["founded"] and ov["sect"]["pawns"] == []
    assert ov["settings"]["sect_name"] == "Nameless Sect"                        # a name kept for later
    ov = client.post("/api/setup", json={"name": "Frost Lotus Valley", "master": "Jay", "courses": [], "study_only": True}).json()
    assert ov["settings"]["sect_name"] == "Frost Lotus Valley" and ov["settings"]["sect_master"] == "Jay"
    assert client.get("/api/overview").json()["onboarded"]


def test_study_only_records_everything_and_pays_the_sect_nothing():
    client.post("/api/setup", json={"courses": ["isc2-cc"], "study_only": True})
    answers, fin = _study()
    assert answers and all(a["correct"] and a["rewards"]["qi"] == 0 and a["rewards"]["insight"] == 0 for a in answers)
    assert fin["counted"] and fin["streak"] == 1 and not fin["events"]                   # the streak is study's own
    ov = client.get("/api/overview").json()
    assert ov["today"]["answers"] == len(answers) and ov["sect"]["insight"] == 0 and not ov["events"]
    assert client.get("/api/stats").json()["cards"] == len(answers)
    # the sect takes no orders while it is off; holiday mode still works
    assert client.post("/api/sect/tick", json={"hours": 5}).status_code == 409
    assert client.post("/api/sect/research", json={"tech": "irrigation"}).status_code == 409
    assert client.post("/api/sect/seclusion", json={"on": True}).json()["seclusion"] is True
    assert client.post("/api/sect/seclusion", json={"on": False}).json()["seclusion"] is False


def test_the_sim_does_not_advance_while_off_and_enabling_skips_the_paused_time():
    client.post("/api/setup", json={"name": "Azure Lantern", "courses": ["isc2-cc"]})
    st = state.get()
    hour = st["colony"]["hour"]
    assert client.post("/api/sect-mode", json={"on": False}).json() == {"ok": True, "sect_enabled": False, "founded": True}
    # a week away while paused: no catch-up, not now and not when it is turned back on
    st["colony"]["last_real"] = time.time() - 7 * 86400
    ov = client.get("/api/overview").json()
    assert st["colony"]["hour"] == hour and not ov["events"] and ov["settings"]["sect_enabled"] is False
    _study()
    assert st["colony"]["hour"] == hour and st["colony"]["insight"] == 0
    st["colony"]["last_real"] = time.time() - 7 * 86400
    r = client.post("/api/sect-mode", json={"on": True}).json()
    assert r["ok"] and r["sect_enabled"] and r["founded"]
    ov = client.get("/api/overview").json()
    assert st["colony"]["hour"] == hour and not ov["events"] and ov["sect"]["name"] == "Azure Lantern"
    assert len(ov["sect"]["pawns"]) == 3                                               # nothing was deleted
    assert client.post("/api/sect/tick", json={"hours": 2}).json()["ok"]


def test_turning_it_on_founds_a_sect_that_never_was():
    client.post("/api/setup", json={"name": "Frost Lotus Valley", "courses": ["isc2-cc"], "study_only": True})
    state.get()["colony"]["last_real"] = time.time() - 30 * 86400
    r = client.post("/api/sect-mode", json={"on": True}).json()
    assert r["founded"] and r["sect_enabled"]
    ov = client.get("/api/overview").json()
    assert ov["sect"]["name"] == "Frost Lotus Valley" and len(ov["sect"]["pawns"]) == 3
    assert ov["sect"]["day"] == 1                                                      # starts fresh, no month of catch-up
    # or with a name given there and then
    state.reset_for_tests()
    client.post("/api/setup", json={"courses": [], "study_only": True})
    client.post("/api/sect-mode", json={"on": True, "name": "Nine Bell Abode", "master": "Jay"})
    ov = client.get("/api/overview").json()
    assert ov["sect"]["name"] == "Nine Bell Abode" and ov["sect"]["master"] == "Jay"


def test_nothing_in_the_sect_blocks_study():
    """A pending event, sealed gates or a paused sect never stop a session, an answer or a trial."""
    for mode in ("on", "off"):
        state.reset_for_tests()
        client.post("/api/setup", json={"name": "Azure Lantern", "courses": ["isc2-cc"], "study_only": mode == "off"})
        st = state.get()
        c = colony._c(st, time.time())
        c["pending"] = {"kind": "x", "title": "A stranger at the gate", "text": "?", "options": [{"id": "a", "label": "Let them in"}]}
        c["seclusion"] = True
        answers, fin = _study()
        assert answers and all(a["correct"] for a in answers) and fin["counted"], mode
        t = client.post("/api/trial/start", json={"course": "isc2-cc"}).json()
        assert t["ok"], mode
        assert client.post("/api/trial/submit", json={"trial": t["trial"], "answers": []}).json()["ok"], mode


def test_import_keeps_the_choice():
    client.post("/api/setup", json={"courses": ["isc2-cc"], "study_only": True})
    blob = client.get("/api/export").json()
    state.reset_for_tests()
    assert client.post("/api/import", json=blob).json()["ok"]
    assert client.get("/api/overview").json()["settings"]["sect_enabled"] is False
