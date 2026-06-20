import numpy as np
import pandas as pd

import ta


def detect_market_regime(df, trend_df):
    if df is None or len(df) < 50:
        return "ranging"

    try:
        sma20 = df["close"].rolling(20).mean()
        x = np.arange(20)
        slope = np.polyfit(x, sma20.tail(20).values, 1)[0]
        slope_norm = slope / df["close"].iloc[-1]
    except Exception:
        slope_norm = 0.0

    try:
        atr_series = ta.volatility.average_true_range(
            df["high"], df["low"], df["close"], window=14
        )
        atr_norm = float((atr_series / df["close"]).iloc[-1]) if not atr_series.empty else 0.002
    except Exception:
        atr_norm = 0.002

    if abs(slope_norm) > 0.0006:
        return "trending"
    elif atr_norm > 0.005:
        return "volatile"
    else:
        return "ranging"


def get_regime_params(regime, symbol="BTC/USDT"):
    is_alt = symbol != "BTC/USDT"
    if regime == "trending":
        return {
            "breakout_lookback": 12,
            "volume_multiplier": 1.1,
            "score_threshold": 2.5,
            "sl_atr_mult": 3.0 if is_alt else 2.0,
            "rr_ratio": 2.0 if is_alt else 2.5,
        }
    elif regime == "volatile":
        return {
            "breakout_lookback": 20,
            "volume_multiplier": 1.5,
            "score_threshold": 99.0,
            "sl_atr_mult": 4.0 if is_alt else 3.0,
            "rr_ratio": 1.5,
        }
    else:
        return {
            "breakout_lookback": 8,
            "volume_multiplier": 0.9,
            "score_threshold": 3.5,
            "sl_atr_mult": 3.0 if is_alt else 2.0,
            "rr_ratio": 1.5,
        }



