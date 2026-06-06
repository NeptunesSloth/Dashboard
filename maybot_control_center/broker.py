"""READ-ONLY Alpaca paper-account client with graceful fallback.

This module *only reads* from a configured Alpaca account — account balances,
open positions, and recent filled orders — to mirror the live paper portfolio
into the command center. It NEVER places, modifies, or cancels orders: there is
deliberately no POST/PATCH/DELETE path here.

Like the rest of the dashboard it degrades gracefully: when the broker isn't
configured, the HTTP client is unavailable, or the network is down, every
function returns an empty value instead of raising. ``requests`` is imported
optionally and the stdlib ``urllib`` is used as a fallback.

Env knobs:
  * ``MAYBOT_BROKER`` — set to ``"alpaca"`` to enable.
  * ``ALPACA_API_KEY`` / ``ALPACA_SECRET_KEY`` — credentials (both required).
  * ``ALPACA_BASE_URL`` — defaults to the PAPER endpoint.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

# Default to Alpaca's PAPER trading endpoint — never the live one.
_DEFAULT_BASE = "https://paper-api.alpaca.markets"
_TIMEOUT = 6.0  # seconds; keep the dashboard snappy even if Alpaca is slow


def enabled() -> bool:
    """True only when the broker is configured *and* both keys are present."""
    if os.getenv("MAYBOT_BROKER", "").strip().lower() != "alpaca":
        return False
    return bool(os.getenv("ALPACA_API_KEY", "").strip()
                and os.getenv("ALPACA_SECRET_KEY", "").strip())


def _base_url() -> str:
    return (os.getenv("ALPACA_BASE_URL", "").strip() or _DEFAULT_BASE).rstrip("/")


def _headers() -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", ""),
        "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY", ""),
        "Accept": "application/json",
    }


def _get(path: str, params: dict | None = None):
    """Issue a read-only GET and return parsed JSON, or ``None`` on any failure.

    Uses ``requests`` when installed; otherwise falls back to stdlib urllib.
    Every network/parse error is swallowed so callers always get a value.
    """
    if not enabled():
        return None
    url = _base_url() + path

    # Optional, faster client first.
    try:
        import requests  # optional dependency
    except Exception:
        requests = None  # type: ignore[assignment]

    if requests is not None:
        try:
            resp = requests.get(url, headers=_headers(), params=params or {}, timeout=_TIMEOUT)
            if resp.status_code != 200:
                return None
            return resp.json()
        except Exception:
            return None

    # Stdlib fallback — build the query string by hand.
    try:
        if params:
            from urllib.parse import urlencode
            url = url + "?" + urlencode(params)
        req = urllib.request.Request(url, headers=_headers(), method="GET")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            if getattr(r, "status", 200) != 200:
                return None
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
        return None
    except Exception:
        return None


def _num(value, default: float = 0.0) -> float:
    """Coerce an Alpaca string/number field to float, defaulting on junk."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def account() -> dict:
    """Account summary ``{"equity","cash","buying_power","currency"}``.

    Returns ``{}`` when disabled or on any failure.
    """
    data = _get("/v2/account")
    if not isinstance(data, dict):
        return {}
    try:
        return {
            "equity": _num(data.get("equity")),
            "cash": _num(data.get("cash")),
            "buying_power": _num(data.get("buying_power")),
            "currency": data.get("currency") or "USD",
        }
    except Exception:
        return {}


def positions() -> list[dict]:
    """Open positions mapped to command.py's ``positions()`` shape.

    Each item: ``{"ticker","side","qty","entry","last","pnl","pnl_pct"}``.
    Returns ``[]`` when disabled or on any failure.
    """
    data = _get("/v2/positions")
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for p in data:
        if not isinstance(p, dict):
            continue
        try:
            # Alpaca side is "long"/"short"; normalize to LONG/SHORT.
            side = str(p.get("side", "long")).upper()
            side = "SHORT" if side == "SHORT" else "LONG"
            out.append({
                "ticker": p.get("symbol", ""),
                "side": side,
                "qty": abs(_num(p.get("qty"))),
                "entry": round(_num(p.get("avg_entry_price")), 4),
                "last": round(_num(p.get("current_price")), 4),
                "pnl": round(_num(p.get("unrealized_pl")), 2),
                "pnl_pct": round(_num(p.get("unrealized_plpc")) * 100.0, 2),
            })
        except Exception:
            continue
    return out


def recent_fills(limit: int = 20) -> list[dict]:
    """Recent *filled* orders ``{"ticker","side","qty","price","ts"}``.

    Returns ``[]`` when disabled or on any failure.
    """
    try:
        lim = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        lim = 20
    data = _get("/v2/orders", {"status": "closed", "limit": lim, "direction": "desc"})
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for o in data:
        if not isinstance(o, dict):
            continue
        # Only surface orders that actually filled.
        if str(o.get("status", "")).lower() != "filled":
            continue
        try:
            qty = _num(o.get("filled_qty")) or _num(o.get("qty"))
            out.append({
                "ticker": o.get("symbol", ""),
                "side": str(o.get("side", "")).upper(),
                "qty": abs(qty),
                "price": round(_num(o.get("filled_avg_price")), 4),
                "ts": o.get("filled_at") or o.get("updated_at") or o.get("submitted_at"),
            })
        except Exception:
            continue
        if len(out) >= lim:
            break
    return out
