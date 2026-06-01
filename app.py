import streamlit as st
from components.watchlist import render_watchlist_sidebar
from modules import swing_trading, earnings, reddit_sentiment, ai_screener, portfolio

st.set_page_config(
    page_title="Aktier AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ── Typography ─────────────────────────────────── */
html, body, [class*="css"] {
    font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
}

/* ── Remove Streamlit chrome ────────────────────── */
/* Use display:none so sidebar is completely unaffected */
header[data-testid="stHeader"] { display: none !important; }
footer { display: none !important; }
#MainMenu { display: none !important; }
/* Hide the sidebar collapse button — sidebar stays permanently open */
[data-testid="stSidebarCollapseButton"] { display: none !important; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

/* ── Tabs ───────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 1px solid rgba(128,128,128,0.2);
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    height: 38px;
    padding: 0 18px;
    border-radius: 8px 8px 0 0;
    font-size: 13px;
    font-weight: 500;
    background: transparent;
    border: none;
    color: rgba(128,128,128,0.8);
    transition: color 0.15s;
}
.stTabs [aria-selected="true"] {
    color: #4caf50 !important;
    border-bottom: 2px solid #4caf50 !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab"]:hover { color: inherit; }

/* ── Metric cards ───────────────────────────────── */
[data-testid="stMetric"] {
    background: rgba(128,128,128,0.06);
    border: 1px solid rgba(128,128,128,0.12);
    border-radius: 10px;
    padding: 14px 18px;
}
[data-testid="stMetricLabel"] { font-size: 12px; opacity: 0.6; }
[data-testid="stMetricValue"] { font-size: 22px; font-weight: 600; }

/* ── Buttons ────────────────────────────────────── */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
    font-size: 13px;
    transition: all 0.15s;
}
.stButton > button[kind="primary"] { background: #4caf50; border-color: #4caf50; }
.stButton > button[kind="primary"]:hover { background: #43a047; border-color: #43a047; }

/* ── Sidebar ────────────────────────────────────── */
[data-testid="stSidebar"] {
    border-right: 1px solid rgba(128,128,128,0.15);
}
[data-testid="stSidebar"] .block-container { padding-top: 1rem; }

/* ── Expander ───────────────────────────────────── */
.streamlit-expanderHeader {
    border-radius: 8px;
    font-size: 13px;
}

/* ── Divider ────────────────────────────────────── */
hr { opacity: 0.15; margin: 1rem 0; }

/* ── Selectbox / multiselect ────────────────────── */
[data-baseweb="select"] { border-radius: 8px !important; }

/* ── Dataframe ──────────────────────────────────── */
[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }

/* ── Info / warning / error boxes ──────────────── */
[data-testid="stAlert"] { border-radius: 8px; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

watchlist = render_watchlist_sidebar()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Swing Trading",
    "🔍 AI Screener",
    "📅 Earnings Kalender",
    "💬 Marked Sentiment",
    "📈 Modelportefølje",
])

with tab1:
    swing_trading.render(watchlist)

with tab2:
    ai_screener.render(watchlist)

with tab3:
    earnings.render(watchlist)

with tab4:
    reddit_sentiment.render()

with tab5:
    portfolio.render(watchlist)
