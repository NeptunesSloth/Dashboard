"""Offline trainer for the Tier-A trading-signal model. NOT run in CI.

Builds a tiny next-day-direction classifier on top of the SAME features the
runtime uses (``maybot_control_center.signals.features_from_closes``) and saves
it to ``maybot_control_center/models/signal_model.joblib`` so the runtime picks
it up automatically (``source == "model"``).

Usage
-----
    # From a local OHLCV CSV (columns: date, open, high, low, close, volume):
    python3 tools/train_signal.py --csv data/AAPL.csv

    # Or pull daily bars via yfinance (needs the lib + a network):
    python3 tools/train_signal.py --symbols AAPL NVDA MSFT --period 5y

    # Pick the estimator and the test fraction (held out as the FUTURE tail):
    python3 tools/train_signal.py --csv data/AAPL.csv --model gbm --test-frac 0.25

Honesty caveats (read before trusting any number this prints)
-------------------------------------------------------------
* Overfitting: with a handful of noisy features and a flexible estimator it is
  trivial to fit the past. In-sample accuracy means nothing.
* Leakage: features must use ONLY information available at decision time. We
  label with the *next* bar's direction and train strictly on the *past* tail,
  testing on the *future* tail (walk-forward, NO shuffling). Shuffling a time
  series leaks the future into training and inflates accuracy — do not do it.
* Regime change: a model fit on one regime (low-vol bull, say) routinely fails
  in another. A test-set edge over buy-and-hold is necessary, not sufficient.
* Costs: real fills pay spread + commission + slippage. We print a crude
  cost-aware hit-rate, but it is a sanity check, not a backtest.

All heavy imports (numpy, pandas, sklearn, joblib, yfinance) are guarded so this
file at least *parses* and prints a helpful message without them.
"""
from __future__ import annotations

import argparse
import os
import sys

# Make the package importable when run as a plain script from the repo root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from maybot_control_center import signals  # pure-python, always importable

_MODEL_OUT = os.path.join(_REPO_ROOT, "maybot_control_center", "models", "signal_model.joblib")


def _load_csv_closes(path: str) -> list[float]:
    """Read close prices from an OHLCV CSV using only the stdlib csv module."""
    import csv

    closes: list[float] = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        # Tolerate Close/close/CLOSE column naming.
        fields = {f.lower(): f for f in (reader.fieldnames or [])}
        col = fields.get("close")
        if not col:
            raise SystemExit(f"CSV {path!r} has no 'close' column (found: {reader.fieldnames})")
        for row in reader:
            try:
                closes.append(float(row[col]))
            except (TypeError, ValueError):
                continue
    return closes


def _load_yf_closes(symbol: str, period: str) -> list[float]:
    """Pull daily closes via yfinance; raises if unavailable so caller can warn."""
    import yfinance as yf  # guarded by caller

    data = yf.Ticker(symbol).history(period=period, interval="1d")
    return [float(c) for c in list(data["Close"])]


