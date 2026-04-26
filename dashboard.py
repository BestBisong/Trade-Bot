import streamlit as st
import pandas as pd
import json, os, datetime
from config.settings import SESSION_START, SESSION_END

st.set_page_config(page_title="JARVIS Trading Terminal", layout="wide")


def safe_read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            content = f.read().strip()
            if not content:
                return default
            return json.loads(content)
    except Exception:
        return default


st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap');

        .stApp {
            background:
                radial-gradient(circle at 10% 10%, rgba(255, 170, 108, 0.15), transparent 30%),
                radial-gradient(circle at 90% 20%, rgba(120, 174, 255, 0.12), transparent 28%),
                linear-gradient(135deg, #071120 0%, #0f1f33 40%, #132842 100%);
            color: #eef4ff;
            font-family: 'Space Grotesk', sans-serif;
        }

        h1, h2, h3, h4 { color: #f6fbff !important; }

        .status-badge {
            border-radius: 999px;
            padding: 0.25rem 0.9rem;
            font-size: 0.85rem;
            font-weight: 700;
            display: inline-block;
            margin-bottom: 0.8rem;
            font-family: 'IBM Plex Mono', monospace;
        }

        .status-active {
            background: rgba(61, 213, 152, 0.18);
            color: #91ffd0;
            border: 1px solid rgba(90, 224, 166, 0.45);
        }

        .status-idle {
            background: rgba(255, 188, 97, 0.20);
            color: #ffcc84;
            border: 1px solid rgba(255, 194, 111, 0.55);
        }

        .glass-card {
            border: 1px solid rgba(189, 218, 255, 0.23);
            border-radius: 18px;
            background: linear-gradient(145deg, rgba(16, 31, 48, 0.85), rgba(17, 35, 58, 0.65));
            box-shadow: 0 8px 24px rgba(4, 10, 19, 0.35);
            padding: 14px 16px;
            margin-bottom: 10px;
        }

        .label {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.78rem;
            color: #94b5df;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .value {
            font-size: 1.25rem;
            font-weight: 700;
            margin-top: 2px;
            color: #f4fbff;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# 1. SIDEBAR: Session Control
st.sidebar.header("Control Plane")
now = datetime.datetime.now().time()
start = datetime.datetime.strptime(SESSION_START, "%H:%M").time()
end = datetime.datetime.strptime(SESSION_END, "%H:%M").time()

if start <= now <= end:
    st.sidebar.success(f"Session active until {SESSION_END}")
else:
    st.sidebar.warning("Standby: outside trading window")

# 2. MAIN: Performance Metrics
st.title("JARVIS AI Trading Terminal")

bot_state = safe_read_json("bot_state.json", {})
history = safe_read_json("trade_history.json", [])
trades = safe_read_json("active_trades.json", [])
wf_gate = bot_state.get("walk_forward_gate", {}) if isinstance(bot_state, dict) else {}
tuning = bot_state.get("tuning", {}) if isinstance(bot_state, dict) else {}
tuned_params = tuning.get("params", {}) if isinstance(tuning, dict) else {}

wallet = float(bot_state.get("wallet", 100.0))
risk = bot_state.get("risk", {}) if isinstance(bot_state, dict) else {}
closed_trades = len(history) if isinstance(history, list) else 0
wins = len([t for t in history if isinstance(t, dict) and float(t.get("pnl", 0)) > 0]) if isinstance(history, list) else 0
win_rate = (wins / closed_trades * 100.0) if closed_trades else 0.0

if start <= now <= end:
    st.markdown('<div class="status-badge status-active">SESSION ACTIVE</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="status-badge status-idle">SESSION STANDBY</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Virtual Wallet", f"${wallet:.2f}", f"{risk.get('daily_pnl_pct', 0.0):+.2f}% today")
with col2:
    st.metric("Active Trades", f"{len(trades)} / 2", f"{closed_trades} closed")
with col3:
    st.metric("Win Rate", f"{win_rate:.1f}%", f"{risk.get('consecutive_losses', 0)} loss streak")

col4, col5, col6 = st.columns(3)
with col4:
    st.metric("Daily PnL $", f"${risk.get('loss_today', 0.0):.2f}")
with col5:
    st.metric("Trades Today", str(risk.get("trades_today", 0)))
with col6:
    st.metric("Cooldown", "ON" if risk.get("cooldown_until") else "OFF")

col7, col8, col9 = st.columns(3)
with col7:
    gate_ok = wf_gate.get("allowed", False)
    st.metric("Walk-Forward Gate", "PASS" if gate_ok else "BLOCK")
with col8:
    measured = wf_gate.get("measured", {}) if isinstance(wf_gate, dict) else {}
    st.metric("WF Win Rate", f"{float(measured.get('win_rate', 0.0)):.1f}%")
with col9:
    st.metric("Tuning Action", str(tuning.get("action", "n/a")).upper())

st.subheader("Equity and PnL")
if history:
    hist_df = pd.DataFrame(history)
    if "closed_at" in hist_df.columns:
        hist_df["closed_at"] = pd.to_datetime(hist_df["closed_at"], errors="coerce")
    if "pnl" in hist_df.columns:
        hist_df["pnl"] = pd.to_numeric(hist_df["pnl"], errors="coerce").fillna(0.0)
    hist_df = hist_df.sort_values("closed_at")
    hist_df["equity"] = 100.0 + hist_df["pnl"].cumsum()

    p1, p2 = st.columns(2)
    with p1:
        st.line_chart(hist_df.set_index("closed_at")["equity"], height=240)
    with p2:
        st.bar_chart(hist_df.set_index("closed_at")["pnl"], height=240)
else:
    st.caption("No closed trade history available yet for equity chart.")

# 3. THE "BRAIN" VIEW: Active Trade Logic
st.subheader("Active Logic Monitor")
if trades:
    for t in trades:
        with st.expander(f"Position: {t['symbol']} ({t['side'].upper()})"):
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Entry:** ${float(t['entry_price']):.4f}")
            c2.write(f"**Target (TP):** ${float(t['tp']):.4f}")
            c3.write(f"**Safety (SL):** ${float(t['sl']):.4f}")
            c4, c5 = st.columns(2)
            c4.write(f"**Reason:** {t.get('status', 'N/A')}")
            confidence = float(t.get("confidence", 0.5))
            c5.write(f"**ML Confidence:** {confidence:.2f} | **Regime:** {t.get('regime', 'n/a')}")
            st.progress(max(0.0, min(confidence, 1.0)), text="ML Conviction Strength")
else:
    st.info("Bot is scanning for a high-probability entry...")


st.subheader("Market Heartbeat")
heartbeat = safe_read_json("scan_heartbeat.json", {})
if heartbeat:
    st.table(pd.DataFrame([heartbeat]).T.rename(columns={0: "Last Scan Time"}))
else:
    st.caption("No heartbeat data yet.")

st.subheader("Self-Tuning Parameters")
t1, t2, t3 = st.columns(3)
with t1:
    st.markdown(
        f"""
        <div class="glass-card">
            <div class="label">ML Long (Trending/Ranging)</div>
            <div class="value">{float(tuned_params.get('ml_conf_long_trending', 0.57)):.3f} / {float(tuned_params.get('ml_conf_long_ranging', 0.60)):.3f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with t2:
    st.markdown(
        f"""
        <div class="glass-card">
            <div class="label">ML Short (Trending/Ranging)</div>
            <div class="value">{float(tuned_params.get('ml_conf_short_trending', 0.43)):.3f} / {float(tuned_params.get('ml_conf_short_ranging', 0.40)):.3f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with t3:
    st.markdown(
        f"""
        <div class="glass-card">
            <div class="label">ATR Floor / Stop ATR Scale</div>
            <div class="value">{float(tuned_params.get('atr_min_pct', 0.0015)):.4f} / {float(tuned_params.get('stop_atr_scale', 1.0)):.3f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.caption(f"Last tuning update: {tuning.get('updated_at', 'n/a')} | Next review: {tuning.get('next_review_at', 'n/a')}")

st.subheader("Recent Closed Trades")
if history:
    hist_df = pd.DataFrame(history).tail(20).iloc[::-1]
    if "pnl" in hist_df.columns:
        hist_df["pnl"] = pd.to_numeric(hist_df["pnl"], errors="coerce")
    st.dataframe(hist_df, use_container_width=True)
else:
    st.caption("No closed trades recorded yet.")