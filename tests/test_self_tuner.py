from backtesting.self_tuner import tune_from_walk_forward, DEFAULT_PARAMS


def test_tuner_tightens_under_poor_performance():
    metrics = {
        "win_rate": 48.0,
        "avg_window_pnl": -12.0,
        "worst_drawdown_pct": 15.0,
    }
    tuned, action = tune_from_walk_forward(metrics, DEFAULT_PARAMS)

    assert action == "tighten"
    assert tuned["ml_conf_long_trending"] >= DEFAULT_PARAMS["ml_conf_long_trending"]
    assert tuned["atr_min_pct"] >= DEFAULT_PARAMS["atr_min_pct"]



def test_tuner_loosens_under_strong_performance():
    metrics = {
        "win_rate": 61.0,
        "avg_window_pnl": 10.0,
        "worst_drawdown_pct": 6.0,
    }
    tuned, action = tune_from_walk_forward(metrics, DEFAULT_PARAMS)

    assert action == "loosen"
    assert tuned["ml_conf_long_trending"] <= DEFAULT_PARAMS["ml_conf_long_trending"]
    assert tuned["atr_min_pct"] <= DEFAULT_PARAMS["atr_min_pct"]
