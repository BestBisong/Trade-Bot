import logging
from datetime import datetime, timedelta

class MarketKillSwitch:
    def __init__(self, drop_threshold=2.0, window_minutes=5):
        self.drop_threshold = drop_threshold
        self.window_minutes = window_minutes
        self.price_history = [] 
        self.is_active = False
        self.last_crash_time = None

    def check_crash(self, current_btc_price):
        now = datetime.now()
        self.price_history.append((now, current_btc_price))
        
        #
        cutoff = now - timedelta(minutes=self.window_minutes)
        self.price_history = [p for p in self.price_history if p[0] >= cutoff]

        if len(self.price_history) < 2:
            return False

        
        max_price = max(p[1] for p in self.price_history)
        drop_pct = ((max_price - current_btc_price) / max_price) * 100

        if drop_pct >= self.drop_threshold:
            logging.error(f" MARKET CRASH DETECTED: BTC dropped {drop_pct:.2f}% in {self.window_minutes} mins.")
            self.is_active = True
            self.last_crash_time = now
            return True
            
        
        if self.is_active and (now - self.last_crash_time > timedelta(hours=1)):
            logging.info("RECOVERY: Market stabilized. Resuming bot operations.")
            self.is_active = False
            self.price_history = [] 

        return self.is_active