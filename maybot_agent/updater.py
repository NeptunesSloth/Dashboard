"""Self-update: re-pull the agent bundle from the control center and restart.

Triggered by the dashboard (over the tunnel or direct HTTP) via
``POST /api/self-update``. The bundle is the same one the installer uses, served
from ``{control}/agent-bundle.tgz`` — so an update is "fetch + extract over
ourselves + restart". Under systemd (the installer default) exiting brings us
back via ``Restart=always``; otherwise we re-exec the process.
"""
from __future__ import annotations

import io
import os
import sys
import tarfile
import threading
import time
import urllib.request
from pathlib import Path

from . import __version__ as AGENT_VERSION


def _target_dir() -> Path:
    """The install dir (parent of the maybot_agent package) we extract into."""
    return Path(__file__).resolve().parent.parent


def _download(url: str, timeout: float = 60.0) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (operator-supplied URL)
        return r.read()


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract, refusing any member that would escape ``dest`` (path traversal)."""
    dest = dest.resolve()
    for m in tar.getmembers():
        if not (dest / m.name).resolve().is_relative_to(dest):
            raise ValueError(f"unsafe path in bundle: {m.name}")
    tar.extractall(dest)


def apply_update(control_url: str | None = None, download=None) -> dict:
    """Fetch + extract the latest bundle. Returns {ok, ...} — no restart."""
    control = (control_url or os.getenv("MAYBOT_CONTROL_CENTER_URL", "")).rstrip("/")
    if not control:
        return {"ok": False, "error": "MAYBOT_CONTROL_CENTER_URL not set"}
    download = download or _download
    target = _target_dir()
    try:
        data = download(f"{control}/agent-bundle.tgz")
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            _safe_extract(tar, target)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"download/extract failed: {exc}"}
    req = target / "requirements-agent.txt"
    if req.exists():
        try:
            import subprocess
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
                           timeout=240, check=False)
        except Exception:  # noqa: BLE001
            pass            # a dependency hiccup shouldn't block the code update
    return {"ok": True}


def _under_systemd() -> bool:
    return bool(os.getenv("INVOCATION_ID")) or os.path.exists("/run/systemd/system")


def _restart() -> None:
    time.sleep(1.0)                       # let the HTTP/tunnel response flush first
    if _under_systemd():
        os._exit(0)                       # Restart=always brings us back on the new code
    try:
        os.execv(sys.executable, [sys.executable, *sys.argv])
    except Exception:  # noqa: BLE001
        os._exit(0)


def update_and_restart(control_url: str | None = None, download=None, restart: bool = True) -> dict:
    res = apply_update(control_url, download)
    if res.get("ok") and restart:
        threading.Thread(target=_restart, daemon=True).start()
        res.update(restarting=True, version=AGENT_VERSION)
    return res
