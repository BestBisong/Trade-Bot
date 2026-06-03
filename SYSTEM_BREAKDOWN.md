# 📘 JARVIS Quant System: Exhaustive Technical Specification & Systems Manual

This document is the ultimate technical specification for the optimized **JARVIS hybrid quantitative trading engine**. It covers every equation, parameter, signal state, intelligence pipeline, and network architecture in absolute detail.

---

## 🗺️ SECTION 1: SYSTEM OVERVIEW & LIFE CYCLE

The JARVIS system operates on a hybrid momentum and mean-reversion model. It integrates classical technical indicators, regime-classification mathematics, and a rolling walk-forward Random Forest machine learning model to execute high-expectancy trades.

```
       [Market Data Fetch] (Binance/Bybit 1h & 4h Candlesticks)
                │
                ▼
     [Regime Classification] ───► (Trending, Volatile, or Ranging)
                │
                ▼
     [Feature Engineering] ────► (Precomputes RSI, MACD, BB, Volatility Features)
                │
                ▼
     [ML Model Confidence] ───► (Rolling Random Forest Directional Fit)
                │
                ▼
     [Regime-Specific Scoring] ─► (Dynamic Score Tally: Adds/Subtracts Points)
                │
                ▼
     [Risk & Sizing Filters] ──► (Calculates Qty, Checks Wallet Risk & Exchange Rules)
                │
                ▼
     [Live Trade Execution] ───► (Sends Market Orders to Bybit Exchange)
                │
                ▼
     [Continuous Monitoring] ──► (Telemeters Stats to JSON DB & Next.js Web UI)
```

---

## 📡 SECTION 1.1: BINANCE MARKET DATA FETCHING SPECIFICATION

The system fetches high-quality, real-time historical market price-action directly from the **Binance Spot Exchange** API using the professional **CCXT** framework. This raw feed acts as the ground-truth fuel for both our feature-engineering pipeline and our machine learning classifier.

### 1. API Endpoint & Robust Network Retry Pipeline
*   **API Target**: `Binance Spot Public REST API` via the CCXT `fetch_ohlcv` method.
*   **Robust Network Retry Guard**: Public exchange APIs are prone to temporary drops and rate-limiting. The system implements a **5-stage Exponential Backoff Pipeline** to prevent scanner crashes:
    *   If a request fails (due to connection reset or `RateLimitExceeded`), the bot sleeps for:
        $$\text{Sleep Duration} = \text{Attempt} \times 2 \text{ seconds}$$
    *   It retries up to **5 times** (sleeping 2s, 4s, 6s, 8s, and 10s respectively) before raising an error. This keeps the bot alive through temporary ISP drops and high-volatility flash traffic.
*   **Rate-Limit Compliance**: The fetcher respects Binance rate limits by sleeping `exchange.rateLimit` milliseconds between batches, and sleeping **1.5 seconds** between active symbols to guarantee zero IP throttling or API bans.

### 2. Candlestick Data Schema & Raw Payload
The raw payload returned by Binance is parsed into a standardized DataFrame with **6 core columns**:

| Column Name | Data Type | Description / Standardized Formatting |
| :--- | :--- | :--- |
| **timestamp** | `DatetimeIndex` | Parsed from raw Unix milliseconds (UTC time). Set as the DataFrame's unique search index. |
| **open** | `Float64` | The opening transaction price of the asset at the start of the 1h candle. |
| **high** | `Float64` | The absolute highest transaction price recorded during the 1h candle interval. |
| **low** | `Float64` | The absolute lowest transaction price recorded during the 1h candle interval. |
| **close** | `Float64` | The final settlement/closing price of the asset at the end of the 1h candle. |
| **volume** | `Float64` | The total quantity of base assets (e.g. BTC, ETH) traded during the 1h candle. |

### 3. Data Cleaning & Sanitation Protocol
Before the candlestick matrix is sent to the Machine Learning pipeline, it passes through our **Data Sanitizer (`data_cleaner.py`)**:
1.  **Drop Missing Data**: Triggers `.dropna()` to eliminate incomplete candle rows (which can occur during rare API server restarts).
2.  **Discard Null Trading Volume**: Filters out any candles where `volume <= 0` (`df = df[df["volume"] > 0]`). This is crucial because standard technical indicators (like Volume Z-scores or ATR) divide by volume; filtering zero volume completely **prevents division-by-zero errors** that crash models.

