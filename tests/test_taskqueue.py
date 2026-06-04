from maybot_control_center import taskqueue


def setup_function():
    taskqueue.clear()


def test_create_defaults_to_queued():
    t = taskqueue.create("do a thing")
    assert t["status"] == "queued" and t["priority"] == "normal" and t["assignee"] is None


def test_create_with_assignee_is_assigned():
    t = taskqueue.create("do a thing", assignee="Nova")
    assert t["status"] == "assigned" and t["assignee"] == "Nova"


def test_board_counts_and_priority_order():
    taskqueue.create("low one", priority="low")
    taskqueue.create("urgent one", priority="urgent")
    taskqueue.create("normal one")
    board = taskqueue.board()
    assert board["counts"]["queued"] == 3
    # active queued sorted by priority desc → urgent first
    assert board["columns"]["queued"][0]["title"] == "urgent one"


def test_reassign_and_status():
    t = taskqueue.create("x")
    taskqueue.reassign(t["id"], "Forge")
    assert taskqueue.get(t["id"])["assignee"] == "Forge"
    taskqueue.set_status(t["id"], "done", result="shipped")
    g = taskqueue.get(t["id"])
    assert g["status"] == "done" and g["result"] == "shipped"


def test_active_count_excludes_finished():
    taskqueue.create("a", assignee="Nova")
    t2 = taskqueue.create("b", assignee="Nova")
    assert taskqueue.active_count("Nova") == 2
    taskqueue.set_status(t2["id"], "done")
    assert taskqueue.active_count("Nova") == 1


def test_dispatch_lifecycle():
    t = taskqueue.create("work", assignee="Nova")
    taskqueue.link_dispatch(t["id"], "Nova")
    assert taskqueue.get(t["id"])["status"] == "in_progress"
    taskqueue.on_agent_finished("Nova", ok=True, reply="all good")
    g = taskqueue.get(t["id"])
    assert g["status"] == "done" and "all good" in g["result"]


def test_on_finished_failure():
    t = taskqueue.create("work", assignee="Nova")
    taskqueue.link_dispatch(t["id"], "Nova")
    taskqueue.on_agent_finished("Nova", ok=False, reply="boom")
    assert taskqueue.get(t["id"])["status"] == "failed"


def test_cancel():
    t = taskqueue.create("x")
    taskqueue.cancel(t["id"])
    assert taskqueue.get(t["id"])["status"] == "cancelled"
