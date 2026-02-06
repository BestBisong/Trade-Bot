import ccxt
from data.market_data import format_ohlcv
from data.data_cleaner import clean

exchange = ccxt.bitget({"enableRateLimit": True})

def fetch(symbol, timeframe="5m", limit=100):
    try:
        
        raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = format_ohlcv(raw)
        return clean(df)
    except Exception as e:
        print(f"Bitget Fetch Error: {e}")
        return None