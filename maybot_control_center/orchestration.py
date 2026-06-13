"""Cyber-range orchestration control plane (the seam, not the VMs).

The dashboard is a control PANEL: it tells an external hypervisor (Proxmox / ESXi
/ Firecracker / cloud) to launch isolated VM labs and brokers browser access — it
does NOT host VMs. This module is the provider-agnostic seam that the API calls.

Honesty contract (enforced, not aspirational):
- The default provider is ``none`` — every health check returns ``not_configured``
  and every launch is HONESTLY REJECTED. No fake "running" VM is ever recorded.
- The Proxmox provider is an INTERFACE SKELETON: it reports whether its config is
  present, but never claims to have booted a VM, because that driver isn't
  implemented/verified in this build. It returns ``unavailable`` with a clear
  reason. (Wire a real driver + tests before it can return ``running``.)
- No mock success, no placeholder running VMs, no fake browser-console links.

Data model (persisted via ``store``; see docs/CYBER_RANGE_ARCHITECTURE.md §6):
- lab templates + labs        -> ``lab_catalog.yaml`` (config-driven, no hardcoding)
- lab sessions                -> ``_state['sessions']``
- provider config             -> environment (MAYBOT_RANGE_PROVIDER, MAYBOT_PROXMOX_*)
- lifecycle events            -> ``_state['events']``
- validation results          -> ``_state['validations']``
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import yaml

from . import store

LAB_CATALOG_FILE = Path(os.getenv("MAYBOT_LAB_CATALOG_FILE", "lab_catalog.yaml"))

# Honest session lifecycle states. A `none`/unconfigured provider NEVER reaches
# "running" — it stops at "unavailable".
LIFECYCLE = ("requested", "provisioning", "running", "stopped", "reset",
             "failed", "unavailable", "destroyed", "expired")

_lock = threading.RLock()
_state: dict = {"sessions": {}, "events": [], "validations": []}


# ---------------------------------------------------------------------------
# providers
# ---------------------------------------------------------------------------
class RangeProvider:
    """A backend that can launch/stop/reset isolated VM labs. Subclasses MUST NOT
    report a VM as running unless it genuinely is."""

    name = "base"
    kind = "abstract"

    def health(self) -> dict:
        raise NotImplementedError

    def launch(self, lab: dict, owner: str) -> dict:
        raise NotImplementedError

    def session_status(self, session: dict) -> dict:
        return {"status": session.get("status", "unknown")}

    def stop(self, session: dict) -> dict:
        return {"ok": True, "status": "stopped"}

    def reset(self, session: dict) -> dict:
        return {"ok": True, "status": "reset"}

    def destroy(self, session: dict) -> dict:
        return {"ok": True, "status": "destroyed"}


class NullProvider(RangeProvider):
    """The safe default: no infrastructure connected. Every launch is honestly
    rejected; nothing is ever marked running."""

    name = "none"
    kind = "none"

    def health(self) -> dict:
        return {"provider": self.name, "status": "not_configured", "configured": False,
                "detail": "No VM infrastructure is connected. Labs are simulated only; "
                          "connect a hypervisor (see docs/CYBER_RANGE_DEPLOYMENT.md) to run real VMs."}

    def launch(self, lab: dict, owner: str) -> dict:
        return {"ok": False, "status": "unavailable",
                "detail": "Infrastructure not connected — no VM was launched. "
                          "Set MAYBOT_RANGE_PROVIDER and deploy a hypervisor first."}


class ProxmoxProvider(RangeProvider):
    """INTERFACE SKELETON for a future Proxmox VE backend. It reports whether the
    required config is present, but does NOT implement provisioning here, so it
    never claims a VM is running. A real driver (with tests against a live node)
    must replace ``launch`` before this provider can return ``running``."""

    name = "proxmox"
    kind = "hypervisor"

    def _config(self) -> dict:
        return {"url": os.getenv("MAYBOT_PROXMOX_URL", "").strip(),
                "token": os.getenv("MAYBOT_PROXMOX_TOKEN", "").strip(),
                "node": os.getenv("MAYBOT_PROXMOX_NODE", "").strip()}

    def configured(self) -> bool:
        c = self._config()
        return bool(c["url"] and c["token"] and c["node"])

    def health(self) -> dict:
        if not self.configured():
            return {"provider": self.name, "status": "not_configured", "configured": False,
                    "detail": "Proxmox config missing — set MAYBOT_PROXMOX_URL / _TOKEN / _NODE."}
        # Config present, but the provisioning driver is NOT implemented/verified
        # in this build. Be honest: 'unverified', not 'ok'.
        return {"provider": self.name, "status": "unverified", "configured": True,
                "detail": "Proxmox config detected, but the provisioning driver is not implemented or "
                          "verified in this build. Implement + test a real driver before launching VMs."}

    def launch(self, lab: dict, owner: str) -> dict:
        return {"ok": False, "status": "unavailable",
                "detail": "Proxmox provider is an interface skeleton — no driver is implemented in this "
                          "build, so no VM was launched. See docs/CYBER_RANGE_DEPLOYMENT.md."}


_PROVIDERS: dict[str, RangeProvider] = {p.name: p for p in (NullProvider(), ProxmoxProvider())}


def get_provider(name: str | None = None) -> RangeProvider:
    sel = (name or os.getenv("MAYBOT_RANGE_PROVIDER", "none")).strip().lower()
    return _PROVIDERS.get(sel, _PROVIDERS["none"])


def list_providers() -> dict:
    selected = (os.getenv("MAYBOT_RANGE_PROVIDER", "none")).strip().lower()
    return {"selected": selected if selected in _PROVIDERS else "none",
            "providers": [{**p.health(), "name": p.name, "kind": p.kind} for p in _PROVIDERS.values()]}


def provider_health(name: str | None = None) -> dict:
    return get_provider(name).health()


# ---------------------------------------------------------------------------
# lab catalog (config-driven; no hardcoded labs)
# ---------------------------------------------------------------------------
def load_catalog() -> dict:
    if not LAB_CATALOG_FILE.exists():
        return {"templates": [], "labs": []}
    try:
        data = yaml.safe_load(LAB_CATALOG_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return {"templates": [], "labs": []}
    return {"templates": data.get("templates") or [], "labs": data.get("labs") or []}


def list_labs() -> dict:
    cat = load_catalog()
    health = provider_health()
    return {"labs": cat["labs"], "templates": cat["templates"],
            "infrastructure": health, "live": health.get("status") == "ok"}


def _lab(lab_id: str) -> dict | None:
    return next((l for l in load_catalog()["labs"] if str(l.get("lab_id")) == str(lab_id)), None)


# ---------------------------------------------------------------------------
# session lifecycle
# ---------------------------------------------------------------------------
def _event(session_id: str, action: str, outcome: str, detail: str = "") -> None:
    with _lock:
        _state["events"].append({"session": session_id, "action": action, "outcome": outcome,
                                 "detail": detail[:300], "ts": int(time.time())})
        del _state["events"][:-500]
        _save()


def _save() -> None:
    if store.enabled():
        with _lock:
            store.save_state("orchestration", dict(_state))


def load_persisted() -> None:
    data = store.load_state("orchestration")
    if isinstance(data, dict):
        with _lock:
            _state["sessions"] = data.get("sessions") or {}
            _state["events"] = data.get("events") or []
            _state["validations"] = data.get("validations") or []


def launch_lab(lab_id: str, owner: str = "scholar", provider: str | None = None) -> dict:
    """Request a lab. With no real provider this is HONESTLY REJECTED — no running
    session is created and no VM is faked."""
    lab = _lab(lab_id)
    if not lab:
        return {"ok": False, "error": "unknown_lab", "detail": f"no lab '{lab_id}' in the catalog"}
    prov = get_provider(provider)
    health = prov.health()
    res = prov.launch(lab, owner)
    if not res.get("ok"):
        # rejected — record the attempt, but do NOT create a running session.
        sid = f"sess-{int(time.time()*1000)}"
        _event(sid, "launch", "rejected", res.get("detail", ""))
        return {"ok": False, "lab_id": lab_id, "provider": prov.name,
                "provider_status": health.get("status"), "status": res.get("status", "unavailable"),
                "detail": res.get("detail", ""), "session": None}
    # A real provider genuinely booted VMs — record a running session it reported.
    sid = res.get("session_id") or f"sess-{int(time.time()*1000)}"
    session = {"id": sid, "lab_id": lab_id, "owner": owner, "provider": prov.name,
               "status": res.get("status", "provisioning"), "connect_url": res.get("connect_url"),
               "created": int(time.time()), "updated": int(time.time())}
    with _lock:
        _state["sessions"][sid] = session
        _save()
    _event(sid, "launch", "started", f"provider={prov.name}")
    return {"ok": True, "lab_id": lab_id, "provider": prov.name, "status": session["status"],
            "session": _public(session)}


def _public(session: dict) -> dict:
    return {"id": session["id"], "lab_id": session["lab_id"], "owner": session["owner"],
            "provider": session["provider"], "status": session["status"],
            "connect_url": session.get("connect_url"), "created": session.get("created"),
            "updated": session.get("updated")}


def session_status(session_id: str) -> dict:
    with _lock:
        s = _state["sessions"].get(session_id)
    if not s:
        return {"ok": False, "error": "unknown_session", "status": "unknown"}
    prov = get_provider(s.get("provider"))
    live = prov.session_status(s)
    return {"ok": True, **_public(s), "live_status": live.get("status")}


def _transition(session_id: str, action: str) -> dict:
    with _lock:
        s = _state["sessions"].get(session_id)
    if not s:
        return {"ok": False, "error": "unknown_session"}
    prov = get_provider(s.get("provider"))
    res = getattr(prov, action)(s)
    new = {"stop": "stopped", "reset": "reset", "destroy": "destroyed"}[action]
    with _lock:
        s["status"] = res.get("status", new)
        s["updated"] = int(time.time())
        if action == "destroy":
            _state["sessions"].pop(session_id, None)
        _save()
    _event(session_id, action, "ok")
    return {"ok": True, "session_id": session_id, "status": res.get("status", new)}


def stop_lab(session_id: str) -> dict:
    return _transition(session_id, "stop")


def reset_lab(session_id: str) -> dict:
    return _transition(session_id, "reset")


def destroy_lab(session_id: str) -> dict:
    return _transition(session_id, "destroy")


def list_sessions(owner: str | None = None) -> dict:
    with _lock:
        ss = [_public(s) for s in _state["sessions"].values()
              if owner is None or s.get("owner") == owner]
    return {"sessions": ss, "count": len(ss)}


def record_validation(session_id: str, condition: str, passed: bool, evidence: dict | None = None) -> dict:
    """Deterministic validation result for a session (the validation ENGINE that
    verifies real evidence — AI never decides correctness)."""
    rec = {"session": session_id, "condition": str(condition), "passed": bool(passed),
           "evidence": evidence or {}, "ts": int(time.time())}
    with _lock:
        _state["validations"].append(rec)
        del _state["validations"][:-500]
        _save()
    return rec


def events(limit: int = 50) -> list[dict]:
    with _lock:
        return [dict(e) for e in _state["events"][-limit:][::-1]]
