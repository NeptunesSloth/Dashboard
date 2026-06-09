from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from .agent_client import call_agent, gather_fleet
from .notifier import check_and_notify
from . import history
from . import incidents

try:
    from maybot_agent import __version__ as LATEST_AGENT_VERSION
except Exception:  # pragma: no cover - agent package always ships alongside
    LATEST_AGENT_VERSION = "1.0"

_last_summary: dict = {}


def last_summary() -> dict:
    return dict(_last_summary)


def _num(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def _shape_device(d: dict, ping: dict, proj_resp: dict) -> tuple[dict, list[dict]]:
    """Turn raw ping/projects responses into a ``(device_row, projects)`` tuple.

    Shared by the sync ``_fetch_device`` and the async ``aggregate_async`` so
    both paths produce identical row/project shapes — only the transport
    (sync ``requests`` vs async ``httpx``) differs.
    """
    reachable = bool(ping.get("online"))
    auth_error = bool(proj_resp.get("auth_error"))
    online = reachable and not auth_error
    # The agent reports its version in the (already-made) ping payload — capture
    # it here so the fleet can flag hosts running an outdated agent (no extra call).
    version = (ping.get("data") or {}).get("version") if reachable else None
    device_row = {
        "name": d.get("name", "unknown"),
        "online": online,
        "auth_error": auth_error,
        "version": version,
        "agent_outdated": bool(version) and version != LATEST_AGENT_VERSION,
        "status_code": proj_resp.get("status_code", ping.get("status_code", "unknown")) if reachable else ping.get("status_code", "unknown"),
        "error": (proj_resp.get("error") if auth_error else ping.get("error")),
        "url": d.get("url", "unknown"),
    }
    projects: list[dict] = []
    if online:
        p = proj_resp.get("data", [])
        if isinstance(p, list):
            for pr in p:
                pr["device"] = d.get("name", "unknown")
                projects.append(pr)
    return device_row, projects


def _fetch_device(d: dict) -> tuple[dict, list[dict]]:
    # /api/ping is unauthenticated (reachability); the API token is enforced on
    # /api/projects, so a wrong/missing token shows up as auth_error there.
    ping = call_agent(d, "/api/ping")
    reachable = bool(ping.get("online"))
    proj_resp = call_agent(d, "/api/projects") if reachable else {}
    return _shape_device(d, ping, proj_resp)


def _finalize(device_rows: list[dict], projects: list[dict], _t0: float) -> dict:
    """Post-processing shared by the sync ``aggregate`` and async
    ``aggregate_async``: build the summary, run notifications/history/incidents,
    annotate projects, and stash the last summary.

    Factored out so the sync and async fleet polls differ ONLY in how they
    gather the network data; everything downstream is identical.
    """
    import time
    summary = {
        "total_devices": len(device_rows),
        "online_devices": sum(1 for x in device_rows if x["online"]),
        "offline_devices": sum(1 for x in device_rows if not x["online"]),
        "agents_outdated": sum(1 for x in device_rows if x.get("agent_outdated")),
        "latest_agent_version": LATEST_AGENT_VERSION,
        "total_projects": len(projects),
        "projects_with_warnings_errors": sum(1 for p in projects if p.get("health") in {"warning", "error"}),
        "bots_running": sum(1 for p in projects if p.get("type") == "trading_bot" and p.get("status") == "running"),
        "total_trading_profit_today": round(sum(_num(p.get("metrics", {}).get("profit_today")) for p in projects if p.get("type") == "trading_bot"), 4),
        "total_trading_profit_this_week": round(sum(_num(p.get("metrics", {}).get("profit_this_week")) for p in projects if p.get("type") == "trading_bot"), 4),
        "total_open_exposure": round(sum(_num(p.get("metrics", {}).get("open_exposure")) for p in projects if p.get("type") == "trading_bot"), 4),
        "tests_failing": sum(1 for p in projects if str(p.get("metrics", {}).get("last_test_result", "")).lower() in {"failed", "error"}),
        "local_ai_hosts_total": sum(1 for p in projects if p.get("type") == "local_ai_host"),
        "local_ai_hosts_online": sum(1 for p in projects if p.get("type") == "local_ai_host" and p.get("metrics", {}).get("status") == "online"),
        "local_ai_hosts_offline": sum(1 for p in projects if p.get("type") == "local_ai_host" and p.get("metrics", {}).get("status") == "offline"),
        "local_ai_hosts_with_errors": sum(1 for p in projects if p.get("type") == "local_ai_host" and p.get("health") in {"warning", "error"}),
    }
    from . import github_repo
    if github_repo.enabled():
        projects.extend(github_repo.collect())  # tracked GitHub repos as projects

    check_and_notify(projects)
    history.record(projects)            # record first so SLO/error-budget see this poll
    history.attach(projects)

    from . import governance, errorbudget, meridians, oaths, escalation, acks
    eb_by_key = {f"{r['device']}:{r['project']}": r for r in errorbudget.snapshot()["projects"]}
    health_by_key = {f"{p.get('device', '?')}:{p.get('name', '?')}": str(p.get("health", "unknown"))
                     for p in projects}
    for p in projects:
        governance.mark_personal(p)     # flag the Ancestor's off-limits personal bots
        errorbudget.annotate(p, eb_by_key)   # error-budget / freeze state
        meridians.annotate(p, health_by_key)  # blocked-meridian (downstream) tag
        oaths.annotate(p)               # incident ownership (sworn oath)
        acks.annotate(p)                # operator acknowledgement / snooze

    incidents.maybe_dispatch(projects)
    try:
        from . import diagnosis
        diagnosis.sweep(projects)        # heuristic root-cause → notifications bell
    except Exception:
        pass
    escalation.sweep()                  # escalate unacknowledged, unsilenced incidents
    _last_summary.clear()
    _last_summary.update(summary)
    try:
        from . import selfcheck
        selfcheck.note_poll((time.perf_counter() - _t0) * 1000, len(device_rows), len(projects))
    except Exception:
        pass
    return {"summary": summary, "devices": device_rows, "projects": projects}


def aggregate(devices: list[dict]) -> dict:
    import time
    _t0 = time.perf_counter()
    device_rows: list[dict] = []
    projects: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(len(devices), 16) or 1) as pool:
        for device_row, device_projects in pool.map(_fetch_device, devices):
            device_rows.append(device_row)
            projects.extend(device_projects)

    return _finalize(device_rows, projects, _t0)


