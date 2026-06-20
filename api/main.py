import os
import json
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Quant Bot API")

# Enable CORS for the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SettingsModel(BaseModel):
    auto_trading_enabled: bool
    partial_tp_enabled: bool
    dynamic_ml_risk: bool
    daily_200sma_guard: bool
    trailing_stop_enabled: bool
    allow_shorts: bool
    risk_per_trade: float
    max_notional_per_trade: float
    symbols: List[str]
    trend_guard_enabled: bool

class ManualTradeModel(BaseModel):
    symbol: str
    side: str
    qty: float
    entry_price: Optional[float] = None
    sl: float
    tp: float

class CloseTradeModel(BaseModel):
    symbol: str

def safe_read(file_path, default):
    if not os.path.exists(file_path):
        return default
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
            return json.loads(content) if content else default
    except Exception:
        return default

def append_command(command: dict):
    commands = safe_read("bot_commands.json", [])
    commands.append(command)
    try:
        with open("bot_commands.json", "w") as f:
            json.dump(commands, f, default=str)
    except Exception as e:
        print(f"Failed to write command: {e}")

@app.get("/api/state")
def get_state():
    state = safe_read("bot_state.json", {"wallet": 100.0, "active_trades": 0, "prices": {}})
    heartbeat = safe_read("scan_heartbeat.json", {})
    settings = safe_read("settings_config.json", {
        "auto_trading_enabled": True,
        "partial_tp_enabled": False,
        "dynamic_ml_risk": False,
        "daily_200sma_guard": True,
        "trailing_stop_enabled": False,
        "allow_shorts": True,
        "risk_per_trade": 0.035,
        "max_notional_per_trade": 3.0,
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "trend_guard_enabled": True
    })
    diagnostics = safe_read("scan_diagnostics.json", {})
    return {
        "wallet": state.get("wallet", 100.0),
        "timestamp": state.get("timestamp"),
        "risk": state.get("risk", {}),
        "heartbeats": heartbeat,
        "prices": state.get("prices", {}),
        "settings": settings,
        "diagnostics": diagnostics
    }

@app.get("/api/trades")
def get_trades():
    trades = safe_read("active_trades.json", [])
    return [t for t in trades if t.get("symbol") in ["BTC/USDT", "ETH/USDT"]]

@app.get("/api/history")
def get_history():
    history = safe_read("trade_history.json", [])
    return [h for h in history if h.get("symbol") in ["BTC/USDT", "ETH/USDT"]]

@app.get("/api/settings")
def get_settings():
    return safe_read("settings_config.json", {
        "auto_trading_enabled": True,
        "partial_tp_enabled": False,
        "dynamic_ml_risk": False,
        "daily_200sma_guard": True,
        "trailing_stop_enabled": False,
        "allow_shorts": True,
        "risk_per_trade": 0.035,
        "max_notional_per_trade": 3.0,
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "trend_guard_enabled": True
    })

@app.post("/api/settings")
def update_settings(settings: SettingsModel):
    try:
        with open("settings_config.json", "w") as f:
            json.dump(settings.dict(), f, default=str)
        return {"status": "success", "settings": settings}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/trade")
def place_manual_trade(trade: ManualTradeModel):
    cmd = {
        "type": "open_trade",
        "symbol": trade.symbol,
        "side": trade.side,
        "qty": trade.qty,
        "entry_price": trade.entry_price,
        "sl": trade.sl,
        "tp": trade.tp,
        "timestamp": datetime.now().isoformat()
    }
    append_command(cmd)
    
    # Also log command in terminal logs for instant user feedback
    log_file = "logs/bot.log"
    os.makedirs("logs", exist_ok=True)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S')} - SYSTEM | Manual order queue request: {trade.side.upper()} {trade.symbol} Qty: {trade.qty} | SL: {trade.sl} | TP: {trade.tp}\n")
    except Exception:
        pass
        
    return {"status": "success", "message": f"Command sent to open {trade.side} on {trade.symbol}"}

@app.post("/api/close")
def close_trade(trade: CloseTradeModel):
    cmd = {
        "type": "close_trade",
        "symbol": trade.symbol,
        "timestamp": datetime.now().isoformat()
    }
    append_command(cmd)
    
    log_file = "logs/bot.log"
    os.makedirs("logs", exist_ok=True)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S')} - SYSTEM | Manual close queue request: {trade.symbol}\n")
    except Exception:
        pass
        
    return {"status": "success", "message": f"Command sent to close position on {trade.symbol}"}

@app.post("/api/clear-history")
def clear_history():
    try:
        with open("trade_history.json", "w") as f:
            json.dump([], f)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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
                
            if len(events) >= 20:
                break
                
        return events
    except Exception as e:
        return [{"time": "ERROR", "message": f"Failed to read live logs: {str(e)}"}]
