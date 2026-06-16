"""Comics Library API routes.

Mounted by ``app.py`` via ``include_router``. Reads use the control token;
mutations (upload, ingest, feeds, export, delete) require the operator role.
Path params are validated against ``deps.SAFE_NAME``; file serving is guarded
against traversal inside :mod:`comics` (``resolve_within_library``).
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

from .. import comics
from ..deps import SAFE_NAME as _SAFE_NAME
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token

router = APIRouter()


def _name(x: str) -> str:
    if not _SAFE_NAME.match(x or ""):
        raise HTTPException(404, "not found")
    return x


class IngestUrlIn(BaseModel):
    series_title: str
    url: str


class FeedIn(BaseModel):
    url: str
    series_title: str
    interval_min: float | None = None


class ProgressIn(BaseModel):
    page: int


class ReadIn(BaseModel):
    read: bool = True


class ExportIn(BaseModel):
    dest: str
    series: str | None = None


# ---- browse (read) ----
@router.get("/api/comics")
def comics_index(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    snap = comics.snapshot()
    snap["series"] = comics.list_series()
    return snap


@router.get("/api/comics/bundle")
def comics_library_bundle(x_control_token: str = Header(default="")):
    # Registered before /api/comics/{series} so "bundle" isn't read as a series.
    _check_token(x_control_token)
    return StreamingResponse(
        comics.bundle_stream(None, None), media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="comics-library.zip"'})


@router.get("/api/comics/{series}")
def comics_series(series: str, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    s = comics.get_series(_name(series))
    if not s:
        raise HTTPException(404, "series not found")
    return s


@router.get("/api/comics/{series}/bundle")
def comics_series_bundle(series: str, issues: str = Query(default=""),
                         x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    _name(series)
    sel = [i for i in (issues.split(",") if issues else []) if i] or None
    return StreamingResponse(
        comics.bundle_stream(series, sel), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{series}.zip"'})


@router.get("/api/comics/{series}/{issue}")
def comics_issue(series: str, issue: str, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    i = comics.get_issue(_name(series), _name(issue))
    if not i:
        raise HTTPException(404, "issue not found")
    return i


@router.get("/api/comics/{series}/{issue}/pages")
def comics_issue_pages(series: str, issue: str, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    p = comics.get_issue_pages(_name(series), _name(issue))
    if p is None:
        raise HTTPException(404, "issue not found")
    return p


@router.get("/api/comics/{series}/{issue}/page/{n}")
def comics_issue_page(series: str, issue: str, n: int,
                      x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    res = comics.page_bytes(_name(series), _name(issue), n)
    if not res:
        raise HTTPException(404, "page not found")
    data, media = res
    return Response(content=data, media_type=media,
                    headers={"Cache-Control": "private, max-age=3600"})


@router.get("/api/comics/{series}/{issue}/cover")
def comics_issue_cover(series: str, issue: str, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    path = comics.cover_path(_name(series), _name(issue))
    if not path:
        raise HTTPException(404, "no cover")
    return FileResponse(path)


@router.get("/api/comics/{series}/{issue}/download")
def comics_issue_download(series: str, issue: str, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    path = comics.issue_file_path(_name(series), _name(issue))
    if not path:
        raise HTTPException(404, "issue not found")
    i = comics.get_issue(series, issue) or {}
    disposition = "inline" if i.get("fmt") == "pdf" else "attachment"
    return FileResponse(path, filename=i.get("file") or f"{issue}",
                        content_disposition_type=disposition)


# ---- ingest / mutate (operator) ----
@router.post("/api/comics/upload")
async def comics_upload(request: Request, series_title: str = Query(...),
                        filename: str = Query(...), x_control_token: str = Header(default="")):
    # Raw-body upload (the file bytes are the request body) so we don't depend on
    # python-multipart — keeping a bare install bootable.
    _check_operator(x_control_token)
    data = await request.body()
    try:
        return comics.ingest_upload(series_title, filename or "upload", data)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/api/comics/ingest-url")
def comics_ingest_url(body: IngestUrlIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return comics.ingest_url(body.series_title, body.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(502, f"download failed: {exc}")


@router.post("/api/comics/feeds")
def comics_add_feed(body: FeedIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return comics.add_feed(body.url, body.series_title, body.interval_min)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/api/comics/feeds/{feed_id}/poll")
def comics_poll_feed(feed_id: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return comics.poll_feed(_name(feed_id))


@router.delete("/api/comics/feeds/{feed_id}")
def comics_remove_feed(feed_id: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not comics.remove_feed(_name(feed_id)):
        raise HTTPException(404, "feed not found")
    return {"ok": True}


@router.post("/api/comics/export")
def comics_export(body: ExportIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    series = _name(body.series) if body.series else None
    try:
        return comics.export_to(body.dest, series)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))


@router.post("/api/comics/{series}/{issue}/progress")
def comics_progress(series: str, issue: str, body: ProgressIn,
                    x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not comics.set_progress(_name(series), _name(issue), body.page):
        raise HTTPException(404, "issue not found")
    return {"ok": True}


@router.post("/api/comics/{series}/{issue}/read")
def comics_mark_read(series: str, issue: str, body: ReadIn,
                     x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not comics.mark_read(_name(series), _name(issue), body.read):
        raise HTTPException(404, "issue not found")
    return {"ok": True}


@router.delete("/api/comics/{series}/{issue}")
def comics_delete_issue(series: str, issue: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not comics.remove_issue(_name(series), _name(issue)):
        raise HTTPException(404, "issue not found")
    return {"ok": True}


@router.delete("/api/comics/{series}")
def comics_delete_series(series: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not comics.remove_series(_name(series)):
        raise HTTPException(404, "series not found")
    return {"ok": True}
