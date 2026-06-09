"""Shared request helpers used by the app and its routers.

Auth/role gates, per-project ACL, device resolution, and the safe-name pattern
live here (not in ``app.py``) so domain routers (``routers/*``) can import them
without importing the FastAPI app — avoiding circular imports as routes are
extracted out of the monolith. ``app.py`` re-exports these under their original
``_`` names for backward compatibility.
"""
from __future__ import annotations

import re

from fastapi import Header, HTTPException

from . import authz
from .config import all_devices

# A safe device/project name component.
SAFE_NAME = re.compile(r'^[a-zA-Z0-9_\-\.]{1,128}$')


def role(token: str) -> str:
    r = authz.role_for(token)
    if r is None:
        raise HTTPException(status_code=401, detail="invalid control token")
    return r


def check_token(x_control_token: str = Header(default="")):
    """Any valid role (viewer or operator)."""
    role(x_control_token)


def check_operator(x_control_token: str = Header(default="")):
    """Operator role required for mutating actions."""
    if role(x_control_token) != "operator":
        raise HTTPException(status_code=403, detail="operator role required")


def check_project_access(token: str, device: str, project: str):
    """Per-project ACL gate (no-op unless a user declares a `projects` list)."""
    if not authz.can_access_project(token, device, project):
        raise HTTPException(status_code=403, detail="not authorized for this project")


def resolve_device(device_name: str):
    device = next((d for d in all_devices() if d.get("name") == device_name), None)
    if not device:
        raise HTTPException(404, "device not found")
    return device
