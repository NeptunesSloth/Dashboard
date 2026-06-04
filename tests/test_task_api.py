"""Endpoint coverage for the task-assignment overhaul."""
from fastapi.testclient import TestClient

from maybot_control_center.app import app
from maybot_control_center import taskqueue, agents, routing, orchestrator

client = TestClient(app)


def setup_function():
    taskqueue.clear()


def test_board_endpoint():
    taskqueue.create("x")
    r = client.get("/api/tasks")
    assert r.status_code == 200 and r.json()["counts"]["queued"] == 1


def test_create_without_dispatch():
    r = client.post("/api/tasks", json={"title": "plan things", "dispatch": False, "priority": "high"})
    assert r.status_code == 200
    assert r.json()["status"] == "queued" and r.json()["priority"] == "high"


def test_create_requires_title():
    assert client.post("/api/tasks", json={"title": "  "}).status_code == 400


def test_set_status_endpoint():
    t = taskqueue.create("x")
    r = client.post(f"/api/tasks/{t['id']}/status", json={"status": "done", "result": "ok"})
    assert r.status_code == 200 and r.json()["status"] == "done"
    assert client.post(f"/api/tasks/{t['id']}/status", json={"status": "bogus"}).status_code == 400


def test_assign_goal_routes_and_enqueues(monkeypatch):
    monkeypatch.setattr(routing, "best_fit",
                        lambda goal: {"agent": "Nova", "reason": "stub", "ranked": []})
    monkeypatch.setattr(agents, "assign_task", lambda name, task: {"name": name})
    monkeypatch.setattr("maybot_control_center.governance.route_task", lambda n, critical: (n, None))
    r = client.post("/api/assign/goal", json={"goal": "refactor the api", "dispatch": True})
    assert r.status_code == 200
    body = r.json()
    assert body["routed_to"] == "Nova"
    assert body["task"]["status"] == "in_progress"


def test_assign_goal_409_when_no_one_eligible(monkeypatch):
    monkeypatch.setattr(routing, "best_fit", lambda goal: None)
    assert client.post("/api/assign/goal", json={"goal": "x"}).status_code == 409


def test_assign_preview(monkeypatch):
    monkeypatch.setattr(routing, "rank", lambda goal: [{"agent": "Nova", "score": 50.0}])
    r = client.get("/api/assign/preview?goal=do+stuff")
    assert r.status_code == 200 and r.json()["ranked"][0]["agent"] == "Nova"


def test_orchestrate_endpoint(monkeypatch):
    monkeypatch.setattr(orchestrator, "orchestrate",
                        lambda goal, mx, dispatch: {"parent": {"id": 1}, "subtasks": []})
    r = client.post("/api/orchestrate", json={"goal": "build a feature", "dispatch": False})
    assert r.status_code == 200 and r.json()["parent"]["id"] == 1


def test_orchestrate_requires_goal():
    assert client.post("/api/orchestrate", json={"goal": ""}).status_code == 400
