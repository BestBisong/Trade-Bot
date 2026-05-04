import time, logging, datetime, json, os, asyncio
from execution.broker import BybitBroker
from data.data_fetcher import fetch, fetch_confluence, close_exchange
from signals.signal_generator import generate
from config.settings import SYMBOLS, TIMEFRAME
from strategies.ml_strategy import MLStrategy
from strategies.regime import detect_market_regime, get_regime_params
from risk.risk_manager import RiskManager
from execution.sizing import calculate_order_quantity, apply_slippage, settlement_pnl

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

    state = {"wallet": wallet, "timestamp": datetime.datetime.now().isoformat(), "risk": risk_snapshot, "active_trades": len(active_trades)}
    if system_snapshot: state.update(system_snapshot)
    _safe_write_json("bot_state.json", state)

    if scan_heartbeat:
        hb = _safe_read_json("scan_heartbeat.json", {})
        hb.update(scan_heartbeat)
        _safe_write_json("scan_heartbeat.json", hb)

async def scan_symbol(symbol, broker, ml_agent, active_trades, virtual_wallet, tuned_params, now):
    """Core scanning logic for a single symbol."""
    if any(t['symbol'] == symbol for t in active_trades): return
    
    try:
        df, trend_df = await fetch_confluence(symbol, base_tf=TIMEFRAME, trend_tf="1h")
        if df is None or trend_df is None: return
        
        ml_agent.continuous_learn(df)
        signal, status, _ = generate(df, trend_df, ml_agent, tuned_params=tuned_params)
        
        if signal in ["BUY", "SELL"]:
            entry_price = await broker.price(symbol)
            if entry_price is None: return

            regime = detect_market_regime(df, trend_df)
            params = get_regime_params(regime)
            
            tr = (df['high'] - df['low']).rolling(14).mean()
            atr = float(tr.iloc[-1]) if not tr.empty else entry_price * 0.001
            sl_dist = atr * float(params["sl_atr_mult"])
            
            sl = entry_price - sl_dist if signal == "BUY" else entry_price + sl_dist
            tp = entry_price + (sl_dist * float(params["rr_ratio"])) if signal == "BUY" else entry_price - (sl_dist * float(params["rr_ratio"]))

            rules = EXCHANGE_RULES.get(symbol, {"min_qty": 0.00001, "qty_precision": 5, "min_notional": 5.0})
            qty = calculate_order_quantity(virtual_wallet, entry_price, sl_dist, 0.01, MAX_NOTIONAL_PER_TRADE, rules["min_qty"], rules["qty_precision"], rules["min_notional"])
            
            if qty > 0:
                entry_fill = apply_slippage(entry_price, signal.lower(), SLIPPAGE_BPS)
                order = await broker.place_order(symbol, signal.lower(), qty, entry_fill)
                
                if order:
                    active_trades.append({
                        'symbol': symbol, 'side': signal.lower(), 'entry_price': entry_fill,
                        'tp': tp, 'sl': sl, 'qty': qty, 'expiry': now + datetime.timedelta(hours=4),
                        'df': df, 'opened_at': now.isoformat(), 'status': status, 'regime': regime
                    })
                    logging.info(f"OPENED | {signal} {symbol} | Regime: {regime} | Score: {status}")
    except Exception as e:
        logging.error(f"SCAN_ERROR | {symbol}: {e}")

async def run_bot():
    broker = BybitBroker(paper_mode=True)
    ml_agent = MLStrategy()
    risk_mgmt = RiskManager(max_daily_loss=5.0, max_consecutive_losses=3, cooldown_minutes=30, max_open_positions=3)
    
    virtual_wallet = float(_safe_read_json("bot_state.json", {}).get("wallet", INITIAL_WALLET))
    active_trades = []
    tuned_params = _safe_read_json("tuned_params.json", {})

    logging.info("JARVIS | Async Engine Online. Monitoring parallel streams...")

    try:
        while True:
            now = datetime.datetime.now()
            risk_mgmt.mark_equity(virtual_wallet)
            risk_snapshot = risk_mgmt.summary(equity=virtual_wallet)

            for trade in active_trades[:]:
                current_price = await broker.price(trade['symbol'])
                if not current_price: continue

                if trade['side'] == "buy" and current_price >= (trade['entry_price'] + (trade['tp'] - trade['entry_price']) * 0.5):
                    trade['sl'] = max(trade['sl'], trade['entry_price'])
                elif trade['side'] == "sell" and current_price <= (trade['entry_price'] - (trade['entry_price'] - trade['tp']) * 0.5):
                    trade['sl'] = min(trade['sl'], trade['entry_price'])

                hit_tp = (trade['side'] == "buy" and current_price >= trade['tp']) or (trade['side'] == "sell" and current_price <= trade['tp'])
                hit_sl = (trade['side'] == "buy" and current_price <= trade['sl']) or (trade['side'] == "sell" and current_price >= trade['sl'])
                
                if hit_tp or hit_sl or now >= trade['expiry']:
                    exit_fill = apply_slippage(current_price, trade['side'], SLIPPAGE_BPS)
                    pnl = settlement_pnl(trade['entry_price'], exit_fill, trade['qty'], trade['side'], TAKER_FEE_RATE)
                    
                    virtual_wallet += pnl
                    risk_mgmt.update_stats(pnl)
                    _append_trade_history({"symbol": trade['symbol'], "pnl": pnl, "reason": "tp" if hit_tp else "sl", "closed_at": now.isoformat()})
                    logging.info(f"CLOSED | {trade['symbol']} | PnL: ${pnl:.2f} | Wallet: ${virtual_wallet:.2f}")
                    active_trades.remove(trade)

            if broker.can_open_new_trades() and risk_mgmt.allowed(virtual_wallet):
                tasks = [scan_symbol(s, broker, ml_agent, active_trades, virtual_wallet, tuned_params, now) for s in SYMBOLS]
                await asyncio.gather(*tasks)

            update_shared_data(active_trades, virtual_wallet, risk_snapshot)
            await asyncio.sleep(10)
    finally:
        await broker.close()
        await close_exchange()

if __name__ == "__main__":
    asyncio.run(run_bot())