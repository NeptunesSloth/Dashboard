from __future__ import annotations

from pathlib import Path
import psutil
from .cache import cached

_TTL = 5.0


def _details(pid: int) -> dict:
    p = psutil.Process(pid)
    return {
        "running": p.is_running(),
        "pid": pid,
        "cpu": p.cpu_percent(0.1),
        "ram_mb": round(p.memory_info().rss / 1024 / 1024, 2),
        "cmdline": " ".join(p.cmdline()),
    }


def _find(*, pid_file: str | None, cmdline_contains: str | None, process_name: str | None, cwd: str | None) -> dict:
    if pid_file:
        try:
            pid_path = Path(cwd or ".") / pid_file
            pid = int(pid_path.read_text(encoding="utf-8").strip())
            return _details(pid)
        except Exception:
            return {"running": False, "pid": "unknown", "cpu": "unknown", "ram_mb": "unknown", "cmdline": "unknown"}

    if cmdline_contains:
        for proc in psutil.process_iter(["pid", "cmdline"]):
            cmd = " ".join(proc.info.get("cmdline") or [])
            if cmdline_contains in cmd:
                try:
                    return _details(proc.info["pid"])
                except Exception:
                    continue
        return {"running": False, "pid": "unknown", "cpu": "unknown", "ram_mb": "unknown", "cmdline": "unknown"}

    if process_name:
        for proc in psutil.process_iter(["pid", "name"]):
            if process_name.lower() in (proc.info.get("name") or "").lower():
                try:
                    return _details(proc.info["pid"])
                except Exception:
                    continue
        return {"running": False, "pid": "unknown", "cpu": "unknown", "ram_mb": "unknown", "cmdline": "unknown"}

    return {"running": "unknown", "pid": "unknown", "cpu": "unknown", "ram_mb": "unknown", "cmdline": "unknown"}


def find_process(*, pid_file: str | None = None, cmdline_contains: str | None = None, process_name: str | None = None, cwd: str | None = None) -> dict:
    key = ("proc", pid_file, cmdline_contains, process_name, cwd)
    return cached(key, _TTL, _find, pid_file=pid_file, cmdline_contains=cmdline_contains, process_name=process_name, cwd=cwd)
