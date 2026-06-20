from strategies.rsi_strategy import RSIStrategy
from strategies.bollinger_strategy import BollingerStrategy
from strategies.sma_strategy import SMAStrategy
from strategies.regime import detect_market_regime, get_regime_params

_RSI = RSIStrategy()
_MACD = SMAStrategy()
_BB = BollingerStrategy()


def generate(df, trend_df, ml, tuned_params=None):
    """
    JARVIS scoring with adaptive regime adjustments.
    In Ranging/Volatile regimes, trend-following filters are bypassed to allow trading range swings.
    In Trending regimes, strict 4H trend-following is enforced.
    """
    tuned = tuned_params or {}

    trend_fast = trend_df["close"].rolling(20).mean().iloc[-1]
    trend_slow = trend_df["close"].rolling(50).mean().iloc[-1]
    market_bullish = trend_fast > trend_slow

    regime = detect_market_regime(df, trend_df)
    params = get_regime_params(regime)

    session_lookback = df.tail(params["breakout_lookback"])
    session_high = session_lookback["high"].max()
    session_low = session_lookback["low"].min()
    current_price = df["close"].iloc[-1]

    session_range = (session_high - session_low) or 1e-9
    range_pos = (current_price - session_low) / session_range

    ml_prob = ml.confidence(df)
    rsi_sig = _RSI.signal(df)
    sma_sig = _MACD.signal(df)
    bb_sig = _BB.signal(df)

    def sig_val(s):
        return 1 if s == "BUY" else (-1 if s == "SELL" else 0)

    score = 0.0

    if regime == "trending":
        if (market_bullish and current_price > trend_fast):
            score += 2.0
        elif ((not market_bullish) and current_price < trend_fast):
            score -= 2.0

        score += sig_val(sma_sig) * 2.0

        if bb_sig == "SELL" and market_bullish:
            score += 1.5
        elif bb_sig == "BUY" and (not market_bullish):
            score -= 1.5

        if rsi_sig == "BUY" and market_bullish:
            score += 1.0
        elif rsi_sig == "SELL" and (not market_bullish):
            score -= 1.0

    elif regime == "volatile":
        if current_price > session_high:
            score += 2.5
        elif current_price < session_low:
            score -= 2.5
        score += sig_val(sma_sig) * 1.0
        score += sig_val(rsi_sig) * 1.0

    else:
        # Ranging regime: trade mean reversion
        if current_price > session_high:
            score -= 1.5
        elif current_price < session_low:
            score += 1.5

        score += sig_val(bb_sig) * 2.5
        score += sig_val(rsi_sig) * 2.0
        score += sig_val(sma_sig) * 0.5

    # Adaptive ML thresholds
    if regime == "trending":
        ml_threshold_long = float(tuned.get("ml_conf_long_trending", 0.58))
        ml_threshold_short = float(tuned.get("ml_conf_short_trending", 0.42))
    elif regime == "volatile":
        ml_threshold_long = float(tuned.get("ml_conf_long_volatile", 0.60))
        ml_threshold_short = float(tuned.get("ml_conf_short_volatile", 0.40))
    else:
        # Ranging: slightly lower thresholds to adapt to lower volatility ranging markets
        ml_threshold_long = float(tuned.get("ml_conf_long_ranging", 0.55))
        ml_threshold_short = float(tuned.get("ml_conf_short_ranging", 0.45))

    if ml_prob >= ml_threshold_long:
        score += 2.0
    elif ml_prob <= ml_threshold_short:
        score -= 2.0

    avg_vol = df["volume"].rolling(20).mean().iloc[-2]
    if df["volume"].iloc[-2] > (avg_vol * params["volume_multiplier"]):
        if market_bullish:
            score += 1.0
        else:
            score -= 1.0

    threshold = params["score_threshold"]

    if score >= threshold:
        signal = "BUY"
    elif score <= -threshold:
        signal = "SELL"
    else:
        signal = "HOLD"

    details = {
        "regime": regime,
        "score": round(score, 2),
        "threshold": threshold,
        "ml_prob": round(ml_prob, 4),
        "rsi": round(float(df["rsi"].iloc[-1]), 2) if "rsi" in df else None,
        "rsi_sig": rsi_sig,
        "sma_sig": sma_sig,
        "bb_sig": bb_sig,
        "market_bullish": bool(market_bullish),
        "blocked_by": None
    }

    if signal == "HOLD":
        diag = f"SCORE:{score:.1f}|POS:{range_pos:.2f}|ML:{ml_prob:.2f}|{regime}"
        details["blocked_by"] = "INSUFFICIENT_SCORE"
        return "HOLD", diag, details

    # Strict trend filter applied to all regimes if enabled
    trend_guard_enabled = tuned.get("trend_guard_enabled", True)
    if trend_guard_enabled:
        if signal == "BUY" and not market_bullish:
            details["blocked_by"] = "4H_BEAR_TREND_GUARD"
            return "HOLD", f"FILTER:4H_BEAR|{regime}", details
        if signal == "SELL" and market_bullish:
            details["blocked_by"] = "4H_BULL_TREND_GUARD"
            return "HOLD", f"FILTER:4H_BULL|{regime}", details

    return signal, f"SCORE:{score:.1f}|{regime.upper()}", details
