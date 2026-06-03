from maybot_control_center import incidents, agents


def setup_function():
    incidents.clear()


def _enable(monkeypatch):
    monkeypatch.setattr(incidents, "INCIDENT_AGENT", "Medic")
    monkeypatch.setattr(incidents, "STATES", {"error"})
    monkeypatch.setattr(agents, "_agent_def", lambda n: {"name": n} if n == "Medic" else None)


def test_disabled_without_agent(monkeypatch):
    monkeypatch.setattr(incidents, "INCIDENT_AGENT", "")
    calls = []
    monkeypatch.setattr(agents, "assign_task", lambda *a: calls.append(a))
    incidents.maybe_dispatch([{"device": "d", "name": "p", "health": "error"}])
    assert calls == []


def test_dispatches_once_per_incident(monkeypatch):
    _enable(monkeypatch)
    calls = []
    monkeypatch.setattr(agents, "assign_task", lambda name, task: calls.append((name, task)))
    proj = [{"device": "d", "name": "p", "health": "error", "status": "stopped", "type": "trading_bot", "alerts": ["ERROR: down"]}]
    incidents.maybe_dispatch(proj)
    incidents.maybe_dispatch(proj)  # still error → not re-dispatched
    assert len(calls) == 1
    assert calls[0][0] == "Medic" and "TRIBULATION" in calls[0][1] and "ERROR: down" in calls[0][1]


def test_redispatches_after_recovery(monkeypatch):
    _enable(monkeypatch)
    calls = []
    monkeypatch.setattr(agents, "assign_task", lambda name, task: calls.append(name))
    err = [{"device": "d", "name": "p", "health": "error"}]
    ok = [{"device": "d", "name": "p", "health": "ok"}]
    incidents.maybe_dispatch(err)
    incidents.maybe_dispatch(ok)   # recovered → clears
    incidents.maybe_dispatch(err)  # error again → re-dispatch
    assert len(calls) == 2


def test_ignores_healthy_projects(monkeypatch):
    _enable(monkeypatch)
    calls = []
    monkeypatch.setattr(agents, "assign_task", lambda *a: calls.append(a))
    incidents.maybe_dispatch([{"device": "d", "name": "p", "health": "warning"}])  # not in STATES
    assert calls == []
