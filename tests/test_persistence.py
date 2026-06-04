"""State (task board / oaths / silences / autopilot) survives a restart via the store."""
from maybot_control_center import store, taskqueue, oaths, maintenance, autopilot


def setup_function():
    store._reset_for_tests(":memory:")
    store.init()


def teardown_function():
    store._reset_for_tests("")  # disable persistence again for other tests


def test_taskqueue_roundtrip():
    taskqueue.clear()
    t = taskqueue.create("persist me", priority="high", assignee="Nova")
    # simulate a restart: wipe in-memory, reload from the store
    taskqueue._tasks.clear()
    taskqueue._current_by_agent.clear()
    taskqueue.load_persisted()
    got = taskqueue.get(t["id"])
    assert got and got["title"] == "persist me" and got["assignee"] == "Nova"


def test_oaths_roundtrip():
    oaths.clear()
    oaths.claim("d:bot", "Nova", "on it")
    oaths._oaths.clear()
    oaths.load_persisted()
    assert oaths.is_claimed("d", "bot") and oaths.owner("d", "bot") == "Nova"


def test_maintenance_roundtrip():
    maintenance.clear()
    maintenance.silence("d:bot", minutes=60, reason="upkeep")
    maintenance._silences.clear()
    maintenance.load_persisted()
    assert maintenance.is_silenced("d", "bot")


def test_autopilot_roundtrip():
    autopilot.clear()
    autopilot.set_paused(True)              # triggers a save
    autopilot._paused = False               # local change as if restarted
    autopilot._incidents.clear()
    autopilot.load_persisted()
    assert autopilot.status()["paused"] is True


def test_noop_without_db():
    store._reset_for_tests("")              # persistence off
    taskqueue.clear()
    taskqueue.create("ephemeral")
    taskqueue._tasks.clear()
    taskqueue.load_persisted()             # nothing to load
    assert taskqueue.list_tasks() == []
