# 🚀 JARVIS Quant Bot — AWS Deployment & Monitoring Guide

This guide details how to host, run, and monitor the **JARVIS Quant Bot** and its Next.js dashboard on **Amazon Web Services (AWS)** 24/7/365.

---

## 🏗️ Architecture Overview

The JARVIS system consists of three processes that need to run continuously:
1. **FastAPI Backend (Port 8000)**: Serves the REST API for system states, history, logs, and live trades.
2. **Next.js Web Frontend (Port 3000)**: The premium dark-mode dashboard showing portfolio metrics, chart telemetry, and active positions.
3. **Live Quant Bot Scanner (Background)**: Runs the live trading loop, fetches exchange data, evaluates model confidence, and executes trades.

For AWS hosting, you have two primary options:
* **AWS Lightsail (Recommended)**: Flat-rate VPS starting at $3.50 or $5.00/month. It has a simplified dashboard and firewall interface, making it perfect for independent developers.
* **AWS EC2 (Elastic Compute Cloud)**: Standard cloud server. The **`t3.micro`** (or `t2.micro`) instance is **Free Tier Eligible** (750 hours/month free for the first 12 months).

---

## 🔒 Step 1: Provision Server and Open Firewall Ports

### Option A: Using AWS EC2 (Free Tier Eligible)
1. Log in to the **AWS Management Console** and navigate to **EC2**.
2. Click **Launch Instance**.
3. **Name**: `JARVIS-Quant-Bot`
4. **OS Image**: Select **Ubuntu 24.04 LTS** (or Ubuntu 22.04 LTS).
5. **Instance Type**: Select **`t3.micro`** (or `t2.micro` depending on region availability) to stay on the Free Tier.
6. **Key Pair**: Create a new `.pem` key pair (e.g., `jarvis-key.pem`) and download it. Keep it secure!
7. **Network Settings (Security Group)**:
   * Create a security group.
   * Add the following **Inbound Rules**:
     
     | Type | Port Range | Source | Reason |
     | :--- | :--- | :--- | :--- |
     | **SSH** | `22` | My IP (or `0.0.0.0/0`) | Secure Terminal Access |
     | **HTTP** | `80` | `0.0.0.0/0` | Web Interface access (via Nginx proxy) |
     | **HTTPS** | `443` | `0.0.0.0/0` | Secure SSL Web access |
     | **Custom TCP** | `3000` | `0.0.0.0/0` | Direct Frontend port (for initial testing) |
     | **Custom TCP** | `8000` | `0.0.0.0/0` | Direct Backend API port (for initial testing) |

8. Click **Launch Instance**.

### Option B: Using AWS Lightsail (Simplified & Flat Price)
1. Go to **AWS Lightsail** from the console.
2. Click **Create Instance**.
3. Select **Linux/Unix** platform and **Ubuntu 24.04 LTS** blueprint.
4. Select the **$5/month plan** (first 3 months are free!).
5. Click **Create Instance**.
6. Once active, go to the **Networking** tab of the instance:
   * Under **IPv4 Firewall**, click **Add Rule**.
   * Add rules for **Port 3000** (Custom TCP) and **Port 8000** (Custom TCP) open to all, along with SSH (22), HTTP (80), and HTTPS (443).

---

## 🔌 Step 2: Connect to Your Instance

Open PowerShell or Terminal on your local computer, navigate to the folder where you saved your downloaded key pair, and run:

```bash
# 1. Restrict private key permissions (Required on Linux/macOS, optional on Windows)
# chmod 400 jarvis-key.pem

# 2. SSH into the instance (replace with your AWS Public DNS or Public IP)
ssh -i "jarvis-key.pem" ubuntu@YOUR_AWS_PUBLIC_IP
```

Once connected, update the server's local package index:
```bash
sudo apt update && sudo apt upgrade -y
```

---

## 📦 Step 3: Deployment Options

You can deploy using either **Docker Compose (Recommended)** or a **Bare-Metal (systemd/PM2) setup**.

### Method A: Docker Compose Deployment (Recommended)
Docker containers compile everything into isolated packages, meaning you don't need to manually configure Node.js, Python, or PM2 on the server.

We have pre-configured `Dockerfile.backend`, `frontend/Dockerfile`, and `docker-compose.yml` in your project folder!

#### 1. Install Docker & Docker Compose on your AWS server:
```bash
# Install Docker
sudo apt install -y docker.io

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add your user to the docker group so you don't need 'sudo' prefix
sudo usermod -aG docker ubuntu
newgrp docker
```

#### 2. Get the code onto the server:
You can push your local folder to GitHub and clone it:
```bash
git clone https://github.com/your-username/trading-bot.git
cd trading-bot
```
Or upload using SFTP (FileZilla / WinSCP) using your private key (`jarvis-key.pem`).

