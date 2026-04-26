import ccxt
import time
from data.market_data import format_ohlcv
from data.data_cleaner import clean

# Binance has significantly higher public rate limits compared to Bitget
exchange = ccxt.binance({"enableRateLimit": True})

def fetch(symbol, timeframe="5m", limit=100, retries=3):
    """Fetches and cleans market data for specified timeframes with retry logic."""
    for attempt in range(retries):
        try:
            raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = format_ohlcv(raw)
            return clean(df)
        except ccxt.RateLimitExceeded:
            print(f"Rate limit exceeded (attempt {attempt+1}/{retries}). Retrying in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f"Binance Fetch Error on {symbol}: {e}")
            time.sleep(2)
            
    print(f"Failed to fetch {symbol} after {retries} retries.")
    return None

def fetch_confluence(symbol, base_tf="5m", trend_tf="1h"):
    """Jarvis Vision: Gets both entry data and big-picture trend data."""
    base_df = fetch(symbol, base_tf, limit=100)
    if base_df is None:
        return None, None
    trend_df = fetch(symbol, trend_tf, limit=50)
    return base_df, trend_df