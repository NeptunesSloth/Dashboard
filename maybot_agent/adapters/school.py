"""School / LMS adapter — domain-aware health for a learning platform.

Surfaces enrolment and coursework health (students, active courses, assignments
due, overdue items, pass rate, attendance) and pages when work is overdue or
outcomes slip below target.

Config (``projects.yaml``) knobs, all optional:
  * ``query_url``       — HTTP(S) endpoint returning JSON. Recognised keys
                          (with aliases): students/enrolled, courses/active_courses,
                          assignments_due/due, overdue/overdue_assignments,
                          pass_rate/pass_pct, attendance/attendance_pct.
  * ``min_pass_rate``   — warn when pass rate (%) drops below this (default 60).
  * ``min_attendance``  — warn when attendance (%) drops below this (default 70).
  * ``metrics``         — static fallback metrics merged in when nothing is live.

Pass/attendance values may be given as 0..1 fractions or 0..100 percentages;
both are normalised to a percentage for display and thresholds.
"""
from __future__ import annotations

import time

from .base import base_project


def _coalesce(d: dict, *keys):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _as_pct(v):
    """Normalise a rate to a 0..100 percentage; pass through non-numbers."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return round(f * 100, 1) if 0 <= f <= 1 else round(f, 1)


def _fetch(url: str) -> tuple[bool, dict, str | None]:
    try:
        import requests
        r = requests.get(url, timeout=5)
        payload = r.json() if "application/json" in r.headers.get("content-type", "") else {}
        ok = 200 <= r.status_code < 300
        return ok, (payload if isinstance(payload, dict) else {}), (None if ok else f"http {r.status_code}")
    except Exception as exc:
        return False, {}, str(exc)


def adapt(project: dict) -> dict:
    data = base_project(project)
    metrics = data.get("metrics", {})
    static = project.get("metrics", {}) or {}

    try:
        min_pass = float(project.get("min_pass_rate", 60))
    except (TypeError, ValueError):
        min_pass = 60.0
    try:
        min_att = float(project.get("min_attendance", 70))
    except (TypeError, ValueError):
        min_att = 70.0

    school = {
        "students": "unknown",
        "active_courses": "unknown",
        "assignments_due": "unknown",
        "overdue": "unknown",
        "pass_rate_pct": "unknown",
        "attendance_pct": "unknown",
        "last_check_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    query_url = project.get("query_url")
    if query_url:
        ok, payload, err = _fetch(query_url)
        if ok:
            school["students"] = _coalesce(payload, "students", "enrolled", "student_count")
            school["active_courses"] = _coalesce(payload, "courses", "active_courses", "course_count")
            school["assignments_due"] = _coalesce(payload, "assignments_due", "due", "due_count")
            school["overdue"] = _coalesce(payload, "overdue", "overdue_assignments", "late")
            pr = _coalesce(payload, "pass_rate", "pass_pct", "passing_rate")
            school["pass_rate_pct"] = _as_pct(pr) if pr is not None else "unknown"
            at = _coalesce(payload, "attendance", "attendance_pct", "attendance_rate")
            school["attendance_pct"] = _as_pct(at) if at is not None else "unknown"
        else:
            data["alerts"].append(f"WARNING: LMS status query failed: {err}")

    # Static fallback for anything not measured live.
    for live_key, static_key in (("students", "students"), ("active_courses", "active_courses"),
                                 ("assignments_due", "assignments_due"), ("overdue", "overdue")):
        if school[live_key] in (None, "unknown") and static_key in static:
            school[live_key] = static[static_key]
    if school["pass_rate_pct"] in (None, "unknown") and "pass_rate" in static:
        school["pass_rate_pct"] = _as_pct(static["pass_rate"])
    if school["attendance_pct"] in (None, "unknown") and "attendance" in static:
        school["attendance_pct"] = _as_pct(static["attendance"])
    for k, v in list(school.items()):
        if v is None:
            school[k] = "unknown"

    # Outcome heuristics (only when numeric).
    try:
        if isinstance(school["overdue"], (int, float)) and school["overdue"] > 0:
            data["alerts"].append(f"WARNING: {int(school['overdue'])} overdue assignment(s)")
    except Exception:
        pass
    try:
        if isinstance(school["pass_rate_pct"], (int, float)) and school["pass_rate_pct"] < min_pass:
            data["alerts"].append(f"WARNING: pass rate {school['pass_rate_pct']}% below target {min_pass}%")
    except Exception:
        pass
    try:
        if isinstance(school["attendance_pct"], (int, float)) and school["attendance_pct"] < min_att:
            data["alerts"].append(f"WARNING: attendance {school['attendance_pct']}% below target {min_att}%")
    except Exception:
        pass

    metrics.update(school)
    data["metrics"] = metrics
    if any("ERROR" in a for a in data["alerts"]):
        data["health"] = "error"
    elif data["alerts"]:
        data["health"] = "warning"
    return data
