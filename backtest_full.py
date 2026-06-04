"""
JARVIS - Full System Backtester
================================
Fetches 6 months of real historical 5m + 1h data from Binance,
replays every candle through the live signal_generator logic,
and outputs a full institutional-grade performance report.

Usage:
    venv\\Scripts\\python.exe backtest_full.py
"""

import time
import datetime
import logging
import json
import os
from decimal import Decimal, ROUND_DOWN

import numpy as np
import pandas as pd


# ── Project imports ──────────────────────────────────────────────────────────
from backtesting.historical_data import fetch_historical
from backtesting.performance import compute_metrics
from signals.signal_generator import generate
from strategies.ml_strategy import MLStrategy
from strategies.regime import detect_market_regime, get_regime_params
from strategies.execution_levels import stop_distance
from backtesting.self_tuner import load_tuned_params
from execution.sizing import apply_slippage, settlement_pnl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%H:%M:%S",
)

# ── Configuration ─────────────────────────────────────────────────────────────
from config.settings import SYMBOLS, TIMEFRAME, TREND_TIMEFRAME, PARTIAL_TP_ENABLED, DYNAMIC_ML_RISK, DAILY_200SMA_GUARD, TRAILING_STOP_ENABLED

INITIAL_CAPITAL  = 100.0
RISK_PER_TRADE   = 0.035
MAX_NOTIONAL     = 3.0
TAKER_FEE        = 0.0006
SLIPPAGE_BPS     = 5
LOOKBACK_DAYS    = 360

EXCHANGE_RULES = {
    "BTC/USDT": {"min_qty": 0.00001, "qty_precision": 5, "min_notional": 5.0},
    "ETH/USDT": {"min_qty": 0.0001,  "qty_precision": 4, "min_notional": 5.0},
    "SOL/USDT": {"min_qty": 0.01,    "qty_precision": 2, "min_notional": 5.0},
    "XRP/USDT": {"min_qty": 1.0,     "qty_precision": 1, "min_notional": 5.0},
}

WARMUP_CANDLES = 100   # Minimum candles the indicators need before firing


# ── Helpers ───────────────────────────────────────────────────────────────────
def _calc_qty(wallet, entry, sl_dist, rules):
    """Risk-based position sizing obeying exchange constraints."""
    if wallet <= 0 or entry <= 0 or sl_dist <= 0:
        return 0.0
    risk_budget  = wallet * RISK_PER_TRADE
    qty_by_risk  = risk_budget / sl_dist
    qty_by_notional = (wallet * MAX_NOTIONAL) / entry
    raw = min(qty_by_risk, qty_by_notional)

    quant = Decimal("1").scaleb(-int(rules["qty_precision"]))
    qty   = Decimal(str(max(raw, 0))).quantize(quant, rounding=ROUND_DOWN)

    if qty < Decimal(str(rules["min_qty"])):
        return 0.0
    if qty * Decimal(str(entry)) < Decimal(str(rules["min_notional"])):
        return 0.0
    return float(qty)


