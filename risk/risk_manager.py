import logging

class RiskManager:
    def __init__(self, max_daily_loss=5):
        self.max_daily_loss = max_daily_loss
        self.loss_today = 0

    def allowed(self, potential_loss=0):
        """Check if taking another trade exceeds loss limits."""
        if self.loss_today >= self.max_daily_loss:
            logging.warning("Daily loss limit reached. Trading suspended.")
            return False
        return True

    def update_loss(self, actual_loss):
        """Call this after a trade closes to update daily stats."""
        self.loss_today += actual_loss