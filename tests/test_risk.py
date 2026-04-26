from datetime import datetime, timedelta

from risk.risk_manager import RiskManager


def test_daily_loss_lockout():
	rm = RiskManager(max_daily_loss=5.0, max_consecutive_losses=3)
	rm.mark_equity(100.0)

	# Equity drops by 6%, exceeding daily loss threshold.
	assert rm.allowed(equity=94.0) is False


def test_consecutive_losses_trigger_cooldown():
	rm = RiskManager(max_daily_loss=10.0, max_consecutive_losses=2, cooldown_minutes=30)
	rm.mark_equity(100.0)

	rm.update_stats(-1.0)
	assert rm.allowed(equity=99.0) is True

	rm.update_stats(-1.0)
	assert rm.allowed(equity=98.0) is False
	assert rm.cooldown_until is not None


def test_cooldown_expiry_allows_trading_again():
	rm = RiskManager(max_daily_loss=10.0, max_consecutive_losses=1, cooldown_minutes=1)
	rm.mark_equity(100.0)
	rm.update_stats(-1.0)
	assert rm.allowed(equity=99.0) is False

	rm.cooldown_until = datetime.now() - timedelta(seconds=1)
	assert rm.allowed(equity=99.0) is True


def test_can_open_new_trade_obeys_max_open_positions():
	rm = RiskManager(max_daily_loss=10.0, max_consecutive_losses=3, max_open_positions=2)
	rm.mark_equity(100.0)

	assert rm.can_open_new_trade(current_open_positions=1, equity=100.0) is True
	assert rm.can_open_new_trade(current_open_positions=2, equity=100.0) is False
