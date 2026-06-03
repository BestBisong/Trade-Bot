from strategies.rsi_strategy import RSIStrategy
from strategies.bollinger_strategy import BollingerStrategy
from strategies.sma_strategy import SMAStrategy
from strategies.regime import detect_market_regime, get_regime_params

_RSI = RSIStrategy()
_MACD = SMAStrategy()
_BB = BollingerStrategy()


def generate(df, trend_df, ml, tuned_params=None):
    """
    Original JARVIS scoring (restored). Only addition: block trades against 4h trend
    so shorts do not pile up in bull periods (289 sell / 13 buy bug).
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
        if current_price > session_high:
            score -= 1.5
        elif current_price < session_low:
            score += 1.5

        score += sig_val(bb_sig) * 2.5
        score += sig_val(rsi_sig) * 2.0
        score += sig_val(sma_sig) * 0.5

    if regime == "trending":
        ml_threshold_long = float(tuned.get("ml_conf_long_trending", 0.58))
        ml_threshold_short = float(tuned.get("ml_conf_short_trending", 0.42))
    elif regime == "volatile":
        ml_threshold_long = float(tuned.get("ml_conf_long_volatile", 0.60))
        ml_threshold_short = float(tuned.get("ml_conf_short_volatile", 0.40))
    else:
        ml_threshold_long = float(tuned.get("ml_conf_long_ranging", 0.60))
        ml_threshold_short = float(tuned.get("ml_conf_short_ranging", 0.40))

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
        diag = f"SCORE:{score}|POS:{range_pos:.2f}|ML:{ml_prob:.2f}|{regime}"
        return "HOLD", diag, 0

    if signal == "BUY" and not market_bullish:
        return "HOLD", f"FILTER:4H_BEAR|{regime}", 0
    if signal == "SELL" and market_bullish:
        return "HOLD", f"FILTER:4H_BULL|{regime}", 0

    return signal, f"SCORE:{score}|{regime.upper()}", 180
