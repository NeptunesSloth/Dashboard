"""HTTP client the control center uses to reach each agent host.

Optional, opt-in mutual TLS (client certificates) is supported for the
control center ↔ agent link via environment variables. Everything below is
OFF by default — with none of these set, the client behaves exactly as before
(``requests`` default verification, no client certificate presented):

  * ``MAYBOT_AGENT_CA`` — path to a CA bundle (PEM) used to VERIFY each agent's
    server certificate. Sets ``session.verify``. Unset => default verification.
  * ``MAYBOT_AGENT_CLIENT_CERT`` + ``MAYBOT_AGENT_CLIENT_KEY`` — the client
    certificate/key the control center PRESENTS to the agent (mutual TLS).
    Sets ``session.cert = (cert, key)``. Both must be set together; if only one
    is provided it's ignored (a warning is logged) and no client cert is used.

Agent (server) side — DEPLOYMENT CONFIG, not changed in code. To require client
certs, launch the agent's uvicorn with TLS + client-cert verification, e.g.::

    uvicorn maybot_agent.app:app --host 0.0.0.0 --port 8100 \
        --ssl-certfile  /path/server.crt \
        --ssl-keyfile   /path/server.key \
        --ssl-ca-certs  /path/ca.crt \
        --ssl-cert-reqs 2          # ssl.CERT_REQUIRED — verify the client cert

(and point the agents at ``https://`` URLs in devices.yaml). Enforcement of
client certs happens on the agent/uvicorn side; this module only configures
what the control center verifies and presents.
"""
import asyncio
import logging
import os

import httpx
import requests

_log = logging.getLogger("maybot_control_center.agent_client")


def _configure_tls(session: requests.Session) -> requests.Session:
    """Apply opt-in TLS settings to ``session`` from the environment.

    Off by default and re-runnable (pure function of the env + the passed
    session) so it's easy to test. Returns the same session for convenience.

    - ``MAYBOT_AGENT_CA`` -> ``session.verify`` (CA bundle to verify the agent).
    - ``MAYBOT_AGENT_CLIENT_CERT`` + ``MAYBOT_AGENT_CLIENT_KEY`` ->
      ``session.cert`` (client cert/key the control center presents). Both are
      required; a lone half is ignored with a warning rather than crashing.
    """
    ca = os.getenv("MAYBOT_AGENT_CA", "").strip()
    if ca:
        session.verify = ca

    cert = os.getenv("MAYBOT_AGENT_CLIENT_CERT", "").strip()
    key = os.getenv("MAYBOT_AGENT_CLIENT_KEY", "").strip()
    if cert and key:
        session.cert = (cert, key)
    elif cert or key:
        _log.warning(
            "SECURITY: client-cert mTLS not enabled — both MAYBOT_AGENT_CLIENT_CERT "
            "and MAYBOT_AGENT_CLIENT_KEY must be set (got only %s); no client cert "
            "will be presented to agents",
            "MAYBOT_AGENT_CLIENT_CERT" if cert else "MAYBOT_AGENT_CLIENT_KEY",
        )
    return session


_session = _configure_tls(requests.Session())

# Default per-request timeout for polling an agent. A single slow/hung device
# must not stall the whole fleet poll, so each request is capped; a device may
# override with a ``timeout`` field in devices.yaml.
DEFAULT_TIMEOUT = float(os.getenv("MAYBOT_AGENT_TIMEOUT", "5"))


def _device_timeout(device: dict) -> float:
    try:
        t = float(device.get("timeout") or DEFAULT_TIMEOUT)
        return t if t > 0 else DEFAULT_TIMEOUT
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT


def _headers(token: str) -> dict:
    return {"x-api-token": token}


def _wrap(r) -> dict:
    # Accepts any response with ``.status_code``/``.headers``/``.json()`` —
    # works for both ``requests.Response`` and ``httpx.Response`` so the sync
    # and async paths produce identical result shapes.
    is_2xx = 200 <= r.status_code < 300
    is_auth_error = r.status_code in {401, 403}
    payload = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    error = None
    if not is_2xx:
        detail = payload.get("detail") if isinstance(payload, dict) else None
        error = detail or f"http status {r.status_code}"
    return {
        "online": is_2xx,
        "auth_error": is_auth_error,
        "status_code": r.status_code,
        "error": error,
        "data": payload,
    }


def _tunneled(device: dict, endpoint: str, method: str = "GET", body=None, timeout: float | None = None):
    """Route via the reverse tunnel if this host has a live outbound connection;
    returns None to signal "fall back to direct HTTP"."""
    name = device.get("name")
    if not name:
        return None
    from . import tunnel
    if not tunnel.connected(name):
        return None
    return tunnel.call(name, endpoint, method, body, timeout or _device_timeout(device))


def call_agent(device: dict, endpoint: str) -> dict:
    routed = _tunneled(device, endpoint, "GET")
    if routed is not None:
        return routed
    base = device.get("url", "").rstrip("/")
    token = device.get("api_token", "")
    try:
        r = _session.get(f"{base}{endpoint}", headers=_headers(token), timeout=_device_timeout(device))
        return _wrap(r)
    except Exception as exc:
        return {"online": False, "error": str(exc), "data": {}}


def post_agent(device: dict, endpoint: str, timeout: int = 30) -> dict:
    routed = _tunneled(device, endpoint, "POST", None, timeout)
    if routed is not None:
        return routed
    base = device.get("url", "").rstrip("/")
    token = device.get("api_token", "")
    try:
        r = _session.post(f"{base}{endpoint}", headers=_headers(token), timeout=timeout)
        return _wrap(r)
    except Exception as exc:
        return {"online": False, "error": str(exc), "data": {}}


