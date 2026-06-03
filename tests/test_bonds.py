from __future__ import annotations

import pytest

from maybot_control_center import bonds


def setup_function():
    bonds.clear()


def test_bind_creates_symmetric_bond():
    result = bonds.bind("yan", "mei")
    assert result == {"pair": ["mei", "yan"]}
    assert bonds.partner("yan") == "mei"
    assert bonds.partner("mei") == "yan"
    assert bonds.is_bonded("yan")
    assert bonds.is_bonded("mei")


def test_bind_pair_is_sorted():
    assert bonds.bind("zed", "abe") == {"pair": ["abe", "zed"]}


def test_bind_self_raises():
    with pytest.raises(ValueError):
        bonds.bind("yan", "yan")


def test_bind_falsy_raises():
    with pytest.raises(ValueError):
        bonds.bind("", "mei")
    with pytest.raises(ValueError):
        bonds.bind("yan", "")
    with pytest.raises(ValueError):
        bonds.bind("", "")


def test_rebinding_breaks_old_bond():
    bonds.bind("yan", "mei")
    bonds.bind("kai", "luo")
    # Re-bind yan to kai; old partners (mei, luo) must become unbonded.
    bonds.bind("yan", "kai")
    assert bonds.partner("yan") == "kai"
    assert bonds.partner("kai") == "yan"
    assert bonds.partner("mei") is None
    assert bonds.partner("luo") is None
    assert not bonds.is_bonded("mei")
    assert not bonds.is_bonded("luo")
    # Exactly one pair remains.
    assert bonds.pairs() == [["kai", "yan"]]


def test_rebinding_same_partner_is_stable():
    bonds.bind("yan", "mei")
    bonds.bind("yan", "mei")
    assert bonds.partner("yan") == "mei"
    assert bonds.partner("mei") == "yan"
    assert bonds.pairs() == [["mei", "yan"]]


def test_unbind_dissolves_both_directions():
    bonds.bind("yan", "mei")
    assert bonds.unbind("yan") is True
    assert bonds.partner("yan") is None
    assert bonds.partner("mei") is None
    assert not bonds.is_bonded("yan")
    assert not bonds.is_bonded("mei")


def test_unbind_via_partner_side():
    bonds.bind("yan", "mei")
    # Unbinding the partner also dissolves the bond.
    assert bonds.unbind("mei") is True
    assert bonds.partner("yan") is None
    assert bonds.partner("mei") is None


def test_unbind_returns_false_when_no_bond():
    assert bonds.unbind("ghost") is False


def test_reviewer_for_equals_partner():
    bonds.bind("yan", "mei")
    assert bonds.reviewer_for("yan") == bonds.partner("yan") == "mei"
    assert bonds.reviewer_for("mei") == bonds.partner("mei") == "yan"
    assert bonds.reviewer_for("ghost") is None


def test_pairs_deduped_and_sorted():
    bonds.bind("yan", "mei")
    bonds.bind("zed", "abe")
    bonds.bind("kai", "luo")
    result = bonds.pairs()
    # Each bond appears exactly once, each pair sorted, overall sorted.
    assert result == [["abe", "zed"], ["kai", "luo"], ["mei", "yan"]]
    # No duplicates even though the dict stores both directions.
    assert len(result) == 3


def test_pairs_empty_when_no_bonds():
    assert bonds.pairs() == []


def test_snapshot_shape():
    bonds.bind("yan", "mei")
    snap = bonds.snapshot()
    assert set(snap.keys()) == {"pairs", "bonded"}
    assert snap["pairs"] == [["mei", "yan"]]
    assert snap["bonded"] == {"yan": "mei", "mei": "yan"}


def test_snapshot_empty():
    snap = bonds.snapshot()
    assert snap == {"pairs": [], "bonded": {}}


def test_clear_empties_everything():
    bonds.bind("yan", "mei")
    bonds.bind("kai", "luo")
    bonds.clear()
    assert bonds.pairs() == []
    assert bonds.snapshot() == {"pairs": [], "bonded": {}}
    assert bonds.partner("yan") is None
    assert not bonds.is_bonded("kai")