#### 3. Create the persistent state files:
Before starting Docker, initialize empty JSON files on the host so Docker mounts them correctly as files (rather than folders):
```bash
touch bot_state.json active_trades.json scan_heartbeat.json trade_history.json
mkdir -p logs && touch logs/bot.log
```

#### 4. Configure Environment Variables:
Copy your `.env` settings:
```bash
nano .env
```
Paste your Bitget/Bybit API keys, Telegram Bot Token, and Chat ID.

#### 5. Build and Launch:
```bash
# Start all containers in detached (background) mode
docker-compose up --build -d
```
Your app will build (compiling Next.js in production standalone mode) and launch.
* Frontend: `http://YOUR_AWS_PUBLIC_IP:3000`
* Backend API: `http://YOUR_AWS_PUBLIC_IP:8000`

---

### Method B: Bare-Metal Deployment (systemd & PM2)
If you prefer not to use Docker, you can run the bot directly on the Ubuntu server.

#### 1. Install Runtime Engines:
```bash
# Install Python 3, venv, Git, Nginx
sudo apt install -y python3-pip python3-venv git nginx

# Install Node.js (Version 20)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install PM2 (Process Manager for Node) globally
sudo npm install pm2 -g
```

#### 2. Configure Python App & Bot Scanner:
```bash
# Navigate to codebase
cd /home/ubuntu/trading-bot

# Set up python environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. Create systemd services:
This ensures the Python API and the live trading bot automatically boot up on system starts and restart on failures.

**FastAPI Service**:
```bash
sudo nano /etc/systemd/system/jarvis-api.service
```
Paste configuration:
```ini
[Unit]
Description=JARVIS FastAPI Backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/trading-bot
ExecStart=/home/ubuntu/trading-bot/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Live Bot Scanner Service**:
```bash
sudo nano /etc/systemd/system/jarvis-bot.service
```
Paste configuration:
```ini
[Unit]
Description=JARVIS Live Trading Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/trading-bot
ExecStart=/home/ubuntu/trading-bot/venv/bin/python run_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Reload and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable jarvis-api jarvis-bot
sudo systemctl start jarvis-api jarvis-bot
```

#### 4. Configure & Run Frontend (Next.js):
```bash
cd /home/ubuntu/trading-bot/frontend

# Install node dependencies
npm install

# Build Next.js for production
npm run build

# Start Next.js with PM2 to keep it alive 24/7
pm2 start npm --name "jarvis-frontend" -- start
pm2 save
pm2 startup
```

---

## 🔒 Step 4: Configure Production Reverse Proxy & SSL (Nginx + HTTPS)

For testing, exposing ports `3000` and `8000` is acceptable. However, for a persistent, secure, and production-ready setup:
1. **Nginx** will run on Port 80 (HTTP) / Port 443 (HTTPS).
2. It will route all dashboard traffic (`/`) to the Next.js frontend (Port 3000).
3. It will route all API requests (`/api/*`) directly to the FastAPI server (Port 8000).
4. Free SSL certificates from **Let's Encrypt** will encrypt all traffic.

### 1. Configure Nginx
Create a server configuration file:
```bash
sudo nano /etc/nginx/sites-available/jarvis
```
Paste this configuration (replace `yourdomain.com` with your domain name or AWS Elastic IP):
```nginx
server {
    listen 80;
    server_name yourdomain.com; # Or your AWS Public IP / Public DNS

    # Next.js Frontend
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # FastAPI Backend Route
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

Enable the configuration and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/jarvis /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove the default splash page
sudo nginx -t                             # Test config syntax
sudo systemctl restart nginx
```

> [!TIP]
> If you configure Nginx this way, you can go to your **AWS Security Group** and safely **delete the rules for ports 3000 and 8000**. Keeping only ports 22, 80, and 443 open secures your backend from raw database/API scan attacks.

### 2. Install SSL Certificate (Let's Encrypt)
To secure the panel, point a domain name (from Namecheap, GoDaddy, Cloudflare, etc.) to your AWS Public IP, then run:
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```
Follow the interactive prompts to enable SSL redirection. Certbot will configure security headers and automatically renew certificates.

---

## 📊 Step 5: Monitoring Logs and Health Checks

### Check Status (Docker)
```bash
# View running containers
docker ps

# Watch logs of the bot container
docker logs -f trading-bot-backend-1
```

### Check Status (Bare-Metal)
```bash
# Watch FastAPI backend logs
journalctl -u jarvis-api -f

# Watch Live Scanner Trade logs
journalctl -u jarvis-bot -f

# Watch Frontend dashboard status
pm2 logs jarvis-frontend
```

### Heartbeat and State verification
You can query the backend endpoints directly:
```bash
# Query the live state
curl http://localhost:8000/api/state

# Query active position JSON
curl http://localhost:8000/api/trades
```
Your AWS server is now configured, secured, and running the JARVIS Quant Engine!