def put_agent(device: dict, endpoint: str, json_body: dict, timeout: int = 15) -> dict:
    routed = _tunneled(device, endpoint, "PUT", json_body, timeout)
    if routed is not None:
        return routed
    base = device.get("url", "").rstrip("/")
    token = device.get("api_token", "")
    try:
        headers = {**_headers(token), "Content-Type": "application/json"}
        r = _session.put(f"{base}{endpoint}", headers=headers, json=json_body, timeout=timeout)
        return _wrap(r)
    except Exception as exc:
        return {"online": False, "error": str(exc), "data": {}}


# ---------------------------------------------------------------------------
# Opt-in async fleet poll (additive — does NOT replace the sync client above).
#
# This is a BOUNDED async building block, not a full async rewrite of the
# control center. Only the fleet-poll read path (``/api/ping`` + ``/api/projects``
# for every device) gets an async variant here; every existing route and the
# sync ``call_agent``/``post_agent``/``put_agent`` helpers are untouched.
#
# Differences from the sync path, on purpose and documented:
#   * NO reverse-tunnel (``_tunneled``) fallback — the async path always does a
#     direct HTTP request. The tunnel is a synchronous, per-host mechanism; the
#     async fleet poll is for direct-HTTP fleets where avoiding thread overhead
#     for large device counts is the win. Tunnelled hosts should keep using the
#     sync ``aggregate()``.
#   * Uses ``httpx.AsyncClient`` instead of ``requests.Session``, but honours the
#     SAME opt-in mTLS env vars (verify CA + client cert/key) and the same
#     per-device timeout, and returns the SAME ``_wrap``-shaped dicts so results
#     are drop-in compatible with ``_fetch_device``.
# ---------------------------------------------------------------------------


def _async_client_kwargs() -> dict:
    """Translate the opt-in mTLS env vars into ``httpx.AsyncClient`` kwargs.

    Mirrors :func:`_configure_tls` (which configures the sync ``requests``
    session). Off by default: with no env vars set, returns ``{}`` and httpx
    uses its default verification with no client certificate, matching the sync
    client's default behaviour.
    """
    kwargs: dict = {}
    ca = os.getenv("MAYBOT_AGENT_CA", "").strip()
    if ca:
        kwargs["verify"] = ca

    cert = os.getenv("MAYBOT_AGENT_CLIENT_CERT", "").strip()
    key = os.getenv("MAYBOT_AGENT_CLIENT_KEY", "").strip()
    if cert and key:
        kwargs["cert"] = (cert, key)
    elif cert or key:
        _log.warning(
            "SECURITY: client-cert mTLS not enabled (async) — both "
            "MAYBOT_AGENT_CLIENT_CERT and MAYBOT_AGENT_CLIENT_KEY must be set "
            "(got only %s); no client cert will be presented to agents",
            "MAYBOT_AGENT_CLIENT_CERT" if cert else "MAYBOT_AGENT_CLIENT_KEY",
        )
    return kwargs


async def call_agent_async(client, device: dict, endpoint: str) -> dict:
    """Async analogue of :func:`call_agent` for a single GET, using a shared
    ``httpx.AsyncClient``.

    Returns the same ``_wrap``-shaped dict (``online``/``auth_error``/
    ``status_code``/``error``/``data``) as the sync client, or the same
    ``{"online": False, "error": ..., "data": {}}`` on transport failure.
    Direct HTTP only — no reverse-tunnel fallback (see module note above).
    """
    base = device.get("url", "").rstrip("/")
    token = device.get("api_token", "")
    try:
        r = await client.get(
            f"{base}{endpoint}",
            headers=_headers(token),
            timeout=_device_timeout(device),
        )
        return _wrap(r)
    except Exception as exc:
        return {"online": False, "error": str(exc), "data": {}}


async def _fetch_device_async(client, device: dict) -> dict:
    """Fetch ``/api/ping`` then (if reachable) ``/api/projects`` for one device.

    Returns the raw ping/projects responses so the aggregator can apply the
    exact same row-shaping logic the sync ``_fetch_device`` uses — keeping the
    network concern (here) separate from the post-processing concern (there).
    """
    ping = await call_agent_async(client, device, "/api/ping")
    reachable = bool(ping.get("online"))
    proj_resp = await call_agent_async(client, device, "/api/projects") if reachable else {}
    return {"device": device, "ping": ping, "proj_resp": proj_resp}


async def gather_fleet(devices: list[dict]) -> list[dict]:
    """Concurrently poll ``/api/ping`` + ``/api/projects`` for every device.

    Uses a single shared ``httpx.AsyncClient`` (so connection pooling and the
    opt-in mTLS settings apply across the whole fleet) and ``asyncio.gather``
    for concurrency — no thread pool. The win over the sync
    ``ThreadPoolExecutor`` path is avoiding thread overhead for large fleets.

    Returns one ``{"device", "ping", "proj_resp"}`` record per device, in the
    same order as ``devices``. Callers (see ``aggregator.aggregate_async``) turn
    these into the ``(device_row, projects)`` tuples that mirror the sync
    ``_fetch_device`` output.
    """
    if not devices:
        return []
    async with httpx.AsyncClient(**_async_client_kwargs()) as client:
        return await asyncio.gather(
            *(_fetch_device_async(client, d) for d in devices)
        )
