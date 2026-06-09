import csv
import sqlite3
from datetime import datetime

from maybot_agent.adapters.trading_bot import adapt, _derive_activity


def test_derive_activity_maps_daybot_cycle_state():
    assert _derive_activity("closed", 0, 0) == "standby"
    assert _derive_activity("pre-market", 5, 0) == "standby"
    assert _derive_activity("open", 4, 3) == "filling"
    assert _derive_activity("open", 4, 0) == "scanning"
    assert _derive_activity("open", 0, 0) == "scanning"
    assert _derive_activity(None, 0, 0) == "trading"


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
    # live activity fields surfaced for the Base View room
    assert m["market_status"] == "open"
    assert m["tickers_scanned"] == 10
    assert m["activity"] == "filling"  # 4 attempted, 3 filled


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


def test_generic_trades_table_feeds_time_bucketed_pnl(tmp_path):
    """A bot that records executed trades in a generic `trades` table (no DayBot
    pnl_snapshots/paper_trades) must still surface Profit Today/Week/Month, not
    just a lump realized total. This is the "catching trades but no PnL" case."""
    db = tmp_path / "bot.db"
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    # arbitrary column names the bot might use: `profit` for PnL, `exit_time` for close.
    cur.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, symbol TEXT, side TEXT, "
                "entry_time TEXT, exit_time TEXT, profit REAL)")
    now = datetime.now().replace(microsecond=0)
    cur.execute("INSERT INTO trades (symbol, side, entry_time, exit_time, profit) VALUES "
                "('BTC', 'long', ?, ?, 12.5)", (now.isoformat(), now.isoformat()))
    cur.execute("INSERT INTO trades (symbol, side, entry_time, exit_time, profit) VALUES "
                "('ETH', 'short', ?, ?, -3.0)", (now.isoformat(), now.isoformat()))
    conn.commit()
    conn.close()

    out = adapt({"name": "arb", "type": "trading_bot", "path": str(tmp_path), "database": str(db)})
    m = out["metrics"]
    assert m["realized_pnl"] == 9.5          # 12.5 + (-3.0)
    assert m["profit_today"] == 9.5          # both closed today → headline populated
    assert m["profit_this_week"] == 9.5
    assert m["trades_today"] == 2


def test_log_metrics_do_not_clobber_db_pnl(tmp_path):
    """A stale 'total_pnl: 0' log line must not overwrite a real Profit Today
    computed from closed trades in the database."""
    db = tmp_path / "bot.db"
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, exit_time TEXT, pnl REAL)")
    now = datetime.now().replace(microsecond=0)
    cur.execute("INSERT INTO trades (exit_time, pnl) VALUES (?, 42.0)", (now.isoformat(),))
    conn.commit()
    conn.close()

    log = tmp_path / "bot.log"
    log.write_text("cycle done total_pnl=0\n", encoding="utf-8")

    out = adapt({"name": "arb", "type": "trading_bot", "path": str(tmp_path),
                 "database": str(db), "log_file": str(log)})
    assert out["metrics"]["profit_today"] == 42.0   # DB wins over the log's 0
