import time, logging, datetime, json, os, asyncio
from execution.broker import BybitBroker
from data.data_fetcher import fetch, fetch_confluence, close_exchange
from signals.signal_generator import generate
from config.settings import SYMBOLS, TIMEFRAME, TREND_TIMEFRAME, PARTIAL_TP_ENABLED, DYNAMIC_ML_RISK, DAILY_200SMA_GUARD, TRAILING_STOP_ENABLED
from strategies.ml_strategy import MLStrategy
from strategies.regime import detect_market_regime, get_regime_params
from strategies.execution_levels import stop_distance
from backtesting.self_tuner import load_tuned_params
from risk.risk_manager import RiskManager
from execution.sizing import calculate_order_quantity, apply_slippage, settlement_pnl

# Setup logging to both console and logs/bot.log file
os.makedirs("logs", exist_ok=True)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S')

# Console handler
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

# File handler with UTF-8 encoding
fh = logging.FileHandler("logs/bot.log", mode="a", encoding="utf-8")
fh.setFormatter(formatter)
logger.addHandler(fh)


INITIAL_WALLET = 100.0
TAKER_FEE_RATE = 0.0006
RISK_PER_TRADE = 0.035
MAX_NOTIONAL_PER_TRADE = 3.0
SLIPPAGE_BPS = 5

EXCHANGE_RULES = {
    "BTC/USDT": {"min_qty": 0.00001, "qty_precision": 5, "min_notional": 5.0},
    "ETH/USDT": {"min_qty": 0.0001, "qty_precision": 4, "min_notional": 5.0},
    "SOL/USDT": {"min_qty": 0.01, "qty_precision": 2, "min_notional": 5.0},
    "XRP/USDT": {"min_qty": 1.0, "qty_precision": 1, "min_notional": 5.0},
}

def _safe_read_json(path, default):
    if not os.path.exists(path): return default
    try:
        with open(path, "r") as f:
            content = f.read().strip()
            return json.loads(content) if content else default
    except Exception: return default

def _safe_write_json(path, payload):
    with open(path, "w") as f:
        json.dump(payload, f, default=str)

def _append_trade_history(record, path="trade_history.json", max_records=2000):
    history = _safe_read_json(path, [])
    history.append(record)
    _safe_write_json(path, history[-max_records:])

def update_shared_data(active_trades, wallet, risk_snapshot, scan_heartbeat=None, system_snapshot=None):
    clean_trades = [{k: v for k, v in t.items() if k != 'df'} for t in active_trades]
    for t in clean_trades:
        if isinstance(t.get('expiry'), datetime.datetime): t['expiry'] = t['expiry'].isoformat()
    _safe_write_json("active_trades.json", clean_trades)

    state = _safe_read_json("bot_state.json", {"wallet": wallet, "risk": risk_snapshot, "active_trades": len(active_trades), "prices": {}})
    state["wallet"] = wallet
    state["timestamp"] = datetime.datetime.now().isoformat()
    state["risk"] = risk_snapshot
    state["active_trades"] = len(active_trades)
    
    if system_snapshot:
        if "prices" in system_snapshot:
            if "prices" not in state: state["prices"] = {}
            state["prices"].update(system_snapshot["prices"])
        for k, v in system_snapshot.items():
            if k != "prices": state[k] = v
            
    _safe_write_json("bot_state.json", state)

    if scan_heartbeat:
        hb = _safe_read_json("scan_heartbeat.json", {})
        hb.update(scan_heartbeat)
        _safe_write_json("scan_heartbeat.json", hb)

