import ccxt
import time
from data.market_data import format_ohlcv
from data.data_cleaner import clean

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

def fetch_historical(
    symbol: str,
    timeframe: str = "5m",
    since: int = None,
    limit: int = 1000
):
    """
    Fetch large historical OHLCV data for backtesting & ML.
    
    :param symbol: e.g. BTC/USDT
    :param timeframe: e.g. 5m, 1h
    :param since: timestamp in ms
    :param limit: candles per request
    :return: cleaned DataFrame
    """

    all_candles = []
    since_ts = since

    while True:
        candles = exchange.fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            since=since_ts,
            limit=limit
        )

        if not candles:
            break

        all_candles.extend(candles)
        since_ts = candles[-1][0] + 1

        
        time.sleep(exchange.rateLimit / 1000)

        
        if len(candles) < limit:
            break

    df = format_ohlcv(all_candles)
    return clean(df)