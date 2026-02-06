import logging
import ccxt
from config.broker_config import API_KEY, SECRET, PASSWORD
from execution.paper_trader import PaperTrader

class BitgetBroker:
    def __init__(self, paper_mode=True):
        self.paper_mode = paper_mode
        self.tracker = PaperTrader(balance=1000.0) if paper_mode else None
        self.exchange = ccxt.bitget({
            'apiKey': API_KEY,
            'secret': SECRET,
            'password': PASSWORD,
            'enableRateLimit': True,
        })
        if self.paper_mode:
            logging.info(" BROKER | Paper Trading Mode Active. Tracking simulated profit.")

    def price(self, symbol):
        ticker = self.exchange.fetch_ticker(symbol)
        return ticker['last']

    def balance(self, asset="USDT"):
        if self.paper_mode:
            return self.tracker.balance
        bal = self.exchange.fetch_balance()
        return bal.get(asset, {}).get('free', 0)

    def execute_order(self, symbol, side, amount):
        price = self.price(symbol)
        if self.paper_mode:
            cost = price * amount
            if side == "buy":
                self.tracker.balance -= cost
            else:
                self.tracker.balance += cost
            
            self.tracker.log_trade(symbol, side, price, amount)
            return {"status": "simulated", "price": price}
        
        if side == "buy":
            return self.exchange.create_market_buy_order(symbol, amount)
        else:
            return self.exchange.create_market_sell_order(symbol, amount)