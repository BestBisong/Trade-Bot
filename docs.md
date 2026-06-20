# J.A.R.V.I.S. Quantitative Workstation: System Optimizations & Reasoning Docs

This document provides a comprehensive breakdown of the engineering decisions, mathematical reasoning, and architectural changes made during the optimization of the J.A.R.V.I.S. High-Frequency Trading Bot.

---

## 1. Altcoin Volatility Mitigation (Symbol-Specific Risk Management)

### The Problem
During initial multi-asset backtests, adding high-beta altcoins like **SOL** and **XRP** resulted in severe whipsaw losses. The bot was utilizing a uniform **2.0x ATR** stop-loss multiplier across all assets. Because altcoins have a much higher noise-to-trend ratio than Bitcoin, minor counter-trend fluctuations (volatility noise) triggered stop-losses prematurely, right before the price rebounded in the trade's favor.

### The Solution & Reasoning
Instead of excluding these highly profitable assets, we implemented a **symbol-aware parameter loader** in `strategies/regime.py`.

```
                        +--------------------------+
                        |      get_regime_params   |
                        +------------+-------------+
                                     |
                +--------------------+--------------------+
                |                                         |
                v (Symbol: BTC)                           v (Symbol: SOL/XRP)
        +-------+-------+                         +-------+-------+
        | Tight Stops   |                         | Wider Stops   |
        | 2.0x ATR SL   |                         | 3.0x ATR SL   |
        +-------+-------+                         +-------+-------+
                |                                         |
                +--------------------+--------------------+
                                     v
                        +------------+-------------+
                        | Enforced Risk/Reward     |
                        | (Absorbs local noise)    |
                        +--------------------------+
```

* **BTC/USDT:** Kept at **2.0x ATR** for tight risk management and quick exits on invalid setups.
* **SOL/USDT & XRP/USDT:** Scaled up to **3.0x ATR** stop-losses. This gave the trades enough "room to breathe," transforming `SOL` from a major loss-maker into the highest-performing asset in the portfolio (**`+24.29%`** individual return).

---

## 2. Macro Trend Protection (Global Guards)

### The Problem
During sideways, choppy, or major trend-reversal markets, indicators like RSI or Bollinger Bands generate frequent entry signals. Trading these counter-trend signals led to massive drawdowns.

### The Solution & Reasoning
We instituted a double-layer **Global Guard Architecture** in `signals/signal_generator.py` and `run_bot.py`:

```
                 +------------------------------------------+
                 |            Raw Entry Signal              |
                 +--------------------+---------------------+
                                      |
                                      v
                 +--------------------+---------------------+
                 |       Daily 200 SMA Trend Guard          |
                 |  (Price above 200 SMA? Long Only.        |
                 |   Price below 200 SMA? Short Only.)      |
                 +--------------------+---------------------+
                                      |
                                      v (Passes SMA Guard)
                 +--------------------+---------------------+
                 |        4H MACD momentum Guard            |
                 |  (Entry must align with 4H Trend Bias)   |
                 +--------------------+---------------------+
                                      |
                                      v (Passes MACD Guard)
                 +--------------------+---------------------+
                 |           Execution Allowed              |
                 +------------------------------------------+
```

* **Daily 200 SMA Guard:** Acts as a macro regime filter. Under no circumstances will the bot open a Long trade in a macro bear market, nor a Short trade in a macro bull market.
* **4H MACD Guard:** Ensures that even if the 1-hour candles look oversold/overbought, the bot does not trade against the intermediate 4-hour momentum.
* **Result:** Reduced the overall maximum portfolio drawdown from **25.8%** to **16.7%** while increasing the win rate.

---

## 3. Cooldown Shield & Short Trading Integration

### The Problem
By default, short trading was restricted to prevent getting caught in rapid short-squeezes. However, disabling shorts meant the bot was completely idle during bear markets. Furthermore, when a trade was stopped out, the bot would immediately scan and open another trade in the same direction (revenge-trading).

### The Solution & Reasoning
We re-enabled global short trading across all assets but paired it with a strict **24-hour Cooldown Period** (`backtest_full.py` / `run_bot.py`).

```
                    +------------------------------------+
                    |        Position Closed (SL/TP)     |
                    +-----------------+------------------+
                                      |
                                      v
                    +-----------------+------------------+
                    |      Activate 24-Bar Cooldown      |
                    |      for that specific Symbol      |
                    +-----------------+------------------+
                                      |
                +---------------------+---------------------+
                |                                           |
                v (Time < 24 Hours)                         v (Time >= 24 Hours)
        +-------+-------+                           +-------+-------+
        | Blocks scan   |                           | Reset Shield  |
        | & new entries |                           | Allow scans   |
        +---------------+                           +---------------+
```

* **Why 24 hours?** In crypto, liquidations and volatility cascades generally occur within a 24-hour cycle. Restricting the bot from re-entering immediately protects the wallet balance from cascading whipsaw losses.

---

## 4. Frontend & REST API Explainability Update

### The Problem
If the guards successfully blocked trades during choppy markets, the frontend simply showed no activity. This made the bot look passive or broken to the user, rather than defensively optimized.

### The Solution & Reasoning
1. **API Openness (`api/main.py`):**
   * Removed hardcoded `BTC`/`ETH` filters.
   * Removed log filters discarding `SOL` and `XRP` logs so that real-time execution statistics are fully visible on the dashboard.
2. **24H+ Inactivity Diagnostics (`frontend/src/app/page.tsx`):**
   * Implemented a utility function `checkNoTradeDiagnostics` that calculates how long it has been since each asset was traded.
   * Added a warning card (`⚠️ 24H+ INACTIVE`) that parses the system logs and explains *exactly why* no trades were placed (e.g. price is below the 200 SMA, blocked by 4H Trend, or insufficient indicator score).

---

## 5. Version Control Cleanliness

### The Problem
During server deployment (`git pull`), the local environment was constantly aborted because `bot_state.json` and `scan_heartbeat.json` changes (written dynamically by the running bot) conflicted with incoming repository changes.

### The Solution & Reasoning
* We added all dynamic `.json` files to `.gitignore`.
* Ran `git rm --cached` on the server-generated state files to untrack them permanently, ensuring smooth docker redeployments and git merges.
