from pathlib import Path
import logging
import yaml
import os

_log = logging.getLogger("maybot_control_center")

DEVICES_FILE = Path(os.getenv("MAYBOT_DEVICES_FILE", "devices.yaml"))
CONTROL_CENTER_TOKEN = os.getenv("MAYBOT_CONTROL_CENTER_TOKEN", "")

if not CONTROL_CENTER_TOKEN:
    _log.warning("SECURITY: MAYBOT_CONTROL_CENTER_TOKEN is not set — the dashboard API is publicly accessible without authentication")


def load_devices() -> list[dict]:
    if not DEVICES_FILE.exists():
        return []
    with DEVICES_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    devices = data.get("devices", [])
    return devices if isinstance(devices, list) else []


def save_devices(devices: list[dict]) -> None:
    """Persist the file-configured agent hosts back to devices.yaml (atomic write).

    Managed from the dashboard's Hosts screen so operators never have to hand-edit
    YAML. Only known fields are written, in a stable order.
    """
    clean: list[dict] = []
    for d in devices:
        if not isinstance(d, dict) or not d.get("name"):
            continue
        entry = {"name": str(d["name"]), "url": str(d.get("url", "")),
                 "api_token": str(d.get("api_token", ""))}
        if d.get("timeout"):
            try:
                entry["timeout"] = float(d["timeout"])
            except (TypeError, ValueError):
                pass
        clean.append(entry)
    header = (
        "# devices.yaml — the agent hosts the control center pulls data FROM.\n"
        "# Managed from the dashboard (Ops -> Hosts); hand-editing also works.\n"
        "# Each host runs maybot_agent; api_token must equal that host's MAYBOT_API_TOKEN.\n"
    )
    text = header + yaml.safe_dump({"devices": clean}, sort_keys=False, default_flow_style=False, allow_unicode=True)
    DEVICES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEVICES_FILE.with_name(DEVICES_FILE.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(DEVICES_FILE)


def all_devices() -> list[dict]:
    """File-configured devices plus any self-registered agents (file wins on name)."""
    devices = load_devices()
    names = {d.get("name") for d in devices}
    try:
        from . import registry
        for d in registry.registered():
            if d.get("name") not in names:
                devices.append(d)
    except Exception:
        pass
    return devices
