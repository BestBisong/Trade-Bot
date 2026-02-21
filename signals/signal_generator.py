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
    
    buy_score = 0
    sell_score = 0
    
    # Weighting: ML = 2 points, Others = 1 point
    for key, val in signals.items():
        weight = 2 if key == "ML" else 1
        if val == "BUY": buy_score += weight
        if val == "SELL": sell_score += weight

    # Logic for entering trades with specific time windows
    if buy_score >= 3 and signals["ML"] == "BUY":
        return "BUY", "BULLISH_ALIGNMENT", 60 # 60 minute window for long
        
    if sell_score >= 3 and signals["ML"] == "SELL":
        return "SELL", "BEARISH_ALIGNMENT", 30 # 30 minute window for short
        
    return "HOLD", "INSUFFICIENT_ALIGNMENT", 0