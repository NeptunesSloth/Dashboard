from maybot_control_center import metrics, scheduler, notifier, cultivation, agents


# ---- Prometheus metrics ----
def test_metrics_render_has_core_series():
    cultivation.clear()
    cultivation.on_task("Nova", True)
    out = metrics.render()
    assert "# TYPE maybot_treasury_balance gauge" in out
    assert "maybot_treasury_balance" in out
    assert 'maybot_agent_realm{agent="Nova"}' in out
    assert "maybot_llm_calls_total" in out
    assert out.endswith("\n")


# ---- scheduler ----
def test_scheduler_fires_after_interval(monkeypatch, tmp_path):
    f = tmp_path / "schedules.yaml"
    f.write_text("schedules:\n  - {name: nightly, every_minutes: 60, action: task, agent: Nova, task: hi}\n", encoding="utf-8")
    monkeypatch.setattr(scheduler, "SCHEDULES_FILE", f)
    scheduler.clear()
    runs = []
    monkeypatch.setattr(agents, "assign_task", lambda a, t: runs.append((a, t)))

    assert scheduler.tick(now=1000) == []              # first sight: register, don't fire
    assert runs == []
    assert scheduler.tick(now=1000 + 59 * 60) == []    # within the interval
    assert "nightly" in scheduler.tick(now=1000 + 61 * 60)  # past the interval → fire
    assert runs and runs[0] == ("Nova", "hi")


def test_scheduler_idle_without_file(monkeypatch, tmp_path):
    monkeypatch.setattr(scheduler, "SCHEDULES_FILE", tmp_path / "none.yaml")
    assert scheduler.load_schedules() == []
    assert scheduler.tick() == []
    assert scheduler.start() is False


# ---- alert routing ----
class _ImmediateThread:
    def __init__(self, target=None, args=(), daemon=None):
        self._t, self._a = target, args

    def start(self):
        self._t(*self._a)


def test_notify_event_routes_only_subscribed(monkeypatch):
    monkeypatch.setattr(notifier, "ALERT_EVENTS", {"incident"})
    monkeypatch.setattr(notifier, "GENERIC_WEBHOOK", "http://hook")
    monkeypatch.setattr(notifier, "DISCORD_WEBHOOK", "")
    monkeypatch.setattr(notifier, "SLACK_WEBHOOK", "")
    monkeypatch.setattr(notifier.threading, "Thread", _ImmediateThread)
    posted = []
    monkeypatch.setattr(notifier, "_post", lambda url, payload: posted.append((url, payload)))

    notifier.notify_event("incident", "T", "M")
    assert posted and posted[0][0] == "http://hook" and posted[0][1]["event"] == "incident"

    posted.clear()
    notifier.notify_event("tribulation", "T", "M")  # not subscribed
    assert posted == []
