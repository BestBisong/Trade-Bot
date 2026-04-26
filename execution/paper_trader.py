import json, os
from datetime import datetime

class PaperTrader:
    def __init__(self, balance=100.0, filename="trade_history.json"):
        self.filename = filename
        self.initial_balance = 100.0
        self.balance = 100.0
        self.trades = []
        self.open_positions = {}

        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    self.trades = data.get("trades", [])
                
                # Inherit balance from the last successful trade
                if self.trades:
                    last_trade = self.trades[-1]
                    self.balance = last_trade.get('balance_after', 100.0)
                
                self._sync_open_positions()
                print(f"DATABASE | Recalibrated Start: {self.initial_balance} | Current: {self.balance}")
            except Exception as e:
                print(f"DATABASE_ERROR | {e}. Starting fresh at $15.")
        
    def _sync_open_positions(self):
        # Tracks active trades based on history to prevent duplicate opens
        active = {}
        for t in self.trades:
            if t['side'] == "buy": active[t['symbol']] = True
            elif t['side'] == "sell": active.pop(t['symbol'], None)
        self.open_positions = active

    def log_trade(self, symbol, side, price, amount):
        now = datetime.now()
        self.trades.append({
            "timestamp": now.isoformat(),
            "symbol": symbol,
            "side": side,
            "price": price,
            "amount": amount,
            "balance_after": self.balance # Logged after Broker updates balance
        })
        self.save_data()