---

## 📊 SECTION 2: THE 3 TECHNICAL SUB-STRATEGIES

The system uses three base strategies, each pre-calculated in vectorized form to feed features into the ML Model and provide points to the Scoring Generator.

### 1. Relative Strength Index (RSI) Strategy (`rsi_strategy.py`)
*   **Formula**:
    $$\text{RS} = \frac{\text{EMA}(\text{U}, 14)}{\text{EMA}(\text{D}, 14)}$$
    $$\text{RSI} = 100 - \left(\frac{100}{1 + \text{RS}}\right)$$
    *Where $\text{U}$ is price gain, and $\text{D}$ is price loss over a 14-period lookback.*
*   **Signal Output**:
    *   `BUY`: If RSI crosses **below 30** (oversold limit) and turns upward.
    *   `SELL`: If RSI crosses **above 70** (overbought limit) and turns downward.
    *   `HOLD`: Otherwise.

### 2. Bollinger Bands Strategy (`bollinger_strategy.py`)
*   **Formula**:
    $$\text{Middle Band} = \text{SMA}(\text{Close}, 20)$$
    $$\text{Upper Band} = \text{Middle Band} + (2.0 \times \sigma)$$
    $$\text{Lower Band} = \text{Middle Band} - (2.0 \times \sigma)$$
    *Where $\sigma$ is the 20-period standard deviation of the closing prices.*
*   **Signal Output**:
    *   `BUY`: If current price is **less than or equal to the Lower Band** (reversion long trigger).
    *   `SELL`: If current price is **greater than or equal to the Upper Band** (reversion short trigger).
    *   `HOLD`: Otherwise.

### 3. Moving Average Convergence Divergence (MACD) Strategy (`sma_strategy.py`)
*   **Formula**:
    $$\text{MACD Line} = \text{EMA}(\text{Close}, 12) - \text{EMA}(\text{Close}, 26)$$
    $$\text{Signal Line} = \text{EMA}(\text{MACD Line}, 9)$$
    $$\text{Histogram} = \text{MACD Line} - \text{Signal Line}$$
*   **Signal Output**:
    *   `BUY`: When Histogram crosses **above 0** (bullish momentum shift).
    *   `SELL`: When Histogram crosses **below 0** (bearish momentum shift).
    *   `HOLD`: Otherwise.

---

## 📈 SECTION 3: REGIME CLASSIFIER (`regime.py`)

Before signals are scored, the system determines the current market regime using a mathematical classifier. The classifier evaluates the latest 4-hour trend structures and price movements.

```python
# Mathematical Classification Logic
def detect_market_regime(df_1h, df_4h):
    # 1. Volatility Ratio
    atr_1h = ATR(df_1h, 14)
    atr_ma = SMA(atr_1h, 50)
    volatility_ratio = atr_1h / atr_ma
    
    # 2. ADX (Average Directional Index) for trend strength
    adx_val = ADX(df_4h, 14)
    
    # Classification Rules:
    if volatility_ratio > 1.5 and adx_val < 25:
        return "volatile"
    elif adx_val >= 25:
        return "trending"
    else:
        return "ranging"
```

### Regime-Specific Parameters & Controls:
Each regime dynamically alters the trade distance targets and stop sensitivities:

| Regime Name | Definition / Trigger | Breakout Lookback | Vol Multiplier | Score Threshold | Stop Loss ATR Mult | Take Profit Risk/Reward |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **trending** | ADX on 4h chart $\ge 25$ | 12 hours | 1.1x | **3.0** | **2.0x ATR** | **2.5x Risk** |
| **volatile** | Volatility Ratio $> 1.5$ & ADX $< 25$ | 20 hours | 1.5x | **3.0** | **3.0x ATR** | **1.5x Risk** |
| **ranging** | Default state (Low ADX, low volatility) | 8 hours | 0.9x | **2.5** | **1.5x ATR** | **1.5x Risk** |

---

