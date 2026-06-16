"""Comics Library: ingest, reader, feeds, bulk download, and SSD export.

Never touches the network — ``comics.download_file`` is monkeypatched. CBZ files
are built in-memory with ``zipfile``; page bytes are opaque (the reader serves
them as-is), so the entries need only the right extension.
"""
import io
import os
import zipfile

import pytest
from fastapi.testclient import TestClient

from maybot_control_center import authz, comics, store
from maybot_control_center.app import app

client = TestClient(app)


def make_cbz(pages: int = 3) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(1, pages + 1):
            z.writestr(f"{i:03}.png", b"\x89PNG\r\n\x1a\n" + bytes([i] * 4))
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _comics_env(tmp_path, monkeypatch):
    monkeypatch.setattr(comics, "BASE_DIR", str(tmp_path / "lib"))
    monkeypatch.setattr(comics, "EXPORT_DIRS", [])
    store._reset_for_tests("")          # persistence off unless a test enables it
    comics.clear()
    yield
    comics.clear()


# ---- ingest ----
def test_upload_ingest_builds_readable_issue():
    issue = comics.ingest_upload("Amazing Spider-Man", "issue-1.cbz", make_cbz(4))
    assert issue["readable"] and issue["pages"] == 4
    assert issue["cover"] and issue["fmt"] == "cbz"
    sid = "amazing-spider-man"
    assert os.path.isfile(os.path.join(comics.BASE_DIR, sid, issue["file"]))
    assert comics.list_series()[0]["issue_count"] == 1


def test_upload_rejects_unknown_type():
    with pytest.raises(ValueError):
        comics.ingest_upload("Bad", "notes.txt", b"hello")


def test_page_serving_and_out_of_range():
    comics.ingest_upload("Series A", "ch1.cbz", make_cbz(3))
    r = client.get("/api/comics/series-a/ch1/page/0")
    assert r.status_code == 200 and r.content.startswith(b"\x89PNG")
    assert r.headers["content-type"].startswith("image/png")
    assert client.get("/api/comics/series-a/ch1/page/99").status_code == 404


def test_download_returns_original_bytes():
    data = make_cbz(2)
    comics.ingest_upload("Series B", "ch1.cbz", data)
    r = client.get("/api/comics/series-b/ch1/download")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert r.content == data


def test_ingest_url_mocked(monkeypatch):
    monkeypatch.setattr(comics, "download_file", lambda url: ("ch5.cbz", make_cbz(2)))
    r = client.post("/api/comics/ingest-url", json={"series_title": "URL Series", "url": "https://x.test/ch5.cbz"})
    assert r.status_code == 200 and r.json()["pages"] == 2


def test_ingest_url_bad_scheme_or_ext():
    assert client.post("/api/comics/ingest-url", json={"series_title": "S", "url": "ftp://x/a.cbz"}).status_code == 400
    assert client.post("/api/comics/ingest-url", json={"series_title": "S", "url": "https://x/page.html"}).status_code == 400


# ---- feeds / auto-update ----
def _feed_xml(*urls: str) -> str:
    items = "".join(
        f'<item><title>Ch {i}</title><guid>{u}</guid><enclosure url="{u}"/></item>'
        for i, u in enumerate(urls))
    return f'<?xml version="1.0"?><rss><channel>{items}</channel></rss>'


def test_feed_poll_ingests_and_dedupes(monkeypatch):
    feed = comics.add_feed("https://x.test/feed.xml", "Feed Series")
    urls = ["https://x.test/a.cbz", "https://x.test/b.cbz"]

    def fake_dl(url):
        if url.endswith("feed.xml"):
            return ("feed.xml", _feed_xml(*urls).encode())
        return (os.path.basename(url), make_cbz(2))

    monkeypatch.setattr(comics, "download_file", fake_dl)
    first = comics.poll_feed(feed["id"])
    assert first["new"] == 2 and not first["errors"]
    # second poll: same entries are already seen → nothing new
    assert comics.poll_feed(feed["id"])["new"] == 0
    assert comics.get_series("feed-series")["issues"].__len__() == 2


def test_tick_respects_interval(monkeypatch):
    feed = comics.add_feed("https://x.test/feed.xml", "Tick Series", interval_min=60)
    calls = []
    monkeypatch.setattr(comics, "poll_feed", lambda fid: calls.append(fid) or {"new": 0, "errors": []})
    comics.tick(now=0)                       # last_poll is 0, but now=0 → not due
    assert calls == []
    comics.tick(now=10_000)                  # well past 60 min → due
    assert calls == [feed["id"]]


