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
    """Real Proxmox VE backend: clones templates into per-session VMs on an
    isolated VLAN, starts them, and confirms running state via the API. Reports
    ``running`` only when Proxmox confirms every VM is running; ``connect_url``
    stays ``None`` until browser access (Guacamole/noVNC) is wired. Uses the
    mockable client in ``proxmox.py`` so it's testable without a live node."""

    name = "proxmox"
    kind = "hypervisor"

    def _client(self):
        from . import proxmox
        return proxmox.client()

    def configured(self) -> bool:
        return self._client() is not None

    def health(self) -> dict:
        c = self._client()
        if c is None:
            return {"provider": self.name, "status": "not_configured", "configured": False,
                    "detail": "Proxmox config missing — set MAYBOT_PROXMOX_URL / _TOKEN / _NODE."}
        # 'ok' ONLY after a live reachability check against the node.
        try:
            ver = c.version()
            v = ver.get("version") if isinstance(ver, dict) else ""
            return {"provider": self.name, "status": "ok", "configured": True,
                    "detail": f"Proxmox reachable (version {v})."}
        except Exception as exc:
            return {"provider": self.name, "status": "error", "configured": True,
                    "detail": f"Proxmox configured but unreachable: {exc}"}

    def _used_vlans(self) -> set[int]:
        return {int(s.get("meta", {}).get("vlan")) for s in _state["sessions"].values()
                if s.get("meta", {}).get("vlan")}

    def _alloc_vlan(self):
        from . import proxmox
        used = self._used_vlans()
        for v in range(proxmox.VLAN_MIN, proxmox.VLAN_MAX + 1):
            if v not in used:
                return v
        raise RuntimeError("no free VLAN in the configured range")

    def _provision_vms(self, c, sid: str, roles: list[tuple], tmap: dict, vlan: int,
                       created: list[dict]) -> None:
        """Clone + isolate + start + confirm running for each VM. Appends every VM
        it creates to ``created`` (even on partial failure) so the caller can roll
        back exactly what was made. Raises on any failure."""
        from . import proxmox
        for role, name in roles:
            src = tmap[str(name)]
            newid = int(c.next_id())
            _event(sid, "clone", "start", f"{name}({src}) -> {newid}")
            c.wait_task(c.clone(src, newid, proxmox.vm_name(sid, role, newid)), proxmox.CLONE_TIMEOUT)
            created.append({"vmid": newid, "role": role, "template": str(name)})
            c.set_net(newid, proxmox.net_config(vlan))
            _event(sid, "network", "ok", f"vmid={newid} bridge={proxmox.LAB_BRIDGE} vlan={vlan} fw=on")
        for vm in created:
            _event(sid, "start", "begin", f"vmid={vm['vmid']}")
            c.wait_task(c.start(vm["vmid"]), proxmox.START_TIMEOUT)
        for vm in created:
            c.wait_running(vm["vmid"], proxmox.READY_TIMEOUT)   # confirms REAL running state
            _event(sid, "start", "running", f"vmid={vm['vmid']}")

    def _rollback(self, c, created: list[dict]) -> None:
        for vm in created:
            for action in ("stop", "destroy"):
                try:
                    getattr(c, action)(vm["vmid"])
                except Exception:
                    pass

    def launch(self, lab: dict, owner: str) -> dict:
        from . import proxmox
        c = self._client()
        if c is None:
            return {"ok": False, "status": "unavailable",
                    "detail": "Proxmox not configured — set MAYBOT_PROXMOX_URL/_TOKEN/_NODE."}
        tmap = proxmox.template_map()
        roles = ([("attacker", lab.get("attacker_vm"))]
                 + [("target", t) for t in (lab.get("target_vms") or [])])
        roles = [(r, n) for r, n in roles if n]
        missing = sorted({str(n) for _, n in roles if str(n) not in tmap})
        sid = f"sess-{int(time.time()*1000)}"
        if missing:
            _event(sid, "resolve", "failed", f"unmapped templates: {missing}")
            return {"ok": False, "status": "failed", "session_id": sid,
                    "detail": f"templates not mapped to Proxmox VMIDs: {missing} "
                              "(set MAYBOT_PROXMOX_TEMPLATES_FILE / proxmox_templates.yaml)."}
        try:
            vlan = self._alloc_vlan()
        except Exception as exc:
            _event(sid, "network", "failed", str(exc))
            return {"ok": False, "status": "failed", "session_id": sid, "detail": str(exc)}
        created: list[dict] = []
        try:
            self._provision_vms(c, sid, roles, tmap, vlan, created)
        except Exception as exc:
            _event(sid, "provision", "failed", str(exc))
            self._rollback(c, created)
            _event(sid, "rollback", "done", f"removed {len(created)} vm(s)")
            return {"ok": False, "status": "failed", "session_id": sid,
                    "detail": f"provisioning failed and was rolled back: {exc}"}
        connect = proxmox.guacamole_connect_url(sid, created)   # None until browser access exists
        meta = {"vlan": vlan, "node": c.node, "vms": created, "lab": lab,
                "ttl_min": int(lab.get("duration_minutes") or 60)}
        _event(sid, "ready", "running", f"{len(created)} vm(s) on vlan {vlan}; browser_access={'set' if connect else 'not_configured'}")
        return {"ok": True, "session_id": sid, "status": "running",
                "connect_url": connect, "meta": meta,
                "detail": ("VMs running. Browser access (Guacamole/noVNC) is not configured — "
                           "no console URL yet." if not connect else "")}

    def session_status(self, session: dict) -> dict:
        c = self._client()
        vms = session.get("meta", {}).get("vms", [])
        if c is None or not vms:
            return {"status": session.get("status", "unknown")}
        try:
            states = {vm["vmid"]: c.vm_status(vm["vmid"]) for vm in vms}
            running = bool(states) and all(s == "running" for s in states.values())
            return {"status": "running" if running else "degraded", "vm_states": states}
        except Exception as exc:
            return {"status": "unknown", "error": str(exc)}

    def stop(self, session: dict) -> dict:
        from . import proxmox
        c = self._client()
        if c is None:
            return {"ok": False, "status": session.get("status", "unknown")}
        for vm in session.get("meta", {}).get("vms", []):
            try:
                c.wait_task(c.stop(vm["vmid"]), proxmox.START_TIMEOUT)
            except Exception:
                pass
        return {"ok": True, "status": "stopped"}

    def destroy(self, session: dict) -> dict:
        c = self._client()
        if c is None:
            return {"ok": True, "status": "destroyed"}
        self._rollback(c, session.get("meta", {}).get("vms", []))
        return {"ok": True, "status": "destroyed"}

    def reset(self, session: dict) -> dict:
        """Destroy this session's VMs and re-clone the lab into the SAME session
        (same VLAN). Mutates the session's meta in place."""
        from . import proxmox
        c = self._client()
        lab = session.get("meta", {}).get("lab")
        vlan = session.get("meta", {}).get("vlan")
        if c is None or not lab or not vlan:
            return {"ok": False, "status": "failed", "detail": "nothing to reset"}
        sid = session["id"]
        self._rollback(c, session.get("meta", {}).get("vms", []))
        _event(sid, "reset", "recloning", f"vlan {vlan}")
        tmap = proxmox.template_map()
        roles = ([("attacker", lab.get("attacker_vm"))]
                 + [("target", t) for t in (lab.get("target_vms") or [])])
        roles = [(r, n) for r, n in roles if n]
        created: list[dict] = []
        try:
            self._provision_vms(c, sid, roles, tmap, vlan, created)
        except Exception as exc:
            self._rollback(c, created)
            return {"ok": False, "status": "failed", "detail": f"reset failed: {exc}"}
        session["meta"]["vms"] = created
        return {"ok": True, "status": "running"}

    def cleanup_orphans(self, active_ids: set[str]) -> dict:
        """Destroy lab VMs on the node whose session is no longer active."""
        from . import proxmox
        c = self._client()
        if c is None:
            return {"removed": [], "skipped": "not_configured"}
        removed = []
        try:
            for vm in c.list_vms():
                sid = proxmox.session_of(vm.get("name", ""))
                if sid and sid not in active_ids:
                    try:
                        c.stop(vm["vmid"])
                    except Exception:
                        pass
                    try:
                        c.destroy(vm["vmid"])
                        removed.append(vm["vmid"])
                    except Exception:
                        pass
        except Exception as exc:
            return {"removed": removed, "error": str(exc)}
        return {"removed": removed}


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
               "meta": res.get("meta", {}),   # provider state (vm ids, vlan, node) — internal, not exposed
               "created": int(time.time()), "updated": int(time.time())}
    with _lock:
        _state["sessions"][sid] = session
        _save()
    _event(sid, "launch", "started", f"provider={prov.name}")
    return {"ok": True, "lab_id": lab_id, "provider": prov.name, "status": session["status"],
            "session": _public(session), "detail": res.get("detail", "")}


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


# ---------------------------------------------------------------------------
# hygiene: timeout stuck sessions + clean up orphaned VMs
# ---------------------------------------------------------------------------
def reap_stuck_sessions() -> dict:
    """Destroy sessions that have outlived their lab's duration (TTL). Returns the
    session ids reaped."""
    now = int(time.time())
    with _lock:
        stale = [sid for sid, s in _state["sessions"].items()
                 if now - int(s.get("created", now)) > int(s.get("meta", {}).get("ttl_min", 60)) * 60]
    reaped = []
    for sid in stale:
        try:
            destroy_lab(sid)
            _event(sid, "reap", "ttl_expired")
            reaped.append(sid)
        except Exception:
            pass
    return {"reaped": reaped, "count": len(reaped)}


def cleanup_orphans(provider: str | None = None) -> dict:
    """Ask the provider to destroy lab VMs whose session is no longer active
    (e.g. orphaned by a crash). No-op for providers that can't enumerate VMs."""
    prov = get_provider(provider)
    fn = getattr(prov, "cleanup_orphans", None)
    if not callable(fn):
        return {"removed": [], "skipped": "provider_has_no_orphan_cleanup"}
    with _lock:
        active = set(_state["sessions"].keys())
    return fn(active)
