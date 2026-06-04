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
