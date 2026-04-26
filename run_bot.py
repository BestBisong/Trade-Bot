import time, logging, datetime, json, os
from execution.broker import BybitBroker
from data.data_fetcher import fetch, fetch_confluence
from signals.signal_generator import generate
from config.settings import SYMBOLS, TIMEFRAME
from strategies.ml_strategy import MLStrategy
from strategies.regime import detect_market_regime, get_regime_params
from risk.risk_manager import RiskManager
from execution.sizing import calculate_order_quantity, apply_slippage, settlement_pnl
from backtesting.walk_forward import (
    run_walk_forward_validation,
    live_gate_from_walk_forward,
    should_refresh_walk_forward,
)
from backtesting.self_tuner import maybe_update_weekly_tuning

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')

INITIAL_WALLET = 100.0
TAKER_FEE_RATE = 0.0006
MAX_NOTIONAL_PER_TRADE = 0.25
SLIPPAGE_BPS = 5

EXCHANGE_RULES = {
    "BTC/USDT": {"min_qty": 0.00001, "qty_precision": 5, "min_notional": 5.0},
    "ETH/USDT": {"min_qty": 0.0001, "qty_precision": 4, "min_notional": 5.0},
    "SOL/USDT": {"min_qty": 0.01, "qty_precision": 2, "min_notional": 5.0},
    "XRP/USDT": {"min_qty": 1.0, "qty_precision": 1, "min_notional": 5.0},
}


def _safe_read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            content = f.read().strip()
            if not content:
                return default
            return json.loads(content)
    except Exception:
        return default


def _safe_write_json(path, payload):
    with open(path, "w") as f:
        json.dump(payload, f, default=str)


def _append_trade_history(record, path="trade_history.json", max_records=2000):
    history = _safe_read_json(path, [])
    if not isinstance(history, list):
        history = []
    history.append(record)
    _safe_write_json(path, history[-max_records:])


def update_shared_data(active_trades, wallet, risk_snapshot, scan_heartbeat=None, system_snapshot=None):
    """Syncs bot memory with Dashboard files for real-time monitoring."""
    clean_trades = []
    for t in active_trades:
        trade_copy = {k: v for k, v in t.items() if k != 'df'}
        if isinstance(trade_copy.get('expiry'), datetime.datetime):
            trade_copy['expiry'] = trade_copy['expiry'].isoformat()
        clean_trades.append(trade_copy)
    _safe_write_json("active_trades.json", clean_trades)

    state = {
        "wallet": wallet,
        "timestamp": datetime.datetime.now().isoformat(),
        "risk": risk_snapshot,
        "active_trades": len(active_trades),
    }
    if system_snapshot:
        state.update(system_snapshot)
    _safe_write_json("bot_state.json", state)

    if scan_heartbeat:
        current_heartbeat = _safe_read_json("scan_heartbeat.json", {})
        current_heartbeat.update(scan_heartbeat)
        _safe_write_json("scan_heartbeat.json", current_heartbeat)

