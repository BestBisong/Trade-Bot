import yfinance as yf
import logging
import os
import requests
from dotenv import load_dotenv
from cryptopanic import CryptoPanicClient

load_dotenv()

class ExternalDataManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cp_token = os.getenv("CRYPTOPANIC_API_KEY")
        self.news_key = os.getenv("NEWS_API_KEY")
        
        # Initialize CryptoPanic Client if token exists
        self.cp_client = CryptoPanicClient(auth_token=self.cp_token) if self.cp_token else None

    def get_market_sentiment(self, symbol="BTC"):
        """
        Calculates a real-time sentiment score (0.0 to 1.0) using CryptoPanic.
        """
        if not self.cp_client:
            return 0.5

        try:
            coin = symbol.split('/')[0] if '/' in symbol else symbol
            posts = self.cp_client.get_posts(currencies=[coin], filter="hot")
            
            if not posts or 'results' not in posts or len(posts['results']) == 0:
                return 0.5

            total_pos = sum(p.get('votes', {}).get('positive', 0) for p in posts['results'])
            total_neg = sum(p.get('votes', {}).get('negative', 0) for p in posts['results'])
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
            response = requests.get(url).json()
            headlines = [a['title'].lower() for a in response.get('articles', [])[:10]]
            neg_words = ['crash', 'drop', 'bear', 'plummet', 'hack']
            neg_count = sum(1 for h in headlines if any(word in h for word in neg_words))
            return -0.1 * neg_count 
        except:
            return 0.0

    def get_stock_context(self, ticker="^IXIC"):
        """
        Identifies if NASDAQ is leading a move. Returns pct change from open.
        """
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d", interval="5m")
            if not hist.empty:
                return round((hist['Close'].iloc[-1] - hist['Open'].iloc[0]) / hist['Open'].iloc[0], 4)
            return 0.0
        except Exception:
            return 0.0