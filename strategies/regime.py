import numpy as np


def detect_market_regime(df, trend_df):
    """Classify market as trending or ranging from slope and normalized MA spread."""
    if df is None or trend_df is None or len(df) < 60 or len(trend_df) < 60:
        return "ranging"

    close = trend_df["close"]
    fast = close.rolling(20).mean().iloc[-1]
    slow = close.rolling(50).mean().iloc[-1]
    last_close = close.iloc[-1]

    if last_close <= 0:
        return "ranging"

    ma_spread = abs(fast - slow) / last_close

    slope_window = close.tail(20).values
    x = np.arange(len(slope_window))
    slope = np.polyfit(x, slope_window, 1)[0]
    slope_norm = abs(slope) / (last_close + 1e-9)

    if ma_spread > 0.003 and slope_norm > 0.00015:
        return "trending"
    return "ranging"


def get_regime_params(regime):
    """Return execution and signal parameters tuned to market regime."""
    if regime == "trending":
        return {
            "breakout_lookback": 16,
            "volume_multiplier": 1.05,
            "score_threshold": 2,
            "sl_atr_mult": 1.8,
            "rr_ratio": 2.4,
        }

    return {
        "breakout_lookback": 10,
        "volume_multiplier": 1.20,
        "score_threshold": 3,
        "sl_atr_mult": 1.2,
        "rr_ratio": 1.6,
    }
