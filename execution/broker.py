import logging
import ccxt.async_support as ccxt
import os
from datetime import datetime, timedelta
from config.settings import SESSION_START, SESSION_END

class BybitBroker:
    def __init__(self, paper_mode=True):
        self.paper_mode = paper_mode
        self.session_file = "session_state.json"
        
        # Initialize Exchange Connection
        self.exchange = ccxt.bybit({
            'apiKey': os.getenv("BYBIT_API_KEY"),
            'secret': os.getenv("BYBIT_API_SECRET"),
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'} 
        })
        
        if self.paper_mode:
            logging.info("BROKER | Bybit Paper Mode Active. Using Binance for public price data feed.")
            self.public_exchange = ccxt.binance({'enableRateLimit': True})
        else:
            self.public_exchange = None

    async def close(self):
        await self.exchange.close()
        if self.public_exchange:
            await self.public_exchange.close()

    def is_window_active(self):
        """Checks if current time is within session window."""
        now = datetime.now().time()
        try:
            start_time = datetime.strptime(SESSION_START, "%H:%M").time()
            end_time = datetime.strptime(SESSION_END, "%H:%M").time()
            return start_time <= now <= end_time
        except Exception as e:
            logging.error(f"BROKER | Time window error: {e}")
            return False

    def can_open_new_trades(self):
        """Checks if outside the end-of-session buffer."""
        now = datetime.now().time()
        try:
            end_time = datetime.strptime(SESSION_END, "%H:%M").time()
            cutoff = (datetime.combine(datetime.today(), end_time) - timedelta(minutes=15)).time()
            return self.is_window_active() and now <= cutoff
        except Exception:
            return False

    async def price(self, symbol):
        """Fetches the latest tick price asynchronously."""
        try:
            if self.public_exchange:
                ticker = await self.public_exchange.fetch_ticker(symbol)
            else:
                ticker = await self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logging.error(f"BROKER | Price Fetch Error for {symbol}: {e}")
            return None

    async def place_order(self, symbol, side, qty, price=None, params=None):
        """
        Executes a trade on Bybit.
        In paper_mode (virtual wallet), this just logs and returns success.
        In live mode, it hits the Bybit API.
        """
        if self.paper_mode:
            logging.info(f"VIRTUAL_ORDER | {side.upper()} {qty} {symbol} @ {price}")
            return {"id": "virtual_id_" + str(datetime.now().timestamp()), "status": "closed"}

        try:
            order_type = 'limit' if price else 'market'
            order = await self.exchange.create_order(symbol, order_type, side, qty, price, params)
            return order
        except Exception as e:
            logging.error(f"BROKER | Order Placement Error: {e}")
            return None

    async def cancel_order(self, order_id, symbol):
        if self.paper_mode: return True
        try:
            return await self.exchange.cancel_order(order_id, symbol)
        except Exception:
            return False