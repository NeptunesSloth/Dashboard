from __future__ import annotations


from maybot_control_center import chronicle


def setup_function():
    chronicle.clear()


def test_record_creates_entry_shape_and_glyph():
    entry = chronicle.record("yan", "breakthrough", "reached Foundation")
    assert entry is not None
    assert entry["agent"] == "yan"
    assert entry["kind"] == "breakthrough"
    assert entry["glyph"] == "⬆"
    assert entry["detail"] == "reached Foundation"
    assert entry["meta"] == {}
    assert isinstance(entry["id"], int)
    assert isinstance(entry["ts"], int)
    assert set(entry.keys()) == {"id", "agent", "kind", "glyph", "detail", "meta", "ts"}


def test_record_ids_increment_globally():
    a = chronicle.record("yan", "task", "one")
    b = chronicle.record("mei", "task", "two")
    c = chronicle.record("yan", "task", "three")
    assert a["id"] < b["id"] < c["id"]


def test_record_stores_meta_copy():
    meta = {"sect": "azure"}
    entry = chronicle.record("yan", "title", "Elder", meta=meta)
    assert entry["meta"] == {"sect": "azure"}
    # Mutating the caller's dict must not affect stored state.
    meta["sect"] = "tampered"
    assert chronicle.timeline("yan")[0]["meta"] == {"sect": "azure"}


def test_record_skips_falsy_agent():
    assert chronicle.record("", "task", "x") is None
    assert chronicle.record(None, "task", "x") is None
    assert chronicle.snapshot()["total"] == 0


def test_record_skips_operator():
    assert chronicle.record("operator", "task", "x") is None
    assert chronicle.snapshot()["total"] == 0


def test_unknown_kind_gets_default_glyph():
    entry = chronicle.record("yan", "mystery_kind", "huh")
    assert entry["glyph"] == "•"


def test_known_glyph_map():
    for kind, glyph in chronicle.GLYPHS.items():
        e = chronicle.record("yan", kind)
        assert e["glyph"] == glyph


def test_detail_truncated_to_500():
    long_detail = "x" * 600
    entry = chronicle.record("yan", "note", long_detail)
    assert len(entry["detail"]) == 500
    assert chronicle.timeline("yan")[0]["detail"] == "x" * 500


def test_max_per_agent_bounding_keeps_newest(monkeypatch):
    monkeypatch.setattr(chronicle, "MAX_PER_AGENT", 3)
    for i in range(6):
        chronicle.record("yan", "task", f"d{i}")
    tl = chronicle.timeline("yan", limit=100)
    assert len(tl) == 3
    # Only the last three (newest) survive, in document order.
    assert [e["detail"] for e in tl] == ["d3", "d4", "d5"]
    assert chronicle.snapshot()["agents"]["yan"] == 3


def test_timeline_oldest_to_newest_within_slice():
    for i in range(5):
        chronicle.record("yan", "task", f"d{i}")
    tl = chronicle.timeline("yan", limit=3)
    # Most recent 3, still oldest->newest.
    assert [e["detail"] for e in tl] == ["d2", "d3", "d4"]


def test_timeline_respects_limit():
    for i in range(5):
        chronicle.record("yan", "task", f"d{i}")
    assert len(chronicle.timeline("yan", limit=2)) == 2
    assert chronicle.timeline("yan", limit=0) == []
    assert chronicle.timeline("yan", limit=-1) == []


def test_timeline_empty_for_unknown_agent():
    assert chronicle.timeline("ghost") == []


def test_timeline_returns_copies_mutation_safe():
    chronicle.record("yan", "task", "original", meta={"k": "v"})
    tl = chronicle.timeline("yan")
    # Mutate the returned list and its entries.
    tl[0]["detail"] = "HACKED"
    tl[0]["meta"]["k"] = "HACKED"
    tl.append({"id": 999})
    # State must be untouched.
    fresh = chronicle.timeline("yan")
    assert len(fresh) == 1
    assert fresh[0]["detail"] == "original"
    assert fresh[0]["meta"] == {"k": "v"}


def test_recent_merges_across_agents_newest_first():
    chronicle.record("yan", "task", "y1")
    chronicle.record("mei", "task", "m1")
    chronicle.record("yan", "task", "y2")
    chronicle.record("kai", "task", "k1")
    feed = chronicle.recent(limit=50)
    # Newest first by (ts, id) desc.
    assert [e["detail"] for e in feed] == ["k1", "y2", "m1", "y1"]


def test_recent_respects_limit():
    for i in range(5):
        chronicle.record("yan", "task", f"d{i}")
    feed = chronicle.recent(limit=2)
    assert len(feed) == 2
    assert [e["detail"] for e in feed] == ["d4", "d3"]
    assert chronicle.recent(limit=0) == []
    assert chronicle.recent(limit=-3) == []


def test_recent_empty_when_no_entries():
    assert chronicle.recent() == []


def test_recent_returns_copies_mutation_safe():
    chronicle.record("yan", "task", "original")
    feed = chronicle.recent()
    feed[0]["detail"] = "HACKED"
    assert chronicle.recent()[0]["detail"] == "original"


def test_snapshot_counts():
    chronicle.record("yan", "task", "a")
    chronicle.record("yan", "task", "b")
    chronicle.record("mei", "task", "c")
    snap = chronicle.snapshot()
    assert snap == {"agents": {"yan": 2, "mei": 1}, "total": 3}


def test_snapshot_empty():
    assert chronicle.snapshot() == {"agents": {}, "total": 0}


def test_clear_empties_state_and_resets_ids():
    chronicle.record("yan", "task", "a")
    chronicle.record("mei", "task", "b")
    chronicle.clear()
    assert chronicle.snapshot() == {"agents": {}, "total": 0}
    assert chronicle.timeline("yan") == []
    assert chronicle.recent() == []
    # Id counter resets to 1 after clear.
    entry = chronicle.record("yan", "task", "fresh")
    assert entry["id"] == 1
