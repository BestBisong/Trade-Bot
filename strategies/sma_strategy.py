from strategies.base_strategy import BaseStrategy

class SMAStrategy(BaseStrategy):
    def signal(self, df):
        prices = df['close']
        
        # Use EMA for faster reaction time
        ema_fast = prices.ewm(span=12, adjust=False).mean()
        ema_slow = prices.ewm(span=26, adjust=False).mean()
        
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=9, adjust=False).mean()

        if len(macd) < 3: return "HOLD"

        # Identify trend direction
        trend_fast = prices.rolling(20).mean().iloc[-1]
        trend_slow = prices.rolling(50).mean().iloc[-1]
        market_bullish = trend_fast > trend_slow

        # Detect accelerating momentum (crossing AND expanding)
        bull_cross = (macd.iloc[-1] > signal_line.iloc[-1]) and (macd.iloc[-2] <= signal_line.iloc[-2])
        bear_cross = (macd.iloc[-1] < signal_line.iloc[-1]) and (macd.iloc[-2] >= signal_line.iloc[-2])

        # Regime-aware indicator responses
        if market_bullish:
            # Bullish market: only trade continuation buys, never short
            if bull_cross:
                return "BUY"
        else:
            # Bearish market: only trade continuation shorts, never buy dips
            if bear_cross:
                return "SELL"
                
        return "HOLD"