# ── Core backtest loop ────────────────────────────────────────────────────────
def run_backtest_symbol(symbol: str, df_5m, df_1h, df_1d, ml_agent, tuned_params, start_idx=2000) -> list:
    """
    Replays every 5-minute candle through the live signal logic using optimized,
    vectorized precomputations for 100x speed.
    """
    rules = EXCHANGE_RULES.get(symbol, EXCHANGE_RULES["BTC/USDT"])
    trades = []
    open_trade = None
    wallet = INITIAL_CAPITAL
    last_closed_bar = -100

    logging.info(f"  Replaying {len(df_5m) - start_idx} out-of-sample candles for {symbol} ...")

    # ── Daily 200 SMA Guard calculations ─────────────────────────────────────
    sma200_1d = df_1d["close"].rolling(200).mean()
    daily_timestamps = df_1d.index.values
    daily_indices = np.searchsorted(daily_timestamps, df_5m.index.values, side="right") - 1
    daily_indices = np.clip(daily_indices, 0, len(df_1d) - 1)

    # ── Precompute indicators on 5m dataframe ────────────────────────────────
    import ta
    close_5m = df_5m["close"]
    high_5m = df_5m["high"]
    low_5m = df_5m["low"]
    volume_5m = df_5m["volume"]

    # RSI
    rsi_5m = ta.momentum.rsi(close_5m, window=14)

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close=close_5m, window=20, window_dev=2)
    bb_lower = bb.bollinger_lband()
    bb_upper = bb.bollinger_hband()

    # MACD
    ema_fast = close_5m.ewm(span=12, adjust=False).mean()
    ema_slow = close_5m.ewm(span=26, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=9, adjust=False).mean()

    # Trend 5m
    sma20_5m = close_5m.rolling(20).mean()
    sma50_5m = close_5m.rolling(50).mean()
    market_bullish_5m = sma20_5m > sma50_5m

    # Linear regression slope (20 bars SMA20) and ATR Norm
    weights = np.arange(20) - 9.5
    slope_series = sma20_5m.rolling(20).apply(lambda y: np.dot(y, weights) / 665.0, raw=True)
    slope_norm_series = slope_series / (close_5m + 1e-9)

    atr_series = ta.volatility.average_true_range(high_5m, low_5m, close_5m, window=14)
    atr_norm_series = atr_series / (close_5m + 1e-9)

    # Precompute regimes
    regimes = np.where(slope_norm_series.abs() > 0.0002, "trending",
              np.where(atr_norm_series > 0.005, "volatile", "ranging"))

    # Session lookbacks
    high_12 = high_5m.rolling(12).max()
    low_12 = low_5m.rolling(12).min()
    high_20 = high_5m.rolling(20).max()
    low_20 = low_5m.rolling(20).min()
    high_8 = high_5m.rolling(8).max()
    low_8 = low_5m.rolling(8).min()

    # ML Features
    returns = close_5m.pct_change()
    volatility = returns.rolling(20).std()
    atr = atr_series
    trend_ml = np.where(close_5m > sma50_5m, 1, -1)
    volume_z = (volume_5m - volume_5m.rolling(30).mean()) / (volume_5m.rolling(30).std() + 1e-9)
    bb_width = (bb_upper - bb_lower) / (sma20_5m + 1e-9)

    features_df = pd.DataFrame({
        "returns": returns,
        "volatility": volatility,
        "atr": atr,
        "rsi": rsi_5m,
        "trend": trend_ml,
        "volume_z": volume_z,
        "bb_width": bb_width
    })

    # Prepare ML probabilities in rolling walk-forward fashion (matches live bot's adaptation)
    ml_probs = np.full(len(df_5m), 0.5)
    
    retrain_gap = 576
    window_size = 2000
    current_idx = start_idx
    
    # Pre-train OOS model on initial data
    ml_agent.fit_from_dataframe(df_5m.iloc[:current_idx])
    
    while current_idx < len(df_5m):
        end_chunk_idx = min(current_idx + retrain_gap, len(df_5m))
        chunk_features = features_df.iloc[current_idx:end_chunk_idx]
        valid_chunk = chunk_features.dropna(subset=ml_agent.feature_columns)
        
        if len(valid_chunk) > 0 and ml_agent.is_trained and ml_agent.scaler_fitted:
            X_raw = chunk_features.loc[valid_chunk.index, ml_agent.feature_columns]
            X = ml_agent.scaler.transform(X_raw)
            probs = ml_agent.model.predict_proba(X)[:, 1]
            for idx, p in zip(valid_chunk.index, probs):
                loc = df_5m.index.get_loc(idx)
                ml_probs[loc] = p
                
        current_idx = end_chunk_idx
        
        # Retrain on rolling trailing window to adapt to fresh market structure
        if current_idx < len(df_5m):
            train_start = max(0, current_idx - window_size)
            train_df = df_5m.iloc[train_start:current_idx]
            
            # Silent fitting to keep logs clean
            logger = logging.getLogger()
            old_level = logger.level
            logger.setLevel(logging.WARNING)
            ml_agent.fit_from_dataframe(train_df)
            logger.setLevel(old_level)


    # ── Precompute 1h/4h trend ───────────────────────────────────────────────
    trend_fast_1h = df_1h["close"].rolling(20).mean()
    trend_slow_1h = df_1h["close"].rolling(50).mean()

    # Pre-align indices using binary search
    trend_timestamps = df_1h.index.values
    trend_indices = np.searchsorted(trend_timestamps, df_5m.index.values, side="right") - 1
    trend_indices = np.clip(trend_indices, 0, len(df_1h) - 1)

    # ── Main loop ────────────────────────────────────────────────────────────
    for i in range(start_idx, len(df_5m)):
        current_price = float(close_5m.iloc[i])
        now_ts = df_5m.index[i]

        # ── 1. Manage open trade ──────────────────────────────────────────
        if open_trade:
            # Trailing stop update if enabled!
            if TRAILING_STOP_ENABLED:
                current_atr = atr.iloc[i]
                trail_stop = current_price - 3.0 * current_atr
                if trail_stop > open_trade["sl"]:
                    open_trade["sl"] = trail_stop

            # Check for partial profit scale-out if not done yet
            if PARTIAL_TP_ENABLED and not open_trade.get("has_scaled_out", False):
                hit_half_tp = (open_trade["side"] == "buy" and current_price >= open_trade["half_tp"]) or \
                              (open_trade["side"] == "sell" and current_price <= open_trade["half_tp"])
                if hit_half_tp:
                    # Scale out 50%
                    exit_fill_half = apply_slippage(open_trade["half_tp"], open_trade["side"], SLIPPAGE_BPS)
                    pnl_half = settlement_pnl(open_trade["entry"], exit_fill_half, open_trade["qty"] * 0.5, open_trade["side"], TAKER_FEE)
                    wallet += pnl_half
                    
                    open_trade["qty"] = open_trade["qty"] * 0.5
                    open_trade["sl"] = open_trade["entry"]  # Move SL to breakeven!
                    open_trade["has_scaled_out"] = True
                    open_trade["accumulated_pnl"] = pnl_half

            hit_tp  = (open_trade["side"] == "buy"  and current_price >= open_trade["tp"]) or \
                      (open_trade["side"] == "sell" and current_price <= open_trade["tp"])
            hit_sl  = (open_trade["side"] == "buy"  and current_price <= open_trade["sl"]) or \
                      (open_trade["side"] == "sell" and current_price >= open_trade["sl"])
            expired = now_ts >= open_trade["expiry"]

            if hit_tp or hit_sl or expired:
                reason     = "TP" if hit_tp else ("SL" if hit_sl else "EXPIRY")
                exit_fill  = apply_slippage(current_price, open_trade["side"], SLIPPAGE_BPS)
                pnl_second = settlement_pnl(
                    open_trade["entry"], exit_fill,
                    open_trade["qty"],  open_trade["side"], TAKER_FEE
                )
                total_pnl = pnl_second + open_trade.get("accumulated_pnl", 0.0)
                wallet += pnl_second
                trades.append({
                    "symbol": symbol,
                    "side":   open_trade["side"],
                    "entry":  open_trade["entry"],
                    "exit":   exit_fill,
                    "qty":    open_trade["qty"] * (2.0 if open_trade.get("has_scaled_out") else 1.0),
                    "pnl":    total_pnl,
                    "reason": reason + ("_HALF" if open_trade.get("has_scaled_out") and reason == "SL" else ""),
                    "regime": open_trade["regime"],
                    "score":  open_trade["score"],
                    "opened": open_trade["opened"],
                    "closed": str(now_ts),
                })
                open_trade = None
                last_closed_bar = i
            else:
                continue


        # ── 2. Signal Generation ──────────────────────────────────────────
        idx_1h = trend_indices[i]
        if idx_1h < 55:
            continue

        # Trend values
        t_fast = float(trend_fast_1h.iloc[idx_1h])
        t_slow = float(trend_slow_1h.iloc[idx_1h])
        market_bullish = t_fast > t_slow

        regime = regimes[i]
        params = get_regime_params(regime)

        # Breakout session highs/lows
        if regime == "trending":
            session_high = float(high_12.iloc[i])
            session_low = float(low_12.iloc[i])
        elif regime == "volatile":
            session_high = float(high_20.iloc[i])
            session_low = float(low_20.iloc[i])
        else:
            session_high = float(high_8.iloc[i])
            session_low = float(low_8.iloc[i])

        # RSI Signal
        r_val = rsi_5m.iloc[i]
        if r_val < 35:
            rsi_sig = "BUY"
        elif r_val > 65:
            rsi_sig = "SELL"
        else:
            rsi_sig = "HOLD"

        # Bollinger Bands Signal
        bb_l = bb_lower.iloc[i]
        bb_u = bb_upper.iloc[i]
        if current_price < bb_l:
            bb_sig = "BUY"
        elif current_price > bb_u:
            bb_sig = "SELL"
        else:
            bb_sig = "HOLD"

        # MACD Signal
        m_bullish_5m = market_bullish_5m.iloc[i]
        mac = macd.iloc[i]
        sig_l = macd_signal.iloc[i]
        mac_prev = macd.iloc[i-1]
        sig_l_prev = macd_signal.iloc[i-1]
        bull_cross = (mac > sig_l) and (mac_prev <= sig_l_prev)
        bear_cross = (mac < sig_l) and (mac_prev >= sig_l_prev)

        if m_bullish_5m:
            sma_sig = "BUY" if bull_cross else "HOLD"
        else:
            sma_sig = "SELL" if bear_cross else "HOLD"

        def sig_val(s):
            return 1 if s == "BUY" else (-1 if s == "SELL" else 0)

        # Score calculation
        score = 0.0

        if regime == "trending":
            if (market_bullish and current_price > t_fast):
                score += 2.0
            elif ((not market_bullish) and current_price < t_fast):
                score -= 2.0

            score += sig_val(sma_sig) * 2.0

            if bb_sig == "SELL" and market_bullish:
                score += 1.5
            elif bb_sig == "BUY" and (not market_bullish):
                score -= 1.5

            if rsi_sig == "BUY" and market_bullish:
                score += 1.0
            elif rsi_sig == "SELL" and (not market_bullish):
                score -= 1.0

        elif regime == "volatile":
            if current_price > session_high:
                score += 2.5
            elif current_price < session_low:
                score -= 2.5
            score += sig_val(sma_sig) * 1.0
            score += sig_val(rsi_sig) * 1.0

        else:
            if current_price > session_high:
                score -= 1.5
            elif current_price < session_low:
                score += 1.5

            score += sig_val(bb_sig) * 2.5
            score += sig_val(rsi_sig) * 2.0
            score += sig_val(sma_sig) * 0.5

        # ML confidence addition
        ml_prob = ml_probs[i]
        if regime == "trending":
            ml_threshold_long = float(tuned_params.get("ml_conf_long_trending", 0.58))
            ml_threshold_short = float(tuned_params.get("ml_conf_short_trending", 0.42))
        elif regime == "volatile":
            ml_threshold_long = float(tuned_params.get("ml_conf_long_volatile", 0.60))
            ml_threshold_short = float(tuned_params.get("ml_conf_short_volatile", 0.40))
        else:
            ml_threshold_long = float(tuned_params.get("ml_conf_long_ranging", 0.60))
            ml_threshold_short = float(tuned_params.get("ml_conf_short_ranging", 0.40))

        if ml_prob >= ml_threshold_long:
            score += 2.0
        elif ml_prob <= ml_threshold_short:
            score -= 2.0

        # Volume confirmation
        avg_vol = volume_5m.iloc[i-2:i].mean()
        if volume_5m.iloc[i-1] > (avg_vol * params["volume_multiplier"]):
            if market_bullish:
                score += 1.0
            else:
                score -= 1.0

        threshold = params["score_threshold"]

        if score >= threshold:
            signal = "BUY"
        elif score <= -threshold:
            signal = "SELL"
        else:
            continue

        if signal == "BUY" and not market_bullish:
            continue
        if signal == "SELL" and market_bullish:
            continue

        # 3. Macro Market Regime Guard (Daily 200 SMA)
        if DAILY_200SMA_GUARD:
            idx_1d = daily_indices[i]
            daily_sma = float(sma200_1d.iloc[idx_1d])
            if signal == "BUY" and current_price < daily_sma:
                continue
            elif signal == "SELL" and current_price > daily_sma:
                continue

        if i - last_closed_bar < 24:
            continue

        sl_dist = atr.iloc[i] * float(params["sl_atr_mult"]) * float(tuned_params.get("stop_atr_scale", 1.0))
        if sl_dist <= 0:
            continue

        # Dynamic Risk Sizing based on ML confidence (Option 1)
        # Base risk is 3.0%, scaling up to 6.5% for high-probability setups
        if DYNAMIC_ML_RISK:
            if signal == "BUY":
                ml_threshold_long = float(tuned_params.get("ml_conf_long_" + regime, 0.60))
                if ml_prob >= ml_threshold_long + 0.05:
                    dyn_risk = 0.065
                elif ml_prob >= ml_threshold_long:
                    dyn_risk = 0.050
                else:
                    dyn_risk = 0.030
            else:
                ml_threshold_short = float(tuned_params.get("ml_conf_short_" + regime, 0.40))
                short_conf = 1.0 - ml_prob
                short_threshold = 1.0 - ml_threshold_short
                if short_conf >= short_threshold + 0.05:
                    dyn_risk = 0.065
                elif short_conf >= short_threshold:
                    dyn_risk = 0.050
                else:
                    dyn_risk = 0.030
        else:
            dyn_risk = RISK_PER_TRADE

        entry_fill = apply_slippage(current_price, signal.lower(), SLIPPAGE_BPS)
        sl = entry_fill - sl_dist if signal == "BUY" else entry_fill + sl_dist
        tp = entry_fill + sl_dist * float(params["rr_ratio"]) if signal == "BUY" \
             else entry_fill - sl_dist * float(params["rr_ratio"])

        # Risk-based position sizing obeying dynamic risk budget and 3x perpetual leverage limits
        risk_budget  = wallet * dyn_risk
        qty_by_risk  = risk_budget / sl_dist
        qty_by_notional = (wallet * MAX_NOTIONAL) / entry_fill
        raw = min(qty_by_risk, qty_by_notional)

        quant = Decimal("1").scaleb(-int(rules["qty_precision"]))
        qty   = Decimal(str(max(raw, 0))).quantize(quant, rounding=ROUND_DOWN)

        if qty < Decimal(str(rules["min_qty"])):
            continue
        if qty * Decimal(str(entry_fill)) < Decimal(str(rules["min_notional"])):
            continue
        qty = float(qty)

        open_trade = {
            "side":   signal.lower(),
            "entry":  entry_fill,
            "sl":     sl,
            "tp":     tp,
            "qty":    qty,
            "regime": regime,
            "score":  f"SCORE:{score}|{regime.upper()}",
            "opened": str(now_ts),
            "expiry": now_ts + datetime.timedelta(days=7),
            "sl_dist": sl_dist,
            "half_tp": entry_fill + sl_dist if signal == "BUY" else entry_fill - sl_dist,
            "has_scaled_out": False,
            "accumulated_pnl": 0.0,
        }


    return trades
