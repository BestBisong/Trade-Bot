# J.A.R.V.I.S // Cloud & VPS Deployment Master Blueprint

This guide details how to deploy, secure, and monitor the J.A.R.V.I.S quantitative engine and Next.js console 24/7/365 on cloud infrastructure.

---

## 🏗️ 1. Infrastructure Architecture

The system runs three core processes:
1. **Live Quant Bot Scanner:** The background process pulling candle data, calculating signals, and placing Bybit API trades.
2. **FastAPI Backend REST API (Port 8000):** Serves bot state telemetry, database reads, and active trades.
3. **Next.js Web console (Port 3000):** Visualizes the metrics and live logs.

### Recommended Providers:
* **AWS EC2:** Launch a **`t3.micro`** or `t2.micro` instance running **Ubuntu 24.04 LTS** (Free Tier Eligible).
* **AWS Lightsail:** Launch a flat-rate **$5/month** Ubuntu instance.
* **Budget VPS (Ionos, RackNerd):** 1 vCPU, 1GB RAM Ubuntu instances (~$1 - $5/month).

---

## 🔒 2. Firewall and Security Settings

Before deploying, configure your server's security group or firewall settings with the following inbound rules:

| Protocol / Type | Port Range | Source | Purpose |
| :--- | :--- | :--- | :--- |
| **SSH** | `22` | My IP / All | Secure shell terminal connection |
| **HTTP** | `80` | `0.0.0.0/0` | Web console access (HTTP) |
| **HTTPS** | `443` | `0.0.0.0/0` | Secure SSL Web console access (HTTPS) |

*(Note: Keep ports 3000 and 8000 closed to the public if using Nginx reverse proxy to prevent direct API attacks).*

---

## 📦 3. Method A: Docker Compose Deployment (Recommended)

Docker Compose encapsulates Node.js, Python, and environments into isolated containers.

### 1. Install Docker & Docker Compose:
```bash
sudo apt update && sudo apt install -y docker.io
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
sudo usermod -aG docker ubuntu  # Use 'root' instead of 'ubuntu' on raw VPS
newgrp docker
```

### 2. Prepare files and `.env`:
```bash
# Clone code
git clone https://github.com/BestBisong/Trade-Bot.git
cd Trade-Bot

# Initialize state database files on host so Docker mounts them cleanly
touch bot_state.json active_trades.json scan_heartbeat.json trade_history.json
mkdir -p logs && touch logs/bot.log

# Configure API keys and settings
nano .env
```

### 3. Deploy:
```bash
docker-compose up --build -d
```
The console is now live on `http://YOUR_VPS_IP:3000` and API on `http://YOUR_VPS_IP:8000`.

---

## ⚙️ 4. Method B: Bare-Metal Deployment (systemd & PM2)

For low-spec servers (e.g. 512MB RAM), bare-metal avoids container virtualization overhead.

### 1. Install Runtimes:
```bash
# Install Python & Nginx
sudo apt install -y python3-pip python3-venv git nginx

# Install Node.js & Process Manager (PM2)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install pm2 -g
```

### 2. Configure System Services:

**API Service File (`/etc/systemd/system/jarvis-api.service`):**
```ini
[Unit]
Description=JARVIS FastAPI Backend
After=network.target

[Service]
User=root
WorkingDirectory=/root/Trade-Bot
ExecStart=/root/Trade-Bot/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Quant Bot Service File (`/etc/systemd/system/jarvis-bot.service`):**
```ini
[Unit]
Description=JARVIS Live Trading Bot
After=network.target

[Service]
User=root
WorkingDirectory=/root/Trade-Bot
ExecStart=/root/Trade-Bot/venv/bin/python run_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Launch Services:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable jarvis-api jarvis-bot
sudo systemctl start jarvis-api jarvis-bot
```

### 3. Build & PM2 Start Frontend:
```bash
cd /root/Trade-Bot/frontend
npm install
npm run build
pm2 start npm --name "jarvis-frontend" -- start
pm2 save
pm2 startup
```

---

## 🔏 5. Nginx Reverse Proxy & Let's Encrypt SSL Configuration

To route web traffic securely through standard HTTP/HTTPS ports:

### 1. Create Nginx Configuration (`/etc/nginx/sites-available/jarvis`):
```nginx
server {
    listen 80;
    server_name yourdomain.com; # Replace with your domain or IP

    # Next.js UI Frontend
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # FastAPI REST Backend routing
    location /api {
        proxy_pass http://127.0.0.1:8000/api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### 2. Enable & Restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/jarvis /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### 3. Obtain Free Let's Encrypt SSL:
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

---

## 📱 6. Secure Remote Telemetry to Your Phone

### Option A: ngrok Tunneling (Quick & Easy)
Exposes the local web port securely with no VPS firewall modification:
```bash
# Authenticate ngrok
ngrok config add-authtoken <your-auth-token>

# Tunnel Next.js frontend port
ngrok http 3000
```
Simply copy the output `https://xxxx.ngrok-free.app` URL to your phone's browser.

### Option B: Tailscale Mesh VPN (Private & Fully Secured)
If you want to prevent anyone else from seeing your console:
```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```
Enable the Tailscale app on your phone and open `http://<vps-tailscale-ip>:3000` directly.
