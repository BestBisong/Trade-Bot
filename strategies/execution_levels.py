"""Shared ATR stop distance and trade-outcome labeling for ML + live execution."""
import numpy as np
import pandas as pd
import ta

from strategies.regime import get_regime_params


def compute_atr(df, window=14):
    series = ta.volatility.average_true_range(
        high=df["high"], low=df["low"], close=df["close"], window=window
    )
    if series is None or series.empty:
        return float(df["close"].iloc[-1]) * 0.001
    return float(series.iloc[-1])


def stop_distance(df, regime, tuned_params=None):
    """ATR-based stop distance with optional tuned widening."""
    params = get_regime_params(regime)
    scale = 1.0
    if tuned_params:
        scale = float(tuned_params.get("stop_atr_scale", 1.0))
    atr = compute_atr(df)
    return atr * float(params["sl_atr_mult"]) * scale


def passes_volatility_filter(df, tuned_params=None):
    """Skip dead/choppy markets where edge is eaten by fees."""
    if df is None or len(df) < 20:
        return False
    min_pct = 0.0015
    if tuned_params:
        min_pct = float(tuned_params.get("atr_min_pct", min_pct))
    atr = compute_atr(df)
    price = float(df["close"].iloc[-1])
    if price <= 0:
        return False
    return (atr / price) >= min_pct


def label_tp_before_sl(
    high,
    low,
    close,
    atr,
    max_bars=48,
    sl_atr_mult=2.0,
    rr_ratio=2.0,
):
    """
    Per-bar labels aligned with bot exits: 1 = long TP before SL, 0 = long SL before TP.
    Rows without a clear outcome within max_bars are NaN (dropped in training).
    """
    n = len(close)
    labels = np.full(n, np.nan)

    for i in range(n - max_bars - 1):
        entry = float(close[i])
        sl_dist = float(atr[i]) * sl_atr_mult
        if entry <= 0 or sl_dist <= 0 or np.isnan(sl_dist):
            continue

        tp = entry + sl_dist * rr_ratio
        sl = entry - sl_dist

        for j in range(i + 1, i + 1 + max_bars):
            if float(low[j]) <= sl:
                labels[i] = 0
                break
            if float(high[j]) >= tp:
                labels[i] = 1
                break

    return labels
