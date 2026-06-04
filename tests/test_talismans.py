from maybot_control_center import talismans, history


class FakeResp:
    def __init__(self, status):
        self.status_code = status


def setup_function():
    talismans.clear()
    history.clear()


def test_probe_ok_records_history(monkeypatch):
    monkeypatch.setattr(talismans.requests, "get", lambda url, timeout: FakeResp(200))
    r = talismans.probe({"name": "site", "url": "http://x", "expect_status": 200})
    assert r["health"] == "ok" and r["status_code"] == 200
    assert history.get(talismans.DEVICE, "site")[-1]["health"] == "ok"


def test_probe_wrong_status_is_error(monkeypatch):
    monkeypatch.setattr(talismans.requests, "get", lambda url, timeout: FakeResp(500))
    r = talismans.probe({"name": "site", "url": "http://x", "expect_status": 200})
    assert r["health"] == "error" and r["status_code"] == 500


def test_probe_exception_is_error(monkeypatch):
    def boom(url, timeout):
        raise RuntimeError("conn refused")
    monkeypatch.setattr(talismans.requests, "get", boom)
    r = talismans.probe({"name": "site", "url": "http://x"})
    assert r["health"] == "error" and "conn refused" in r["error"]


def test_tick_respects_interval(monkeypatch, tmp_path):
    f = tmp_path / "talismans.yaml"
    f.write_text("talismans:\n  - {name: site, url: 'http://x', every_seconds: 60}\n", encoding="utf-8")
    monkeypatch.setattr(talismans, "TALISMANS_FILE", f)
    monkeypatch.setattr(talismans.requests, "get", lambda url, timeout: FakeResp(200))
    assert talismans.tick(now=1000) == ["site"]      # first probe
    assert talismans.tick(now=1030) == []            # within interval
    assert talismans.tick(now=1070) == ["site"]      # interval elapsed


def test_idle_without_file(monkeypatch, tmp_path):
    monkeypatch.setattr(talismans, "TALISMANS_FILE", tmp_path / "none.yaml")
    assert talismans.load_talismans() == []
    assert talismans.tick() == []
    assert talismans.start() is False
