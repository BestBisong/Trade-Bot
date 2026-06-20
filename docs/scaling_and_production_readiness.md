# J.A.R.V.I.S // Production Readiness & Database Scaling Blueprint

This document outlines the engineering blueprint to transition J.A.R.V.I.S from a file-based paper-trading system to a highly resilient, enterprise-scale production engine.

---

## 🗄️ 1. Database Scaling: Transitioning from JSON to SQL

Currently, J.A.R.V.I.S utilizes local JSON files (`active_trades.json`, `trade_history.json`, etc.) as its database layer. While perfect for lightweight sandboxing, this approach suffers from major production limitations:
* **Race Conditions:** Simultaneous read/write requests from the FastAPI backend and Python scan loop can lead to file corruption.
* **Lack of Query Indexing:** As transaction history grows, parsing large JSON arrays into memory degrades latency.

### The Migration Blueprint:
We recommend migrating to **SQLite** (for simple, single-server VPS setups) or **PostgreSQL** (for multi-server cluster setups) using an ORM like **SQLAlchemy** or **Prisma**:

```
Current: [FastAPI/Bot Loop] <---> [JSON Files] (File lock contention risk)

Target:  [FastAPI/Bot Loop] <---> [SQLAlchemy ORM] <---> [PostgreSQL Database] (Acid compliant, row-locking)
```

### Proposed Database Schema:
```sql
CREATE TABLE trade_history (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    qty NUMERIC(18, 8) NOT NULL,
    entry_price NUMERIC(18, 4) NOT NULL,
    exit_price NUMERIC(18, 4) NOT NULL,
    pnl NUMERIC(18, 4) NOT NULL,
    reason VARCHAR(50) NOT NULL, -- 'tp', 'sl', or 'manual_close'
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE bot_settings (
    id SERIAL PRIMARY KEY,
    auto_trading_enabled BOOLEAN DEFAULT TRUE,
    partial_tp_enabled BOOLEAN DEFAULT FALSE,
    daily_200sma_guard BOOLEAN DEFAULT TRUE,
    allow_shorts BOOLEAN DEFAULT TRUE,
    risk_per_trade NUMERIC(5, 4) DEFAULT 0.02,
    max_notional_per_trade NUMERIC(18, 4) DEFAULT 5.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 📡 2. API Integration & Real-Time Optimization

* **Websockets for Order Telemetry:** The current bot uses REST polling to monitor prices and verify fills. For live execution, we should subscribe to exchange **Websocket Feeds** (e.g., Bybit Private User Streams). This reduces execution latency from 1.5 seconds to < 50 milliseconds, minimizing slippage on stop-loss triggers.
* **External Rate Limiting Guard:** Implement a centralized rate-limiting queue on the API ingest to guarantee the bot never violates exchange limits during periods of extreme market volatility.

---

## 📝 3. Enterprise Logging & Alerting

* **Structured Logging (JSON):** Transition Python's default standard logger to structured JSON logging. This allows log collectors (like ELK Stack, Datadog, or Promtail) to easily parse and query logs:
  ```json
  {"timestamp": "2026-06-20T19:40:00Z", "level": "INFO", "symbol": "BTC/USDT", "event": "ORDER_FILLED", "side": "SHORT", "qty": 0.005, "price": 92400.0}
  ```
* **Log Rotation:** Enforce log rotation in production (e.g., maximum log file size of 50MB, keeping a maximum of 5 historical archives) to prevent VPS disk saturation.
* **Notification Webhooks:** Integrate live alerts via Slack, Telegram, or Discord for critical system events:
  * Database connection failures.
  * Trade executions (with PnL updates).
  * Extreme drawdown warnings (circuit breaker activations).

---

## 🛡️ 4. High Availability & Circuit Breakers

* **Process Clustering (Docker Swarm / Kubernetes):** Run the FastAPI backend and Next.js frontend in a load-balanced cluster across multiple VPS nodes.
* **External Failover Data Feeds:** If the primary price feed (Binance API) goes down, the system should automatically switch to a fallback API (e.g., dYdX, OKX, or CoinGecko) to prevent data gaps from corrupting indicators.
* **Capital Protection Circuit Breaker:** Implement a hard capital check: if the total wallet equity drops by more than **15% in a single 24-hour window**, the bot immediately closes all active positions, disables automatic scanning, and sends an urgent notification to the administrator.
