import csv
import sqlite3
from datetime import datetime

from maybot_agent.adapters.trading_bot import adapt


def test_daybot_db_and_csv_fallback_and_dedup(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    db = logs / "daybot.db"

    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("CREATE TABLE cycle_summaries (recorded_at TEXT, cycle_number INTEGER, mode TEXT, elapsed_seconds REAL, tickers_scanned INTEGER, news_items_found INTEGER, orders_filled INTEGER, orders_attempted INTEGER, open_positions INTEGER, total_exposure_usd REAL, unrealized_pnl REAL, realized_pnl REAL, market_status TEXT, calendar_provider TEXT, data_calls_made INTEGER)")
    cur.execute("CREATE TABLE pnl_snapshots (recorded_at TEXT, balance REAL, total_pnl REAL, unrealized_pnl REAL, total_trades INTEGER, wins INTEGER, losses INTEGER, win_rate REAL, max_drawdown_pct REAL, open_positions INTEGER)")
    cur.execute("CREATE TABLE paper_trades (opened_at TEXT, closed_at TEXT, order_id TEXT, ticker TEXT, direction TEXT, filled_shares REAL, fill_price REAL, close_price REAL, close_reason TEXT, pnl_usd REAL, commission_usd REAL, status TEXT)")
    cur.execute("CREATE TABLE rejected_signals (recorded_at TEXT, cycle_number INTEGER, ticker TEXT, reason TEXT, score REAL)")

    now = datetime.now().replace(microsecond=0)
    cur.execute("INSERT INTO cycle_summaries VALUES (?, 1, 'paper', 2.1, 10, 2, 3, 4, 2, 1200.5, 12.25, 0, 'open', 'x', 44)", (now.isoformat(),))
    cur.execute("INSERT INTO pnl_snapshots VALUES (?, 10000, 33.5, 12.5, 8, 5, 3, 0.625, 4.5, 2)", (now.isoformat(),))
    cur.execute("INSERT INTO paper_trades VALUES (?, ?, 'dup-1', 'AAPL', 'buy', 1, 1, 1, 'tp', 5.0, 0.0, 'closed')", (now.isoformat(), now.isoformat()))
    cur.execute("INSERT INTO rejected_signals VALUES (?, 1, 'MSFT', 'risk', 0.1)", (now.isoformat(),))
    conn.commit()
    conn.close()

    csv_path = logs / f"paper_trades_{now.strftime('%Y%m%d')}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["opened_at", "closed_at", "order_id", "ticker", "direction", "shares", "fill_price", "close_price", "close_reason", "pnl_usd", "commission_usd"])
        w.writerow([now.isoformat(), now.isoformat(), "dup-1", "AAPL", "buy", 1, 1, 1, "tp", 5.0, 0.0])
        w.writerow([now.isoformat(), now.isoformat(), "csv-2", "NVDA", "buy", 1, 1, 1, "tp", 7.0, 0.0])

    out = adapt({
        "name": "daybot",
        "type": "trading_bot",
        "path": str(tmp_path),
        "database": str(db),
        "trade_csv_glob": "logs/paper_trades_*.csv",
    })
    m = out["metrics"]
    assert m["open_positions"] == 2
    assert m["open_exposure"] == 1200.5
    assert m["unrealized_pnl"] == 12.5
    assert m["fill_rate"] == 0.75
    assert m["rejected_trades"] == 1
    assert m["realized_pnl"] == 12.0
    assert m["trades_today"] >= 2


def test_daybot_uses_csv_when_paper_trades_missing(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    db = logs / "daybot.db"
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("CREATE TABLE cycle_summaries (recorded_at TEXT, cycle_number INTEGER, mode TEXT, elapsed_seconds REAL, tickers_scanned INTEGER, news_items_found INTEGER, orders_filled INTEGER, orders_attempted INTEGER, open_positions INTEGER, total_exposure_usd REAL, unrealized_pnl REAL, realized_pnl REAL, market_status TEXT, calendar_provider TEXT, data_calls_made INTEGER)")
    conn.commit()
    conn.close()

    now = datetime.now().replace(microsecond=0)
    csv_path = logs / f"paper_trades_{now.strftime('%Y%m%d')}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["opened_at", "closed_at", "order_id", "ticker", "direction", "shares", "fill_price", "close_price", "close_reason", "pnl_usd", "commission_usd"])
        w.writerow([now.isoformat(), now.isoformat(), "csv-1", "TSLA", "buy", 1, 1, 1, "tp", 9.5, 0.0])

    out = adapt({"name": "daybot", "type": "trading_bot", "path": str(tmp_path), "database": str(db), "trade_csv_glob": "logs/paper_trades_*.csv"})
    assert out["metrics"]["realized_pnl"] == 9.5
    assert out["metrics"]["profit_today"] == 9.5
