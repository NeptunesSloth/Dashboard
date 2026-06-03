from maybot_control_center import memory


def _vault(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "VAULT", str(tmp_path))
    monkeypatch.setattr(memory, "SUBDIR", "MayBot")
    return tmp_path


def test_disabled_when_no_vault(monkeypatch):
    monkeypatch.setattr(memory, "VAULT", "")
    assert memory.enabled() is False
    assert memory.search("anything") == []
    assert memory.write_note("x", "y") is None
    assert memory.context_for("x") == ""


def test_search_ranks_by_keyword_overlap(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    (tmp_path / "trading.md").write_text("notes about the trading bot and pnl", encoding="utf-8")
    (tmp_path / "garden.md").write_text("tomatoes and basil", encoding="utf-8")
    hits = memory.search("trading pnl")
    assert hits and hits[0]["title"] == "trading"
    assert "trading" in hits[0]["excerpt"]
    assert all(h["title"] != "garden" for h in hits)


def test_write_then_read_and_append(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    rel = memory.write_note("My Mission!", "first finding", append=True)
    assert rel == "MayBot/My-Mission.md"  # sanitized filename, dedicated subdir
    memory.write_note("My Mission!", "second finding", append=True)
    body = memory.read_note(rel)
    assert "first finding" in body and "second finding" in body


def test_read_note_rejects_traversal(tmp_path, monkeypatch):
    outside = tmp_path.parent / "secret.md"
    outside.write_text("top secret", encoding="utf-8")
    _vault(tmp_path, monkeypatch)
    assert memory.read_note("../secret.md") is None
    assert memory._safe("../../etc/passwd") is None
    # a legit in-vault note still resolves
    (tmp_path / "ok.md").write_text("fine", encoding="utf-8")
    assert memory.read_note("ok.md") == "fine"


def test_write_cannot_escape_subdir(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    # traversal chars are stripped by the slug, so it stays inside MayBot/
    rel = memory.write_note("../../escape", "x")
    assert rel is not None and rel.startswith("MayBot/")
    assert ".." not in rel


def test_context_for_formats_hits(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    (tmp_path / "release.md").write_text("the v2 release plan and milestones", encoding="utf-8")
    ctx = memory.context_for("release plan")
    assert "Obsidian vault" in ctx and "release" in ctx