# ── Report printer ────────────────────────────────────────────────────────────
PASS  = "[PASS]"
WARN  = "[WARN]"
FAIL  = "[FAIL]"

def grade(value, good, ok):
    if value >= good: return PASS
    if value >= ok:   return WARN
    return FAIL

def print_report(symbol: str, metrics: dict):
    if "error" in metrics:
        logging.warning(f"{symbol}: {metrics['error']}")
        return

    wr  = metrics["win_rate_pct"]
    sh  = metrics["sharpe_ratio"]
    dd  = metrics["max_drawdown_pct"]
    pf  = metrics["profit_factor"]
    ret = metrics["total_return_pct"]
    rr  = metrics["risk_reward_ratio"]
    exp = metrics["expectancy_per_trade_usd"]

    sep = "-" * 55
    print(f"\n{sep}")
    print(f"  {symbol} - BACKTEST REPORT ({LOOKBACK_DAYS} days)")
    print(sep)
    print(f"  Total Trades       : {metrics['total_trades']}")
    print(f"  Wins / Losses      : {metrics['wins']} W / {metrics['losses']} L")
    print(f"  Win Rate           : {wr:.1f}%")
    print(f"  Risk/Reward Ratio  : {rr:.2f}")
    print(f"  Profit Factor      : {pf:.2f}")
    print(f"  Sharpe Ratio       : {sh:.2f}")
    print(f"  Max Drawdown       : {dd:.1f}%")
    print(f"  Total Return       : {ret:+.2f}%")
    print(f"  Expectancy/Trade   : ${exp:.4f}")
    print(f"  Max Consec Losses  : {metrics['max_consecutive_losses']}")
    print(f"  Final Equity       : ${metrics['final_equity_usd']:.2f}")
    print(sep)

# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    since_ts = int(
        (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=LOOKBACK_DAYS))
        .timestamp() * 1000
    )

    all_trades = []
    tuned_params = load_tuned_params()["params"]

    for symbol in SYMBOLS:
        logging.info(f"Fetching {LOOKBACK_DAYS}d of {symbol} data from Binance ...")

        df_5m = fetch_historical(symbol, TIMEFRAME,       since=since_ts)
        time.sleep(1.5)  # Respect rate limit between symbols
        df_1h = fetch_historical(symbol, TREND_TIMEFRAME, since=since_ts)
        time.sleep(1.5)
        # Fetch Daily data with extra lookback for 200 SMA warm-up
        since_ts_1d = since_ts - (220 * 24 * 60 * 60 * 1000)
        df_1d = fetch_historical(symbol, "1d", since=since_ts_1d)
        time.sleep(1.5)
        if df_1d is None or len(df_1d) < 200:
            logging.warning(f"  Insufficient daily data for {symbol} 200 SMA. Using mock.")
            df_1d = pd.DataFrame({"close": [0.0]*250}, index=pd.date_range(end=datetime.datetime.now(), periods=250))

        if df_5m is None or len(df_5m) < WARMUP_CANDLES + 10:
            logging.error(f"  Not enough data for {symbol}. Skipping.")
            continue

        logging.info(f"  {symbol}: {len(df_5m)} x {TIMEFRAME} bars | {len(df_1h)} x {TREND_TIMEFRAME} bars")

        # Out-of-sample ML: train only on pre-test history (no global joblib leakage)
        start_idx = 2000
        if len(df_5m) <= start_idx + 100:
            start_idx = WARMUP_CANDLES

        ml_agent = MLStrategy(model_path=None, load_pretrained=False)
        pretrain_df = df_5m.iloc[:start_idx]
        if ml_agent.fit_from_dataframe(pretrain_df):
            logging.info(f"  ML trained OOS on first {start_idx} candles of {symbol}")
        else:
            logging.warning(f"  ML training skipped for {symbol} (insufficient labeled bars)")

        symbol_trades = run_backtest_symbol(
            symbol, df_5m, df_1h, df_1d, ml_agent, tuned_params, start_idx=start_idx
        )
        all_trades.extend(symbol_trades)

        metrics = compute_metrics(symbol_trades, INITIAL_CAPITAL)
        print_report(symbol, metrics)

    # ── Portfolio-level summary ──────────────────────────────────────────
    if all_trades:
        print("\n" + "=" * 55)
        print("  PORTFOLIO SUMMARY — ALL SYMBOLS COMBINED")
        print("=" * 55)
        portfolio_metrics = compute_metrics(all_trades, INITIAL_CAPITAL)
        print_report("PORTFOLIO", portfolio_metrics)

        buys = [t for t in all_trades if t.get("side") == "buy"]
        sells = [t for t in all_trades if t.get("side") == "sell"]
        print(f"\n  Side mix: {len(buys)} buys / {len(sells)} sells")
        if buys:
            bw = sum(1 for t in buys if t["pnl"] > 0) / len(buys) * 100
            print(f"  Buy  WR: {bw:.1f}%  PnL: ${sum(t['pnl'] for t in buys):.2f}")
        if sells:
            sw = sum(1 for t in sells if t["pnl"] > 0) / len(sells) * 100
            print(f"  Sell WR: {sw:.1f}%  PnL: ${sum(t['pnl'] for t in sells):.2f}")

        # Save full trade log
        log_path = "backtest_trades.json"
        with open(log_path, "w") as f:
            json.dump(all_trades, f, indent=2, default=str)
        logging.info(f"\nFull trade log saved to → {log_path}")
    else:
        logging.warning("No trades were generated across any symbol. Check your signal thresholds.")


if __name__ == "__main__":
    main()
