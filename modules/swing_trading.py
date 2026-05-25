import pandas as pd
import streamlit as st
from services.yfinance_service import fetch_ohlcv
from components.charts import build_swing_chart
from utils.calculations import calculate_ma, calculate_rsi, calculate_macd, calculate_atr, detect_volume_spike, get_signal


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

    close = df['Close'].squeeze()
    volume = df['Volume'].squeeze()
    ma20 = calculate_ma(close, 20)
    ma50 = calculate_ma(close, 50)
    rsi = calculate_rsi(close, 14)
    macd_line, signal_line, _ = calculate_macd(close)
    spike = detect_volume_spike(volume)
    signal = get_signal(rsi, ma20, ma50)

    atr = calculate_atr(df).iloc[-1]
    current_price = float(close.iloc[-1])
    stop_loss = round(current_price - 2 * float(atr), 2) if not pd.isna(atr) else None

    st.plotly_chart(build_swing_chart(df, ticker, stop_loss=stop_loss), use_container_width=True)

    macd_bull = float(macd_line.iloc[-1]) > float(signal_line.iloc[-1])
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Signal", signal if signal else "N/A")
    col2.metric("RSI (14)", f"{rsi.iloc[-1]:.1f}" if not pd.isna(rsi.iloc[-1]) else "N/A")
    col3.metric("MACD", "Bullish" if macd_bull else "Bearish")
    col4.metric("Volumen-spike", "Ja" if spike.iloc[-1] else "Nej")
    col5.metric("Stop-loss (2×ATR)", f"${stop_loss:.2f}" if stop_loss else "N/A")

    if signal == "Bullish":
        st.success("Bullish: RSI under 50 og MA20 over MA50 — optrend bekræftet.")
    elif signal == "Bearish":
        st.error("Bearish: RSI over 50 og MA20 under MA50 — nedtrend bekræftet.")
    else:
        st.info("Neutral: Indikatorer peger i modsat retning — afvent klarere signal.")
