"""Phase 3: Obsidian vault memory for agents.

Point ``MAYBOT_OBSIDIAN_VAULT`` at an Obsidian vault (a folder of markdown
notes) and agents gain a shared, persistent memory: they pull relevant notes in
as context and write findings back.

Safety is the whole game here:
- Reads are confined to ``.md`` files inside the vault. Every path is resolved
  and checked to stay within the vault root, so traversal (``../../etc``) is
  rejected.
- Writes are further confined to a dedicated subfolder
  (``MAYBOT_OBSIDIAN_SUBDIR``, default ``MayBot``) with sanitized filenames, so
  agents can never clobber your hand-written notes.

Note: any notes injected as context are sent to whatever backend the agent
uses (a local host stays local; a ``claude`` agent sends them to the API).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

VAULT = os.getenv("MAYBOT_OBSIDIAN_VAULT", "")
SUBDIR = os.getenv("MAYBOT_OBSIDIAN_SUBDIR", "MayBot")
MAX_FILES = int(os.getenv("MAYBOT_OBSIDIAN_MAX_FILES", "2000"))
MAX_BYTES = 200_000  # per-file read cap

_WORD = re.compile(r"[a-z0-9]+")
_SLUG = re.compile(r"[^a-zA-Z0-9 _-]+")


def enabled() -> bool:
    return bool(VAULT) and Path(VAULT).is_dir()


def _vault() -> Path:
    return Path(VAULT).resolve()


def _safe(rel: str) -> Path | None:
    """Resolve ``rel`` inside the vault; return None if it escapes the root."""
    if not enabled():
        return None
    base = _vault()
    target = (base / rel).resolve()
    if target == base or base in target.parents:
        return target
    return None


def _iter_notes():
    base = _vault()
    n = 0
    for p in sorted(base.rglob("*.md")):
        if p.is_file():
            yield p
            n += 1
            if n >= MAX_FILES:
                return


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _excerpt(text: str, q: set[str], width: int = 240) -> str:
    for line in text.splitlines():
        if q & _tokens(line):
            return line.strip()[:width]
    return text.strip().replace("\n", " ")[:width]


def search(query: str, limit: int = 5) -> list[dict]:
    """Keyword search across the vault; returns the best-matching notes."""
    q = _tokens(query or "")
    if not enabled() or not q:
        return []
    base = _vault()
    scored = []
    for p in _iter_notes():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")[:MAX_BYTES]
        except Exception:
            continue
        score = len(q & (_tokens(text) | _tokens(p.stem)))
        if score:
            scored.append((score, p, text))
    scored.sort(key=lambda r: (-r[0], str(r[1])))
    return [
        {"path": str(p.relative_to(base)), "title": p.stem, "score": score, "excerpt": _excerpt(text, q)}
        for score, p, text in scored[:limit]
    ]


def read_note(rel: str) -> str | None:
    p = _safe(rel)
    if p and p.is_file() and p.suffix == ".md":
        try:
            return p.read_text(encoding="utf-8", errors="ignore")[:MAX_BYTES]
        except Exception:
            return None
    return None


def list_notes(limit: int = 200) -> list[dict]:
    if not enabled():
        return []
    base = _vault()
    out = []
    for p in _iter_notes():
        out.append({"path": str(p.relative_to(base)), "title": p.stem})
        if len(out) >= limit:
            break
    return out


def write_note(title: str, content: str, append: bool = True) -> str | None:
    """Write/append a note under the dedicated subdir. Returns the relative path."""
    if not enabled():
        return None
    slug = _SLUG.sub("", title or "note").strip().replace(" ", "-")[:80] or "note"
    p = _safe(f"{SUBDIR}/{slug}.md")
    if p is None:
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if (append and p.exists()) else "w"
    with p.open(mode, encoding="utf-8") as f:
        if mode == "a":
            f.write("\n\n")
        f.write(content if content.endswith("\n") else content + "\n")
    return str(p.relative_to(_vault()))


def context_for(query: str, limit: int = 3) -> str:
    """A compact block of relevant notes to inject into an agent's prompt."""
    hits = search(query, limit)
    if not hits:
        return ""
    lines = ["Relevant notes from the Obsidian vault (use as background; cite the note title if you rely on it):"]
    lines += [f"- [{h['title']}] {h['excerpt']}" for h in hits]
    return "\n".join(lines)