## 🧠 SECTION 4: MACHINE LEARNING INTELLIGENCE PIPELINE

The core ML model is a **Random Forest Classifier** configured to evaluate whether a setups is a genuine momentum pullback or an over-extended trap.

### 1. Vectorized Feature Engineering
Every hour, the system precomputes a standardized matrix of **8 predictive features**:

1.  **Relative Return**: Current 1-hour return relative to the standard deviation:
    $$f_1 = \frac{\text{Close}_t - \text{Close}_{t-1}}{\text{Close}_{t-1}}$$
2.  **RSI Value**: Raw 14-period RSI value scaled between 0 and 1:
    $$f_2 = \frac{\text{RSI}_t}{100.0}$$
3.  **SMA Ratio**: Ratio of the 20-period simple moving average to the 50-period simple moving average:
    $$f_3 = \frac{\text{SMA}(20)_t}{\text{SMA}(50)_t}$$
4.  **Bollinger Band Bandwidth**: Normalized measure of price expansion:
    $$f_4 = \frac{\text{Upper Band}_t - \text{Lower Band}_t}{\text{Middle Band}_t}$$
5.  **Volatility Z-score**: Current 1h ATR relative to its 50-period average:
    $$f_5 = \frac{\text{ATR}(14)_t - \text{SMA}(\text{ATR}(14), 50)_t}{\text{Std}(\text{ATR}(14), 50)_t}$$
6.  **Volume Z-score**: Normalized volume:
    $$f_6 = \frac{\text{Volume}_t - \text{SMA}(\text{Volume}, 20)_t}{\text{Std}(\text{Volume}, 20)_t}$$
7.  **Price Distance to Band**: Position of current close inside the Bollinger Band range ($0.0 = \text{Lower Band}$, $1.0 = \text{Upper Band}$):
    $$f_7 = \frac{\text{Close}_t - \text{Lower Band}_t}{\text{Upper Band}_t - \text{Lower Band}_t}$$
8.  **Macro Trend Ratio**: Ratio of the 4h fast EMA (20) to the slow EMA (50):
    $$f_8 = \frac{\text{EMA}(20, \text{4h})_t}{\text{EMA}(50, \text{4h})_t}$$

### 2. Symmetric Target Labeling (The 50% Baseline)
To prevent model prediction side-biases, targets are labeled strictly symmetrically:
*   **Label 1 (BUY Success)**: Current price rises to $+1.0 \times \text{ATR}(14)$ before dropping to $-1.0 \times \text{ATR}(14)$.
*   **Label 0 (BUY Fail)**: Current price drops to $-1.0 \times \text{ATR}(14)$ before rising to $+1.0 \times \text{ATR}(14)$.
*   **Impact**: Ensures the model baseline is exactly **50% probability**, allowing robust direction predictions.

### 3. Continuous Rolling Walk-Forward Training & Training Dataset Specs

To survive in the real market, a trading model must avoid **concept drift**—the phenomenon where price-action patterns change over time, rendering static models unprofitable. JARVIS solves this by operating on a continuous **Rolling Walk-Forward Training Pipeline**:

*   **Lookback Window Size (`window_size = 2000`)**: The model trains exclusively on a rolling window of the trailing **2,000 hourly candles**.
    *   **In Calendar Time**: 2,000 hours is exactly **`83.33 days`** (~2.7 months) of historical market history.
    *   **Why 83.33 days?** It is the mathematical sweet spot. It provides enough samples (~2,000) to train a deep Random Forest model without memory errors, while excluding stale historical data from previous years that no longer represents current market liquidity, interest, and volatility regimes.
*   **Retraining Frequency (`retrain_gap = 576`)**: The bot automatically discards its stale brain and retrains a fresh model from scratch every **576 hourly candles**.
    *   **In Calendar Time**: 576 hours is exactly **`24 days`** of active price data.
    *   **Mechanism**: Every 24 days, the window slides forward. The oldest 24 days of data are pruned, and the newest 24 days are added to the training set. A new Random Forest is then fit on the updated 83.33-day database.

### 🛡️ Why This Architecture Survives the "Real Market":

