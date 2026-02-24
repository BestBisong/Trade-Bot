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

# Global variables for Sentiment Caching (To respect 100 req/mo limit)
last_sentiment_check = 0
cached_sentiment = 0.5

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

def fetch_training_data_yfinance(symbols):
    """Fetches historical data from Yahoo Finance and standardizes for MLStrategy."""
    training_data = []
    for s in symbols:
        try:
            clean_sym = s.replace("/USDT", "").replace("/", "-")
            yf_sym = f"{clean_sym}-USD" if not clean_sym.endswith("-USD") else clean_sym
            
            logging.info(f">>> Training: Fetching {yf_sym} from Yahoo Finance...")
            
            # Request 7-day window as requested
            df = yf.download(yf_sym, period="7d", interval="5m", progress=False)
            
            # FIX: Check if df is None OR empty before subscripting
            if df is None or df.empty:
                logging.warning(f"Yahoo returned no data for {yf_sym}. Attempting 15m fallback...")
                # Fallback to 15m interval which is often more stable
                df = yf.download(yf_sym, period="7d", interval="15m", progress=False)
                
            # Final check before processing columns
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                
                df.columns = [col.lower() for col in df.columns]
                training_data.append(df)
            else:
                logging.error(f"FATAL: Could not fetch any data for {yf_sym}. Skipping.")
                
            time.sleep(2.0) # Increased delay to prevent rate-limiting on BTC
        except Exception as e:
            logging.error(f"YFinance Error for {s}: {e}")
    return training_data

def run_bot():
    global last_sentiment_check, cached_sentiment
    print(">>> Bot initializing High-Performance Day Trading Mode...")
    
    # Initialize Core Components
    broker = BitgetBroker(paper_mode=True)
    sizer = PositionSizer(risk_percent=2)
    risk_mgr = RiskManager(max_daily_loss=10)
    ml_agent = MLStrategy()
    ext_data = ExternalDataManager()
    
    trade_metadata = load_metadata()
    last_heartbeat = time.time()
    
    # 1. Training Phase
    logging.info(">>> Gathering massive training dataset via YFinance...")
    training_data = fetch_training_data_yfinance(SYMBOLS)
    
    if training_data:
        ml_agent.train(training_data)
        notify("Bot Online: Training Complete via YFinance. Stock Scanning active.")
    else:
        logging.warning("No training data gathered. Proceeding with caution.")

    # 2. Live Trading Phase
    while True:
        now = datetime.datetime.now()
        market_open = now.replace(hour=8, minute=0, second=0)
        market_close = now.replace(hour=18, minute=0, second=0)

        # 1. EXIT MANAGEMENT (Runs 24/7)
        for symbol in list(broker.tracker.open_positions.keys()):
            meta = trade_metadata.get(symbol)
            if not meta: continue
            
            curr_price = broker.price(symbol)
            side = meta.get("side", "BUY")
            
            if side == "BUY":
                hit_sl = curr_price <= meta["sl"]
                hit_tp = curr_price >= meta["tp"]
            else:
                hit_sl = curr_price >= meta["sl"]
                hit_tp = curr_price <= meta["tp"]

            time_elapsed = (now - meta["entry_time"]).total_seconds() / 60
            timeout = time_elapsed >= meta["duration"] 

            if hit_sl or hit_tp or timeout:
                reason = "TIMEOUT" if timeout else ("SL" if hit_sl else "TP")
                exit_side = "sell" if side == "BUY" else "buy"
                amount = broker.tracker.open_positions[symbol]['amount']
                
                broker.execute_order(symbol, exit_side, amount)
                trade_metadata.pop(symbol, None)
                save_metadata(trade_metadata)
                notify(f"🏁 EXIT {symbol} ({side}): {reason} at {curr_price:.2f}")

        # 2. TRADING WINDOW (Entries only) - Allows Weekend Scanning
        if not (market_open <= now <= market_close):
            if time.time() - last_heartbeat > 300:
                logging.info("Market Closed (Time Window). Monitoring exits only.")
                last_heartbeat = time.time()
            time.sleep(60)
            continue

        # 3. SCAN FOR NEW TRADES
        for symbol in SYMBOLS:
            if symbol in broker.tracker.open_positions: continue
            try:
                # REVISED SENTIMENT LOGIC: Check once per hour to stay within 100 req/mo limit
                current_time = time.time()
                if current_time - last_sentiment_check > 3600:
                    sentiment = ext_data.get_market_sentiment(symbol)
                    cached_sentiment = sentiment
                    last_sentiment_check = current_time
                    logging.info(f"Sentiment Updated: {sentiment} for {symbol}")
                else:
                    sentiment = cached_sentiment

                stock_context = ext_data.get_stock_context("^IXIC")

                # Fetch 500 candles to provide enough warm-up for ML Strategy
                df = fetch(symbol, timeframe=TIMEFRAME, limit=500)
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
                            "duration": window, 
                            "sl": current_price * 0.98 if signal == "BUY" else current_price * 1.02,
                            "tp": current_price * 1.05 if signal == "BUY" else current_price * 0.95
                        }
                        save_metadata(trade_metadata)
                        notify(f"🚀 {signal}: {symbol}\nWindow: {window}m")
                
                if time.time() - last_heartbeat > 600:
                    logging.info(f"Scanning active: {symbol} at {broker.price(symbol)}")
                    last_heartbeat = time.time()

            except Exception as e:
                logging.error(f"SCAN_ERR: {symbol} - {e}")
        
        time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=start_health_server, daemon=True).start()
    run_bot()