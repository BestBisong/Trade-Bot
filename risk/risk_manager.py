import logging
from datetime import datetime, timedelta

class RiskManager:
    def __init__(self, max_daily_loss=5.0, max_consecutive_losses=3, cooldown_minutes=30, max_open_positions=2):
        self.max_daily_loss = max_daily_loss
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_minutes = cooldown_minutes
        self.max_open_positions = max_open_positions

        self.loss_today = 0.0
        self.consecutive_losses = 0
        self.trades_today = 0
        self.wins_today = 0
        self.losses_today = 0
        self.start_day_equity = None
        self.peak_equity = None
        self.current_day = datetime.now().date()
        self.cooldown_until = None

    def _reset_if_new_day(self):
        today = datetime.now().date()
        if today != self.current_day:
            self.current_day = today
            self.loss_today = 0.0
            self.consecutive_losses = 0
            self.trades_today = 0
            self.wins_today = 0
            self.losses_today = 0
            self.start_day_equity = None
            self.cooldown_until = None

    def mark_equity(self, equity):
        self._reset_if_new_day()
        if self.start_day_equity is None:
            self.start_day_equity = float(equity)
            self.peak_equity = float(equity)
        self.peak_equity = max(self.peak_equity, float(equity))

    def daily_loss_pct(self, equity):
        if self.start_day_equity in (None, 0):
            return 0.0
        return ((float(equity) - self.start_day_equity) / self.start_day_equity) * 100.0

    def allowed(self, equity=None):
        self._reset_if_new_day()

        if self.cooldown_until and datetime.now() < self.cooldown_until:
            logging.warning("JARVIS | Cooldown active after loss streak.")
            return False

        if equity is not None and self.daily_loss_pct(equity) <= -self.max_daily_loss:
            logging.error("JARVIS | Daily Loss Limit. Shutting down.")
            return False

        if self.consecutive_losses >= self.max_consecutive_losses:
            self.cooldown_until = datetime.now() + timedelta(minutes=self.cooldown_minutes)
            self.consecutive_losses = 0
            logging.error("JARVIS | Choppy Market Detected. Cooling down.")
            return False

        return True

    def update_stats(self, pnl):
        self._reset_if_new_day()
        self.loss_today += pnl
        self.trades_today += 1

        if pnl < 0:
            self.consecutive_losses += 1
            self.losses_today += 1
        else:
            self.consecutive_losses = 0
            self.wins_today += 1

    def can_open_new_trade(self, current_open_positions, equity=None):
        if not self.allowed(equity=equity):
            return False
        if current_open_positions >= self.max_open_positions:
            return False
        return True

    def summary(self, equity=None):
        self._reset_if_new_day()
        win_rate = 0.0
        if self.trades_today > 0:
            win_rate = (self.wins_today / self.trades_today) * 100.0
        return {
            "loss_today": self.loss_today,
            "consecutive_losses": self.consecutive_losses,
            "trades_today": self.trades_today,
            "wins_today": self.wins_today,
            "losses_today": self.losses_today,
            "win_rate": win_rate,
            "daily_pnl_pct": self.daily_loss_pct(equity) if equity is not None else 0.0,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
        }