async def scan_symbol(symbol, broker, ml_agent, active_trades, virtual_wallet, tuned_params, now):
    """Core scanning logic for a single symbol."""
    if any(t['symbol'] == symbol for t in active_trades): return
    
    try:
        df, trend_df = await fetch_confluence(symbol, base_tf=TIMEFRAME, trend_tf=TREND_TIMEFRAME)
        if df is None or trend_df is None: return

        # Fetch Daily data (1d) to compute 200 SMA Guard
        daily_sma = None
        if DAILY_200SMA_GUARD:
            try:
                df_1d = await fetch(symbol, timeframe="1d", limit=250)
                if df_1d is not None and len(df_1d) >= 200:
                    daily_sma = df_1d["close"].rolling(200).mean().iloc[-1]
            except Exception as ex:
                logging.warning(f"DAILY_SMA_ERROR | Could not calculate Daily 200 SMA for {symbol}: {ex}")
        
        signal, status, _ = generate(df, trend_df, ml_agent, tuned_params=tuned_params)
        logging.info(f"SCANNER | {symbol} | Signal: {signal} | Verdict: {status}")
        
        if signal in ("BUY", "SELL"):
            entry_price = await broker.price(symbol)
            if entry_price is None: return

            # 3. Macro Market Regime Guard (Daily 200 SMA)
            if DAILY_200SMA_GUARD and daily_sma is not None:
                if signal == "BUY" and entry_price < daily_sma:
                    logging.info(f"REGIME_GUARD | {symbol} BUY signal blocked: entry price ${entry_price:.2f} is under Daily 200 SMA (${daily_sma:.2f})")
                    return
                elif signal == "SELL" and entry_price > daily_sma:
                    logging.info(f"REGIME_GUARD | {symbol} SELL signal blocked: entry price ${entry_price:.2f} is above Daily 200 SMA (${daily_sma:.2f})")
                    return

            regime = detect_market_regime(df, trend_df)
            params = get_regime_params(regime)
            sl_dist = stop_distance(df, regime, tuned_params)
            
            sl = entry_price - sl_dist if signal == "BUY" else entry_price + sl_dist
            tp = entry_price + (sl_dist * float(params["rr_ratio"])) if signal == "BUY" else entry_price - (sl_dist * float(params["rr_ratio"]))

            # Dynamic Risk Sizing based on ML confidence (Option 1)
            if DYNAMIC_ML_RISK:
                ml_prob = ml_agent.confidence(df)
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

            rules = EXCHANGE_RULES.get(symbol, {"min_qty": 0.00001, "qty_precision": 5, "min_notional": 5.0})
            qty = calculate_order_quantity(
                virtual_wallet, entry_price, sl_dist,
                dyn_risk, MAX_NOTIONAL_PER_TRADE,
                rules["min_qty"], rules["qty_precision"], rules["min_notional"],
            )
            
            if qty > 0:
                entry_fill = apply_slippage(entry_price, signal.lower(), SLIPPAGE_BPS)
                notional = qty * entry_fill
                logging.info(f"ORDER PREP | {symbol} {signal} | Entry: ${entry_fill:.4f} | Qty: {qty} | Notional: ${notional:.2f} | SL: ${sl:.4f} | TP: ${tp:.4f}")
                
                order = await broker.place_order(symbol, signal.lower(), qty, entry_fill)
                
                if order:
                    active_trades.append({
                        'symbol': symbol, 'side': signal.lower(), 'entry_price': entry_fill,
                        'tp': tp, 'sl': sl, 'qty': qty, 'expiry': now + datetime.timedelta(days=7),
                        'df': df, 'opened_at': now.isoformat(), 'status': status, 'regime': regime,
                        'sl_dist': sl_dist,
                        'half_tp': entry_fill + sl_dist if signal == "BUY" else entry_fill - sl_dist,
                        'has_scaled_out': False,
                        'accumulated_pnl': 0.0
                    })
                    logging.info(f"OPENED | {signal} {symbol} | Regime: {regime} | Score: {status}")
                    try:
                        from signals.telegram_notifier import notify
                        notify(f"🔔 OPENED | {symbol} {signal}\nRegime: {regime}\nScore: {status}\nEntry: ${entry_fill:.4f}\nQty: {qty}\nSL: ${sl:.4f} | TP: ${tp:.4f}")
                    except Exception as e:
                        logging.error(f"TELEGRAM_ERROR | Failed to send order open notification: {e}")
            else:
                logging.info(f"ORDER REJECTED | {symbol} {signal} | Reason: Qty 0 (Constraints failed)")
    except Exception as e:
        logging.error(f"SCAN_ERROR | {symbol}: {e}")

