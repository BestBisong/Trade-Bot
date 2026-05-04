import streamlit as st
import pandas as pd
import json, os, datetime
import altair as alt
from config.settings import SESSION_START, SESSION_END

# Premium Page Config
st.set_page_config(
    page_title="JARVIS | Institutional Trading Terminal",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- PREMIUM CSS STYLING ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&family=JetBrains+Mono:wght@400;500&display=swap');

        /* Main Container */
        .stApp {
            background-color: #05070a;
            color: #eceef2;
            font-family: 'Outfit', sans-serif;
        }

        /* Glassmorphism Cards */
        .metric-card {
            background: rgba(17, 24, 39, 0.7);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 1.5rem;
            transition: all 0.3s ease;
        }
        .metric-card:hover {
            border: 1px solid rgba(0, 122, 255, 0.3);
            transform: translateY(-2px);
        }

        /* Status Glows */
        .glow-green {
            box-shadow: 0 0 15px rgba(16, 185, 129, 0.2);
            border: 1px solid #10b981 !important;
        }
        .glow-blue {
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.2);
            border: 1px solid #3b82f6 !important;
        }

        /* Typography */
        .terminal-text {
            font-family: 'JetBrains Mono', monospace;
            color: #3b82f6;
            font-size: 0.85rem;
        }
        .stat-label {
            color: #94a3b8;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 0.5rem;
        }
        .stat-value {
            font-size: 1.8rem;
            font-weight: 600;
            color: #ffffff;
        }

        /* Signal Badges */
        .signal-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        /* Hide Streamlit elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- DATA UTILITIES ---
def safe_read_json(path, default):
    if not os.path.exists(path): return default
    try:
        with open(path, "r") as f:
            content = f.read().strip()
            return json.loads(content) if content else default
    except Exception: return default

# --- LOAD STATE ---
bot_state = safe_read_json("bot_state.json", {})
history = safe_read_json("trade_history.json", [])
active_trades = safe_read_json("active_trades.json", [])
risk = bot_state.get("risk", {})
wallet = float(bot_state.get("wallet", 100.0))

# --- HEADER SECTION ---
t1, t2 = st.columns([3, 1])
with t1:
    st.markdown("# MY <span style='color:#3b82f6; font-weight:300;'>TERMINAL</span>", unsafe_allow_html=True)
    st.markdown(f"<p class='terminal-text'>CORE: ONLINE | LATENCY: 42ms | NODE: ALPHA-1</p>", unsafe_allow_html=True)

with t2:
    now = datetime.datetime.now().time()
    start = datetime.datetime.strptime(SESSION_START, "%H:%M").time()
    end = datetime.datetime.strptime(SESSION_END, "%H:%M").time()
    
    if start <= now <= end:
        st.markdown('<div class="metric-card glow-green" style="padding: 10px; text-align:center;">SESSION ACTIVE</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="metric-card" style="padding: 10px; text-align:center; color:#94a3b8;">STANDBY MODE</div>', unsafe_allow_html=True)

st.markdown("---")

# --- CORE METRICS GRID ---
m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(f"""
        <div class="metric-card">
            <div class="stat-label">Total Equity</div>
            <div class="stat-value">${wallet:.2f}</div>
            <div style="color:#10b981; font-size:0.85rem;">{risk.get('daily_pnl_pct', 0.0):+.2f}% TODAY</div>
        </div>
    """, unsafe_allow_html=True)

with m2:
    closed = len(history)
    wins = len([t for t in history if float(t.get("pnl", 0)) > 0])
    wr = (wins/closed*100) if closed > 0 else 0
    st.markdown(f"""
        <div class="metric-card">
            <div class="stat-label">Win Rate</div>
            <div class="stat-value">{wr:.1f}%</div>
            <div style="color:#94a3b8; font-size:0.85rem;">{closed} TOTAL TRADES</div>
        </div>
    """, unsafe_allow_html=True)

with m3:
    st.markdown(f"""
        <div class="metric-card">
            <div class="stat-label">Daily PnL</div>
            <div class="stat-value" style="color:{'#10b981' if risk.get('loss_today', 0) >= 0 else '#ef4444'};">
                ${risk.get('loss_today', 0.0):.2f}
            </div>
            <div style="color:#94a3b8; font-size:0.85rem;">{risk.get('trades_today', 0)} TRADES TODAY</div>
        </div>
    """, unsafe_allow_html=True)

with m4:
    cooldown = "ACTIVE" if risk.get("cooldown_until") else "STABLE"
    st.markdown(f"""
        <div class="metric-card">
            <div class="stat-label">Risk Profile</div>
            <div class="stat-value" style="font-size:1.4rem;">{cooldown}</div>
            <div style="color:#94a3b8; font-size:0.85rem;">STREAK: {risk.get('consecutive_losses', 0)}/3</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- CHARTS SECTION ---
c1, c2 = st.columns([2, 1])

with c1:
    st.markdown("### Performance Trend")
    if history:
        h_df = pd.DataFrame(history)
        if "closed_at" in h_df.columns:
            h_df["closed_at"] = pd.to_datetime(h_df["closed_at"])
            h_df = h_df.sort_values("closed_at")
            h_df["equity"] = 100.0 + h_df["pnl"].cumsum()
            
            chart = alt.Chart(h_df).mark_area(
                line={'color':'#3b82f6'},
                color=alt.Gradient(
                    gradient='linear',
                    stops=[alt.GradientStop(color='#3b82f6', offset=0),
                           alt.GradientStop(color='rgba(59, 130, 246, 0)', offset=1)],
                    x1=1, x2=1, y1=1, y2=0
                )
            ).encode(
                x=alt.X('closed_at:T', title=None),
                y=alt.Y('equity:Q', title=None, scale=alt.Scale(zero=False))
            ).properties(height=350)
            st.altair_chart(chart, width='stretch')
        else:
            st.info("Scanner Active: Awaiting first trade settlement...")
    else:
        st.info("Scanner Active: Awaiting first trade settlement...")

with c2:
    st.markdown("### Signal Confluence")
    if active_trades:
        avg_conf = sum([float(t.get('confidence', 0.5)) for t in active_trades]) / len(active_trades)
    else:
        avg_conf = 0.5
    
    st.markdown(f"""
        <div class="metric-card glow-blue" style="text-align:center;">
            <div class="stat-label">Sentiment Score</div>
            <div style="font-size:3rem; font-weight:600; color:#3b82f6;">{avg_conf*100:.0f}%</div>
            <div style="color:#94a3b8; font-size:0.8rem; margin-top:10px;">
                {'BULLISH' if avg_conf > 0.6 else ('BEARISH' if avg_conf < 0.4 else 'NEUTRAL')}
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    heartbeat = safe_read_json("scan_heartbeat.json", {})
    if heartbeat:
        st.markdown("### Heartbeat")
        hb_df = pd.DataFrame([heartbeat]).T.reset_index()
        hb_df.columns = ['Asset', 'Sync']
        st.dataframe(hb_df, width='stretch', hide_index=True)

# --- ACTIVE POSITIONS ---
st.markdown("### Active Positions")
if active_trades:
    for t in active_trades:
        st.markdown(f"""
            <div class="metric-card" style="margin-bottom:15px; border-left: 4px solid {'#10b981' if t['side'] == 'buy' else '#ef4444'};">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-size:1.2rem; font-weight:600;">{t['symbol']}</span>
                        <span class="signal-badge" style="background:rgba({'16,185,129' if t['side'] == 'buy' else '239,68,68'}, 0.2); color:{'#10b981' if t['side'] == 'buy' else '#ef4444'}; margin-left:10px;">
                            {t['side'].upper()}
                        </span>
                    </div>
                    <div class="terminal-text">REGIME: {t.get('regime', 'N/A').upper()}</div>
                </div>
                <div style="display:flex; gap:30px; margin-top:15px;">
                    <div><div class="stat-label">Entry</div><div style="font-family:'JetBrains Mono';">${float(t['entry_price']):.4f}</div></div>
                    <div><div class="stat-label">Target</div><div style="font-family:'JetBrains Mono'; color:#10b981;">${float(t['tp']):.4f}</div></div>
                    <div><div class="stat-label">Stop</div><div style="font-family:'JetBrains Mono'; color:#ef4444;">${float(t['sl']):.4f}</div></div>
                    <div style="flex-grow:1;"><div class="stat-label">Logic</div><div class="terminal-text">{t.get('status', 'WAITING')}</div></div>
                </div>
            </div>
        """, unsafe_allow_html=True)
else:
    st.markdown("<div class='metric-card' style='text-align:center; padding: 40px; color:#94a3b8;'>Scanning for triggers...</div>", unsafe_allow_html=True)