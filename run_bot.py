import time, logging, datetime, json, os, threading
import uvicorn
import pandas as pd
from fastapi import FastAPI
import yfinance as yf
from data.data_fetcher import fetch
from signals.signal_generator import generate
from execution.broker import BitgetBroker
from risk.position_sizer import PositionSizer
from risk.risk_manager import RiskManager
from data.external_source import ExternalDataManager
from signals.telegram_notifier import notify
from config.settings import SYMBOLS, TIMEFRAME
from strategies.ml_strategy import MLStrategy

# Configuration for clean console output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')
METADATA_FILE = "active_trades.json"

# --- RENDER KEEP-AWAKE SERVER ---
app = FastAPI()

@app.get("/health")
def health_check():
    """Keeps the Render instance awake."""
    return {"status": "active", "timestamp": str(datetime.datetime.now())}

def start_health_server():
    """Runs the web server on the port assigned by Render."""
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

# --- METADATA MANAGEMENT ---
def save_metadata(data):
    """Saves active trade information to a local JSON file."""
    try:
        with open(METADATA_FILE, 'w') as f:
            serializable = {k: {**v, "entry_time": v["entry_time"].isoformat()} for k, v in data.items()}
            json.dump(serializable, f, indent=4)
    except Exception as e:
        logging.error(f"Metadata Save Error: {e}")

def load_metadata():
    """Loads active trade information and repairs corrupted JSON if necessary."""
    if os.path.exists(METADATA_FILE) and os.path.getsize(METADATA_FILE) > 0:
        try:
            with open(METADATA_FILE, 'r') as f:
                data = json.load(f)
                return {k: {**v, "entry_time": datetime.datetime.fromisoformat(v["entry_time"])} for k, v in data.items()}
        except json.JSONDecodeError:
            save_metadata({}) 
    return {}

# --- DATA AUGMENTATION WITH YFINANCE ---
def fetch_training_data_yfinance(symbols):
    """Fetches historical data from Yahoo Finance and standardizes for MLStrategy."""
    training_data = []
    for s in symbols:
        try:
            # IMPROVED: Ensure symbol always matches Yahoo Finance format (e.g., SOL-USD)
            clean_sym = s.replace("/USDT", "").replace("/", "-")
            if not clean_sym.endswith("-USD"):
                yf_sym = f"{clean_sym}-USD"
            else:
                yf_sym = clean_sym
                
            logging.info(f">>> Training: Fetching {yf_sym} from Yahoo Finance...")
            
            # Fetching 1 month of 5m history
            df = yf.download(yf_sym, period="1mo", interval="5m")
            
            if not df.empty:
                # Flatten MultiIndex columns (removes the 'SOL-USD' level from headers)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                
                # Convert column names to lowercase to match MLStrategy expectations
                df.columns = [col.lower() for col in df.columns]
                
                training_data.append(df)
            else:
                logging.warning(f"No data found for {yf_sym}. Check ticker format on Yahoo Finance.")
                
            time.sleep(1) # Polite delay to avoid IP blocks
        except Exception as e:
            logging.error(f"YFinance Error for {s}: {e}")
    return training_data

def run_bot():
    print(">>> Bot initializing High-Performance Day Trading Mode...")
    
    # Initialize Core Components
    broker = BitgetBroker(paper_mode=True)
    sizer = PositionSizer(risk_percent=2)
    risk_mgr = RiskManager(max_daily_loss=10)
    ml_agent = MLStrategy()
    ext_data = ExternalDataManager()
    
    trade_metadata = load_metadata()
    last_heartbeat = time.time()
    
    # 1. Training Phase: Using YFinance to bypass Bitget rate limits
    logging.info(">>> Gathering massive training dataset via YFinance...")
    training_data = fetch_training_data_yfinance(SYMBOLS)
    
    if training_data:
        ml_agent.train(training_data)
        notify("Bot Online: Training Complete via YFinance. Stock Scanning active.")
    else:
        logging.warning("No training data gathered. Proceeding with caution.")

    # 2. Live Trading Phase: Uses Bitget API
    while True:
        now = datetime.datetime.now()
        is_weekend = now.weekday() >= 5
        market_open = now.replace(hour=8, minute=0, second=0)
        market_close = now.replace(hour=18, minute=0, second=0)

        # 1. EXIT MANAGEMENT (Runs 24/7)
        for symbol in list(broker.tracker.open_positions.keys()):
            meta = trade_metadata.get(symbol)
            if not meta: continue
            
            curr_price = broker.price(symbol)
            side = meta.get("side", "BUY")
            
            # Directional exit logic for Long (BUY) and Short (SELL)
            if side == "BUY":
                hit_sl = curr_price <= meta["sl"]
                hit_tp = curr_price >= meta["tp"]
            else: # SELL/SHORT side
                hit_sl = curr_price >= meta["sl"]
                hit_tp = curr_price <= meta["tp"]

            time_elapsed = (now - meta["entry_time"]).total_seconds() / 60
            timeout = time_elapsed >= meta["duration"] # Enforces trade time window

            if hit_sl or hit_tp or timeout:
                reason = "TIMEOUT" if timeout else ("SL" if hit_sl else "TP")
                exit_side = "sell" if side == "BUY" else "buy"
                amount = broker.tracker.open_positions[symbol]['amount']
                
                broker.execute_order(symbol, exit_side, amount)
                trade_metadata.pop(symbol, None)
                save_metadata(trade_metadata)
                notify(f"🏁 EXIT {symbol} ({side}): {reason} at {curr_price:.2f}")

        # 2. TRADING WINDOW (Entries only)
        if is_weekend or not (market_open <= now <= market_close):
            if time.time() - last_heartbeat > 300:
                logging.info("Market Closed. Monitoring exits only.")
                last_heartbeat = time.time()
            time.sleep(60)
            continue

        # 3. SCAN FOR NEW TRADES
        for symbol in SYMBOLS:
            if symbol in broker.tracker.open_positions: continue
            try:
                sentiment = ext_data.get_market_sentiment(symbol)
                stock_context = ext_data.get_stock_context("^IXIC")

                # Live data from Bitget
                df = fetch(symbol, timeframe=TIMEFRAME, limit=200)
                if df is None or df.empty:
                    continue

                signal, status, window = generate(df, ml_agent, sentiment, stock_context)
                
                if signal in ["BUY", "SELL"] and risk_mgr.allowed():
                    current_price = broker.price(symbol)
                    amount = sizer.size(broker.balance("USDT"), current_price)
                    
                    if amount > 0:
                        broker.execute_order(symbol, signal.lower(), amount)
                        trade_metadata[symbol] = {
                            "side": signal,
                            "entry_time": now,
                            "duration": window, # Uses the time window from the generator
                            "sl": current_price * 0.98 if signal == "BUY" else current_price * 1.02,
                            "tp": current_price * 1.05 if signal == "BUY" else current_price * 0.95
                        }
                        save_metadata(trade_metadata)
                        notify(f"🚀 {signal}: {symbol}\nWindow: {window}m")
            except Exception as e:
                logging.error(f"SCAN_ERR: {symbol} - {e}")
        
        time.sleep(60)

if __name__ == "__main__":
    # Start the Health Server in a background thread for Render uptime
    threading.Thread(target=start_health_server, daemon=True).start()
    
    # Launch the primary trading loop
    run_bot()