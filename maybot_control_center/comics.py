"""Self-hosted comics / manga library — the sect's "Scripture Archive".

Ingest comic files onto the server, browse them, read them page-by-page in the
browser, download issues (or whole series, or the whole library) to a device,
and **export to an attached SSD** for offline reading. Ongoing series can
**auto-update** from a subscribed RSS/Atom feed.

Opt-in / default-off, like the rest of the project:

* ``MAYBOT_COMICS`` — master switch for the background feed auto-updater. The
  HTTP routes always work (so you can browse/upload), but the poller only runs
  when this is truthy.
* ``MAYBOT_COMICS_DIR`` — on-disk library root (default ``comics_library``). The
  comic files live here; only lightweight metadata is persisted to the DB.
* ``MAYBOT_COMICS_EXPORT_DIRS`` — colon-separated allow-list of base paths the
  server-side export may write into (e.g. SSD mount points). Empty ⇒ the export
  endpoint is disabled. Each entry is ``realpath``-resolved and requests are
  validated with ``realpath`` + ``commonpath`` so a crafted destination can't
  escape an approved mount.

Ingest paths (all generic and operator-supplied — **no site scraping**):

1. Operator file **upload** (``.cbz/.zip/.cbr/.pdf`` or a single image).
2. Direct **file URL** — downloads the file as-is; caller owns its legality.
3. **Feed subscription** — an RSS/Atom feed; the poller ingests new enclosure
   links as the author publishes them.

Metadata is persisted via :mod:`store` (``save_state``/``load_state``) so the
library survives a restart; the actual files always live on disk.
"""
from __future__ import annotations

import os
import re
import shutil
import threading
import time
import zipfile
from collections.abc import Iterator
from urllib.parse import urlparse

from . import store

# ---- config (read once at import, MAYBOT_* convention) ----
BASE_DIR = os.getenv("MAYBOT_COMICS_DIR", "comics_library")
ENABLED = os.getenv("MAYBOT_COMICS", "0").lower() in {"1", "true", "yes", "on"}
FEED_POLL_MIN = float(os.getenv("MAYBOT_COMICS_FEED_INTERVAL_MIN", "60") or 60)
DOWNLOAD_TIMEOUT = float(os.getenv("MAYBOT_COMICS_DL_TIMEOUT", "60") or 60)
MAX_BYTES = int(os.getenv("MAYBOT_COMICS_MAX_BYTES", str(500 * 1024 * 1024)))
USER_AGENT = "maybot-comics"


def _export_dirs() -> list[str]:
    raw = os.getenv("MAYBOT_COMICS_EXPORT_DIRS", "").strip()
    out = []
    for part in raw.split(os.pathsep):
        part = part.strip()
        if part:
            out.append(os.path.realpath(part))
    return out


EXPORT_DIRS = _export_dirs()

COMIC_EXTS = {".cbz", ".zip", ".cbr", ".rar", ".pdf"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
INGEST_EXTS = COMIC_EXTS | IMAGE_EXTS

# ---- in-memory state (metadata only; files live on disk) ----
_lock = threading.Lock()
_series: dict[str, dict] = {}   # series_id -> series record
_feeds: dict[str, dict] = {}    # feed_id   -> feed subscription record
_started = False


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _slug(text: str) -> str:
    """Turn a title/filename into a SAFE_NAME-valid id (letters/digits/-/_/.)."""
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "-", (text or "").strip().lower()).strip("-.")
    return (s or "untitled")[:128]


