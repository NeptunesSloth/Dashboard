"""Artifact vault — a shared, versioned, attributed prompt/tool library.

Disciples *forge* reusable artifacts — prompt templates, tool recipes,
formations, and notes — that others can *wield*. Each artifact carries its
provenance: who originally forged it (the ``creator`` and ``created_at`` never
change), who last edited it, how many times it has been wielded, and by whom.

Under the cultivation costume this is a simple in-memory registry keyed by
artifact ``name``. Forging an existing name bumps its ``version`` and records
the edit while preserving the original attribution. State lives under a lock
and resets on restart (or via :func:`clear`).
"""
from __future__ import annotations

import os
import threading
import time

# Allowed artifact kinds.
KINDS = {"prompt", "tool_recipe", "formation", "note", "manual"}

# Maximum content length, in characters; over-long content is rejected.
MAX_CONTENT = int(os.getenv("MAYBOT_ARTIFACT_MAX_CHARS", "8000"))

_lock = threading.Lock()
# name -> artifact dict (the single source of truth).
_artifacts: dict[str, dict] = {}


def forge(
    creator: str,
    name: str,
    kind: str,
    content: str,
    description: str = "",
) -> dict:
    """Create a new artifact or update an existing one (by ``name``).

    Validation (all raise ValueError): ``creator`` non-empty, ``name``
    non-empty, ``kind`` in :data:`KINDS`, ``content`` non-empty and no longer
    than :data:`MAX_CONTENT` characters (over-long content is rejected, never
    truncated).

    For a brand-new name: ``version`` starts at 1, ``uses`` at 0, and the
    originator's ``creator``/``created_at`` are recorded. For an existing name:
    ``version`` is bumped and ``content``/``description``/``kind`` are updated
    along with ``updated_at`` and ``last_editor``, but the original ``creator``
    and ``created_at`` are preserved (provenance).

    Returns a copy of the stored artifact.
    """
    if not creator:
        raise ValueError("creator must be non-empty")
    if not name:
        raise ValueError("name must be non-empty")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {sorted(KINDS)}")
    if not content:
        raise ValueError("content must be non-empty")
    if len(content) > MAX_CONTENT:
        raise ValueError(f"content exceeds MAX_CONTENT ({MAX_CONTENT} chars)")

    now = time.time()
    with _lock:
        existing = _artifacts.get(name)
        if existing is None:
            artifact = {
                "name": name,
                "kind": kind,
                "content": content,
                "description": description,
                "creator": creator,
                "created_at": now,
                "version": 1,
                "updated_at": None,
                "last_editor": None,
                "uses": 0,
                "last_wielded_by": None,
            }
            _artifacts[name] = artifact
        else:
            existing["kind"] = kind
            existing["content"] = content
            existing["description"] = description
            existing["version"] += 1
            existing["updated_at"] = now
            existing["last_editor"] = creator
            # creator / created_at / uses / last_wielded_by are preserved.
            artifact = existing
        return dict(artifact)


def wield(agent: str, name: str) -> dict:
    """Record that ``agent`` used the artifact ``name``.

    Increments ``uses`` and sets ``last_wielded_by``. Raises KeyError if the
    name is unknown. Returns a copy of the updated artifact.
    """
    with _lock:
        artifact = _artifacts.get(name)
        if artifact is None:
            raise KeyError(name)
        artifact["uses"] += 1
        artifact["last_wielded_by"] = agent
        return dict(artifact)


def get(name: str) -> dict | None:
    """Return a copy of the artifact named ``name``, or None if absent."""
    with _lock:
        artifact = _artifacts.get(name)
        return dict(artifact) if artifact is not None else None


def catalog() -> list[dict]:
    """Return copies of all artifacts, sorted by name."""
    with _lock:
        return [dict(a) for _, a in sorted(_artifacts.items())]


# `list` is a builtin, so expose the catalog under a list-flavoured alias too.
def list_artifacts() -> list[dict]:
    """Alias for :func:`catalog`."""
    return catalog()


def remove(name: str) -> bool:
    """Delete the artifact named ``name``. Return True if it existed."""
    with _lock:
        return _artifacts.pop(name, None) is not None


def snapshot() -> dict:
    """A consistent view: counts, per-kind tallies, and the full catalog."""
    arts = catalog()
    by_kind: dict[str, int] = {}
    for a in arts:
        by_kind[a["kind"]] = by_kind.get(a["kind"], 0) + 1
    return {"count": len(arts), "by_kind": by_kind, "artifacts": arts}


def clear() -> None:
    """Reset the vault, removing all artifacts."""
    with _lock:
        _artifacts.clear()
