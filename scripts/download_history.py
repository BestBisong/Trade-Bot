import os
import sys

# Ensure root directory is in import search path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

import time
import datetime
import logging
import pandas as pd
import ccxt

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(message)s", datefmt="%H:%M:%S")

# Initialize Binance (highest historical limits and liquidity depth)
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
TIMEFRAME = "15m"
DATA_DIR = "data"

def download_historical_csv(symbol: str, timeframe: str, start_str: str) -> str:
    """
    Downloads historical OHLCV data using paginated CCXT requests and saves to CSV.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    file_path = os.path.join(DATA_DIR, f"{symbol.replace('/', '_')}_{timeframe}.csv")
    
    # Convert start date string to timestamp in ms
    start_dt = datetime.datetime.strptime(start_str, "%Y-%m-%d")
    since = int(start_dt.timestamp() * 1000)
    
    all_ohlcv = []
    limit = 1000  # Binance supports up to 1000 candles per fetch
    
    logging.info(f"Downloading {timeframe} history for {symbol} starting from {start_str}...")
    
    while True:
        try:
            # Fetch batch of candles
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            if not ohlcv:
                logging.info(f"Finished downloading {symbol}. No more data returned.")
                break
                
            all_ohlcv.extend(ohlcv)
            
            # The next request should start 1 ms after the last candle in this batch
            last_timestamp = ohlcv[-1][0]
            since = last_timestamp + 1
            
            # Print progress
            last_date = datetime.datetime.fromtimestamp(last_timestamp / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
            logging.info(f"  Fetched {len(ohlcv)} bars. Last candle date: {last_date}")
            
            # Escape route: If last date reaches current time, stop
            if last_timestamp >= int(time.time() * 1000) - (15 * 60 * 1000):
                logging.info(f"Reached current date for {symbol}.")
                break
                
            # Respect rate limit
            time.sleep(1.0)
            
        except ccxt.NetworkError as ne:
            logging.warning(f"Network error: {ne}. Retrying in 5 seconds...")
            time.sleep(5.0)
        except ccxt.RateLimitExceeded as rle:
            logging.warning(f"Rate limit exceeded: {rle}. Retrying in 10 seconds...")
            time.sleep(10.0)
        except Exception as e:
            logging.error(f"Error fetching data: {e}")
            break
            
    if not all_ohlcv:
        logging.error(f"No data fetched for {symbol}.")
        return ""
        
    # Format and save to DataFrame
    df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    
    # Save to CSV
    df.to_csv(file_path)
    logging.info(f"Successfully saved {len(df)} rows to {file_path}")
    return file_path

if __name__ == "__main__":
    # Binance launched in July 2017. Fetch starting from 2017-07-14 (earliest spot data)
    START_DATE = "2017-07-14"
    
    for symbol in SYMBOLS:
        try:
            download_historical_csv(symbol, TIMEFRAME, START_DATE)
        except Exception as e:
            logging.error(f"Failed download for {symbol}: {e}")
        time.sleep(2.0)