# ---- progress / read ----
def test_progress_and_mark_read():
    comics.ingest_upload("Prog", "ch1.cbz", make_cbz(5))
    assert client.post("/api/comics/prog/ch1/progress", json={"page": 2}).status_code == 200
    assert comics.get_issue("prog", "ch1")["last_page"] == 2
    # progress to the last page marks it read
    client.post("/api/comics/prog/ch1/progress", json={"page": 4})
    assert comics.get_issue("prog", "ch1")["read"] is True


# ---- auth ----
def test_read_requires_token_when_auth_active(monkeypatch):
    monkeypatch.setattr(authz, "role_for", lambda t: None)
    assert client.get("/api/comics").status_code == 401


def test_mutations_require_operator(monkeypatch):
    comics.ingest_upload("Sec", "ch1.cbz", make_cbz(2))
    monkeypatch.setattr(authz, "role_for", lambda t: "viewer")
    assert client.get("/api/comics").status_code == 200          # reads allowed
    assert client.delete("/api/comics/sec").status_code == 403   # mutation denied


# ---- path traversal ----
def test_traversal_rejected():
    assert client.get("/api/comics/..%2f..%2fetc/passwd").status_code == 404
    with pytest.raises(ValueError):
        comics.resolve_within_library("..", "..", "etc", "passwd")


# ---- bulk download ----
def _read_zip(chunks) -> list[str]:
    data = b"".join(chunks)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.namelist()


def test_bundle_stream_series_and_library_and_select():
    comics.ingest_upload("Bundle X", "a.cbz", make_cbz(2))
    comics.ingest_upload("Bundle X", "b.cbz", make_cbz(2))
    comics.ingest_upload("Bundle Y", "c.cbz", make_cbz(2))

    series_names = _read_zip(comics.bundle_stream("bundle-x"))
    assert sorted(series_names) == ["bundle-x/a.cbz", "bundle-x/b.cbz"]

    lib_names = _read_zip(comics.bundle_stream(None))
    assert "bundle-y/c.cbz" in lib_names and len(lib_names) == 3

    sel = _read_zip(comics.bundle_stream("bundle-x", issues=["a"]))
    assert sel == ["bundle-x/a.cbz"]


def test_bundle_route_streams():
    comics.ingest_upload("RouteZ", "a.cbz", make_cbz(2))
    r = client.get("/api/comics/routez/bundle")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert z.namelist() == ["routez/a.cbz"]


# ---- export to SSD (allow-list path guard) ----
def test_validate_export_dest(tmp_path, monkeypatch):
    ssd = tmp_path / "ssd"
    ssd.mkdir()
    monkeypatch.setattr(comics, "EXPORT_DIRS", [os.path.realpath(str(ssd))])
    assert comics.validate_export_dest(str(ssd / "sub")) == os.path.realpath(str(ssd / "sub"))
    with pytest.raises(PermissionError):
        comics.validate_export_dest(str(tmp_path / "elsewhere"))
    with pytest.raises(PermissionError):
        comics.validate_export_dest(str(ssd / ".." / ".." / "etc"))


def test_validate_export_disabled_when_unset():
    with pytest.raises(PermissionError):
        comics.validate_export_dest("/anywhere")


def test_export_copies_then_skips(tmp_path, monkeypatch):
    ssd = tmp_path / "ssd"
    ssd.mkdir()
    monkeypatch.setattr(comics, "EXPORT_DIRS", [os.path.realpath(str(ssd))])
    comics.ingest_upload("ExpSeries", "a.cbz", make_cbz(2))
    first = comics.export_to(str(ssd))
    assert first["copied"] == 1 and first["skipped"] == 0
    assert os.path.isfile(os.path.join(str(ssd), "expseries", "a.cbz"))
    second = comics.export_to(str(ssd))      # idempotent: same size+mtime
    assert second["copied"] == 0 and second["skipped"] == 1


def test_export_route_403_for_disallowed_dest():
    assert client.post("/api/comics/export", json={"dest": "/etc"}).status_code == 403


# ---- persistence round-trip ----
def test_metadata_persists(tmp_path):
    store._reset_for_tests(":memory:")
    store.init()
    try:
        comics.ingest_upload("Persist Me", "ch1.cbz", make_cbz(3))
        comics.clear()
        assert comics.list_series() == []
        comics.load_persisted()
        s = comics.get_series("persist-me")
        assert s and s["issues"][0]["pages"] == 3
    finally:
        store._reset_for_tests("")


# ---- remove ----
def test_remove_issue_and_series():
    comics.ingest_upload("Gone", "ch1.cbz", make_cbz(2))
    sid, sdir = "gone", os.path.join(comics.BASE_DIR, "gone")
    assert comics.remove_issue(sid, "ch1") is True
    assert comics.get_series(sid)["issues"] == []
    comics.ingest_upload("Gone", "ch2.cbz", make_cbz(2))
    assert comics.remove_series(sid) is True
    assert comics.get_series(sid) is None
    assert not os.path.isdir(sdir)
