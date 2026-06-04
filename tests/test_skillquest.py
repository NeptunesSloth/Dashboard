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


def test_discover_fetches_howto_doc(monkeypatch):
    monkeypatch.setattr(skillquest, "_search", lambda q: [{"title": "Reranking - Guide", "url": "http://x"}])
    monkeypatch.setattr(skillquest, "_fetch_doc", lambda url: "Reranking reorders candidates by relevance.")
    d = skillquest.discover("Nova")
    assert d["doc"] == "Reranking reorders candidates by relevance."


def test_learned_skill_doc_enters_sect_memory(monkeypatch):
    from maybot_control_center import sectmemory
    sectmemory.clear()
    monkeypatch.setattr("maybot_control_center.skillquest.discover",
                        lambda agent, known, want=None: {"skill": "reranking", "url": "http://x",
                                                         "source": "web", "query": "q",
                                                         "doc": "Reranking reorders results by relevance."})
    cultivation.enter_roaming("Sage")
    cultivation._state["Sage"]["roaming_since"] = time.time() - cultivation.ROAMING_SECONDS - 1
    cultivation.tick_roaming("Sage")
    hits = sectmemory.search("reranking relevance")
    assert hits and "Reranking reorders" in hits[0]["text"]


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
                        lambda agent, known, want=None: {"skill": "tool use", "url": "http://x", "source": "web", "query": "q"})
    cultivation.enter_roaming("Nova")
    cultivation._state["Nova"]["roaming_since"] = time.time() - cultivation.ROAMING_SECONDS - 1
    found = cultivation.tick_roaming("Nova")
    assert found == "tool use"
    assert "tool use" in cultivation.state("Nova")["skills"]


def test_want_drives_query_and_picks_closest(monkeypatch):
    captured = {}
    monkeypatch.setattr(skillquest, "_search",
                        lambda q: captured.update(q=q) or [{"title": "Speculative Decoding - Paper", "url": "http://x"}])
    d = skillquest.discover("Nova", want="fast llm decoding")
    assert captured["q"] == "fast llm decoding"          # searched for what was asked
    assert d["skill"] == "speculative decoding" and d["requested"] is True


def test_want_offline_picks_closest_fallback(monkeypatch):
    monkeypatch.setattr(skillquest, "_search", lambda q: [])   # offline
    d = skillquest.discover("Nova", want="retrieval augmented generation method")
    assert d["source"] == "requested"
    assert d["skill"] == "retrieval-augmented generation"     # closest curated match


def test_want_offline_unmatched_learns_requested(monkeypatch):
    monkeypatch.setattr(skillquest, "_search", lambda q: [])
    d = skillquest.discover("Nova", want="quantum telepathy")
    assert d["skill"] == "quantum telepathy" and d["source"] == "requested"


def test_learn_goal_drives_roaming(monkeypatch):
    cultivation.clear()
    seen = {}
    monkeypatch.setattr("maybot_control_center.skillquest.discover",
                        lambda agent, known, want=None: seen.update(want=want) or {"skill": "tool use", "url": "", "source": "requested", "query": want})
    cultivation.set_learn_goal("Nova", "agent tool use")
    cultivation.enter_roaming("Nova")
    cultivation._state["Nova"]["roaming_since"] = time.time() - cultivation.ROAMING_SECONDS - 1
    cultivation.tick_roaming("Nova")
    assert seen["want"] == "agent tool use"
    assert cultivation.state("Nova")["learn_goal"] is None    # goal consumed


def test_roaming_falls_back_when_discover_none(monkeypatch):
    cultivation.clear()
    monkeypatch.setattr("maybot_control_center.skillquest.discover", lambda agent, known: None)
    cultivation.enter_roaming("Wren")
    cultivation._state["Wren"]["roaming_since"] = time.time() - cultivation.ROAMING_SECONDS - 1
    found = cultivation.tick_roaming("Wren")
    assert found in cultivation.DISCOVERIES   # flavour fallback still works