def run_bot():
    broker = BybitBroker(paper_mode=True)

    if should_refresh_walk_forward(max_age_hours=24):
        try:
            wf_report = run_walk_forward_validation(
                symbols=SYMBOLS,
                timeframe=TIMEFRAME,
                trend_timeframe="1h",
            )
        except Exception as e:
            logging.error(f"WALK_FORWARD | Validation failed: {e}")
            wf_report = {"aggregate": {"total_windows": 0, "win_rate": 0.0, "worst_drawdown_pct": 100.0}}
    else:
        wf_report = _safe_read_json("walk_forward_report.json", {"aggregate": {}})

    gate = live_gate_from_walk_forward(wf_report)

    tuning_result = maybe_update_weekly_tuning(wf_report)
    tuning_state = tuning_result["state"]
    tuned_params = tuning_state.get("params", {})

    if not broker.paper_mode and not gate["allowed"]:
        logging.error(
            "LIVE_CAPITAL_BLOCKED | Walk-forward gate failed: "
            f"{gate['measured']} vs {gate['criteria']}"
        )
        return

    logging.info(f"WALK_FORWARD | Gate result: {gate['allowed']} | Metrics: {gate['measured']}")
    logging.info(f"SELF_TUNER | Updated: {tuning_result['updated']} | Action: {tuning_state.get('action', 'hold')}")

    ml_agent = MLStrategy()
    risk_mgmt = RiskManager(max_daily_loss=5.0, max_consecutive_losses=3, cooldown_minutes=30, max_open_positions=2)
    
    virtual_wallet = float(_safe_read_json("bot_state.json", {}).get("wallet", INITIAL_WALLET))
    if virtual_wallet <= 0:
        virtual_wallet = INITIAL_WALLET

    active_trades = [] 

    logging.info("JARVIS | System Online. Monitoring 3-hour window...")

    while True:
        now = datetime.datetime.now()
        risk_mgmt.mark_equity(virtual_wallet)
        
        # 1. SETTLE ACTIVE TRADES (always active, even outside entry window)
        for trade in active_trades[:]:
            current_df = fetch(trade['symbol'], timeframe="1m", limit=1)
            if current_df is None or current_df.empty:
                continue

            current_price = current_df['close'].iloc[-1]
            
            if trade['side'] == "buy" and current_price >= (trade['entry_price'] + (trade['tp'] - trade['entry_price']) * 0.5):
                trade['sl'] = max(trade['sl'], trade['entry_price'])
            elif trade['side'] == "sell" and current_price <= (trade['entry_price'] - (trade['entry_price'] - trade['tp']) * 0.5):
                trade['sl'] = min(trade['sl'], trade['entry_price'])

            hit_tp = (trade['side'] == "buy" and current_price >= trade['tp']) or \
                     (trade['side'] == "sell" and current_price <= trade['tp'])
            hit_sl = (trade['side'] == "buy" and current_price <= trade['sl']) or \
                     (trade['side'] == "sell" and current_price >= trade['sl'])

            if hit_tp or hit_sl or now >= trade['expiry']:
                exit_fill = apply_slippage(current_price, trade['side'], slippage_bps=SLIPPAGE_BPS)
                pnl = settlement_pnl(
                    entry_price=trade['entry_price'],
                    exit_price=exit_fill,
                    qty=trade['qty'],
                    side=trade['side'],
                    taker_fee_rate=TAKER_FEE_RATE,
                )
                fees = (trade['entry_price'] + exit_fill) * trade['qty'] * TAKER_FEE_RATE

                close_reason = "tp" if hit_tp else ("sl" if hit_sl else "expiry")
                
                virtual_wallet += pnl
                risk_mgmt.update_stats(pnl) 
                ml_agent.learn_from_settlement(trade['df'], (1 if pnl > 0 else 0), pnl)

                _append_trade_history({
                    "symbol": trade['symbol'],
                    "side": trade['side'],
                    "entry_price": trade['entry_price'],
                    "exit_price": exit_fill,
                    "qty": trade['qty'],
                    "pnl": pnl,
                    "fees": fees,
                    "reason": close_reason,
                    "opened_at": trade.get("opened_at"),
                    "closed_at": now.isoformat(),
                })
                
                logging.info(f"CLOSED | {trade['symbol']} | PnL: ${pnl:.2f} | Wallet: ${virtual_wallet:.2f}")
                active_trades.remove(trade)

        session_active = broker.is_window_active()
        can_open_window = broker.can_open_new_trades()
        risk_allowed = risk_mgmt.allowed(equity=virtual_wallet)
        risk_snapshot = risk_mgmt.summary(equity=virtual_wallet)
        update_shared_data(active_trades, virtual_wallet, risk_snapshot)

        if not session_active or not risk_allowed:
            time.sleep(10)
            continue

        # 2. SCAN & CONTINUOUS LEARNING
        for symbol in SYMBOLS:
            update_shared_data(active_trades, virtual_wallet, risk_snapshot, {symbol: now.strftime("%H:%M:%S")})
            
            if any(t['symbol'] == symbol for t in active_trades):
                continue
            if not can_open_window:
                continue
            if not risk_mgmt.can_open_new_trade(len(active_trades), equity=virtual_wallet):
                continue
            
            try:
                df, trend_df = fetch_confluence(symbol, base_tf=TIMEFRAME, trend_tf="1h")
                if df is None or trend_df is None:
                    continue
                
                ml_agent.continuous_learn(df)
                
                signal, status, _ = generate(df, trend_df, ml_agent, tuned_params=tuned_params)
                
                if signal in ["BUY", "SELL"]:
                    entry_price = broker.price(symbol)
                    if entry_price is None:
                        continue

                    regime = detect_market_regime(df, trend_df)
                    params = get_regime_params(regime)
                    rr_ratio = float(params["rr_ratio"])
                    sl_scale = float(tuned_params.get("stop_atr_scale", 1.0))
                    sl_mult = float(params["sl_atr_mult"]) * sl_scale

                    rules = EXCHANGE_RULES.get(symbol, {"min_qty": 0.000001, "qty_precision": 6, "min_notional": 5.0})
                    
                    atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
                    atr = float(atr) if atr and atr > 0 else entry_price * 0.001
                    sl_dist = max(atr * sl_mult, entry_price * 0.002)
                    
                    sl = entry_price - sl_dist if signal == "BUY" else entry_price + sl_dist
                    tp = entry_price + (sl_dist * rr_ratio) if signal == "BUY" else entry_price - (sl_dist * rr_ratio)

                    # Skip trades where expected move is too small after costs.
                    expected_gross_move = abs(tp - entry_price)
                    est_cost = (entry_price * 2 * TAKER_FEE_RATE) + (entry_price * (SLIPPAGE_BPS / 10000.0) * 2)
                    if expected_gross_move <= est_cost * 1.5:
                        logging.info(f"EDGE_REJECTED | {symbol} expected move too small vs cost model.")
                        continue
                    
                    qty = calculate_order_quantity(
                        wallet=virtual_wallet,
                        entry_price=entry_price,
                        stop_distance=sl_dist,
                        risk_per_trade=0.01,
                        max_notional_fraction=MAX_NOTIONAL_PER_TRADE,
                        min_qty=rules["min_qty"],
                        qty_precision=rules["qty_precision"],
                        min_notional=rules["min_notional"],
                    )
                    if qty <= 0:
                        logging.info(f"SIZING_REJECTED | {symbol} does not satisfy exchange constraints.")
                        continue

                    confidence = ml_agent.confidence(df)
                    entry_fill = apply_slippage(entry_price, signal.lower(), slippage_bps=SLIPPAGE_BPS)
                    
                    active_trades.append({
                        'symbol': symbol, 'side': signal.lower(), 'entry_price': entry_fill,
                        'tp': tp, 'sl': sl, 'qty': qty, 
                        'expiry': now + datetime.timedelta(hours=2), 'df': df,
                        'opened_at': now.isoformat(), 'status': status,
                        'confidence': round(confidence, 4), 'regime': regime,
                    })
                    update_shared_data(
                        active_trades,
                        virtual_wallet,
                        risk_snapshot,
                        system_snapshot={
                            "walk_forward_gate": gate,
                            "tuning": tuning_state,
                        },
                    )
                    logging.info(
                        f"OPENED | {signal} {symbol} | Regime: {regime} | "
                        f"RR: 1:{rr_ratio:.1f} | ATR: {atr:.4f} | ML: {confidence:.2f}"
                    )
            except Exception as e:
                logging.error(f"Scan Error for {symbol}: {e}")

        update_shared_data(
            active_trades,
            virtual_wallet,
            risk_snapshot,
            system_snapshot={
                "walk_forward_gate": gate,
                "tuning": tuning_state,
            },
        )

        time.sleep(30) 

if __name__ == "__main__":
    run_bot()