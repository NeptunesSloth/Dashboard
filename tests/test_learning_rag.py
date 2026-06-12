"""Bring-your-own material (RAG): attach notes to a track and have lessons,
quizzes, and exams grounded in them."""
import pytest

from maybot_control_center import learning


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    learning._state.clear()
    learning._state.update(learning._blank())
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Tutor"})
    yield


MATERIAL = "ACME runbook: rotate API keys every 30 days. The SOC triages in Splunk. Escalate sev1 to on-call."


def test_set_get_clear_material():
    assert learning.set_material("cybersecurity", MATERIAL, "ACME runbook")["ok"] is True
    g = learning.get_material("cybersecurity")
    assert g["present"] is True and g["name"] == "ACME runbook" and g["chars"] == len(MATERIAL)
    # surfaced on the track listing
    track = next(t for t in learning.list_tracks()["tracks"] if t["id"] == "cybersecurity")
    assert track["material"] == "ACME runbook"
    assert learning.clear_material("cybersecurity")["ok"] is True
    assert learning.get_material("cybersecurity")["present"] is False


def test_set_material_validates():
    assert "unknown track" in learning.set_material("nope", MATERIAL)["error"]
    assert "no material" in learning.set_material("cybersecurity", "   ")["error"]


def test_material_truncated_to_cap(monkeypatch):
    monkeypatch.setattr(learning, "MATERIAL_CAP", 50)
    res = learning.set_material("cybersecurity", "x" * 500)
    assert res["truncated"] is True and res["chars"] == 50


def test_material_grounds_lessons():
    learning.set_material("cybersecurity", MATERIAL)
    seen = {}

    def spy(member, messages):
        seen.setdefault("user", messages[1]["content"])
        return True, "lesson", None

    learning.get_lesson("cybersecurity", "Incident Response", chat=spy)
    assert "GROUND YOUR TEACHING" in seen["user"] and "Splunk" in seen["user"]


def test_material_grounds_quizzes():
    learning.set_material("cybersecurity", MATERIAL)
    seen = {}

    def spy(member, messages):
        seen.setdefault("user", messages[1]["content"])
        return True, '{"questions":[{"q":"Q","choices":["a","b"],"answer":0,"explanation":"x"}]}', None

    learning.generate_quiz("cybersecurity", "Incident Response", chat=spy)
    assert "ACME runbook" in seen["user"]


def test_no_material_no_grounding():
    seen = {}

    def spy(member, messages):
        seen.setdefault("user", messages[1]["content"])
        return True, "lesson", None

    learning.get_lesson("cybersecurity", "Incident Response", chat=spy)
    assert "GROUND YOUR TEACHING" not in seen["user"]
