# --- UPDATED BROKER_CONFIG.PY ---
BROKER = "bybit"

BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

BYBIT = {
    "name": "bybit",
    "market": "spot", 
    "base_asset": "USDT"
}