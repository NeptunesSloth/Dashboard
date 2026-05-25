from pathlib import Path
import yaml
import os

DEVICES_FILE = Path(os.getenv("MAYBOT_DEVICES_FILE", "devices.yaml"))


def load_devices() -> list[dict]:
    if not DEVICES_FILE.exists():
        return []
    with DEVICES_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    devices = data.get("devices", [])
    return devices if isinstance(devices, list) else []
