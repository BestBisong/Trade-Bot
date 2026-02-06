import os
from dotenv import load_dotenv

load_dotenv()

BROKER = "bitget" 


API_KEY = os.getenv("BITGET_API_KEY")
SECRET = os.getenv("BITGET_API_SECRET")
PASSWORD = os.getenv("BITGET_PASSWORD")

BITGET = {
    "name": "bitget",
    "market": "spot",
    "base_asset": "USDT"
}