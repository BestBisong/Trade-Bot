import ta
from strategies.base_strategy import BaseStrategy

class RSIStrategy(BaseStrategy):
    def signal(self, df):
        df['rsi'] = ta.momentum.rsi(df['close'], window=14)
        if len(df) < 15: return "HOLD"
        
        rsi = df['rsi'].iloc[-1]
        
        # Robust threshold-based oversold/overbought signals
        if rsi < 35:
            return "BUY"
        elif rsi > 65:
            return "SELL"
            
        return "HOLD"