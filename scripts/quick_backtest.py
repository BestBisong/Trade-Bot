"""Fast local backtest on saved CSV (one symbol) for iteration."""
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)

import pandas as pd
from backtest_full import run_backtest_symbol, INITIAL_CAPITAL
from backtesting.performance import compute_metrics
from backtesting.self_tuner import load_tuned_params
from strategies.ml_strategy import MLStrategy

SYMBOL = "BTC/USDT"
TF = "15m"
TREND_TF = "4h"
START_IDX = 2000
LOOKBACK_BARS = 17280  # ~180d on 15m


def main():
    base = pd.read_csv(os.path.join(root, "data", f"BTC_USDT_{TF}.csv"), parse_dates=["timestamp"])
    base.set_index("timestamp", inplace=True)
    if len(base) > LOOKBACK_BARS + START_IDX:
        base = base.iloc[-(LOOKBACK_BARS + START_IDX) :]
    trend = base.resample("4h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()

    tuned = load_tuned_params()["params"]
    ml = MLStrategy(model_path=None, load_pretrained=False)
    ml.fit_from_dataframe(base.iloc[:START_IDX])

    trades = run_backtest_symbol(SYMBOL, base, trend, ml, tuned, start_idx=START_IDX)
    m = compute_metrics(trades, INITIAL_CAPITAL)
    print(m)
    buys = [t for t in trades if t["side"] == "buy"]
    sells = [t for t in trades if t["side"] == "sell"]
    print(f"buys={len(buys)} sells={len(sells)}")


if __name__ == "__main__":
    main()