async def run_bot():
    broker = BybitBroker(paper_mode=True)
    ml_agent = MLStrategy(load_pretrained=True)
    risk_mgmt = RiskManager(max_daily_loss=5.0, max_consecutive_losses=3, cooldown_minutes=30, max_open_positions=3)
    
    virtual_wallet = float(_safe_read_json("bot_state.json", {}).get("wallet", INITIAL_WALLET))
    active_trades = []
    tuned_params = load_tuned_params()["params"]

    logging.info("JARVIS | Async Engine Online. Monitoring parallel streams...")
    try:
        from signals.telegram_notifier import notify
        notify("🚀 JARVIS Quant Bot Online & Scanning Market Data...")
    except Exception as e:
        logging.error(f"TELEGRAM_ERROR | Failed to send startup notification: {e}")

    logging.info("JARVIS | Warming ML on historical candles...")
    for s in SYMBOLS:
        try:
            hist_df = await fetch(s, timeframe=TIMEFRAME, limit=1000)
            if hist_df is not None and len(hist_df) > 100:
                ml_agent.continuous_learn(hist_df, force=True)
                logging.info(f"JARVIS | ML refreshed on {len(hist_df)} bars for {s}")
        except Exception as e:
            logging.error(f"JARVIS | ML warmup failed for {s}: {e}")

    try:
        while True:
            try:
                now = datetime.datetime.now()
                risk_mgmt.mark_equity(virtual_wallet)
                risk_snapshot = risk_mgmt.summary(equity=virtual_wallet)
                for trade in active_trades[:]:
                    current_price = await broker.price(trade['symbol'])
                    if not current_price: continue
                    trade['current_price'] = current_price

                    # Trailing stop update if enabled!
                    if TRAILING_STOP_ENABLED:
                        import ta
                        trade_df = trade.get('df')
                        if trade_df is not None:
                            current_atr = ta.volatility.average_true_range(
                                trade_df["high"], trade_df["low"], trade_df["close"], window=14
                            ).iloc[-1]
                            
                            if trade['side'] == "buy":
                                trail_stop = current_price - 3.0 * current_atr
                                if trail_stop > trade['sl']:
                                    trade['sl'] = trail_stop
                                    logging.info(f"TRAILING STOP | {trade['symbol']} Stop Loss raised to ${trail_stop:.2f}")

                    # Check for partial profit scale-out if enabled
                    if PARTIAL_TP_ENABLED and not trade.get('has_scaled_out', False):
                        hit_half_tp = (trade['side'] == "buy" and current_price >= trade['half_tp']) or \
                                      (trade['side'] == "sell" and current_price <= trade['half_tp'])
                        if hit_half_tp:
                            exit_fill_half = apply_slippage(trade['half_tp'], trade['side'], SLIPPAGE_BPS)
                            pnl_half = settlement_pnl(trade['entry_price'], exit_fill_half, trade['qty'] * 0.5, trade['side'], TAKER_FEE_RATE)
                            
                            # Realize profit on the first half
                            virtual_wallet += pnl_half
                            risk_mgmt.update_stats(pnl_half)
                            
                            # Scale down live position size and adjust stop loss to breakeven!
                            trade['qty'] = trade['qty'] * 0.5
                            trade['sl'] = trade['entry_price']
                            trade['has_scaled_out'] = True
                            trade['accumulated_pnl'] = pnl_half
                            
                            # Execute broker position adjustment (Bybit paper-trade adjust)
                            await broker.place_order(trade['symbol'], "sell" if trade['side'] == "buy" else "buy", trade['qty'], exit_fill_half)
                            logging.info(f"SCALED OUT | {trade['symbol']} | Locked half profit: ${pnl_half:.2f} | Moved SL to Breakeven")
                            try:
                                from signals.telegram_notifier import notify
                                notify(f"💵 SCALED OUT | {trade['symbol']}\nLocked half profit: ${pnl_half:.2f}\nMoved SL to Breakeven")
                            except Exception as e:
                                logging.error(f"TELEGRAM_ERROR | Failed to send scale out notification: {e}")

                    hit_tp = (trade['side'] == "buy" and current_price >= trade['tp']) or (trade['side'] == "sell" and current_price <= trade['tp'])
                    hit_sl = (trade['side'] == "buy" and current_price <= trade['sl']) or (trade['side'] == "sell" and current_price >= trade['sl'])
                    
                    if hit_tp or hit_sl or now >= trade['expiry']:
                        exit_fill = apply_slippage(current_price, trade['side'], SLIPPAGE_BPS)
                        pnl_second = settlement_pnl(trade['entry_price'], exit_fill, trade['qty'], trade['side'], TAKER_FEE_RATE)
                        
                        total_pnl = pnl_second + trade.get('accumulated_pnl', 0.0)
                        virtual_wallet += pnl_second
                        risk_mgmt.update_stats(pnl_second)
                        
                        reason = "tp" if hit_tp else ("sl" if hit_sl else "expiry")
                        _append_trade_history({
                            "symbol": trade['symbol'], 
                            "pnl": total_pnl, 
                            "reason": reason + ("_half" if trade.get('has_scaled_out') and reason == "sl" else ""), 
                            "closed_at": now.isoformat()
                        })
                        if trade.get('df') is not None:
                            ml_agent.learn_from_settlement(trade['df'], pnl=total_pnl)
                        logging.info(f"CLOSED | {trade['symbol']} | PnL: ${total_pnl:.2f} | Wallet: ${virtual_wallet:.2f}")
                        try:
                            from signals.telegram_notifier import notify
                            notify(f"🏁 CLOSED | {trade['symbol']}\nReason: {reason.upper()}\nPnL: ${total_pnl:.2f}\nWallet: ${virtual_wallet:.2f}")
                        except Exception as e:
                            logging.error(f"TELEGRAM_ERROR | Failed to send order close notification: {e}")
                        
                        # Close remaining position at the broker
                        await broker.place_order(trade['symbol'], "sell" if trade['side'] == "buy" else "buy", trade['qty'], exit_fill)
                        active_trades.remove(trade)

                can_trade = (
                    broker.can_open_new_trades()
                    and risk_mgmt.allowed(virtual_wallet)
                    and risk_mgmt.can_open_new_trade(len(active_trades), equity=virtual_wallet)
                )
                if can_trade:
                    for s in SYMBOLS:
                        await scan_symbol(s, broker, ml_agent, active_trades, virtual_wallet, tuned_params, now)
                        price_val = await broker.price(s)
                        update_shared_data(
                            active_trades, virtual_wallet, risk_snapshot,
                            scan_heartbeat={s: datetime.datetime.now().strftime("%H:%M:%S")},
                            system_snapshot={"prices": {s: price_val}} if price_val else None
                        )
                        await asyncio.sleep(1.5)

                update_shared_data(active_trades, virtual_wallet, risk_snapshot)
                logging.info(f"JARVIS | Scan cycle complete. Active positions: {len(active_trades)} | Wallet: ${virtual_wallet:.2f}")
            except Exception as e:
                logging.error(f"SYSTEM_GLITCH | Exception occurred in loop cycle: {e}", exc_info=True)
            await asyncio.sleep(10)
    finally:
        await broker.close()
        await close_exchange()

if __name__ == "__main__":
    asyncio.run(run_bot())
