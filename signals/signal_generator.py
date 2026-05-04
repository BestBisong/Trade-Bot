from strategies.rsi_strategy import RSIStrategy
from strategies.bollinger_strategy import BollingerStrategy
from strategies.sma_strategy import SMAStrategy
from strategies.regime import detect_market_regime, get_regime_params

def generate(df, trend_df, ml, tuned_params=None):
    """
    JARVIS SIGNAL GENERATOR 2.0
    Weighted Scoring System:
    - Context (1H Trend): +1
    - Momentum (RSI/SMA): +1 each
    - Machine Learning: +2
    - Structure (Breakout/Pullback): +1 to +2
    """
    
    # 1. MARKET CONTEXT (The Foundation)
    trend_fast = trend_df['close'].rolling(20).mean().iloc[-1]
    trend_slow = trend_df['close'].rolling(50).mean().iloc[-1]
    market_bullish = trend_fast > trend_slow
    
    regime = detect_market_regime(df, trend_df)
    params = get_regime_params(regime)
    tuned = tuned_params or {}

    # 2. PRICE STRUCTURE (The Setup)
    session_lookback = df.tail(params["breakout_lookback"])
    session_high = session_lookback['high'].max()
    session_low = session_lookback['low'].min()
    current_price = df['close'].iloc[-1]
    
    # Range Position (0.0 = Bottom, 1.0 = Top)
    session_range = (session_high - session_low) or 1e-9
    range_pos = (current_price - session_low) / session_range
    
    # 3. CONFLUENCE JURORS (The Evidence)
    ml_prob = ml.confidence(df)
    rsi_sig = RSIStrategy().signal(df)
    sma_sig = SMAStrategy().signal(df)
    
    def sig_val(s): return 1 if s == "BUY" else (-1 if s == "SELL" else 0)
    
    # 4. WEIGHTED SCORING
    score = 0
    
    # Trend Alignment (+1)
    if (market_bullish and current_price > trend_fast): score += 1
    elif (not market_bullish and current_price < trend_fast): score -= 1
    
    # Indicators (+1 each)
    score += sig_val(rsi_sig)
    score += sig_val(sma_sig)
    
    # ML Confidence (+2 if strong)
    ml_threshold_long = float(tuned.get("ml_conf_long", 0.55))
    ml_threshold_short = float(tuned.get("ml_conf_short", 0.45))
    
    if ml_prob >= ml_threshold_long: score += 2
    elif ml_prob <= ml_threshold_short: score -= 2
    
    # Structure Scoring
    # Breakout is strong (+2), Pullback is subtle (+1)
    if current_price > session_high: score += 2
    elif current_price < session_low: score -= 2
    elif range_pos < 0.3 and market_bullish: score += 1 # Pullback in uptrend
    elif range_pos > 0.7 and not market_bullish: score -= 1 # Pullback in downtrend

    # Volume Surge (+1)
    avg_vol = df['volume'].rolling(20).mean().iloc[-2]
    if df['volume'].iloc[-2] > (avg_vol * params["volume_multiplier"]):
        if market_bullish: score += 1
        else: score -= 1

    # 5. FINAL VERDICT
    threshold = params["score_threshold"]
    
    if score >= threshold:
        return "BUY", f"SCORE:{score}|{regime.upper()}", 180
    elif score <= -threshold:
        return "SELL", f"SCORE:{score}|{regime.upper()}", 180

    # Diagnostics for Dashboard
    diag = f"SCORE:{score}|POS:{range_pos:.2f}|ML:{ml_prob:.2f}|{regime}"
    return "HOLD", diag, 0