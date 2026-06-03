import os
import json
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Quant Bot API")

# Enable CORS for the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def safe_read(file_path, default):
    if not os.path.exists(file_path):
        return default
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
            return json.loads(content) if content else default
    except Exception:
        return default

@app.get("/api/state")
def get_state():
    state = safe_read("bot_state.json", {"wallet": 100.0, "active_trades": 0, "prices": {}})
    heartbeat = safe_read("scan_heartbeat.json", {})
    return {
        "wallet": state.get("wallet", 100.0),
        "timestamp": state.get("timestamp"),
        "risk": state.get("risk", {}),
        "heartbeats": heartbeat,
        "prices": state.get("prices", {})
    }

@app.get("/api/trades")
def get_trades():
    trades = safe_read("active_trades.json", [])
    return [t for t in trades if t.get("symbol") in ["BTC/USDT", "ETH/USDT"]]

@app.get("/api/history")
def get_history():
    history = safe_read("trade_history.json", [])
    return [h for h in history if h.get("symbol") in ["BTC/USDT", "ETH/USDT"]]


@app.get("/api/logs")
def get_logs():
    log_file = "logs/bot.log"
    if not os.path.exists(log_file):
        return [{"time": datetime.now().strftime("%H:%M:%S"), "message": "SYSTEM | Live bot log initialized. Waiting for scanner..."}]
        
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        events = []
        # Traverse from newest to oldest for immediate responsiveness
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            
            # Strict symbol filter to keep dashboard pure
            if any(pruned in line for pruned in ["SOL", "XRP"]):
                continue
                
            # Split standard format: HH:MM:SS - MESSAGE
            if " - " in line:
                t_part, msg_part = line.split(" - ", 1)
                events.append({"time": t_part, "message": msg_part})
            else:
                events.append({"time": datetime.now().strftime("%H:%M:%S"), "message": line})
                
            if len(events) >= 15:
                break
                
        return events
    except Exception as e:
        return [{"time": "ERROR", "message": f"Failed to read live logs: {str(e)}"}]


