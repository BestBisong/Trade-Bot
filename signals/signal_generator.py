import logging
from strategies.sma_strategy import SMAStrategy
from strategies.rsi_strategy import RSIStrategy
from strategies.bollinger_strategy import BollingerStrategy

def generate(df, ml):
    """
    Balanced Signal Generator: Uses a weighted system to find high-probability 
    trades without being overly restrictive.
    """
    sma = SMAStrategy()
    rsi = RSIStrategy()
    bb = BollingerStrategy()
    

    signals = {
        "SMA": sma.signal(df),
        "RSI": rsi.signal(df),
        "BB": bb.signal(df),
        "ML": ml.signal(df)
    }
    
    
    score = 0
    if signals["ML"] == "BUY": score += 2
    if signals["SMA"] == "BUY": score += 1
    if signals["RSI"] == "BUY": score += 1
    if signals["BB"] == "BUY": score += 1
    

    if score >= 4 and signals["ML"] == "BUY":
        return "BUY", f"HIGH_CONFIDENCE_{score}_PTS", 20
    elif score >= 3 and signals["ML"] == "BUY":
        return "BUY", f"BALANCED_ENTRY_{score}_PTS", 10
        
    return "HOLD", "INSUFFICIENT_ALIGNMENT", 0