import psutil


def find_process(name: str | None = None, pid: int | None = None) -> dict:
    try:
        if pid:
            proc = psutil.Process(pid)
            return {"running": proc.is_running(), "pid": pid, "cpu": proc.cpu_percent(0.1), "ram_mb": round(proc.memory_info().rss / 1024 / 1024, 2)}
        if name:
            for proc in psutil.process_iter(["pid", "name"]):
                if name.lower() in (proc.info.get("name") or "").lower():
                    p = psutil.Process(proc.info["pid"])
                    return {"running": True, "pid": p.pid, "cpu": p.cpu_percent(0.1), "ram_mb": round(p.memory_info().rss / 1024 / 1024, 2)}
    except Exception:
        pass
    return {"running": "unknown", "pid": "unknown", "cpu": "unknown", "ram_mb": "unknown"}
