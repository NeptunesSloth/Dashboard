from pathlib import Path
import logging
import os
import tempfile
import yaml


def _atomic_write(path: Path, text: str) -> None:
    """Write text atomically with a UNIQUE temp file, so concurrent writers can
    never tear each other's output (a shared .tmp name corrupts the file)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass

_log = logging.getLogger("maybot_control_center")

DEVICES_FILE = Path(os.getenv("MAYBOT_DEVICES_FILE", "devices.yaml"))
CONTROL_CENTER_TOKEN = os.getenv("MAYBOT_CONTROL_CENTER_TOKEN", "")

if not CONTROL_CENTER_TOKEN:
    _log.warning("SECURITY: MAYBOT_CONTROL_CENTER_TOKEN is not set — the dashboard API is publicly accessible without authentication")


def load_devices() -> list[dict]:
    if not DEVICES_FILE.exists():
        return []
    try:
        data = yaml.safe_load(DEVICES_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        _log.warning("devices.yaml could not be parsed — treating as empty")
        return []
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
    _atomic_write(DEVICES_FILE, text)


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
