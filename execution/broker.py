import logging
import ccxt
import os
import json
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
            logging.info("BROKER | Bybit Paper Mode Active.")

    def is_window_active(self):
        """
        JARVIS UPGRADE: Automated Time-Window Intelligence.
        Checks if the current time falls within the 3-hour Power Hour session.
        """
        now = datetime.now().time()
        
        try:
            # Parse session times from config
            start_time = datetime.strptime(SESSION_START, "%H:%M").time()
            end_time = datetime.strptime(SESSION_END, "%H:%M").time()
            
            # DISCIPLINE FILTER: Buffer Zone
            # We stop taking NEW trades 15 minutes before the session ends 
            # so we aren't trapped in a position when the bot shuts down.
            buffer_dt = datetime.combine(datetime.today(), end_time) - timedelta(minutes=15)
            new_trade_cutoff = buffer_dt.time()

            # Logic: We are active if between Start and End
            if start_time <= now <= end_time:
                return True
            
            return False
        except Exception as e:
            logging.error(f"BROKER | Time window error: {e}")
            return False

    def can_open_new_trades(self):
        """Returns True only when the session is active and outside cutoff buffer."""
        now = datetime.now().time()

        try:
            start_time = datetime.strptime(SESSION_START, "%H:%M").time()
            end_time = datetime.strptime(SESSION_END, "%H:%M").time()

            buffer_dt = datetime.combine(datetime.today(), end_time) - timedelta(minutes=15)
            new_trade_cutoff = buffer_dt.time()

            return start_time <= now <= new_trade_cutoff
        except Exception as e:
            logging.error(f"BROKER | New trade cutoff error: {e}")
            return False

    def get_session_status(self):
        """Returns a string status for the dashboard UI."""
        if self.is_window_active():
            now = datetime.now().time()
            end = datetime.strptime(SESSION_END, "%H:%M").time()
            rem = datetime.combine(datetime.today(), end) - datetime.combine(datetime.today(), now)
            return f"ACTIVE | Remaining: {str(rem).split('.')[0]}"
        return "INACTIVE | Awaiting Power Hour"

    def price(self, symbol):
        """Fetches the latest tick price with error handling."""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logging.error(f"BROKER | Price Fetch Error for {symbol}: {e}")
            return None

    def stop_session(self):
        """Emergency Manual Stop."""
        logging.warning("BROKER | Master Kill-Switch triggered by user.")
        # This can be used to override the automated timer if needed
        return False