def _natkey(name: str):
    """Natural sort key so page2 < page10."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def _series_dir(series_id: str) -> str:
    return os.path.join(BASE_DIR, series_id)


def resolve_within_library(*parts: str) -> str:
    """Resolve a path under the library root, rejecting traversal.

    Mirrors the realpath+commonpath guard in routers/pages.py ``assets()``.
    Raises ``ValueError`` if the resolved path escapes ``BASE_DIR``.
    """
    base = os.path.realpath(BASE_DIR)
    target = os.path.realpath(os.path.join(base, *parts))
    if base != target and os.path.commonpath([base, target]) != base:
        raise ValueError("path escapes comics library")
    return target


def _detect_fmt(filename: str, head: bytes) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if head[:4] == b"PK\x03\x04" or ext in (".cbz", ".zip"):
        return "cbz"
    if head[:4] == b"Rar!" or ext in (".cbr", ".rar"):
        return "cbr"
    if head[:5] == b"%PDF-" or ext == ".pdf":
        return "pdf"
    if ext in IMAGE_EXTS:
        return "img"
    return "cbz"  # default: treat unknown archives as zip


def _extract_index(path: str, fmt: str) -> tuple[list[str] | None, bool]:
    """Return (sorted image-entry names, readable). Readable archives feed the
    page-by-page reader; everything else is download-only in v1."""
    if fmt in ("cbz",):
        try:
            with zipfile.ZipFile(path) as zf:
                names = [n for n in zf.namelist()
                         if os.path.splitext(n)[1].lower() in IMAGE_EXTS]
            names.sort(key=_natkey)
            return (names, True) if names else (None, False)
        except Exception:
            return (None, False)
    if fmt == "cbr":
        try:
            import rarfile  # optional, lazy — needs unrar/unar at runtime
        except Exception:
            return (None, False)
        try:
            with rarfile.RarFile(path) as rf:
                names = [n for n in rf.namelist()
                         if os.path.splitext(n)[1].lower() in IMAGE_EXTS]
            names.sort(key=_natkey)
            return (names, True) if names else (None, False)
        except Exception:
            return (None, False)
    return (None, False)  # pdf / img: no page reader in v1


def _read_archive_entry(path: str, fmt: str, name: str) -> bytes | None:
    if fmt == "cbz":
        with zipfile.ZipFile(path) as zf:
            return zf.read(name)
    if fmt == "cbr":
        try:
            import rarfile
        except Exception:
            return None
        with rarfile.RarFile(path) as rf:
            return rf.read(name)
    return None


def _make_cover(series_id: str, issue_id: str, path: str, fmt: str,
                page_index: list[str] | None) -> str | None:
    """Copy the first page out as ``<issue_id>.cover.<ext>`` (cbz/cbr only)."""
    if not page_index:
        return None
    first = page_index[0]
    ext = os.path.splitext(first)[1].lower() or ".jpg"
    cover_name = f"{issue_id}.cover{ext}"
    try:
        data = _read_archive_entry(path, fmt, first)
        if not data:
            return None
        with open(os.path.join(_series_dir(series_id), cover_name), "wb") as fh:
            fh.write(data)
        return cover_name
    except Exception:
        return None


def _media_type(name: str) -> str:
    ext = os.path.splitext(name)[1].lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
            ".pdf": "application/pdf"}.get(ext, "application/octet-stream")


# --------------------------------------------------------------------------
# persistence
# --------------------------------------------------------------------------
def _persist() -> None:
    """Write metadata blob to the store. Call while holding ``_lock``."""
    if store.enabled():
        try:
            store.save_state("comics", {"series": _series, "feeds": _feeds})
        except Exception:
            pass


def load_persisted() -> None:
    global _series, _feeds
    if not store.enabled():
        return
    blob = store.load_state("comics")
    if not blob:
        return
    with _lock:
        _series = blob.get("series", {}) or {}
        _feeds = blob.get("feeds", {}) or {}


def clear() -> None:
    """Reset in-memory state (test helper). Does NOT touch disk."""
    global _started
    with _lock:
        _series.clear()
        _feeds.clear()
    _started = False


# --------------------------------------------------------------------------
# ingest
# --------------------------------------------------------------------------
def _store_file(series_title: str, filename: str, data: bytes, source: str,
                source_ref: str = "", series_id: str | None = None) -> dict:
    """Write bytes to disk, build the issue record, register + persist it.

    Shared by upload / URL / feed ingest. Returns the issue record.
    """
    if len(data) > MAX_BYTES:
        raise ValueError(f"file exceeds MAYBOT_COMICS_MAX_BYTES ({MAX_BYTES} bytes)")
    sid = series_id or _slug(series_title)
    if not re.match(r"^[a-zA-Z0-9_.-]{1,128}$", sid):
        raise ValueError("invalid series id")
    fmt = _detect_fmt(filename, data[:8])
    ext = {"cbz": ".cbz", "cbr": ".cbr", "pdf": ".pdf"}.get(fmt) \
        or os.path.splitext(filename)[1].lower() or ".bin"
    stem = _slug(os.path.splitext(os.path.basename(filename))[0]) or "issue"

    sdir = _series_dir(sid)
    os.makedirs(sdir, exist_ok=True)

    with _lock:
        series = _series.get(sid)
        # unique issue id within the series
        issue_id = stem
        n = 2
        existing = (series or {}).get("issues", {})
        while issue_id in existing:
            issue_id = f"{stem}-{n}"
            n += 1

    stored_name = f"{issue_id}{ext}"
    target = resolve_within_library(sid, stored_name)
    with open(target, "wb") as fh:
        fh.write(data)

    page_index, readable = _extract_index(target, fmt)
    cover = _make_cover(sid, issue_id, target, fmt, page_index)
    now = time.time()
    issue = {
        "id": issue_id,
        "title": os.path.splitext(os.path.basename(filename))[0] or issue_id,
        "file": stored_name,
        "fmt": fmt,
        "bytes": len(data),
        "pages": len(page_index) if page_index else None,
        "page_index": page_index,
        "readable": readable,
        "cover": cover,
        "added": now,
        "source": source,
        "source_ref": source_ref,
        "read": False,
        "last_page": 0,
    }

    with _lock:
        series = _series.get(sid)
        if series is None:
            series = {"id": sid, "title": series_title or sid, "cover": None,
                      "feed_id": None, "created": now, "updated": now, "issues": {}}
            _series[sid] = series
        series["issues"][issue_id] = issue
        series["updated"] = now
        if cover:
            series["cover"] = f"{issue_id}/{cover}"  # informational; cover endpoint uses ids
        _persist()
    return issue


def ingest_upload(series_title: str, filename: str, data: bytes) -> dict:
    """Ingest an operator-uploaded file into ``series_title``."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in INGEST_EXTS:
        raise ValueError(f"unsupported file type: {ext or '(none)'}")
    return _store_file(series_title, filename, data, source="upload", source_ref="upload")


