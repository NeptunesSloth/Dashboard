import time

import pytest

from maybot_control_center import skillquest, cultivation


def setup_function():
    skillquest.clear()


def test_normalize():
    assert skillquest._normalize("Retrieval-Augmented Generation - Wikipedia") == "retrieval-augmented generation"
    assert skillquest._normalize("Tool use | Anthropic") == "tool use"
    assert skillquest._normalize("Vector Search: A Guide") == "vector search"


def test_discover_from_web(monkeypatch):
    monkeypatch.setattr(skillquest, "_search", lambda q: [{"title": "Vector Search - Guide", "url": "http://x"}])
    d = skillquest.discover("Nova")
    assert d["skill"] == "vector search" and d["source"] == "web" and d["url"] == "http://x"
    assert skillquest.last("Nova")["skill"] == "vector search"


def test_discover_skips_known(monkeypatch):
    monkeypatch.setattr(skillquest, "_search",
                        lambda q: [{"title": "Vector Search", "url": "u1"}, {"title": "Reranking", "url": "u2"}])
    d = skillquest.discover("Nova", known={"vector search"})
    assert d["skill"] == "reranking"


def test_discover_offline_fallback_on_error(monkeypatch):
    def boom(q):
        raise RuntimeError("no network")
    monkeypatch.setattr(skillquest, "_search", boom)
    d = skillquest.discover("Nova")
    assert d["source"] == "offline" and d["skill"] in skillquest.FALLBACK


def test_discover_none_when_exhausted(monkeypatch):
    monkeypatch.setattr(skillquest, "_search", lambda q: [])
    known = {s for s in skillquest.FALLBACK}
    assert skillquest.discover("Nova", known=known) is None


def test_roaming_learns_real_web_skill(monkeypatch):
    cultivation.clear()
    monkeypatch.setattr("maybot_control_center.skillquest.discover",
                        lambda agent, known: {"skill": "tool use", "url": "http://x", "source": "web", "query": "q"})
    cultivation.enter_roaming("Nova")
    cultivation._state["Nova"]["roaming_since"] = time.time() - cultivation.ROAMING_SECONDS - 1
    found = cultivation.tick_roaming("Nova")
    assert found == "tool use"
    assert "tool use" in cultivation.state("Nova")["skills"]


def test_roaming_falls_back_when_discover_none(monkeypatch):
    cultivation.clear()
    monkeypatch.setattr("maybot_control_center.skillquest.discover", lambda agent, known: None)
    cultivation.enter_roaming("Wren")
    cultivation._state["Wren"]["roaming_since"] = time.time() - cultivation.ROAMING_SECONDS - 1
    found = cultivation.tick_roaming("Wren")
    assert found in cultivation.DISCOVERIES   # flavour fallback still works
