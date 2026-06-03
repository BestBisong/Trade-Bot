from backtesting.walk_forward import live_gate_from_walk_forward
from strategies.regime import get_regime_params


def test_regime_params_differ_between_trending_and_ranging():
	trending = get_regime_params("trending")
	ranging = get_regime_params("ranging")

	assert trending["sl_atr_mult"] > ranging["sl_atr_mult"]
	assert trending["rr_ratio"] > ranging["rr_ratio"]
	assert trending["score_threshold"] >= ranging["score_threshold"]


def test_live_gate_blocks_when_metrics_fail_thresholds():
	report = {
		"aggregate": {
			"total_windows": 2,
			"win_rate": 48.0,
			"worst_drawdown_pct": 14.0,
		}
	}
	gate = live_gate_from_walk_forward(report)
	assert gate["allowed"] is False


def test_live_gate_allows_when_metrics_pass_thresholds():
	report = {
		"aggregate": {
			"total_windows": 5,
			"win_rate": 57.0,
			"worst_drawdown_pct": 8.0,
		}
	}
	gate = live_gate_from_walk_forward(report)
	assert gate["allowed"] is True