1.  **Excludes "Look-Ahead" Bias (Data Leakage)**:
    During backtesting, at any simulated hour $t$, the machine learning model has **zero knowledge** of any future data $t+1$. It has only seen the preceding 2,000 candles. This mimics live trading with 100% mathematical precision.
2.  **Destroys Concept Drift (Market Regime Shifts)**:
    If the market shifts from a high-volatility bull run to a low-volatility bear market, a static model will keep buying pullbacks that never recover. Our walk-forward pipeline will discard the old bull market data within a few weeks and retrain exclusively on the new bear market regime, naturally learning the new price dynamics.
3.  **Strict Feature Normalization**:
    All 8 features (returns, RSI, volume Z-scores) are dynamically scaled using a **StandardScaler** fitted *only* on the active 83.33-day training window. When predicting on live data, the inputs are scaled relative to recent history rather than all-time history, protecting the model from scaling errors during massive price pumps.


---

## 🔢 SECTION 5: THE DYNAMIC SCORING ENGINE (`signal_generator.py`)

When a scan cycle completes, the system sums up scoring points based on the active market regime. A signal triggers only if the score clears the regime's specific **Score Threshold**.

```
                           [Score = 0.0]
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
  [Trending Regime]      [Volatile Regime]      [Ranging Regime]
  • 4h Bullish: +2.0     • Break High: +2.5     • Break High: -1.5
  • MACD BUY:   +2.0     • Break Low:  -2.5     • Break Low:  +1.5
  • BB Long:    +1.5     • MACD BUY:   +1.0     • BB Long:    +2.5
  • RSI BUY:    +1.0     • RSI BUY:    +1.0     • RSI BUY:    +2.0
                                                • MACD BUY:   +0.5
          └──────────────────────┬──────────────────────┘
                                 │
                                 ▼
                     [Volume & ML Confidence]
                     • ML Prob >= Threshold: +2.0
                     • Volume Expansion:    +1.0
                                 │
                                 ▼
                 [Final Threshold Evaluation]
                 • Score >= Threshold  ==► BUY
                 • Score <= -Threshold ==► SELL
```

### 1. Trending Regime Scoring (Threshold: 3.0)
*   **Trend Direction**: If $4\text{h Trend is Bullish}$ and $\text{Price} > \text{EMA}(20)$: **`+2.0`** points (or **`-2.0`** if bearish).
*   **Momentum**: If MACD Histogram crosses above 0: **`+2.0`** points (or **`-2.0`** if below).
*   **Bollinger Bands**: If price pullbacks to Lower Band during bull market: **`+1.5`** points.
*   **RSI**: If RSI crosses below 30 during bull market: **`+1.0`** point.

### 2. Volatile Regime Scoring (Threshold: 3.0)
*   **Breakout**: 
    *   If current price breaks above the session high: **`+2.5`** points.
    *   If current price breaks below the session low: **`-2.5`** points.
*   **MACD**: If MACD is bullish: **`+1.0`** point (or **`-1.0`** if bearish).
*   **RSI**: If RSI is oversold: **`+1.0`** point (or **`-1.0`** if overbought).

### 3. Ranging Regime Scoring (Threshold: 2.5)
*   **Reversion Boundaries**:
    *   If current price breaks above the session high: **`-1.5`** points (predicting drop).
    *   If current price breaks below the session low: **`+1.5`** points (predicting rise).
*   **Bollinger Bands**: If price touches Lower Band: **`+2.5`** points (or **`-2.5`** if Upper Band).
*   **RSI**: If RSI is oversold ($<30$): **`+2.0`** points (or **`-2.0`** if overbought).
*   **MACD**: If MACD is bullish: **`+0.5`** points.

---

### 🛡️ ML & Volume Confluence Super-Filters:
Regardless of the regime, the scoring tallies these two overlay metrics:
1.  **ML Confidence overlay**:
    *   If ML confidence probability is $\ge 0.58$: Add **`+2.0`** points.
    *   If ML confidence probability is $\le 0.42$: Subtract **`+2.0`** points.
2.  **Volume Expansion overlay**:
    *   If current volume exceeds the 20-period average volume $\times \text{Volume Multiplier}$: Add **`+1.0`** point (direction aligned with macro trend).

---

