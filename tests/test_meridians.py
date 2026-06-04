from maybot_control_center import meridians


def _write(tmp_path, monkeypatch, text):
    f = tmp_path / "meridians.yaml"
    f.write_text(text, encoding="utf-8")
    monkeypatch.setattr(meridians, "MERIDIANS_FILE", f)


def test_no_file_no_deps(tmp_path, monkeypatch):
    monkeypatch.setattr(meridians, "MERIDIANS_FILE", tmp_path / "none.yaml")
    assert meridians.load_map() == {}
    assert meridians.blocked_upstreams("d:a", {"d:b": "error"}) == []


def test_blocked_upstreams(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch,
           "meridians:\n  - project: d:web\n    depends_on: [d:api, d:db]\n")
    health = {"d:web": "error", "d:api": "error", "d:db": "ok"}
    assert meridians.blocked_upstreams("d:web", health) == ["d:api"]
    health["d:db"] = "warning"
    assert set(meridians.blocked_upstreams("d:web", health)) == {"d:api", "d:db"}


def test_annotate_tags_downstream(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, "meridians:\n  - project: d:web\n    depends_on: [d:api]\n")
    p = {"device": "d", "name": "web", "health": "error"}
    meridians.annotate(p, {"d:web": "error", "d:api": "error"})
    assert p["blocked_by"] == ["d:api"]


def test_annotate_skips_when_upstream_healthy(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, "meridians:\n  - project: d:web\n    depends_on: [d:api]\n")
    p = {"device": "d", "name": "web", "health": "error"}
    meridians.annotate(p, {"d:web": "error", "d:api": "ok"})
    assert "blocked_by" not in p
