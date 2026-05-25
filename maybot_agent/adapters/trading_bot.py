from __future__ import annotations

from pathlib import Path
import sqlite3
import re
from .base import base_project


DEFAULTS = {
    "profit_today": "unknown", "profit_this_week": "unknown", "profit_this_month": "unknown",
    "realized_pnl": "unknown", "unrealized_pnl": "unknown", "open_exposure": "unknown",
    "open_positions": "unknown", "trades_today": "unknown", "fills_today": "unknown", "fill_rate": "unknown",
    "rejected_trades": "unknown", "risk_blocked_trades": "unknown", "last_trade_time": "unknown",
}


def _parse_log_metrics(log_file: str | None) -> dict:
    out = {}
    if not log_file or not Path(log_file).exists():
        return out
    text = Path(log_file).read_text(encoding="utf-8", errors="ignore").splitlines()[-400:]
    patterns = {
        "profit_today": r"total_pnl[:=]\s*(-?\d+(?:\.\d+)?)",
        "unrealized_pnl": r"unrealized_pnl[:=]\s*(-?\d+(?:\.\d+)?)",
        "fills_today": r"orders_filled[:=]\s*(\d+)",
        "trades_today": r"orders_attempted[:=]\s*(\d+)",
        "fill_rate": r"fill_rate[:=]\s*(\d+(?:\.\d+)?)",
        "open_positions": r"open_positions[:=]\s*(\d+)",
        "open_exposure": r"total_exposure_usd[:=]\s*(-?\d+(?:\.\d+)?)",
        "risk_blocked_trades": r"risk_blocked[:=]\s*(\d+)",
        "rejected_trades": r"rejected[:=]\s*(\d+)",
    }
    for line in reversed(text):
        for k, p in patterns.items():
            if k in out:
                continue
            m = re.search(p, line, re.IGNORECASE)
            if m:
                out[k] = float(m.group(1)) if "." in m.group(1) else int(m.group(1))
    return out


def adapt(project: dict) -> dict:
    data = base_project(project)
    metrics = data.get("metrics", {})
    metrics.update(DEFAULTS)
    metrics.update(project.get("metrics", {}))

    db_path = project.get("database")
    if db_path and not Path(db_path).exists():
        data["alerts"].append("WARNING: trading database missing")
    if db_path and Path(db_path).exists():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1)
            cur = conn.cursor()
            for table, col, key in [("trades", "pnl", "realized_pnl"), ("positions", "unrealized_pnl", "unrealized_pnl"), ("positions", "exposure", "open_exposure")]:
                try:
                    cur.execute(f"SELECT SUM({col}) FROM {table}")
                    v = cur.fetchone()[0]
                    if v is not None:
                        metrics[key] = round(float(v), 4)
                except Exception:
                    pass
            conn.close()
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                data["alerts"].append("WARNING: sqlite database locked")

    metrics.update(_parse_log_metrics(project.get("log_file")))
    data["metrics"] = metrics
    if any("ERROR" in a for a in data["alerts"]):
        data["health"] = "error"
    elif data["alerts"]:
        data["health"] = "warning"
    return data
