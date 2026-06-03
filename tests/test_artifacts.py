from __future__ import annotations

import pytest

from maybot_control_center import artifacts


def setup_function():
    artifacts.clear()


# --- forge validation -----------------------------------------------------

def test_forge_empty_creator_raises():
    with pytest.raises(ValueError):
        artifacts.forge("", "p1", "prompt", "hello")


def test_forge_empty_name_raises():
    with pytest.raises(ValueError):
        artifacts.forge("yan", "", "prompt", "hello")


def test_forge_bad_kind_raises():
    with pytest.raises(ValueError):
        artifacts.forge("yan", "p1", "nonsense", "hello")


def test_forge_empty_content_raises():
    with pytest.raises(ValueError):
        artifacts.forge("yan", "p1", "prompt", "")


def test_forge_too_long_content_raises():
    too_long = "x" * (artifacts.MAX_CONTENT + 1)
    with pytest.raises(ValueError):
        artifacts.forge("yan", "p1", "prompt", too_long)


def test_forge_max_length_content_allowed():
    at_limit = "x" * artifacts.MAX_CONTENT
    art = artifacts.forge("yan", "p1", "prompt", at_limit)
    assert art["content"] == at_limit


def test_all_kinds_allowed():
    for kind in artifacts.KINDS:
        art = artifacts.forge("yan", f"a-{kind}", kind, "body")
        assert art["kind"] == kind


# --- new artifact ----------------------------------------------------------

def test_new_artifact_defaults():
    art = artifacts.forge("yan", "p1", "prompt", "body", "a desc")
    assert art["name"] == "p1"
    assert art["kind"] == "prompt"
    assert art["content"] == "body"
    assert art["description"] == "a desc"
    assert art["creator"] == "yan"
    assert art["version"] == 1
    assert art["uses"] == 0
    assert art["updated_at"] is None
    assert art["last_editor"] is None
    assert art["last_wielded_by"] is None
    assert art["created_at"] is not None


def test_new_artifact_return_has_full_shape():
    art = artifacts.forge("yan", "p1", "prompt", "body")
    expected_keys = {
        "name", "kind", "content", "description", "creator", "created_at",
        "version", "updated_at", "last_editor", "uses", "last_wielded_by",
    }
    assert set(art.keys()) == expected_keys


# --- re-forging (update) ---------------------------------------------------

def test_reforge_bumps_version_and_preserves_provenance():
    first = artifacts.forge("yan", "p1", "prompt", "body1", "desc1")
    original_creator = first["creator"]
    original_created = first["created_at"]

    second = artifacts.forge("mei", "p1", "note", "body2", "desc2")
    assert second["version"] == 2
    assert second["kind"] == "note"
    assert second["content"] == "body2"
    assert second["description"] == "desc2"
    # Provenance preserved.
    assert second["creator"] == original_creator
    assert second["created_at"] == original_created
    # Edit tracked.
    assert second["last_editor"] == "mei"
    assert second["updated_at"] is not None


def test_reforge_third_time():
    artifacts.forge("yan", "p1", "prompt", "v1")
    artifacts.forge("yan", "p1", "prompt", "v2")
    art = artifacts.forge("zoe", "p1", "prompt", "v3")
    assert art["version"] == 3
    assert art["last_editor"] == "zoe"
    assert art["creator"] == "yan"


def test_reforge_preserves_uses():
    artifacts.forge("yan", "p1", "prompt", "v1")
    artifacts.wield("mei", "p1")
    art = artifacts.forge("yan", "p1", "prompt", "v2")
    assert art["uses"] == 1


# --- wield -----------------------------------------------------------------

def test_wield_increments_uses_and_sets_wielder():
    artifacts.forge("yan", "p1", "prompt", "body")
    a1 = artifacts.wield("mei", "p1")
    assert a1["uses"] == 1
    assert a1["last_wielded_by"] == "mei"
    a2 = artifacts.wield("zoe", "p1")
    assert a2["uses"] == 2
    assert a2["last_wielded_by"] == "zoe"


def test_wield_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        artifacts.wield("mei", "nope")


# --- get -------------------------------------------------------------------

def test_get_missing_returns_none():
    assert artifacts.get("nope") is None


def test_get_returns_copy():
    artifacts.forge("yan", "p1", "prompt", "body")
    got = artifacts.get("p1")
    got["content"] = "mutated"
    got["version"] = 999
    again = artifacts.get("p1")
    assert again["content"] == "body"
    assert again["version"] == 1


# --- catalog ---------------------------------------------------------------

def test_catalog_sorted_by_name():
    artifacts.forge("yan", "zed", "prompt", "b")
    artifacts.forge("yan", "abe", "note", "b")
    artifacts.forge("yan", "mid", "tool_recipe", "b")
    names = [a["name"] for a in artifacts.catalog()]
    assert names == ["abe", "mid", "zed"]


def test_catalog_returns_copies():
    artifacts.forge("yan", "p1", "prompt", "body")
    cat = artifacts.catalog()
    cat[0]["content"] = "mutated"
    assert artifacts.get("p1")["content"] == "body"


def test_list_artifacts_is_catalog():
    artifacts.forge("yan", "p1", "prompt", "body")
    assert artifacts.list_artifacts() == artifacts.catalog()


# --- remove ----------------------------------------------------------------

def test_remove_existing_returns_true():
    artifacts.forge("yan", "p1", "prompt", "body")
    assert artifacts.remove("p1") is True
    assert artifacts.get("p1") is None


def test_remove_missing_returns_false():
    assert artifacts.remove("nope") is False


# --- snapshot --------------------------------------------------------------

def test_snapshot_empty():
    snap = artifacts.snapshot()
    assert snap == {"count": 0, "by_kind": {}, "artifacts": []}


def test_snapshot_counts_by_kind():
    artifacts.forge("yan", "a", "prompt", "b")
    artifacts.forge("yan", "b", "prompt", "b")
    artifacts.forge("yan", "c", "note", "b")
    snap = artifacts.snapshot()
    assert snap["count"] == 3
    assert snap["by_kind"] == {"prompt": 2, "note": 1}
    assert [a["name"] for a in snap["artifacts"]] == ["a", "b", "c"]


# --- clear -----------------------------------------------------------------

def test_clear_empties_vault():
    artifacts.forge("yan", "p1", "prompt", "body")
    artifacts.forge("yan", "p2", "note", "body")
    artifacts.clear()
    assert artifacts.catalog() == []
    assert artifacts.snapshot()["count"] == 0
