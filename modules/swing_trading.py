import pandas as pd
import streamlit as st
from services.yfinance_service import fetch_ohlcv
from components.charts import build_swing_chart
from utils.calculations import calculate_ma, calculate_rsi, detect_volume_spike, get_signal


def render(watchlist: list[str]) -> None:
    st.header("Swing Trading")

    if not watchlist:
        st.warning("Tilføj aktier til din watchlist i sidebaren.")
        return

    ticker = st.selectbox("Vælg aktie", watchlist)

    with st.spinner(f"Henter data for {ticker}..."):
        df = fetch_ohlcv(ticker)

    if df is None or df.empty:
        st.error(f"Kunne ikke hente data for {ticker}. Tjek at ticker-symbolet er korrekt.")
        return

    st.plotly_chart(build_swing_chart(df, ticker), use_container_width=True)

    close = df['Close'].squeeze()
    volume = df['Volume'].squeeze()
    ma20 = calculate_ma(close, 20)
    ma50 = calculate_ma(close, 50)
    rsi = calculate_rsi(close, 14)
    spike = detect_volume_spike(volume)
    signal = get_signal(rsi, ma20, ma50)

    col1, col2, col3 = st.columns(3)
    col1.metric("Signal", signal if signal else "N/A")
    col2.metric("RSI (14)", f"{rsi.iloc[-1]:.1f}" if not pd.isna(rsi.iloc[-1]) else "N/A")
    col3.metric("Volumen-spike", "Ja" if spike.iloc[-1] else "Nej")

    if signal == "Bullish":
        st.success("Bullish: RSI under 50 og MA20 over MA50 — optrend bekræftet.")
    elif signal == "Bearish":
        st.error("Bearish: RSI over 50 og MA20 under MA50 — nedtrend bekræftet.")
    else:
        st.info("Neutral: Indikatorer peger i modsat retning — afvent klarere signal.")
