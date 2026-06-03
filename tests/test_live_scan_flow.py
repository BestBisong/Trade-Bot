import pytest
import datetime
import pandas as pd
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from run_bot import scan_symbol

@pytest.mark.anyio
@patch("run_bot.fetch_confluence")
@patch("run_bot.fetch")
async def test_live_scan_symbol_success_flow(mock_fetch_1d, mock_fetch_confluence):
    # 1. Setup mock 1h and 4h price dataframes
    now = datetime.datetime.now()
    times = [now - datetime.timedelta(hours=i) for i in range(100, 0, -1)]
    
    df_1h = pd.DataFrame({
        "open": np.random.uniform(50000, 51000, 100),
        "high": np.random.uniform(51000, 52000, 100),
        "low": np.random.uniform(49000, 50000, 100),
        "close": np.random.uniform(50000, 51000, 100),
        "volume": np.random.uniform(10, 100, 100)
    }, index=times)
    
    df_4h = df_1h.copy()
    mock_fetch_confluence.return_value = (df_1h, df_4h)
    
    # 2. Setup mock 1D daily dataframe for 200 SMA calculation
    daily_times = [now - datetime.timedelta(days=i) for i in range(250, 0, -1)]
    df_1d = pd.DataFrame({
        "close": np.full(250, 48000.0) # Price is 48,000; Entry price will be 50,000+ (Above 200 SMA)
    }, index=daily_times)
    mock_fetch_1d.return_value = df_1d

    # 3. Setup mock Bybit Broker
    mock_broker = MagicMock()
    mock_broker.price = AsyncMock(return_value=50500.0)
    mock_broker.place_order = AsyncMock(return_value={"order_id": "mock_order_123"})
    
    # 4. Setup mock ML Agent
    mock_ml_agent = MagicMock()
    mock_ml_agent.confidence = MagicMock(return_value=0.62)
    
    # 5. Active trades and wallet state
    active_trades = []
    virtual_wallet = 100.0
    tuned_params = {
        "breakout_lookback": 12,
        "volume_multiplier": 1.1,
        "score_threshold": 3.0,
        "sl_atr_mult": 2.0,
        "rr_ratio": 2.5,
        "ml_conf_long_trending": 0.60,
        "ml_conf_long_ranging": 0.60,
        "ml_conf_long_volatile": 0.60,
    }
    
    # 6. Patch signals.generate to return a BUY signal
    with patch("run_bot.generate") as mock_generate:
        mock_generate.return_value = ("BUY", "SCORE:4|TRENDING", 0.62)
        
        # 7. Run scan_symbol
        await scan_symbol(
            symbol="BTC/USDT",
            broker=mock_broker,
            ml_agent=mock_ml_agent,
            active_trades=active_trades,
            virtual_wallet=virtual_wallet,
            tuned_params=tuned_params,
            now=now
        )
        
        # 8. Assertions to verify correct live execution flow
        assert len(active_trades) == 1
        trade = active_trades[0]
        assert trade["symbol"] == "BTC/USDT"
        assert trade["side"] == "buy"
        assert trade["entry_price"] > 0
        assert trade["tp"] > trade["entry_price"]
        assert trade["sl"] < trade["entry_price"]
        assert trade["qty"] > 0
        assert trade["has_scaled_out"] is False
        
        # Verify broker calls
        mock_broker.price.assert_called_with("BTC/USDT")
        mock_broker.place_order.assert_called()
