class OrderExecutor:
    def __init__(self, broker):
        self.broker = broker

    def buy(self, symbol, amount):
        return self.broker.exchange.create_market_buy_order(symbol, amount)

    def sell(self, symbol, amount):
        return self.broker.exchange.create_market_sell_order(symbol, amount)