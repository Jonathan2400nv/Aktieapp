import streamlit as st
from components.watchlist import render_watchlist_sidebar
from modules import swing_trading, earnings, reddit_sentiment, ai_screener, portfolio

st.set_page_config(
    page_title="Aktie App",
    page_icon="📈",
    layout="wide",
)

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
