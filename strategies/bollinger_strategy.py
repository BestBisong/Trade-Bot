import ta as ta_lib
from strategies.base_strategy import BaseStrategy

class BollingerStrategy(BaseStrategy):
    def signal(self, df):
        """Standard Bollinger Band mean-reversion for scalping."""
        indicator_bb = ta_lib.volatility.BollingerBands(
            close=df['close'], window=20, window_dev=2
        )
        
        last_price = df['close'].iloc[-1]
        lower_band = indicator_bb.bollinger_lband().iloc[-1]
        upper_band = indicator_bb.bollinger_hband().iloc[-1]
        # print(f"Bollinger Bands - Lower: {lower_band}, Upper: {upper_band}, Last Price: {last_price}")
        if last_price < lower_band:
            return "BUY"
        elif last_price > upper_band:
            return "SELL"
        return "HOLD"