## 📐 SECTION 6: SIZING, SLIPPAGE, & RISK PIPELINE

Once a BUY signal clears the scoring threshold, it passes through the sizing and risk management pipelines in `execution/sizing.py` and `risk/risk_manager.py` to prevent capital degradation.

### 1. Sizing Equation (2% Risk Budget)
The system calculates the exact order size to risk no more than **2% of current total wallet equity**:
$$\text{Risk Cash} = \text{Wallet Equity} \times 0.02$$
$$\text{Quantity} = \frac{\text{Risk Cash}}{\text{Stop Loss Distance}}$$
*Where Stop Loss Distance is $\text{ATR}(14) \times \text{sl\_atr\_mult}$ of the active regime.*

### 2. Exchange Constraint Checks
The calculated Quantity passes through three strict filters to prevent exchange order execution failures:
1.  **Min Quantity check**: If $\text{Quantity} < \text{Exchange Min Qty}$, the order is rejected.
2.  **Quantity Precision filter**: The quantity is rounded down to match the exchange token precision rules (e.g. 5 decimals for BTC, 4 decimals for ETH).
3.  **Min Notional check**: The absolute dollar size of the trade ($\text{Quantity} \times \text{Price}$) must exceed **$5.00**.

### 3. Slippage & Fee Drag Model
*   **Taker Fee Rate**: **$0.0006$ (0.06%)** is factored into both opening and closing fills.
*   **Slippage Buffer**: **5 Basis Points (0.05%)** is simulated for backtests and executed live:
    $$\text{Long Entry Fill} = \text{Price} \times (1 + 0.0005)$$
    $$\text{Long Exit Fill} = \text{Price} \times (1 - 0.0005)$$
*   **Net Profit Settlement**:
    $$\text{Trade PnL} = \left((\text{Exit Fill} - \text{Entry Fill}) \times \text{Quantity}\right) - \left((\text{Entry Fill} + \text{Exit Fill}) \times \text{Quantity} \times 0.0006\right)$$

---

## 📱 SECTION 7: DEPLOYMENT & MOBILE DASHBOARD SETUP

This section details how to host your bot on a Cloud VPS and securely monitor it on your phone **with zero time limits**.

### 1. VPS Provisioning
1.  Sign up for **DigitalOcean**, **Hetzner**, or **Linode**.
2.  Create an Ubuntu 22.04 LTS VPS instance (minimum: 1 CPU, 1GB RAM, cost: ~$5/month).

### 2. Service Installation & Startup
Log into your VPS via SSH and install dependencies:
```bash
# Update server
sudo apt update && sudo apt upgrade -y

# Install Python and Node.js
sudo apt install python3-pip python3-venv nodejs npm screen -y

# Setup code and virtual environment
git clone <your-repository-url> trading-bot
cd trading-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start background manager
screen -S jarvis-system
source venv/bin/activate
python start_all.py
```
*(Press `Ctrl + A` then `D` to detach the screen and leave the system running forever in the background).*

### 3. Exposing the Web UI Dashboard to Your Phone

#### Option A: Quick & Easy (Using ngrok Tunneling)
`ngrok` exposes the local Next.js frontend port `3000` to a secure public URL:
1.  Install `ngrok` on your VPS.
2.  Authenticate it using your free token: `ngrok config add-authtoken <your-token>`
3.  Launch the tunnel:
    ```bash
    ngrok http 3000
    ```
4.  **Save the output URL** (e.g., `https://xxxx.ngrok-free.app`) to your phone's home screen. You can now access your live trading dashboard from your mobile browser anywhere, anytime.

#### Option B: Private & VPN Encrypted (Using Tailscale)
If you want to ensure absolutely nobody else can access your dashboard, use a private mesh VPN:
1.  Sign up for a free **Tailscale** account.
2.  Install Tailscale on both your VPS and your mobile phone:
    ```bash
    curl -fsSL https://tailscale.com/install.sh | sh
    sudo tailscale up
    ```
3.  Enable Tailscale on your mobile phone's app.
4.  Type your VPS's private Tailscale IP (e.g., `http://100.x.x.x:3000`) into your phone's browser. Only your authenticated phone can ever open the dashboard!
