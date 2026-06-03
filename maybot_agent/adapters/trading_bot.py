from __future__ import annotations

from pathlib import Path
import sqlite3
import re
import csv
from datetime import datetime, timedelta
from .base import base_project


DEFAULTS = {
    "profit_today": "unknown", "profit_this_week": "unknown", "profit_this_month": "unknown",
    "realized_pnl": "unknown", "unrealized_pnl": "unknown", "open_exposure": "unknown",
    "open_positions": "unknown", "trades_today": "unknown", "fills_today": "unknown", "fill_rate": "unknown",
    "rejected_trades": "unknown", "risk_blocked_trades": "unknown", "last_trade_time": "unknown",
}

def _derive_activity(market_status, attempted, filled) -> str:
    """Map a DayBot cycle into a short activity verb for the Base View badge."""
    ms = str(market_status or "").lower()
    if ms and any(t in ms for t in ("closed", "pre", "after", "holiday")):
        return "standby"
    if attempted and int(attempted) > 0:
        return "filling" if (filled or 0) > 0 else "scanning"
    if "open" in ms:
        return "scanning"
    return "trading"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    for candidate in (s, s.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate)
        except Exception:
            pass
    return None


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
    closed_rows: list[dict] = []
    has_db_trade_pnl = False
    if db_path and Path(db_path).exists():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=3)
            cur = conn.cursor()
            for table, col, key in [("trades", "pnl", "realized_pnl"), ("positions", "unrealized_pnl", "unrealized_pnl"), ("positions", "exposure", "open_exposure")]:
                try:
                    cur.execute(f"SELECT SUM({col}) FROM {table}")
                    v = cur.fetchone()[0]
                    if v is not None:
                        metrics[key] = round(float(v), 4)
                except Exception:
                    pass
            # DayBot schema support
            try:
                cur.execute("SELECT open_positions, total_exposure_usd, unrealized_pnl, orders_filled, orders_attempted, market_status, tickers_scanned, mode FROM cycle_summaries ORDER BY recorded_at DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    open_positions, exposure, unrl, filled, attempted, market_status, tickers_scanned, cyc_mode = row
                    if open_positions is not None:
                        metrics["open_positions"] = int(open_positions)
                    if exposure is not None:
                        metrics["open_exposure"] = round(float(exposure), 4)
                    if unrl is not None:
                        metrics["unrealized_pnl"] = round(float(unrl), 4)
                    if filled is not None:
                        metrics["fills_today"] = int(filled)
                        metrics["orders_filled"] = int(filled)
                    if attempted is not None:
                        metrics["orders_attempted"] = int(attempted)
                        if int(attempted) > 0:
                            metrics["fill_rate"] = round(float(filled or 0) / float(attempted), 4)
                    if market_status is not None:
                        metrics["market_status"] = str(market_status)
                    if tickers_scanned is not None:
                        metrics["tickers_scanned"] = int(tickers_scanned)
                    if cyc_mode and not metrics.get("mode"):
                        metrics["mode"] = str(cyc_mode)
                    metrics["activity"] = _derive_activity(market_status, attempted, filled)
            except Exception:
                pass
            try:
                cur.execute("SELECT recorded_at, total_pnl, unrealized_pnl, open_positions FROM pnl_snapshots ORDER BY recorded_at DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    _, total_pnl, unrl, open_positions = row
                    if total_pnl is not None:
                        metrics["profit_today"] = round(float(total_pnl), 4)
                    if unrl is not None:
                        metrics["unrealized_pnl"] = round(float(unrl), 4)
                    if open_positions is not None:
                        metrics["open_positions"] = int(open_positions)
            except Exception:
                pass
            try:
                cur.execute("SELECT COUNT(*) FROM rejected_signals")
                v = cur.fetchone()[0]
                metrics["rejected_trades"] = int(v or 0)
            except Exception:
                pass
            try:
                cur.execute("SELECT opened_at, closed_at, order_id, pnl_usd, status FROM paper_trades")
                rows = cur.fetchall()
                for opened_at, closed_at, order_id, pnl_usd, status in rows:
                    if pnl_usd is None:
                        continue
                    has_db_trade_pnl = True
                    closed_rows.append({
                        "opened_at": opened_at,
                        "closed_at": closed_at,
                        "order_id": order_id,
                        "pnl_usd": float(pnl_usd),
                        "status": status,
                    })
            except Exception:
                pass
            conn.close()
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                data["alerts"].append("WARNING: sqlite database locked")

    # Optional CSV fallback/merge for DayBot-style trade files
    csv_glob = project.get("trade_csv_glob")
    if csv_glob:
        csv_rows: list[dict] = []
        base_path = Path(project.get("path") or ".")
        for p in sorted(base_path.glob(csv_glob)):
            try:
                with p.open("r", encoding="utf-8", newline="") as f:
                    for row in csv.DictReader(f):
                        try:
                            pnl = float(row.get("pnl_usd", "") or 0.0)
                        except Exception:
                            continue
                        csv_rows.append({
                            "opened_at": row.get("opened_at"),
                            "closed_at": row.get("closed_at"),
                            "order_id": row.get("order_id"),
                            "pnl_usd": pnl,
                            "status": "closed" if row.get("closed_at") else "open",
                        })
            except Exception:
                pass
        if csv_rows and (not has_db_trade_pnl):
            closed_rows.extend(csv_rows)
        elif csv_rows and has_db_trade_pnl:
            seen = {str(r.get("order_id")) for r in closed_rows if r.get("order_id")}
            for r in csv_rows:
                oid = str(r.get("order_id") or "")
                if oid and oid in seen:
                    continue
                closed_rows.append(r)

    if closed_rows:
        now = datetime.now()
        start_today = datetime(now.year, now.month, now.day)
        start_week = start_today - timedelta(days=start_today.weekday())
        start_month = datetime(now.year, now.month, 1)
        pnl_today = pnl_week = pnl_month = realized = 0.0
        trades_today = fills_today = 0
        last_trade_time = None
        for row in closed_rows:
            pnl = float(row.get("pnl_usd") or 0.0)
            realized += pnl
            dt = _parse_dt(row.get("closed_at")) or _parse_dt(row.get("opened_at"))
            if dt:
                if last_trade_time is None or dt > last_trade_time:
                    last_trade_time = dt
                if dt >= start_today:
                    pnl_today += pnl
                    trades_today += 1
                    fills_today += 1
                if dt >= start_week:
                    pnl_week += pnl
                if dt >= start_month:
                    pnl_month += pnl
        metrics["realized_pnl"] = round(realized, 4)
        metrics["profit_today"] = round(pnl_today, 4)
        metrics["profit_this_week"] = round(pnl_week, 4)
        metrics["profit_this_month"] = round(pnl_month, 4)
        metrics["trades_today"] = trades_today
        metrics["fills_today"] = max(int(metrics.get("fills_today", 0) if isinstance(metrics.get("fills_today"), int) else 0), fills_today)
        if last_trade_time:
            metrics["last_trade_time"] = last_trade_time.isoformat()

    metrics.update(_parse_log_metrics(project.get("log_file")))
    data["metrics"] = metrics
    if any("ERROR" in a for a in data["alerts"]):
        data["health"] = "error"
    elif data["alerts"]:
        data["health"] = "warning"
    return data