def _build_dataset(closes: list[float]) -> tuple[list[list[float]], list[int]]:
    """Build (X, y) where y is next-bar up(1)/down(0) and X are PAST-only features.

    We slide a window over the series, computing features from closes[:i+1]
    (information available at time i) and labelling with the sign of the return
    from i -> i+1. This ordering is what keeps the future out of the features.
    """
    X: list[list[float]] = []
    y: list[int] = []
    order = ("ret_1", "ret_5", "ret_10", "momentum", "rsi_14", "realized_vol")
    # Need some history for stable features; start once we have >= 20 bars.
    for i in range(20, len(closes) - 1):
        feats = signals.features_from_closes(closes[: i + 1])
        X.append([float(feats[k]) for k in order])
        nxt = closes[i + 1]
        cur = closes[i]
        y.append(1 if (cur and nxt > cur) else 0)
    return X, y


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the offline signal model.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", help="Path to an OHLCV CSV with a 'close' column.")
    src.add_argument("--symbols", nargs="+", help="Symbols to pull via yfinance.")
    parser.add_argument("--period", default="5y", help="yfinance lookback (default 5y).")
    parser.add_argument("--model", choices=["logreg", "gbm"], default="logreg",
                        help="logreg=LogisticRegression, gbm=GradientBoosting.")
    parser.add_argument("--test-frac", type=float, default=0.25,
                        help="Fraction of the FUTURE tail held out for testing.")
    parser.add_argument("--cost-bps", type=float, default=5.0,
                        help="Round-trip cost in basis points for the cost-aware hit-rate.")
    parser.add_argument("--out", default=_MODEL_OUT, help="Where to save the model.")
    args = parser.parse_args(argv)

    # ---- Guard heavy imports here so --help / parse works without the libs. ----
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import GradientBoostingClassifier
        import joblib
    except Exception as exc:  # pragma: no cover - depends on optional libs
        print(f"[train_signal] ML libs unavailable ({exc}). "
              f"Install scikit-learn + joblib to train. Aborting.", file=sys.stderr)
        return 2

    # ---- Gather close prices from CSV or yfinance. ----
    closes: list[float] = []
    if args.csv:
        closes = _load_csv_closes(args.csv)
    else:
        for sym in args.symbols:
            try:
                closes.extend(_load_yf_closes(sym, args.period))
            except Exception as exc:  # pragma: no cover - network/lib dependent
                print(f"[train_signal] could not pull {sym}: {exc}", file=sys.stderr)
    closes = [c for c in closes if isinstance(c, (int, float)) and c > 0]
    if len(closes) < 60:
        print(f"[train_signal] need >=60 usable closes, got {len(closes)}.", file=sys.stderr)
        return 2

    X, y = _build_dataset(closes)
    if len(set(y)) < 2:
        print("[train_signal] labels are single-class; cannot train.", file=sys.stderr)
        return 2

    # ---- WALK-FORWARD split: train on the PAST, test on the FUTURE. ----
    # NO shuffling. Shuffling a time series lets the model peek at future bars
    # that share information with the test set (autocorrelation, overlapping
    # windows) and badly inflates accuracy. The split index is purely temporal.
    split = int(len(X) * (1.0 - args.test_frac))
    split = max(1, min(split, len(X) - 1))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    if args.model == "gbm":
        clf = GradientBoostingClassifier(random_state=0)
    else:
        clf = LogisticRegression(max_iter=1000)
    clf.fit(X_train, y_train)

    # ---- Metrics. ----
    preds = list(clf.predict(X_test))
    acc = sum(int(p == t) for p, t in zip(preds, y_test)) / len(y_test)

    # Buy-and-hold baseline = base rate of "up" days in the test window. Beating
    # this is the bar; a model that just predicts "up" every day matches it.
    baseline = sum(y_test) / len(y_test)

    # Cost-aware hit-rate: only count a trade as a "win" when the predicted move
    # clears a round-trip cost threshold. Here we approximate by requiring the
    # next-bar return magnitude (recovered from the test slice) to exceed cost.
    test_closes = closes[20 + split + 1:]  # aligns roughly with X_test labels
    cost = args.cost_bps / 10_000.0
    wins = traded = 0
    for k, p in enumerate(preds):
        if k + 1 >= len(test_closes):
            break
        cur, nxt = test_closes[k], test_closes[k + 1]
        if not cur:
            continue
        ret = (nxt - cur) / cur
        if abs(ret) <= cost:                 # move too small to overcome costs
            continue
        traded += 1
        went_up = ret > 0
        if (p == 1 and went_up) or (p == 0 and not went_up):
            wins += 1
    cost_hit = (wins / traded) if traded else float("nan")

    print(f"[train_signal] model={args.model}  n_train={len(X_train)}  n_test={len(X_test)}")
    print(f"[train_signal] test accuracy        : {acc:.4f}")
    print(f"[train_signal] buy-and-hold baseline: {baseline:.4f}  (base rate of up-days)")
    print(f"[train_signal] cost-aware hit-rate  : {cost_hit:.4f}  "
          f"({traded} trades clearing {args.cost_bps:.1f} bps)")
    if acc <= baseline:
        print("[train_signal] WARNING: model does not beat the naive baseline. "
              "Treat as no edge.")

    # ---- Save. ----
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    joblib.dump(clf, args.out)
    print(f"[train_signal] saved model -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
