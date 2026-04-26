from strategies.rsi_strategy import RSIStrategy
from strategies.bollinger_strategy import BollingerStrategy
from strategies.sma_strategy import SMAStrategy
from strategies.regime import detect_market_regime, get_regime_params

def generate(df, trend_df, ml, tuned_params=None):
    """
    JARVIS SIGNAL GENERATOR
    Implements: Multi-Timeframe Trend Alignment, Session Breakout Planning, 
    and High-Conviction Confluence.
    """
    
    # 1. BIG PICTURE: 1H Trend Alignment (The Compass)
    # We strictly align with the 1-hour 20 SMA to catch 'Big Moves'
    trend_fast = trend_df['close'].rolling(20).mean().iloc[-1]
    trend_slow = trend_df['close'].rolling(50).mean().iloc[-1]
    market_bullish = trend_fast > trend_slow
    
    regime = detect_market_regime(df, trend_df)
    params = get_regime_params(regime)
    tuned = tuned_params or {}

    # 2. MARKET PLANNING: Session Range (The Sniper Nest)
    session_lookback = df.tail(params["breakout_lookback"])
    session_high = session_lookback['high'].max()
    session_low = session_lookback['low'].min()
    current_price = df['close'].iloc[-1]
    ml_prob_up = ml.confidence(df)
    
    # 3. COLLECT SIGNALS (The Jurors)
    ml_sig = ml.signal(df)
    rsi_sig = RSIStrategy().signal(df)
    bb_sig = BollingerStrategy().signal(df)
    sma_sig = SMAStrategy().signal(df)

    def score(sig):
        return 1 if sig == "BUY" else (-1 if sig == "SELL" else 0)

    # 4. CALCULATE CONVICTION (The Filter)
    # We require the ML 'Brain' and at least one other juror to agree
    weighted_score = (
        2 * score(ml_sig)
        + 1 * score(sma_sig)
        + 1 * score(rsi_sig)
        + 1 * score(bb_sig)
    )
    
    # 5. VOLUME CONFIRMATION (The Engine)
    # Moves without volume are 'fake-outs'
    avg_vol = df['volume'].rolling(20).mean().iloc[-1]
    high_volume = df['volume'].iloc[-1] > (avg_vol * params["volume_multiplier"])

    atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
    atr = float(atr) if atr and atr > 0 else 0.0
    atr_pct = (atr / current_price) if current_price > 0 else 0.0

    # 6. FINAL EXECUTION LOGIC (The Action)
    
    # LONG CONDITIONS:
    # Bullish Trend + ML Buy + Juror Support + Volume Spike + Breakout above Session High
    is_long_breakout = current_price > session_high
    conf_long = float(tuned.get("ml_conf_long_trending", 0.57) if regime == "trending" else tuned.get("ml_conf_long_ranging", 0.60))
    conf_short = float(tuned.get("ml_conf_short_trending", 0.43) if regime == "trending" else tuned.get("ml_conf_short_ranging", 0.40))
    atr_floor = float(tuned.get("atr_min_pct", 0.0015))

    ml_conf_long_ok = ml_prob_up >= conf_long
    score_threshold = params["score_threshold"]

    if market_bullish and weighted_score >= score_threshold and high_volume and is_long_breakout and ml_conf_long_ok and atr_pct >= atr_floor:
        return "BUY", f"JARVIS_CONFIRMED_LONG_BREAKOUT|REGIME:{regime}", 180
        
    # SHORT CONDITIONS:
    # Bearish Trend + ML Sell + Juror Support + Volume Spike + Breakout below Session Low
    is_short_breakout = current_price < session_low
    ml_conf_short_ok = ml_prob_up <= conf_short
    if (not market_bullish) and weighted_score <= -score_threshold and high_volume and is_short_breakout and ml_conf_short_ok and atr_pct >= atr_floor:
        return "SELL", f"JARVIS_CONFIRMED_SHORT_BREAKOUT|REGIME:{regime}", 180

    # 7. DIAGNOSTICS: Tell the Dashboard why we are holding
    reasons = []
    if not high_volume:
        reasons.append("LOW_VOLUME_ZONE")
    if score(ml_sig) > 0 and not is_long_breakout:
        reasons.append("AWAITING_HIGH_BREAKOUT")
    if score(ml_sig) < 0 and not is_short_breakout:
        reasons.append("AWAITING_LOW_BREAKOUT")
    if score(ml_sig) > 0 and not market_bullish:
        reasons.append("TREND_CONFLICT_BEARISH_1H")
    if score(ml_sig) < 0 and market_bullish:
        reasons.append("TREND_CONFLICT_BULLISH_1H")
    if abs(weighted_score) < score_threshold:
        reasons.append("WEAK_CONFLUENCE")
    if atr_pct < atr_floor:
        reasons.append("LOW_VOLATILITY_EDGE")
    if score(ml_sig) > 0 and not ml_conf_long_ok:
        reasons.append("LOW_ML_CONFIDENCE_LONG")
    if score(ml_sig) < 0 and not ml_conf_short_ok:
        reasons.append("LOW_ML_CONFIDENCE_SHORT")
    reasons.append(f"REGIME:{regime}")

    reason = "|".join(reasons) if reasons else "WAITING_FOR_CONFLUENCE"

    return "HOLD", reason, 0