"""Domain-aware health for the game_server / school / ai_project / website adapters."""
from maybot_agent.adapters import game_server, school, ai_project, website


class _Resp:
    def __init__(self, status=200, text="", json_data=None, ctype="application/json"):
        self.status_code = status
        self.text = text
        self._json = json_data or {}
        self.headers = {"content-type": ctype}

    def json(self):
        return self._json


# ---- game_server ----
def test_game_server_full_and_low_tps(monkeypatch):
    monkeypatch.setattr(game_server, "_fetch_status",
                        lambda url: (True, {"players": 20, "max_players": 20, "map": "arena", "tps": 8}, 9.0, None))
    out = game_server.adapt({"name": "g", "type": "game_server", "query_url": "http://x/status"})
    m = out["metrics"]
    assert m["players"] == 20 and m["map"] == "arena"
    assert out["health"] == "warning"
    assert any("full" in a for a in out["alerts"])
    assert any("tick rate" in a for a in out["alerts"])


def test_game_server_query_failure_is_error(monkeypatch):
    monkeypatch.setattr(game_server, "_fetch_status", lambda url: (False, {}, "unknown", "boom"))
    out = game_server.adapt({"name": "g", "type": "game_server", "query_url": "http://x"})
    assert out["health"] == "error"
    assert out["metrics"]["online"] is False


def test_game_server_tcp_probe(monkeypatch):
    monkeypatch.setattr(game_server, "_tcp_open", lambda host, port: False)
    out = game_server.adapt({"name": "g", "type": "game_server", "host": "h", "port": 25565})
    assert out["metrics"]["online"] is False and out["health"] == "error"


def test_game_server_static_fallback():
    out = game_server.adapt({"name": "g", "type": "game_server", "metrics": {"players": 3, "max_players": 64}})
    assert out["metrics"]["players"] == 3 and out["health"] == "ok"


# ---- school ----
def test_school_overdue_and_low_pass(monkeypatch):
    monkeypatch.setattr(school, "_fetch",
                        lambda url: (True, {"students": 30, "courses": 4, "overdue": 5, "pass_rate": 0.4, "attendance": 90}, None))
    out = school.adapt({"name": "s", "type": "school", "query_url": "http://x"})
    m = out["metrics"]
    assert m["students"] == 30 and m["pass_rate_pct"] == 40.0  # 0.4 normalised to %
    assert out["health"] == "warning"
    assert any("overdue" in a for a in out["alerts"])
    assert any("pass rate" in a for a in out["alerts"])


def test_school_healthy(monkeypatch):
    monkeypatch.setattr(school, "_fetch",
                        lambda url: (True, {"students": 10, "overdue": 0, "pass_rate": 95, "attendance": 99}, None))
    out = school.adapt({"name": "s", "type": "school", "query_url": "http://x"})
    assert out["health"] == "ok" and out["alerts"] == []


# ---- ai_project ----
def test_ai_project_log_oom(monkeypatch, tmp_path):
    log = tmp_path / "train.log"
    log.write_text("epoch 1 ok\nRuntimeError: CUDA out of memory\n")
    monkeypatch.setattr(ai_project, "_fetch", lambda url: (True, {"phase": "training", "loss": 0.2}, None))
    out = ai_project.adapt({"name": "a", "type": "ai_project", "query_url": "http://x", "log_file": str(log)})
    assert out["metrics"]["phase"] == "training"
    assert out["health"] == "error"
    assert any("CUDA out of memory" in a for a in out["alerts"])


def test_ai_project_static_only():
    out = ai_project.adapt({"name": "a", "type": "ai_project", "metrics": {"model": "resnet", "phase": "serving"}})
    assert out["metrics"]["model"] == "resnet" and out["health"] == "ok"


# ---- website (cert + content) ----
def test_website_content_assertion_fails(monkeypatch):
    monkeypatch.setattr(website.requests, "get",
                        lambda url, timeout=5: _Resp(200, text="<html>oops</html>", ctype="text/html"))
    out = website.adapt({"name": "w", "type": "website", "health_url": "http://x/", "expect_text": "Welcome"})
    assert out["health"] == "error"
    assert out["metrics"]["content_ok"] is False


def test_website_cert_expiring_soon(monkeypatch):
    monkeypatch.setattr(website.requests, "get",
                        lambda url, timeout=5: _Resp(200, text="ok", ctype="text/plain"))
    monkeypatch.setattr(website, "_cert_days_left", lambda host, port=443: (3.0, None))
    out = website.adapt({"name": "w", "type": "website", "health_url": "https://x/", "expect_text": "ok"})
    assert out["metrics"]["cert_days_left"] == 3.0
    assert out["health"] == "error"
    assert any("certificate expires" in a for a in out["alerts"])


def test_website_cert_warn_window(monkeypatch):
    monkeypatch.setattr(website.requests, "get",
                        lambda url, timeout=5: _Resp(200, text="ok", ctype="text/plain"))
    monkeypatch.setattr(website, "_cert_days_left", lambda host, port=443: (15.0, None))
    out = website.adapt({"name": "w", "type": "website", "health_url": "https://x/"})
    assert out["health"] == "warning"
    assert any("certificate expires in 15.0" in a for a in out["alerts"])
