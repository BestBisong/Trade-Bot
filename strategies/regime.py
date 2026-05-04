import numpy as np
import pandas as pd

def detect_market_regime(df, trend_df):
    """
    Advanced Regime Detection:
    - Trending: Strong ADX (>25) and price above/below key MAs.
    - Volatile: High ATR relative to average.
    - Ranging: Low ADX and sideways price action.
    """
    if df is None or len(df) < 50:
        return "ranging"

    # Calculate ADX (Directional Movement)
    # Simplified version for speed
    plus_dm = df['high'].diff().clip(lower=0)
    minus_dm = df['low'].diff().clip(lower=0)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low'] - df['close'].shift()).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(14).mean()
    atr_norm = atr / df['close']
    
    # Trend Strength (Slope of 20 SMA)
    sma20 = df['close'].rolling(20).mean()
    x = np.arange(20)
    slope = np.polyfit(x, sma20.tail(20).values, 1)[0]
    slope_norm = slope / df['close'].iloc[-1]

    # Classification
    if abs(slope_norm) > 0.0002:
        return "trending"
    elif atr_norm.iloc[-1] > 0.005:
        return "volatile"
    else:
        return "ranging"

def get_regime_params(regime):
    """Execution parameters tailored to the detected regime."""
    if regime == "trending":
        return {
            "breakout_lookback": 12,
            "volume_multiplier": 1.1,
            "score_threshold": 3,
            "sl_atr_mult": 1.5,
            "rr_ratio": 2.5,
        }
    elif regime == "volatile":
        return {
            "breakout_lookback": 20,
            "volume_multiplier": 1.5,
            "score_threshold": 4,
            "sl_atr_mult": 2.5,
            "rr_ratio": 1.5,
        }
    else: # ranging
        return {
            "breakout_lookback": 8,
            "volume_multiplier": 0.9,
            "score_threshold": 2,
            "sl_atr_mult": 1.2,
            "rr_ratio": 1.8,
        }

