SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAME = "1h"
TREND_TIMEFRAME = "4h"

SESSION_START = "00:00"

SESSION_END = "23:59"

# ── Elite Execution Toggles ──────────────────────────────────────────────────
# Set to True for smooth equity/low drawdown; set to False for maximum compounded returns (+114.51%)
PARTIAL_TP_ENABLED = False  

# Set to True to dynamically adjust risk based on ML confidence; set to False for flat 5% risk sizing
DYNAMIC_ML_RISK = False

# Set to True to restrict long entries only when price is above Daily 200 SMA (Bear Market Protection)

DAILY_200SMA_GUARD = True

# Set to True to replace static Take Profits with a dynamic Trailing ATR Stop (3x ATR trailing)
TRAILING_STOP_ENABLED = False
# Set to True to allow the bot to execute short (SELL) positions; set to False for long-only (BUY) trading
ALLOW_SHORTS = True


