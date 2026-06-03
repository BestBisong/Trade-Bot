"""Print signal mix and hold reasons for the last 180d window.

Usage:
  python scripts/diagnose_signals.py
  python scripts/diagnose_signals.py BTC/USDT
"""
import argparse
import datetime
import sys
import os
from collections import Counter

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)

import pandas as pd
from backtesting.historical_data import fetch_historical
from backtesting.self_tuner import load_tuned_params
from signals.signal_generator import generate
from strategies.ml_strategy import MLStrategy
from config.settings import SYMBOLS, TIMEFRAME, TREND_TIMEFRAME

since = int(
    (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=180)).timestamp() * 1000
)
STEP = 48


def _load_csv(symbol):
    path = os.path.join(
        root, "data", f"{symbol.replace('/', '_')}_{TIMEFRAME}.csv"
    )
    if not os.path.exists(path):
        return None, None
    base = pd.read_csv(path, parse_dates=["timestamp"])
    base.set_index("timestamp", inplace=True)
    base = base.iloc[-17280:]
    trend = base.resample("4h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    return base, trend


def diagnose_symbol(symbol, use_csv=False):
    if use_csv:
        base, trend = _load_csv(symbol)
    else:
        base = fetch_historical(symbol, TIMEFRAME, since=since)
        trend = fetch_historical(symbol, TREND_TIMEFRAME, since=since)
    if base is None or trend is None:
        print(f"{symbol}: no data")
        return

    ml = MLStrategy(load_pretrained=True)
    tuned = load_tuned_params()["params"]
    signals = Counter()
    holds = Counter()

    for i in range(200, len(base), STEP):
        sub = base.iloc[: i + 1].tail(200)
        tr = trend.loc[trend.index <= sub.index[-1]].tail(150)
        if len(tr) < 55:
            continue
        sig, status, _ = generate(sub, tr, ml, tuned_params=tuned)
        signals[sig] += 1
        if sig == "HOLD":
            holds[status.split("|")[0] if status else "?"] += 1

    print(f"\n{symbol}: {dict(signals)}")
    if holds:
        print(f"  top HOLD: {holds.most_common(5)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol", nargs="?", help="e.g. BTC/USDT (default: all)")
    parser.add_argument("--csv", action="store_true", help="use local data/*.csv (fast)")
    args = parser.parse_args()
    symbols = [args.symbol] if args.symbol else SYMBOLS
    for sym in symbols:
        print(f"Scanning {sym} ...", flush=True)
        diagnose_symbol(sym, use_csv=args.csv)


if __name__ == "__main__":
    main()
