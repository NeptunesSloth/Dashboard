from maybot_control_center import sectmemory


def setup_function():
    sectmemory.clear()


def test_add_and_search_relevance(monkeypatch):
    monkeypatch.setattr(sectmemory, "ENABLED", True)
    sectmemory.add("retrieval augmented generation pipeline with vector search", agent="Nova", kind="skill")
    sectmemory.add("the trading bot crashed on a null order id", agent="Forge", kind="postmortem")
    hits = sectmemory.search("how do I add vector search retrieval")
    assert hits and "retrieval" in hits[0]["text"]


def test_search_empty_query():
    assert sectmemory.search("") == []


def test_context_for_formats(monkeypatch):
    monkeypatch.setattr(sectmemory, "ENABLED", True)
    sectmemory.add("function calling lets the model invoke tools", agent="Sage", kind="skill")
    ctx = sectmemory.context_for("function calling tools")
    assert "Relevant sect knowledge" in ctx and "function calling" in ctx


def test_disabled_adds_nothing(monkeypatch):
    monkeypatch.setattr(sectmemory, "ENABLED", False)
    assert sectmemory.add("anything") is None
    assert sectmemory.snapshot()["count"] == 0


def test_cap(monkeypatch):
    monkeypatch.setattr(sectmemory, "ENABLED", True)
    monkeypatch.setattr(sectmemory, "CAP", 5)
    for i in range(12):
        sectmemory.add(f"entry number {i} about reranking")
    assert sectmemory.snapshot()["count"] == 5


def test_snapshot_shape(monkeypatch):
    monkeypatch.setattr(sectmemory, "ENABLED", True)
    sectmemory.add("hello world knowledge", agent="Nova", kind="task")
    s = sectmemory.snapshot()
    assert s["count"] == 1 and s["recent"][0]["agent"] == "Nova"
