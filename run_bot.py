import time, logging, datetime, json, os
from data.data_fetcher import fetch
from signals.signal_generator import generate
from execution.broker import BitgetBroker
from risk.position_sizer import PositionSizer
from risk.risk_manager import RiskManager
from data.external_source import ExternalDataManager
from signals.telegram_notifier import notify
from config.settings import SYMBOLS, TIMEFRAME
from strategies.ml_strategy import MLStrategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')
METADATA_FILE = "active_trades.json"

def save_metadata(data):
    with open(METADATA_FILE, 'w') as f:
        serializable = {k: {**v, "entry_time": v["entry_time"].isoformat()} for k, v in data.items()}
        json.dump(serializable, f, indent=4)

def load_metadata():
    if os.path.exists(METADATA_FILE) and os.path.getsize(METADATA_FILE) > 0:
        try:
            with open(METADATA_FILE, 'r') as f:
                data = json.load(f)
                return {k: {**v, "entry_time": datetime.datetime.fromisoformat(v["entry_time"])} for k, v in data.items()}
        except json.JSONDecodeError:
            print(">>> Repairing corrupted active_trades.json...")
    return {}

def run_bot():
    print(">>> Bot initializing High-Performance Day Trading Mode...")
    broker = BitgetBroker(paper_mode=True)
    sizer = PositionSizer(risk_percent=2)
    risk_mgr = RiskManager(max_daily_loss=10)
    ml_agent = MLStrategy()
    ext_data = ExternalDataManager()
    
    trade_metadata = load_metadata()
    last_heartbeat = time.time()
    
    # Train ML with deep 2000 candle history
    ml_agent.train([fetch(s, limit=2000) for s in SYMBOLS])
    notify("Bot Online: Session Started. Scanning active.")

    while True:
        now = datetime.datetime.now()
        
        # HEARTBEAT LOGGER
        # Prints to console every 60 seconds so you know it's not "stuck"
        if time.time() - last_heartbeat > 60:
            logging.info(f"HEARTBEAT | Scanning {len(SYMBOLS)} symbols | Trades Active: {len(broker.tracker.open_positions)}")
            last_heartbeat = time.time()

        # 1. Day Trading Time Window (08:00 to 18:00)
        market_open = now.replace(hour=8, minute=0, second=0)
        market_close = now.replace(hour=18, minute=0, second=0)

        # 2. MANAGE EXITS (TP, SL, or Exhaustion)
        for symbol in list(broker.tracker.open_positions.keys()):
            meta = trade_metadata.get(symbol)
            if not meta: continue
            
            current_price = broker.price(symbol)
            time_elapsed = (now - meta["entry_time"]).total_seconds() / 60
            is_exhausted = time_elapsed >= meta["duration"]

            if current_price <= meta["sl"] or current_price >= meta["tp"] or is_exhausted:
                reason = "TIMEOUT" if is_exhausted else "TP/SL"
                amount = broker.tracker.open_positions[symbol]['amount']
                broker.execute_order(symbol, "sell", amount)
                trade_metadata.pop(symbol, None)
                save_metadata(trade_metadata)
                notify(f"🏁 EXIT {symbol}: {reason} at {current_price:.4f}")

        if not (market_open <= now <= market_close):
            if now.hour == 18 and now.minute < 5:
                logging.info("🌙 Market Closed. Entering standby mode.")
            time.sleep(300)
            continue

        # 3. SCAN FOR NEW OPPORTUNITIES
        for symbol in SYMBOLS:
            if symbol in broker.tracker.open_positions: continue
            try:
                sentiment = ext_data.get_market_sentiment(symbol)
                stock_context = ext_data.get_stock_context("^IXIC")

                df = fetch(symbol, timeframe=TIMEFRAME, limit=200)
                signal, status, window = generate(df, ml_agent, sentiment, stock_context)
                current_price = broker.price(symbol)

                if signal == "BUY" and risk_mgr.allowed():
                    amount = sizer.size(broker.balance("USDT"), current_price)
                    if amount > 0:
                        broker.execute_order(symbol, "buy", amount)
                        trade_metadata[symbol] = {
                            "entry_time": now,
                            "duration": window, 
                            "sl": current_price * 0.98,
                            "tp": current_price * 1.05
                        }
                        save_metadata(trade_metadata)
                        notify(f"⚡ BUY: {symbol}\nWindow: {window}m\nConfidence Score: {sentiment:.2f}")
            except Exception as e:
                logging.error(f"SCAN_ERR: {symbol} - {e}")
        
        time.sleep(60)

if __name__ == "__main__":
    run_bot()