from strategies.base_strategy import BaseStrategy

class SMAStrategy(BaseStrategy):
    def signal(self, df):
        prices = df['close']
        sma_fast = prices.rolling(20).mean()
        sma_slow = prices.rolling(50).mean()

        # print(f"SMA Fast: {sma_fast.iloc[-1]}, SMA Slow: {sma_slow.iloc[-1]}")

        if sma_fast.iloc[-1] > sma_slow.iloc[-1]:
            return "BUY"
        elif sma_fast.iloc[-1] < sma_slow.iloc[-1]:
            return "SELL"
        return "HOLD"