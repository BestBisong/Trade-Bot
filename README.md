# J.A.R.V.I.S // Advanced Multi-Regime Quantitative Workstation

J.A.R.V.I.S. (Joint Automated Regime Valuation & Integration System) is a high-performance quantitative trading platform designed to scan, analyze, and execute trades across diverse market regimes (Trending, Ranging, and Volatile). The architecture integrates machine learning signals with classical technical analysis and rigorous macro risk guards to achieve stable portfolio returns while strictly limiting drawdowns.

---

## 🖥️ System Architecture & Execution Flow

The system is designed as a decoupled, multi-layered service architecture:

```
                  +---------------------------------------+
                  |           Binance/Bybit API           |
                  +-------------------+-------------------+
                                      |
                                      | (1h & 4h Candle Data)
                                      v
                  +-------------------+-------------------+
                  |           Data Fetcher                |
                  +-------------------+-------------------+
                                      |
                                      | (Clean Pandas DataFrames)
                                      v
+-------------------------------------+-------------------------------------+
|                             Execution Engine                              |
|                                                                           |
|   +--------------------------+             +--------------------------+   |
|   |  Market Regime Detector  |             |     ML Model Agent       |   |
|   |  (Slope & Volatility)    |             |   (Walk-Forward Ensemble)|   |
|   +------------+-------------+             +------------+-------------+   |
|                |                                        |                 |
|                +-------------------+--------------------+                 |
|                                    | (Regime + ML Probability)            |
|                                    v                                      |
|                       +------------+-------------+                        |
|                       | Signal Generator Scorer  |                        |
|                       | (Indicator Confluence)   |                        |
|                       +------------+-------------+                        |
|                                    | (Raw Signal Verdict)                 |
|                                    v                                      |
|                       +------------+-------------+                        |
|                       |   Macro Market Guards    |                        |
|                       | (4H Trend & Daily 200SMA)|                        |
|                       +------------+-------------+                        |
|                                    | (Filtered Signal Verdict)            |
|                                    v                                      |
|                       +------------+-------------+                        |
|                       |   Risk & Position Sizing |                        |
|                       | (Symbol-Specific ATR SL) |                        |
|                       +------------+-------------+                        |
+------------------------------------|--------------------------------------+
                                     |
                                     | (Authorized Orders)
                                     v
                  +-------------------+-------------------+
                  |        Bybit Broker (Paper/Live)      |
                  +-------------------+-------------------+
                                      |
                                      | (Active State & Diagnostics Logs)
                                      v
                  +-------------------+-------------------+
                  |           FastAPI REST API            |
                  +-------------------+-------------------+
                                      |
                                      | (REST / Real-time Poll)
                                      v
                  +-------------------+-------------------+
                  |       Next.js React Frontend HUD      |
                  +---------------------------------------+
```

---

## 📦 Key System Modules

1. **`run_bot.py` (Orchestration Loop):** The main execution pipeline that schedules periodic market scans, retrieves real-time pricing, calls the signal scoring modules, and interacts with the Broker interface.
2. **`signals/signal_generator.py`:** Aggregates classical indicators (RSI, Bollinger Bands, Moving Averages) and combines them with walk-forward machine learning confidence levels to construct a weighted signal score.
3. **`strategies/regime.py`:** Classifies market conditions into **Trending**, **Ranging**, or **Volatile** states using rolling linear regression slopes and normalized Average True Range (ATR) metrics.
4. **`strategies/ml_strategy.py`:** Manages rolling training and predictions using scikit-learn models, dynamically identifying high-probability windows for directionality.
5. **`risk/risk_manager.py`:** Enforces risk management, including daily drawdown caps, max consecutive loss cutoffs, and cooldown windows to prevent revenge trading.
6. **`execution/`:** Implements precision order execution (using Bybit SDK), manages slippage, handles order quantity precision boundaries, and calculates dynamic settlement.
7. **`api/main.py`:** A FastAPI service mapping real-time bot statistics, scanner diagnostics, log files, and active trade positions to clean REST endpoints.
8. **`frontend/`:** A Next.js (TypeScript/Tailwind CSS) dashboard delivering a command-center interface with real-time diagnostics, explains reasons for scan blocks, and visualizes asset performance.

---

## ⚙️ Core Strategy Configuration

* **Timeframe:** 1-Hour candles for signal scanning; 4-Hour and Daily candles for macro trend filtering.
* **Universal Macro Guards:** 
  * **Daily 200 SMA Guard:** Blocks LONG entries when price is below the 200 SMA, and SHORT entries when price is above the 200 SMA.
  * **4H MACD Trend Guard:** Filters out trades opposing the macro 4H momentum.
* **Symbol-Specific Tuning:** 
  * **BTC/USDT:** Trades both sides (Long/Short) using standard, tight stop-losses (`2.0x ATR`) to maximize expectancy.
  * **High-Beta Altcoins (SOL/USDT, XRP/USDT):** Trade both sides but apply wider stop-losses (`3.0x ATR`) to absorb higher volatility and avoid noise stop-outs.

---

## 📈 Performance Profile (360-Day Backtest)

The system-wide parameters are tuned and validated using historical data across diverse market regimes:
* **Combined Return:** **`+45.74%`**
* **Max Portfolio Drawdown:** **`16.7%`** (Target: < 25%)
* **Sharpe Ratio:** **`1.91`**
* **Profit Factor:** **`1.30`**
* **Trade Frequency:** **`127 trades`** (~2.5 trades per week, optimizing transaction fees)

---

## 🚀 Quick Start Guide

### Backend & API Setup
1. Clone the repository and activate the virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Run the FastAPI REST server:
   ```bash
   python -m uvicorn api.main:app --port 8000 --reload
   ```
3. Start the execution bot (defaulting to Paper Trading mode):
   ```bash
   python run_bot.py
   ```

### Frontend Workstation Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   npm install
   ```
2. Start the hot-reloading Next.js dev server:
   ```bash
   npm run dev
   ```
3. Open `http://localhost:3000` to access the J.A.R.V.I.S Dashboard.

---

*Disclaimer: This project is a quantitative framework designed for simulation and paper-trading validation. Past performance does not guarantee future live returns.*