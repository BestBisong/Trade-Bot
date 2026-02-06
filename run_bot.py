import time, logging, datetime, json, os
from data.data_fetcher import fetch
from signals.signal_generator import generate
from execution.broker import BitgetBroker
from risk.position_sizer import PositionSizer
from risk.risk_manager import RiskManager
from risk.kill_switch import MarketKillSwitch
from signals.telegram_notifier import notify
from config.settings import SYMBOLS, TIMEFRAME
from strategies.ml_strategy import MLStrategy
from risk.stop_loss import stop_loss

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')

METADATA_FILE = "active_trades.json"

def save_metadata(data):
    with open(METADATA_FILE, 'w') as f:
        serializable = {k: {**v, "entry_time": v["entry_time"].isoformat()} for k, v in data.items()}
        json.dump(serializable, f, indent=4)

def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            data = json.load(f)
            return {k: {**v, "entry_time": datetime.datetime.fromisoformat(v["entry_time"])} for k, v in data.items()}
    return {}

def check_higher_timeframe_trend(symbol):
    """Balanced Filter: Allows trades if Trending OR Oversold (Bottom Hunting)."""
    try:
        df_1h = fetch(symbol, timeframe='1h', limit=50)
        if df_1h is None or len(df_1h) < 20: return False

        # Trend: Price near/above 20 SMA
        sma_20 = df_1h['close'].rolling(20).mean().iloc[-1]
        current_price = df_1h['close'].iloc[-1]
        is_trending = current_price > (sma_20 * 0.99)
        
        # Mean Reversion: 1h RSI is Oversold
        delta = df_1h['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_1h = 100 - (100 / (1 + (gain / loss).iloc[-1]))
        is_oversold = rsi_1h < 35
        
        return is_trending or is_oversold
    except:
        return False

def run_bot():
    print(">>> Bot initializing Pro Features (Balanced Mode)...")
    broker = BitgetBroker(paper_mode=True)
    sizer = PositionSizer(risk_percent=2) 
    risk_mgr = RiskManager(max_daily_loss=5)
    ml_agent = MLStrategy()
    
    trade_metadata = load_metadata()
    open_on_exchange = list(broker.tracker.open_positions.keys())
    trade_metadata = {s: m for s, m in trade_metadata.items() if s in open_on_exchange}
    save_metadata(trade_metadata)

    ml_agent.train([fetch(s, limit=1000) for s in SYMBOLS])
    notify("🚀 Pro Bot Started: Balanced Risk & Trailing Stops Active.")

    last_summary_date = None

    while True:
        now = datetime.datetime.now()
        if not (now.weekday() < 5 and 10 <= now.hour < 16):
            if now.hour == 16 and last_summary_date != now.date():
                metrics = broker.tracker.get_daily_metrics()
                if metrics: notify(f"📊 SUMMARY | PnL: {metrics['pnl']:.2f} USDT")
                last_summary_date = now.date()
            time.sleep(300)
            continue

        # Manage Open Trades (Trailing SL/TP)
        for symbol in list(broker.tracker.open_positions.keys()):
            meta = trade_metadata.get(symbol)
            if not meta: continue
            
            current_price = broker.price(symbol)
            
            # Trailing Stop: Buffer 1.5% below current price to lock in gains
            potential_sl = current_price * 0.985 
            if potential_sl > meta["sl"]:
                meta["sl"] = potential_sl
                save_metadata(trade_metadata)

            if current_price <= meta["sl"] or current_price >= meta["tp"]:
                amount = 0
                for t in reversed(broker.tracker.trades):
                    if t['symbol'] == symbol and t['side'] == 'buy':
                        amount = t['amount']; break
                broker.execute_order(symbol, "sell", amount)
                trade_metadata.pop(symbol, None)
                save_metadata(trade_metadata)
                notify(f"🏁 EXIT: {symbol} at {current_price:.2f}")

        # Scan for Opportunities
        for symbol in SYMBOLS:
            if symbol in broker.tracker.open_positions: continue
            try:
                if not check_higher_timeframe_trend(symbol): continue

                df = fetch(symbol, timeframe=TIMEFRAME)
                signal, status, duration = generate(df, ml_agent) 
                current_price = broker.price(symbol)

                if signal == "BUY" and risk_mgr.allowed():
                    amount = sizer.size(broker.balance("USDT"), current_price)
                    if amount > 0:
                        broker.execute_order(symbol, "buy", amount)
                        trade_metadata[symbol] = {
                            "entry_time": now, "duration": duration,
                            "sl": current_price * 0.98, "tp": current_price * 1.05
                        }
                        save_metadata(trade_metadata)
                        notify(f"⚡ BUY: {symbol}\nReason: {status}\nSL: {trade_metadata[symbol]['sl']:.2f}")
            except Exception as e:
                logging.error(f"SCAN_ERR: {symbol} - {e}")
        time.sleep(60)

if __name__ == "__main__":
    run_bot()