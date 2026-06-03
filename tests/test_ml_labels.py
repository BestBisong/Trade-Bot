import numpy as np
import pandas as pd

from strategies.execution_levels import label_tp_before_sl, passes_volatility_filter
from strategies.ml_strategy import MLStrategy


def test_label_tp_before_sl_assigns_clear_outcomes():
    n = 60
    close = np.full(n, 100.0)
    close[10:15] = 110.0
    high = close + 0.5
    low = close - 0.5
    atr = np.full(n, 1.0)

    labels = label_tp_before_sl(high, low, close, atr, max_bars=8, sl_atr_mult=2.0, rr_ratio=2.0)
    labeled = labels[~np.isnan(labels)]
    assert len(labeled) > 0
    assert set(np.unique(labeled)).issubset({0.0, 1.0})


def test_passes_volatility_filter_rejects_flat_market():
    df = pd.DataFrame(
        {
            "open": [100.0] * 30,
            "high": [100.1] * 30,
            "low": [99.9] * 30,
            "close": [100.0] * 30,
            "volume": [1000.0] * 30,
        }
    )
    assert passes_volatility_filter(df, {"atr_min_pct": 0.01}) is False


def test_ml_prepare_training_features_has_target_column():
    n = 200
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": rng.uniform(1000, 2000, n),
        }
    )
    ml = MLStrategy(model_path=None, load_pretrained=False)
    prepared = ml.prepare_training_features(df)
    assert not prepared.empty
    assert "target" in prepared.columns