def download_file(url: str) -> tuple[str, bytes]:
    """Download a URL → (filename, bytes). The single network boundary; tests
    monkeypatch this so nothing hits the network."""
    import requests
    resp = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT,
                        headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    chunks = bytearray()
    for chunk in resp.iter_content(65536):
        chunks += chunk
        if len(chunks) > MAX_BYTES:
            raise ValueError(f"download exceeds MAYBOT_COMICS_MAX_BYTES ({MAX_BYTES} bytes)")
    # filename: Content-Disposition, else URL path basename
    name = os.path.basename(urlparse(url).path) or "download"
    cd = resp.headers.get("content-disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    if m:
        name = os.path.basename(m.group(1).strip())
    return name, bytes(chunks)


def ingest_url(series_title: str, url: str) -> dict:
    """Download a direct file URL and ingest it. Caller owns the URL's legality."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("url must be http(s)")
    ext = os.path.splitext(parsed.path)[1].lower()
    if ext not in INGEST_EXTS:
        raise ValueError(f"url must point at a comic/image file ({ext or 'no extension'})")
    filename, data = download_file(url)
    return _store_file(series_title, filename, data, source="url", source_ref=url)


# --------------------------------------------------------------------------
# feeds / auto-update
# --------------------------------------------------------------------------
def _parse_feed(text: str, kind: str) -> list[dict]:
    """Extract comic/image enclosure links from an RSS/Atom feed (stdlib XML).

    Generic: reads ``<enclosure url>`` / ``<link>`` only — no HTML scraping.
    """
    import xml.etree.ElementTree as ET
    out: list[dict] = []
    try:
        root = ET.fromstring(text)
    except Exception:
        return out

    def _localname(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].lower()

    def _looks_comic(u: str) -> bool:
        return os.path.splitext(urlparse(u).path)[1].lower() in INGEST_EXTS

    for el in root.iter():
        if _localname(el.tag) not in ("item", "entry"):
            continue
        title, url, guid = "", "", ""
        for child in el:
            ln = _localname(child.tag)
            if ln == "title" and child.text:
                title = child.text.strip()
            elif ln in ("guid", "id") and child.text:
                guid = child.text.strip()
            elif ln == "enclosure":
                href = child.attrib.get("url") or child.attrib.get("href") or ""
                if _looks_comic(href):
                    url = href
            elif ln == "link":
                href = child.attrib.get("href") or (child.text or "")
                rel = child.attrib.get("rel", "")
                if _looks_comic(href) and (rel in ("", "enclosure", "alternate") or not url):
                    url = url or href
        if url:
            out.append({"title": title, "url": url, "guid": guid or url})
    return out


def add_feed(url: str, series_title: str, interval_min: float | None = None) -> dict:
    """Subscribe a series to an RSS/Atom feed for auto-update."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("feed url must be http(s)")
    import uuid
    fid = uuid.uuid4().hex
    sid = _slug(series_title)
    now = time.time()
    feed = {
        "id": fid,
        "url": url,
        "kind": "rss",
        "series_id": sid,
        "interval_min": float(interval_min) if interval_min else FEED_POLL_MIN,
        "enabled": True,
        "last_poll": 0.0,
        "last_status": "",
        "seen": [],
    }
    with _lock:
        _feeds[fid] = feed
        series = _series.get(sid)
        if series is None:
            _series[sid] = {"id": sid, "title": series_title or sid, "cover": None,
                            "feed_id": fid, "created": now, "updated": now, "issues": {}}
        else:
            series["feed_id"] = fid
        _persist()
    return feed


def poll_feed(feed_id: str) -> dict:
    """Fetch + parse a feed, ingest new entries (deduped via ``seen``)."""
    with _lock:
        feed = _feeds.get(feed_id)
        if not feed:
            return {"new": 0, "errors": ["no such feed"]}
        url, sid, kind, seen = feed["url"], feed["series_id"], feed["kind"], list(feed["seen"])
        title = (_series.get(sid) or {}).get("title", sid)
    errors: list[str] = []
    new = 0
    try:
        _, raw = download_file(url)
        entries = _parse_feed(raw.decode("utf-8", "replace"), kind)
    except Exception as exc:
        with _lock:
            f = _feeds.get(feed_id)
            if f:
                f["last_poll"] = time.time()
                f["last_status"] = f"error: {exc}"
                _persist()
        return {"new": 0, "errors": [str(exc)]}

    for entry in entries:
        key = entry.get("guid") or entry.get("url")
        if not key or key in seen:
            continue
        try:
            filename, data = download_file(entry["url"])
            _store_file(title, filename or entry.get("title") or "issue", data,
                        source="feed", source_ref=feed_id, series_id=sid)
            seen.append(key)
            new += 1
        except Exception as exc:
            errors.append(f"{entry.get('url')}: {exc}")

    with _lock:
        f = _feeds.get(feed_id)
        if f:
            f["seen"] = seen
            f["last_poll"] = time.time()
            f["last_status"] = "ok" if not errors else f"ok ({len(errors)} errors)"
            _persist()
    return {"new": new, "errors": errors}


def remove_feed(feed_id: str) -> bool:
    with _lock:
        if feed_id not in _feeds:
            return False
        sid = _feeds[feed_id]["series_id"]
        del _feeds[feed_id]
        series = _series.get(sid)
        if series and series.get("feed_id") == feed_id:
            series["feed_id"] = None
        _persist()
    return True


def tick(now: float | None = None) -> dict:
    """Poll any feed whose interval has elapsed. Pure + testable."""
    now = now if now is not None else time.time()
    with _lock:
        due = [fid for fid, f in _feeds.items()
               if f.get("enabled") and (now - f.get("last_poll", 0)) >= f["interval_min"] * 60]
    ran: dict = {}
    for fid in due:
        try:
            ran[fid] = poll_feed(fid)
        except Exception as exc:
            ran[fid] = {"new": 0, "errors": [str(exc)]}
    return ran


def _loop() -> None:
    while True:
        time.sleep(60)
        try:
            tick()
        except Exception:
            pass


def start() -> bool:
    """Start the feed auto-updater (no-op unless ``MAYBOT_COMICS`` is on)."""
    global _started
    if _started or not ENABLED:
        return False
    _started = True
    threading.Thread(target=_loop, daemon=True).start()
    return True


# --------------------------------------------------------------------------
# read API
# --------------------------------------------------------------------------
def list_series() -> list[dict]:
    with _lock:
        out = []
        for s in _series.values():
            out.append({"id": s["id"], "title": s["title"], "cover": s.get("cover"),
                        "feed_id": s.get("feed_id"), "updated": s.get("updated"),
                        "issue_count": len(s.get("issues", {}))})
        out.sort(key=lambda x: x["title"].lower())
        return out


def _issue_view(issue: dict) -> dict:
    """Public issue record (drops the internal page_index list)."""
    return {k: v for k, v in issue.items() if k != "page_index"}


def get_series(series_id: str) -> dict | None:
    with _lock:
        s = _series.get(series_id)
        if not s:
            return None
        issues = sorted(s.get("issues", {}).values(), key=lambda i: _natkey(i["id"]))
        return {"id": s["id"], "title": s["title"], "cover": s.get("cover"),
                "feed_id": s.get("feed_id"), "created": s.get("created"),
                "updated": s.get("updated"), "issues": [_issue_view(i) for i in issues]}


def get_issues(series_id: str) -> list[dict]:
    s = get_series(series_id)
    return s["issues"] if s else []


def get_issue(series_id: str, issue_id: str) -> dict | None:
    with _lock:
        s = _series.get(series_id)
        i = s and s.get("issues", {}).get(issue_id)
        return _issue_view(i) if i else None


def _raw_issue(series_id: str, issue_id: str) -> dict | None:
    # Lock-free: mutating callers (set_progress/mark_read/remove_issue) already
    # hold ``_lock`` and must not re-acquire it (Lock is non-reentrant); read-only
    # callers tolerate the atomic dict lookup.
    s = _series.get(series_id)
    return s and s.get("issues", {}).get(issue_id)


def get_issue_pages(series_id: str, issue_id: str) -> dict | None:
    i = _raw_issue(series_id, issue_id)
    if not i:
        return None
    return {"pages": i.get("pages"), "readable": bool(i.get("readable"))}


def issue_file_path(series_id: str, issue_id: str) -> str | None:
    i = _raw_issue(series_id, issue_id)
    if not i:
        return None
    try:
        path = resolve_within_library(series_id, i["file"])
    except ValueError:
        return None
    return path if os.path.isfile(path) else None


def page_bytes(series_id: str, issue_id: str, n: int) -> tuple[bytes, str] | None:
    i = _raw_issue(series_id, issue_id)
    if not i or not i.get("readable"):
        return None
    index = i.get("page_index") or []
    if n < 0 or n >= len(index):
        return None
    path = issue_file_path(series_id, issue_id)
    if not path:
        return None
    try:
        data = _read_archive_entry(path, i["fmt"], index[n])
    except Exception:
        return None
    if data is None:
        return None
    return data, _media_type(index[n])


def cover_path(series_id: str, issue_id: str | None = None) -> str | None:
    with _lock:
        s = _series.get(series_id)
        if not s:
            return None
        issues = s.get("issues", {})
        if issue_id:
            target = issues.get(issue_id)
        else:
            # newest issue with a cover
            target = next((i for i in sorted(issues.values(),
                          key=lambda x: x.get("added", 0), reverse=True) if i.get("cover")), None)
        cover = target and target.get("cover")
        iid = target and target.get("id")
    if not cover or not iid:
        return None
    try:
        path = resolve_within_library(series_id, cover)
    except ValueError:
        return None
    return path if os.path.isfile(path) else None


def mark_read(series_id: str, issue_id: str, read: bool = True) -> bool:
    with _lock:
        i = _raw_issue(series_id, issue_id)
        if not i:
            return False
        i["read"] = bool(read)
        _persist()
    return True


def set_progress(series_id: str, issue_id: str, page: int) -> bool:
    with _lock:
        i = _raw_issue(series_id, issue_id)
        if not i:
            return False
        pages = i.get("pages")
        p = max(0, int(page))
        if pages:
            p = min(p, pages - 1)
            if p >= pages - 1:
                i["read"] = True
        i["last_page"] = p
        _persist()
    return True


def remove_issue(series_id: str, issue_id: str) -> bool:
    with _lock:
        i = _raw_issue(series_id, issue_id)
        if not i:
            return False
        for fname in (i.get("file"), i.get("cover")):
            if not fname:
                continue
            try:
                p = resolve_within_library(series_id, fname)
                if os.path.isfile(p):
                    os.remove(p)
            except Exception:
                pass
        del _series[series_id]["issues"][issue_id]
        _persist()
    return True


def remove_series(series_id: str) -> bool:
    with _lock:
        if series_id not in _series:
            return False
        try:
            sdir = resolve_within_library(series_id)
            if os.path.isdir(sdir):
                shutil.rmtree(sdir)
        except Exception:
            pass
        del _series[series_id]
        for fid in [f for f, v in _feeds.items() if v["series_id"] == series_id]:
            del _feeds[fid]
        _persist()
    return True


# --------------------------------------------------------------------------
# offline-first: bulk download + export-to-SSD
# --------------------------------------------------------------------------
def _iter_selected(series_id: str | None, issues: list[str] | None):
    """Yield (abs_path, arcname) for the selection. Every path is traversal-checked."""
    with _lock:
        if series_id:
            sids = [series_id] if series_id in _series else []
        else:
            sids = list(_series.keys())
        plan = []
        for sid in sids:
            s = _series[sid]
            for iid, issue in s.get("issues", {}).items():
                if issues and iid not in issues:
                    continue
                plan.append((sid, issue["file"]))
    for sid, fname in plan:
        try:
            path = resolve_within_library(sid, fname)
        except ValueError:
            continue
        if os.path.isfile(path):
            yield path, f"{sid}/{fname}"


class _StreamBuffer:
    """File-like sink that hands written bytes off to the generator."""

    def __init__(self):
        self._buf = bytearray()

    def write(self, b):
        self._buf += b
        return len(b)

    def flush(self):
        pass

    def take(self) -> bytes:
        data = bytes(self._buf)
        self._buf.clear()
        return data


def bundle_stream(series_id: str | None = None,
                  issues: list[str] | None = None) -> Iterator[bytes]:
    """Stream a ZIP of the selection in constant memory (ZIP_STORED — comics are
    already compressed). ``series_id=None`` ⇒ whole library; ``issues`` ⇒ subset.
    """
    buf = _StreamBuffer()
    zf = zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED, allowZip64=True)
    try:
        for path, arcname in _iter_selected(series_id, issues):
            with zf.open(arcname, "w") as dest, open(path, "rb") as src:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    dest.write(chunk)
                    data = buf.take()
                    if data:
                        yield data
            data = buf.take()
            if data:
                yield data
    finally:
        zf.close()
    data = buf.take()
    if data:
        yield data


