from pathlib import Path


def read_logs(path: str | None, level: str = "ALL", tail: int = 200) -> dict:
    if not path:
        return {"status": "unknown", "lines": []}
    p = Path(path)
    if not p.exists():
        return {"status": "unknown", "lines": []}
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()[-tail:]
    if level != "ALL":
        lines = [ln for ln in lines if level.upper() in ln.upper()]
    return {"status": "ok", "lines": lines}
