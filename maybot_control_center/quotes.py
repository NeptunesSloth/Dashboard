"""Live market-price provider with in-memory caching and graceful fallback.

The command center's ``positions()`` view ships static demo / env-supplied
numbers. This module optionally layers *live* last-trade prices on top so the
Trade Center floor reads like a real ticker — without ever becoming a hard
dependency. The market-data library (``yfinance``) is imported optionally and
every network path is wrapped: when the provider is unset, the lib is missing,
or there's no network, callers transparently fall back to their existing data.

Env knobs:
  * ``MAYBOT_QUOTES_PROVIDER`` — ``"yfinance"`` to go live; anything else / unset
    keeps the dashboard fully offline.
  * ``MAYBOT_QUOTES_TTL`` — cache TTL in seconds (default 20) so we never hammer
    the upstream API on every render.
"""
from __future__ import annotations

import os
import threading
import time

# Cache: symbol -> (price, fetched_at_epoch_seconds). A short TTL keeps the
# Trade Center responsive while shielding the upstream API from request storms.
_lock = threading.Lock()
_cache: dict[str, tuple[float, float]] = {}


def _provider() -> str:
    """The configured live provider name (lowercased), or "" when offline."""
    return os.getenv("MAYBOT_QUOTES_PROVIDER", "").strip().lower()


def _ttl() -> float:
    """Cache TTL in seconds (default 20); bad values degrade to the default."""
    try:
        return float(os.getenv("MAYBOT_QUOTES_TTL", "20") or 20)
    except Exception:
        return 20.0


def live() -> bool:
    """True only when a real market-data provider is configured."""
    return _provider() == "yfinance"


def _fetch_yfinance(symbols: list[str]) -> dict[str, float]:
    """Best-effort last prices via the optional ``yfinance`` dependency.

    Wrapped so a missing library, malformed data, or a dead network can never
    raise into callers — any failure simply yields ``{}``.
    """
    out: dict[str, float] = {}
    try:
        import yfinance  # optional; may be absent or have no network
    except Exception:
        return {}
    for sym in symbols:
        try:
            ticker = yfinance.Ticker(sym)
            price: float | None = None
            # Prefer the lightweight fast_info path when present.
            fast = getattr(ticker, "fast_info", None)
            if fast is not None:
                last = getattr(fast, "last_price", None)
                if last is None:
                    try:
                        last = fast["last_price"]  # mapping-style access
                    except Exception:
                        last = None
                if last is not None:
                    price = float(last)
            # Fall back to recent history if fast_info gave us nothing.
            if price is None:
                hist = ticker.history(period="1d")
                if hist is not None and not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            if price is not None and price == price:  # filter NaN
                out[sym] = float(price)
        except Exception:
            # Skip just this symbol; never abort the whole batch.
            continue
    return out


def get_quotes(symbols: list[str]) -> dict[str, float]:
    """Return ``{symbol: last_price}`` for the requested tickers.

    Honors the configured provider and a short TTL cache. Returns ``{}`` when
    no live provider is configured or on any error, so callers fall back to
    their existing (demo / env) data. Never raises.
    """
    if not symbols:
        return {}
    provider = _provider()
    if provider != "yfinance":
        return {}

    # Normalize / de-dupe while preserving the caller's symbols.
    wanted = [s for s in dict.fromkeys(symbols) if s]
    now = time.time()
    ttl = _ttl()

    result: dict[str, float] = {}
    missing: list[str] = []
    with _lock:
        for sym in wanted:
            cached = _cache.get(sym)
            if cached is not None and (now - cached[1]) < ttl:
                result[sym] = cached[0]
            else:
                missing.append(sym)

    if missing:
        try:
            fresh = _fetch_yfinance(missing)
        except Exception:
            fresh = {}
        if fresh:
            stamp = time.time()
            with _lock:
                for sym, price in fresh.items():
                    _cache[sym] = (price, stamp)
            result.update(fresh)

    return result


def enrich_positions(positions: list[dict]) -> list[dict]:
    """Recompute ``last``/``pnl``/``pnl_pct`` from live quotes where available.

    Input/output dicts share command.py's ``positions()`` shape:
    ``{"ticker","side","qty","entry","last","pnl","pnl_pct"}``. Positions without
    a live quote (or with unusable fields) are returned unchanged. Pure and
    never raises.
    """
    if not positions:
        return positions

    tickers = [p.get("ticker") for p in positions if p.get("ticker")]
    try:
        quotes = get_quotes([t for t in tickers if isinstance(t, str)])
    except Exception:
        quotes = {}
    if not quotes:
        return positions

    out: list[dict] = []
    for pos in positions:
        ticker = pos.get("ticker")
        price = quotes.get(ticker) if isinstance(ticker, str) else None
        if price is None:
            out.append(pos)  # no live data for this one — leave it untouched
            continue
        try:
            qty = float(pos.get("qty", 0) or 0)
            entry = float(pos.get("entry", 0) or 0)
            side = str(pos.get("side", "LONG")).upper()
            last = float(price)
            # SHORT positions profit as price falls; LONG as it rises.
            per_share = (entry - last) if side == "SHORT" else (last - entry)
            pnl = per_share * qty
            pnl_pct = (per_share / entry * 100.0) if entry else 0.0
            updated = dict(pos)
            updated["last"] = round(last, 4)
            updated["pnl"] = round(pnl, 2)
            updated["pnl_pct"] = round(pnl_pct, 2)
            out.append(updated)
        except Exception:
            out.append(pos)  # malformed fields — keep original untouched
    return out
