import logging

class RiskManager:
    def __init__(self, max_daily_loss=10):
        self.max_daily_loss = max_daily_loss
        self.loss_today = 0
        self.trades_today = 0
        self.wins_today = 0

    def allowed(self):
        if self.loss_today <= -self.max_daily_loss:
            logging.warning("Daily loss limit reached.")
            return False
        return True

    def update_stats(self, pnl):
        self.loss_today += pnl
        self.trades_today += 1
        if pnl > 0:
            self.wins_today += 1

    def get_daily_summary(self):
        return (f"DAILY SUMMARY\n"
                f"Total Trades: {self.trades_today}\n"
                f"Wins: {self.wins_today}\n"
                f"Daily PnL: {self.loss_today:.2f} USDT")