#!/bin/bash

# Start the live trading bot in the background
echo "[INFO] Starting JARVIS Live Trading Bot in background..."
python run_bot.py &

# Start the FastAPI server in the foreground
echo "[INFO] Starting JARVIS FastAPI Backend on port 8000..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
