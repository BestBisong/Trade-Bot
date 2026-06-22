import ccxt.async_support as ccxt
import asyncio
import time
import aiohttp
from data.market_data import format_ohlcv
from data.data_cleaner import clean

# Lazily initialized to support custom session and loop context
exchange = None
session = None

def get_exchange():
    global exchange, session
    if exchange is None:
        resolver = aiohttp.ThreadedResolver()
        connector = aiohttp.TCPConnector(resolver=resolver)
        session = aiohttp.ClientSession(connector=connector)
        exchange = ccxt.gate({
            "enableRateLimit": True,
            "session": session
        })
    return exchange

async def fetch(symbol, timeframe="5m", limit=100, retries=3):
    """Fetches and cleans market data asynchronously with retry logic."""
    ex = get_exchange()
    for attempt in range(retries):
        try:
            raw = await ex.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = format_ohlcv(raw)
            return clean(df)
        except ccxt.RateLimitExceeded:
            await asyncio.sleep(5)
        except Exception as e:
            import logging
            logging.error(f"FETCH_ERROR | Failed to fetch {symbol} ({timeframe}) on attempt {attempt + 1}: {e}")
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
    global exchange, session
    if exchange is not None:
        await exchange.close()
        exchange = None
    if session is not None:
        await session.close()
        session = None