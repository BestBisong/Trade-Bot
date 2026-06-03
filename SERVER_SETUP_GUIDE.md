# JARVIS Quant Bot — 1-Year Server Setup & Deployment Guide

To run your optimized bot for a full year stably and safely, you should host it on a **Virtual Private Server (VPS)**. 

Below is the complete, step-by-step deployment blueprint using the ultra-cheap **Ionos VPS XS ($1.00/month)** or **RackNerd ($10.88/year)** running **Ubuntu 24.04 LTS**.

---

## Step 1: Purchase the Server

1. Go to **Ionos** (Search *"Ionos VPS XS"*) or **RackNerd** (Search *"RackNerd cheap KVM VPS"*).
2. Choose their basic plan (**1 GB RAM / 1 vCPU / 10-15 GB SSD**).
3. Select **`Ubuntu 24.04 LTS`** (or `Ubuntu 22.04 LTS`) as the Operating System.
4. Complete checkout. You will receive an email with your **Server IP**, username (`root`), and **Password**.

---

## Step 2: Prepare Your Local Code for Upload

To ensure a fast, lightweight upload, you should **exclude** temporary local folders (like `venv` or `.next`).

We have prepared your workspace. You only need to copy these essential files to your server:
*   `api/` (FastAPI backend)
*   `config/` (Settings toggles)
*   `data/`, `execution/`, `risk/`, `signals/`, `strategies/` (Core quant logic)
*   `tests/` (Automated validation suite)
*   `run_bot.py`, `start_all.py` (Execution entries)
*   `requirements.txt` (Package list)
*   `tuned_params.json` (Optimized model parameters)

---

## Step 3: Connect and Configure Your Server

Open **PowerShell** or **Command Prompt** on your computer and connect to your new VPS:

```powershell
# 1. Connect via SSH (replace with your server's IP address)
ssh root@YOUR_SERVER_IP

# 2. Update the server packages
sudo apt update && sudo apt upgrade -y

# 3. Install Python, virtual environment, and git tools
sudo apt install -y python3-pip python3-venv git htop
```

---

## Step 4: Setup the Code and Environment

Once you upload your files to the server (you can use a free tool like **FileZilla** or **WinSCP** to drag-and-drop the files), run the following on the server:

```bash
# 1. Navigate to the uploaded folder
cd /root/trading_bot

# 2. Create and activate a clean Linux virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install all required libraries
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 5: Ensure 24/7/365 Uptime using `systemd`

Instead of running the bot in a terminal that can close, we will configure **Linux systemd services**. This ensures that if the server ever restarts (for updates or maintenance), **the bot and API will automatically reboot themselves instantly.**

### 1. Create the API & Telemetry Service
Run this command on the server to create the service file:
```bash
sudo nano /etc/systemd/system/jarvis-api.service
```
Paste this configuration inside:
```ini
[Unit]
Description=JARVIS FastAPI Backend
After=network.target

[Service]
User=root
WorkingDirectory=/root/trading_bot
ExecStart=/root/trading_bot/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
*(Press `Ctrl+O` then `Enter` to save, and `Ctrl+X` to exit nano)*.

### 2. Create the Trading Bot Service
Run this command on the server:
```bash
sudo nano /etc/systemd/system/jarvis-bot.service
```
Paste this configuration inside:
```ini
[Unit]
Description=JARVIS Live Trading Bot
After=network.target

[Service]
User=root
WorkingDirectory=/root/trading_bot
ExecStart=/root/trading_bot/venv/bin/python run_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
*(Press `Ctrl+O` then `Enter` to save, and `Ctrl+X` to exit nano)*.

---

## Step 6: Start and Enable the Services

Run these commands to tell the server to load the new services and run them permanently:

```bash
# Reload the system service registry
sudo systemctl daemon-reload

# Start the API and Bot services
sudo systemctl start jarvis-api
sudo systemctl start jarvis-bot

# Configure both services to start automatically on system reboot
sudo systemctl enable jarvis-api
sudo systemctl enable jarvis-bot
```

### 📊 How to Monitor Your Services:

```bash
# Check if the Live Bot is running cleanly:
sudo systemctl status jarvis-bot

# Watch the bot's live logs stream in real-time:
journalctl -u jarvis-bot -f
```

Your JARVIS engine is now fully secured, running 24/7/365 on an industrial Linux server for less than a dollar a month, completely immune to reboots or terminal disconnects!
