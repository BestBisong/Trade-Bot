import ta
from strategies.base_strategy import BaseStrategy

class RSIStrategy(BaseStrategy):
    def signal(self, df):
        df['rsi'] = ta.momentum.rsi(df['close'], window=14)
        rsi = df['rsi'].iloc[-1]
        
        # Standard Overbought/Oversold
        if rsi < 30: return "BUY"
        if rsi > 70: return "SELL"
        
    
        if len(df) > 10:
            price_lows = df['low'].tail(10).values
            rsi_lows = df['rsi'].tail(10).values
            if price_lows[-1] < price_lows[-5] and rsi_lows[-1] > rsi_lows[-5]:
                if rsi < 40: return "BUY" # Early entry on divergence
                
        return "HOLD"