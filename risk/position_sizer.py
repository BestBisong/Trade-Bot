class PositionSizer:
    def __init__(self, risk_percent=1):
        self.risk_percent = risk_percent / 100

    def size(self, balance, current_price):
        risk_amount = balance * self.risk_percent
        quantity = risk_amount / current_price
       
        if (quantity * current_price) < 0.1:
            return 0
            
# In live trading, use the exchange minimum (5.0)
# exchange_min = 5.0 
# if (quantity * current_price) < exchange_min:
#     return 0
        return round(quantity, 6)