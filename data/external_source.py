import yfinance as yf
import logging
import os
import requests
from dotenv import load_dotenv

load_dotenv()

class ExternalDataManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cp_token = os.getenv("CRYPTOPANIC_API_KEY")
        self.news_key = os.getenv("NEWS_API_KEY")

    def get_market_sentiment(self, symbol="BTC"):
        """
        Calculates sentiment by calling the CryptoPanic API directly.
        Uses 'params' to avoid 404 errors caused by improper URL construction.
        """
        if not self.cp_token:
            return 0.5

        try:
            # Ensure the ticker is uppercase (e.g., BTC)
            coin = symbol.split('/')[0].upper() if '/' in symbol else symbol.upper()
            
            # API endpoint base (without trailing query string to avoid 404)
            url = "https://cryptopanic.com/api/v1/posts/"
            
            # Using params handles URL encoding correctly for the Basic plan
            params = {
                "auth_token": self.cp_token,
                "currencies": coin,
                "filter": "hot"
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            # Check for success before parsing JSON to prevent crashes
            if response.status_code != 200:
                self.logger.error(f"CryptoPanic API Error: Status {response.status_code} for {coin}")
                return 0.5
                
            data = response.json()
            posts = data.get('results', [])
            
            if not posts:
                return 0.5

            total_pos = sum(p.get('votes', {}).get('positive', 0) for p in posts)
            total_neg = sum(p.get('votes', {}).get('negative', 0) for p in posts)
            total_votes = total_pos + total_neg

            return round(total_pos / total_votes, 2) if total_votes > 0 else 0.5
        except Exception as e:
            self.logger.error(f"Sentiment Error: {e}")
            return 0.5

    def get_financial_news_impact(self):
        """
        Uses NewsAPI to check for global 'Market Crash' keywords.
        """
        if not self.news_key:
            return 0.0

        try:
            url = f"https://newsapi.org/v2/everything?q=market+crash&sortBy=relevancy&apiKey={self.news_key}"
            response = requests.get(url)
            
            if response.status_code != 200:
                return 0.0
                
            data = response.json()
            headlines = [a['title'].lower() for a in data.get('articles', [])[:10]]
            neg_words = ['crash', 'drop', 'bear', 'plummet', 'hack']
            neg_count = sum(1 for h in headlines if any(word in h for word in neg_words))
            return -0.1 * neg_count 
        except:
            return 0.0

    def get_stock_context(self, ticker="^IXIC"):
        """
        Identifies if NASDAQ is leading a move. Returns pct change from open.
        Uses 60d period internally to avoid 'NoneType' errors on specific tickers.
        """
        try:
            stock = yf.Ticker(ticker)
            # Use max intraday period (60d) to ensure data availability
            hist = stock.history(period="60d", interval="5m")
            if hist is not None and not hist.empty:
                # Calculate change from today's open to current price
                return round((hist['Close'].iloc[-1] - hist['Open'].iloc[-1]) / hist['Open'].iloc[-1], 4)
            return 0.0
        except Exception:
            return 0.0