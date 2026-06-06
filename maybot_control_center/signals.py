"""Tier-A ML trading-signal layer (with a deterministic heuristic fallback).

This module exposes a small, dependency-light "signal" surface the command
center can consult to rank symbols. It is engineered to *always* import and run
OFFLINE, even when none of the optional ML / market-data libraries are present:

  * If a trained model lives at ``models/signal_model.joblib`` AND both
    ``joblib`` and ``scikit-learn`` import, that model is loaded (and cached)
    and used to score symbols (``source == "model"``).
  * Otherwise we fall back to a transparent technical heuristic computed from a
    handful of pure-python features (``source == "heuristic"``). Recent price
    bars are fetched via ``yfinance`` when available; with no network / no
    yfinance we synthesize a DETERMINISTIC pseudo price walk seeded by the
    symbol name, so scores are sensible and stable run-to-run.

Honesty caveat: the heuristic is a toy. It is meant to look and behave like a
real signal layer (stable shapes, bounded outputs, graceful degradation), not
to make money. See ``tools/train_signal.py`` for the offline trainer and its
own caveats about overfitting, leakage, and regime change.

Env:
  ``MAYBOT_SIGNALS == "1"`` enables the layer. When disabled, ``score_symbols``
  returns ``[]`` so callers can wire it in with zero behavioural change.
"""
from __future__ import annotations

import math
import os

# Model lives next to this file so it ships with the package when present.
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "signal_model.joblib")

# Cache the loaded model object (or False once we've decided it's unavailable)
# so we only pay the import + disk cost once per process.
_MODEL_CACHE: object | None = None
_MODEL_TRIED: bool = False


def enabled() -> bool:
    """True when the signal layer is switched on via ``MAYBOT_SIGNALS == "1"``."""
    return os.getenv("MAYBOT_SIGNALS", "0").strip() == "1"


