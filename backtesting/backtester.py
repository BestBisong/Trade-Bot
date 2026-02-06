import pandas as pd
from signals.signal_generator import generate

class Backtester:
    def __init__(self, initial_balance=1000):
        self.balance = initial_balance
        self.history = []

    def run_backtest(self, df):
        """Processes historical data through the hybrid strategy."""
        
        for i in range(50, len(df)):
            window = df.iloc[:i+1]
            signal, status = generate(window)
            
            if signal != "HOLD":
                price = window['close'].iloc[-1]
                self.history.append({
                    'timestamp': window.index[-1],
                    'signal': signal,
                    'price': price,
                    'strategy': status
                })
        
        return pd.DataFrame(self.history)