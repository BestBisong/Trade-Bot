import pandas as pd

from backtesting.walk_forward import run_walk_forward_validation, live_gate_from_walk_forward


class Backtester:
    def __init__(self, symbols, timeframe="5m", trend_timeframe="1h"):
        self.symbols = symbols
        self.timeframe = timeframe
        self.trend_timeframe = trend_timeframe

    def run_backtest(self):
        report = run_walk_forward_validation(
            symbols=self.symbols,
            timeframe=self.timeframe,
            trend_timeframe=self.trend_timeframe,
        )
        gate = live_gate_from_walk_forward(report)

        rows = report.get("windows", [])
        df = pd.DataFrame(rows)
        if not df.empty:
            df["live_gate_allowed"] = gate["allowed"]
        return df
