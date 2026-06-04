from maybot_control_center import orchestrator, taskqueue, routing


def setup_function():
    taskqueue.clear()


def test_heuristic_splits_on_connectives():
    subs = orchestrator._heuristic("build the page and then write tests, then deploy", 6)
    assert [s["title"] for s in subs] == ["build the page", "write tests", "deploy"]


def test_heuristic_single_when_atomic():
    subs = orchestrator._heuristic("ship it", 6)
    assert len(subs) == 1 and subs[0]["title"] == "ship it"


def test_decompose_uses_llm_when_available(monkeypatch):
    monkeypatch.setattr(orchestrator, "_plan_llm",
                        lambda goal, n: [{"title": "A", "description": "do a"},
                                         {"title": "B", "description": ""}])
    subs = orchestrator.decompose("anything")
    assert [s["title"] for s in subs] == ["A", "B"]


def test_decompose_falls_back_to_heuristic(monkeypatch):
    monkeypatch.setattr(orchestrator, "_plan_llm", lambda goal, n: None)
    subs = orchestrator.decompose("alpha and beta")
    assert [s["title"] for s in subs] == ["alpha", "beta"]


def test_orchestrate_creates_parent_and_routed_subtasks(monkeypatch):
    monkeypatch.setattr(orchestrator, "_plan_llm", lambda goal, n: None)  # heuristic
    monkeypatch.setattr(routing, "best_fit",
                        lambda text: {"agent": "Nova", "reason": "stub", "ranked": []})
    res = orchestrator.orchestrate("design the ui and write tests", dispatch=False)
    assert res["parent"]["source"] == "orchestrator"
    assert len(res["subtasks"]) == 2
    assert all(s["routed_to"] == "Nova" for s in res["subtasks"])
    # subtasks are linked to the parent on the board
    children = [t for t in taskqueue.list_tasks() if t["parent_id"] == res["parent"]["id"]]
    assert len(children) == 2


def test_orchestrate_requires_goal():
    import pytest
    with pytest.raises(ValueError):
        orchestrator.orchestrate("   ")