async def aggregate_async(devices: list[dict]) -> dict:
    """Async, opt-in twin of :func:`aggregate` — ADDITIVE building block.

    Gathers the per-device ``/api/ping`` + ``/api/projects`` data concurrently
    with ``httpx.AsyncClient`` (via :func:`agent_client.gather_fleet`) instead of
    a thread pool, then runs the EXACT same post-processing through
    :func:`_finalize`. Result shape is identical to ``aggregate`` (same
    ``summary``/``devices``/``projects`` keys and the same per-row keys).

    Scope: this is a bounded async slice for the fleet-poll READ path only — it
    is NOT a full async rewrite, and it is NOT yet wired into any route. The
    sync ``aggregate`` and the ``/api/overview`` route are unchanged and remain
    the default.

    Caveat: the async path does DIRECT HTTP only (no reverse-tunnel fallback);
    fleets that rely on the reverse tunnel should keep using ``aggregate``.

    Follow-up (not in this change): add an async ``/api/overview`` handler that
    calls ``await aggregate_async(devices)`` when ``MAYBOT_ASYNC_POLL`` is set
    (and direct-HTTP is in use), falling back to ``aggregate`` otherwise.
    """
    import time
    _t0 = time.perf_counter()
    device_rows: list[dict] = []
    projects: list[dict] = []

    for record in await gather_fleet(devices):
        device_row, device_projects = _shape_device(
            record["device"], record["ping"], record["proj_resp"]
        )
        device_rows.append(device_row)
        projects.extend(device_projects)

    return _finalize(device_rows, projects, _t0)
