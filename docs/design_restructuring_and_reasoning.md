# J.A.R.V.I.S // Design Restructuring & Quantitative Reasoning

This document details the software engineering and quantitative reasoning behind the architectural shift of J.A.R.V.I.S. from a passive data monitoring tool to a high-performance, active trading engine.

---

## 🔄 1. Overview of the Design Shift

```
[ Passive Monitoring Bot ] 
  • Low activity levels
  • Generic default parameters (One-Size-Fits-All)
  • Limited trend checks (frequent whipsaws)
  • Altcoins blocked or stopped out prematurely
               │
               ▼
[ Active Multi-Asset Execution Engine ]
  • Dynamic regime-aware parameter loading
  • Symbol-specific risk profiling (wider altcoin stops)
  • Re-enabled short trading under strict macro guards
  • Cleaned portfolio symbols (alpha optimization)
```

---

## 📐 2. Symbol-Specific Risk Profiling (ATR Stops)

Previously, the bot utilized a universal stop-loss setting (e.g., `2.0x ATR`) for all traded symbols. While this worked for Bitcoin due to its relatively stable price action, it proved fatal for high-beta altcoins.

### The Volatility Trap:
Altcoins like **SOL** and **XRP** exhibit high intraday noise and volatility. A standard `2.0x ATR` stop-loss is frequently triggered by random wick expansions (whipsaws) before the price reverses in the intended direction. This turned potentially winning trades into net losses.

### The Restructuring Solution (`strategies/regime.py`):
We implemented symbol-aware parameter overrides:
```python
def get_regime_params(regime, symbol="BTC/USDT"):
    # Default parameters based on regime
    params = get_base_regime_params(regime)
    
    # Symbol-specific risk profile overrides
    if symbol in ["SOL/USDT", "XRP/USDT"]:
        # Give high-beta altcoins room to breathe to avoid whipsaws
        params["sl_atr_mult"] = 3.0  # Increased from 2.0
        params["tp_atr_mult"] = 4.5  # Maintain a 1.5x risk-reward ratio
        
    return params
```
* **Reasoning:** Increasing the stop loss to `3.0x ATR` absorbs normal altcoin price noise. Backtests validated that this simple change turned `SOL/USDT` from a losing asset into the highest performer in the portfolio (**`+24.29%`** individual return).

---

## ⏱️ 3. Trade Frequency & Safety Cooldown Optimization

A common problem for active trading bots is **revenge trading**—where the bot suffers a loss and immediately re-enters a trade in the same direction, compounding the loss as a trend collapses.

### The Safety Shield (`run_bot.py` & `backtest_full.py`):
The engine enforces a **24-candle safety cooldown period** after a trade is closed on a symbol.
* **Tuning:** We experimented with reducing this cooldown to `12 bars` to increase trade frequency. However, testing showed a significant increase in drawdowns as the bot was pulled back into cascading losses during rapid market selloffs.
* **Decision:** Maintained the **24-hour cooldown** as a non-negotiable safety guard. The risk-adjusted return (Sharpe Ratio of `1.91`) was preserved by keeping this defense mechanism intact.

---

## 🛡️ 4. Global Macro Trend Guards

To ensure the bot never fights the macro trend, we applied two layers of trend-alignment guards across **all** regimes:

1. **Daily 200 SMA Guard:** Trades are restricted based on macro cycle bias. Longs are only allowed when price is above the 200 SMA; Shorts are only allowed when price is below.
2. **4H Trend Guard (MACD Trend):** Restricts execution to the direction of the 4H momentum.
* **Reasoning:** By applying these filters globally, we prevent the bot from taking counter-trend mean-reversion trades during strong trending regimes, which historically accounted for the largest drawdowns.

---

## 🚫 5. Portfolio Optimization: The Removal of ETH/USDT

During portfolio testing under the new active short-trading setup, **ETH/USDT**'s performance degraded heavily, ending as the worst-performing asset.

### The Liquidity-Sweep Structure of ETH:
ETH price action is highly prone to **stop-hunting / liquidity sweeps**. Before making a sustained downward move, ETH frequently experiences short squeezes that break local resistance levels.
* When the stop loss was tight (`2.0x ATR`), it was hit frequently by these sweeps.
* When we expanded the stop loss to `3.0x ATR`, the sweeps still hit the stop, but the loss size was 50% larger.
* **Decision:** We removed `ETH/USDT` from the active symbol basket in `settings.py` and replaced it with clean mean-reverters (**SOL** and **XRP**) and the macro anchor (**BTC**). This protected the portfolio's net expectancy.
