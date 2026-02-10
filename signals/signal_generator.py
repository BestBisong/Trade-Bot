from strategies.sma_strategy import SMAStrategy
from strategies.rsi_strategy import RSIStrategy
from strategies.bollinger_strategy import BollingerStrategy

def generate(df, ml, sentiment=0.5, stock_context=0.0):
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
    
    # Contextual Modifiers
    if sentiment > 0.65: score += 1
    if stock_context < -0.01: score -= 2 # Negative stock market drag

    # Signal Returns: (Signal, Reason, Window_Minutes)
    if score >= 5 and signals["ML"] == "BUY":
        return "BUY", "ULTRA_CONFIDENCE", 60
    elif score >= 3 and signals["ML"] == "BUY":
        return "BUY", "BALANCED_ENTRY", 30
        
    return "HOLD", "INSUFFICIENT_ALIGNMENT", 0