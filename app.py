import streamlit as st
from components.watchlist import render_watchlist_sidebar
from modules import swing_trading, earnings, reddit_sentiment, saxo_placeholder

st.set_page_config(
    page_title="Aktie App",
    page_icon="📈",
    layout="wide",
)

watchlist = render_watchlist_sidebar()

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Swing Trading",
    "📅 Earnings Kalender",
    "💬 Reddit Sentiment",
    "🏦 Saxo Bank",
])

with tab1:
    swing_trading.render(watchlist)

with tab2:
    earnings.render(watchlist)

with tab3:
    reddit_sentiment.render()

with tab4:
    saxo_placeholder.render()
