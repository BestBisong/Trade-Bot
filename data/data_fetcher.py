import ccxt.async_support as ccxt
import asyncio
import time
from data.market_data import format_ohlcv
from data.data_cleaner import clean

# Kraken for data (US-friendly, no geo-blocking for public endpoints)
exchange = ccxt.kraken({"enableRateLimit": True})

async def fetch(symbol, timeframe="5m", limit=100, retries=3):
    """Fetches and cleans market data asynchronously with retry logic."""
    for attempt in range(retries):
        try:
            raw = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = format_ohlcv(raw)
            return clean(df)
        except ccxt.RateLimitExceeded:
            await asyncio.sleep(5)
        except Exception as e:
            await asyncio.sleep(2)
            
    return None

async def fetch_confluence(symbol, base_tf="5m", trend_tf="1h"):
    """Parallel fetch of entry and trend data."""
    results = await asyncio.gather(
        fetch(symbol, base_tf, limit=100),
        fetch(symbol, trend_tf, limit=100)
    )
    return results[0], results[1]

async def close_exchange():
    """Properly close the async exchange connection."""
    await exchange.close()