def export_enabled() -> bool:
    return bool(EXPORT_DIRS)


def validate_export_dest(dest: str) -> str:
    """Realpath + commonpath membership check against the export allow-list."""
    if not EXPORT_DIRS:
        raise PermissionError("comics export disabled: set MAYBOT_COMICS_EXPORT_DIRS")
    real = os.path.realpath(dest)
    for base in EXPORT_DIRS:
        if real == base or os.path.commonpath([base, real]) == base:
            return real
    raise PermissionError("destination not in MAYBOT_COMICS_EXPORT_DIRS allow-list")


def _up_to_date(src: str, dst: str) -> bool:
    if not os.path.isfile(dst):
        return False
    try:
        s, d = os.stat(src), os.stat(dst)
        return s.st_size == d.st_size and int(s.st_mtime) == int(d.st_mtime)
    except Exception:
        return False


def export_to(dest: str, series_id: str | None = None) -> dict:
    """Copy/sync the library (or one series) to an approved external mount.

    Idempotent: a file already present with the same size+mtime is skipped, so
    re-running before a trip only copies what changed.
    """
    real_dest = validate_export_dest(dest)
    copied, skipped = [], []
    for src, arcname in _iter_selected(series_id, None):
        out = os.path.join(real_dest, arcname)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if _up_to_date(src, out):
            skipped.append(arcname)
            continue
        shutil.copy2(src, out)
        copied.append(arcname)
    return {"dest": real_dest, "copied": len(copied), "skipped": len(skipped), "files": copied}


# --------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------
def snapshot() -> dict:
    rarfile_ok = False
    try:
        import rarfile  # noqa: F401
        rarfile_ok = True
    except Exception:
        pass
    with _lock:
        series_count = len(_series)
        issue_count = sum(len(s.get("issues", {})) for s in _series.values())
        feeds = [{"id": f["id"], "url": f["url"], "series_id": f["series_id"],
                  "enabled": f["enabled"], "interval_min": f["interval_min"],
                  "last_poll": f["last_poll"] or None, "last_status": f["last_status"]}
                 for f in _feeds.values()]
    return {
        "enabled": ENABLED,
        "base_dir": BASE_DIR,
        "series_count": series_count,
        "issue_count": issue_count,
        "feeds": feeds,
        "export_enabled": export_enabled(),
        "deps": {"rarfile": rarfile_ok},
    }