# --------------------------------------------------------------------------- #
# Features — pure python, no numpy. Reused by BOTH the model and heuristic paths
# so training and inference always agree on the feature contract.
# --------------------------------------------------------------------------- #
def features_from_closes(closes: list[float]) -> dict:
    """Compute simple technical features from a list of close prices.

    Returns a dict with stable keys (returns over 1/5/10 bars, a short-vs-long
    momentum, RSI(14), and realized volatility). Everything is plain python and
    defensively clamped so degenerate / tiny series never raise.

    Keys: ``ret_1, ret_5, ret_10, momentum, rsi_14, realized_vol``.
    """
    out = {
        "ret_1": 0.0,
        "ret_5": 0.0,
        "ret_10": 0.0,
        "momentum": 0.0,
        "rsi_14": 50.0,        # neutral RSI when undefined
        "realized_vol": 0.0,
    }
    # Keep only finite, positive prices; bail to neutral defaults if too short.
    px = [float(c) for c in closes if isinstance(c, (int, float)) and math.isfinite(c) and c > 0]
    n = len(px)
    if n < 2:
        return out

    def _ret(lookback: int) -> float:
        # Percentage return over ``lookback`` bars (clamped to available data).
        k = min(lookback, n - 1)
        prev = px[-1 - k]
        return (px[-1] - prev) / prev if prev else 0.0

    out["ret_1"] = _ret(1)
    out["ret_5"] = _ret(5)
    out["ret_10"] = _ret(10)

    # Momentum: short MA vs long MA, normalized by long MA. Positive => uptrend.
    short_w = min(5, n)
    long_w = min(20, n)
    short_ma = sum(px[-short_w:]) / short_w
    long_ma = sum(px[-long_w:]) / long_w
    out["momentum"] = (short_ma - long_ma) / long_ma if long_ma else 0.0

    # Per-bar simple returns, used for RSI and realized volatility.
    rets = [(px[i] - px[i - 1]) / px[i - 1] for i in range(1, n) if px[i - 1]]

    # RSI(14) — Wilder's classic, computed over the last 14 deltas available.
    window = rets[-14:]
    gains = [r for r in window if r > 0]
    losses = [-r for r in window if r < 0]
    avg_gain = sum(gains) / len(window) if window else 0.0
    avg_loss = sum(losses) / len(window) if window else 0.0
    if avg_loss == 0:
        out["rsi_14"] = 100.0 if avg_gain > 0 else 50.0
    else:
        rs = avg_gain / avg_loss
        out["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))

    # Realized volatility — std-dev of returns (population), pure python.
    if len(rets) >= 2:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        out["realized_vol"] = math.sqrt(var)

    return out


# Canonical feature order — the trainer must emit a model expecting THIS order.
_FEATURE_ORDER = ("ret_1", "ret_5", "ret_10", "momentum", "rsi_14", "realized_vol")


def _feature_vector(feats: dict) -> list[float]:
    """Flatten a feature dict into the canonical ordered vector for the model."""
    return [float(feats.get(k, 0.0)) for k in _FEATURE_ORDER]


# --------------------------------------------------------------------------- #
# Price bars — optional yfinance, deterministic synthetic fallback otherwise.
# --------------------------------------------------------------------------- #
def _synthetic_closes(symbol: str, n: int = 60) -> list[float]:
    """Deterministic pseudo price walk seeded by the symbol string.

    No randomness module state, no network: identical input => identical output,
    which is exactly what we need for stable offline scores and reproducible
    tests. The walk uses cheap trig of a symbol-derived seed so different tickers
    get visibly different (but fixed) shapes.
    """
    seed = sum((i + 1) * ord(ch) for i, ch in enumerate(symbol.upper())) or 1
    base = 50.0 + (seed % 400)              # starting price in a plausible range
    drift = ((seed % 7) - 3) * 0.0009       # small per-bar drift, sign varies
    closes: list[float] = []
    price = base
    for t in range(n):
        # Bounded oscillation + drift — purely a function of (seed, t).
        wobble = math.sin((seed % 13 + 1) * 0.21 * t + (seed % 5)) * 0.012
        price *= (1.0 + drift + wobble)
        if price <= 1.0:                     # keep prices positive & sane
            price = 1.0 + (seed % 3)
        closes.append(round(price, 4))
    return closes


def _recent_closes(symbol: str) -> list[float]:
    """Best-effort recent close prices for ``symbol``.

    Tries yfinance if importable and a network is reachable; any failure (no
    lib, no network, empty frame) silently falls back to the deterministic
    synthetic walk so this never throws and always returns usable data.
    """
    try:
        import yfinance as yf  # optional; absent in the offline default

        data = yf.Ticker(symbol).history(period="3mo", interval="1d")
        closes = [float(c) for c in list(data["Close"]) if math.isfinite(float(c)) and float(c) > 0]
        if len(closes) >= 15:
            return closes
    except Exception:
        # Any of: ImportError, network error, KeyError, empty data — fall back.
        pass
    return _synthetic_closes(symbol)


# --------------------------------------------------------------------------- #
# Model loading (cached) — only used when joblib + sklearn + file all present.
# --------------------------------------------------------------------------- #
def _load_model() -> object | None:
    """Load and cache the trained model, or return ``None`` if unavailable.

    Returns the cached model on subsequent calls. A single failed attempt is
    remembered (cache stays ``None`` but ``_MODEL_TRIED`` flips) so we don't
    re-probe the disk / imports on every score.
    """
    global _MODEL_CACHE, _MODEL_TRIED
    if _MODEL_TRIED:
        return _MODEL_CACHE
    _MODEL_TRIED = True
    if not os.path.exists(_MODEL_PATH):
        _MODEL_CACHE = None
        return None
    try:
        import joblib            # optional
        import sklearn           # noqa: F401 — ensure the unpickled estimator can load

        _MODEL_CACHE = joblib.load(_MODEL_PATH)
    except Exception:
        _MODEL_CACHE = None
    return _MODEL_CACHE


def _model_loaded() -> bool:
    return _load_model() is not None


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def _heuristic_score(feats: dict) -> tuple[float, str, float]:
    """Map features to (score in 0..1, direction, confidence in 0..1).

    Transparent and bounded: a logistic squash of a weighted blend of momentum,
    multi-horizon returns, and a mean-reversion nudge from RSI. Confidence grows
    with the strength of the signal away from neutral (0.5) and is damped when
    realized volatility is high (noisy => less trustworthy).
    """
    # RSI re-centred to [-1, 1]; we lean slightly contrarian on extremes.
    rsi_centered = (feats["rsi_14"] - 50.0) / 50.0
    raw = (
        2.4 * feats["momentum"]
        + 1.1 * feats["ret_5"]
        + 0.6 * feats["ret_10"]
        + 0.3 * feats["ret_1"]
        - 0.25 * rsi_centered          # fade overbought / buy oversold, gently
    )
    score = 1.0 / (1.0 + math.exp(-12.0 * raw))   # logistic squash into (0,1)
    score = max(0.0, min(1.0, score))

    if score > 0.55:
        direction = "long"
    elif score < 0.45:
        direction = "short"
    else:
        direction = "flat"

    # Distance from neutral drives confidence; high vol erodes it.
    edge = abs(score - 0.5) * 2.0
    vol_penalty = min(0.4, feats["realized_vol"] * 4.0)
    confidence = max(0.0, min(1.0, edge * (1.0 - vol_penalty)))
    return score, direction, confidence


def _model_score(model: object, feats: dict) -> tuple[float, str, float]:
    """Score via the loaded sklearn estimator; degrade to heuristic on error."""
    try:
        vec = [_feature_vector(feats)]
        # Prefer calibrated probabilities when the estimator exposes them.
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(vec)[0]
            # Probability of the "up / long" class. Binary classifiers expose
            # classes_ as e.g. [0, 1]; default to the last column otherwise.
            score = float(proba[-1])
            classes = list(getattr(model, "classes_", []))
            if 1 in classes:
                score = float(proba[classes.index(1)])
        else:
            pred = float(model.predict(vec)[0])
            score = max(0.0, min(1.0, pred))
    except Exception:
        return _heuristic_score(feats)

    score = max(0.0, min(1.0, score))
    if score > 0.55:
        direction = "long"
    elif score < 0.45:
        direction = "short"
    else:
        direction = "flat"
    confidence = abs(score - 0.5) * 2.0
    return score, direction, confidence


def score_symbols(symbols: list[str]) -> list[dict]:
    """Score each symbol; one dict per symbol. Returns ``[]`` when disabled.

    Each dict: ``{"symbol", "score" (0..1), "direction" ("long"|"short"|"flat"),
    "confidence" (0..1), "source" ("model"|"heuristic")}``. Never raises — a
    per-symbol failure degrades that symbol to a neutral heuristic entry.
    """
    if not enabled():
        return []

    model = _load_model()
    use_model = model is not None
    out: list[dict] = []
    for sym in symbols:
        symbol = str(sym).strip().upper()
        try:
            feats = features_from_closes(_recent_closes(symbol))
            if use_model:
                score, direction, confidence = _model_score(model, feats)
                source = "model"
            else:
                score, direction, confidence = _heuristic_score(feats)
                source = "heuristic"
        except Exception:
            # Last-resort neutral entry so the list shape is always complete.
            score, direction, confidence, source = 0.5, "flat", 0.0, "heuristic"
        out.append({
            "symbol": symbol,
            "score": round(float(score), 6),
            "direction": direction,
            "confidence": round(float(confidence), 6),
            "source": source,
        })
    return out


def model_info() -> dict:
    """Report which scoring path is active and where the model would live."""
    loaded = _model_loaded()
    return {
        "loaded": loaded,
        "path": _MODEL_PATH,
        "source": "model" if loaded else "heuristic",
    }
