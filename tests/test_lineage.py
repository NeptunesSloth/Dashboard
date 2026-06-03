from __future__ import annotations

from maybot_control_center import lineage


def setup_function():
    lineage.clear()


def test_record_origin_sets_source():
    lineage.record_origin("A", "s1", "quest")
    o = lineage.skill_origin("s1")
    assert o == {"agent": "A", "skill": "s1", "source": "quest"}


def test_record_origin_default_source():
    lineage.record_origin("A", "s1")
    assert lineage.skill_origin("s1")["source"] == "discovered"


def test_record_origin_first_writer_wins():
    lineage.record_origin("A", "s1", "discovered")
    lineage.record_origin("B", "s1", "quest")
    o = lineage.skill_origin("s1")
    assert o["agent"] == "A"
    assert o["source"] == "discovered"


def test_record_origin_ignores_falsy():
    lineage.record_origin("", "s1")
    lineage.record_origin("A", "")
    assert lineage.origins() == []


def test_record_transmission_adds_edge():
    lineage.record_transmission("A", "B", "s1")
    assert lineage.edges() == [{"teacher": "A", "student": "B", "skill": "s1"}]


def test_record_transmission_dedups():
    lineage.record_transmission("A", "B", "s1")
    lineage.record_transmission("A", "B", "s1")
    assert len(lineage.edges()) == 1


def test_record_transmission_distinct_edges_kept():
    lineage.record_transmission("A", "B", "s1")
    lineage.record_transmission("A", "B", "s2")
    lineage.record_transmission("A", "C", "s1")
    assert len(lineage.edges()) == 3


def test_record_transmission_ignores_self():
    lineage.record_transmission("A", "A", "s1")
    assert lineage.edges() == []
    # no fallback origin created either
    assert lineage.skill_origin("s1") is None


def test_record_transmission_ignores_falsy():
    lineage.record_transmission("", "B", "s1")
    lineage.record_transmission("A", "", "s1")
    lineage.record_transmission("A", "B", "")
    assert lineage.edges() == []


def test_record_transmission_sets_fallback_origin():
    lineage.record_transmission("A", "B", "s1")
    o = lineage.skill_origin("s1")
    assert o == {"agent": "A", "skill": "s1", "source": "transmission"}


def test_record_transmission_does_not_override_origin():
    lineage.record_origin("X", "s1", "discovered")
    lineage.record_transmission("A", "B", "s1")
    o = lineage.skill_origin("s1")
    assert o["agent"] == "X"
    assert o["source"] == "discovered"


def test_skill_origin_unknown():
    assert lineage.skill_origin("nope") is None
    assert lineage.skill_origin("") is None


def test_lineage_of_chain():
    # A originates s1, A teaches B s1, B teaches C s1.
    lineage.record_origin("A", "s1", "discovered")
    lineage.record_transmission("A", "B", "s1")
    lineage.record_transmission("B", "C", "s1")

    la = lineage.lineage_of("A")
    assert la["originated"] == ["s1"]
    assert la["learned_from"] == []
    assert {"student": "B", "skill": "s1"} in la["taught"]

    lb = lineage.lineage_of("B")
    assert lb["originated"] == []
    assert lb["learned_from"] == [{"teacher": "A", "skill": "s1"}]
    assert lb["taught"] == [{"student": "C", "skill": "s1"}]

    lc = lineage.lineage_of("C")
    assert lc["learned_from"] == [{"teacher": "B", "skill": "s1"}]
    assert lc["taught"] == []
    assert lc["originated"] == []


def test_lineage_of_empty_agent():
    assert lineage.lineage_of("") == {
        "learned_from": [],
        "taught": [],
        "originated": [],
    }


def test_lineage_of_unknown_agent():
    lineage.record_transmission("A", "B", "s1")
    assert lineage.lineage_of("Z") == {
        "learned_from": [],
        "taught": [],
        "originated": [],
    }


def test_graph_nodes_are_union():
    lineage.record_origin("A", "s1", "discovered")
    lineage.record_transmission("A", "B", "s1")
    lineage.record_transmission("B", "C", "s1")
    lineage.record_origin("D", "s2", "quest")  # origin-only agent, no edges

    g = lineage.graph()
    assert set(g["nodes"]) == {"A", "B", "C", "D"}
    # no duplicate nodes
    assert len(g["nodes"]) == len(set(g["nodes"]))
    assert g["edges"] == lineage.edges()
    assert g["origins"] == lineage.origins()


def test_clear_empties():
    lineage.record_origin("A", "s1")
    lineage.record_transmission("A", "B", "s1")
    lineage.clear()
    assert lineage.origins() == []
    assert lineage.edges() == []
    assert lineage.graph() == {"nodes": [], "edges": [], "origins": []}
