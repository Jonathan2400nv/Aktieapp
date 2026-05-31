import pandas as pd
import streamlit as st
from services.yfinance_service import fetch_ohlcv
from components.charts import build_price_chart, build_indicator_chart, INDICATOR_OPTIONS
from utils.calculations import (
    calculate_ma, calculate_rsi, calculate_macd, calculate_atr,
    detect_volume_spike, score_signal, calculate_trade_levels,
)


def _get_mtf_signals(ticker: str) -> list[dict]:
    import yfinance as yf
    configs = [
        ("Ugentlig",  "1y",  "1wk"),
        ("Daglig",    "6mo", "1d"),
        ("4-timers",  "60d", "1h"),
    ]
    rows = []
    for label, period, interval in configs:
        try:
            raw = yf.download(ticker, period=period, interval=interval,
                              progress=False, auto_adjust=True)
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            if raw.empty or len(raw) < 50:
                rows.append({"Tidshorisont": label, "Trend": "—", "RSI": "—", "MA20 vs MA50": "—"})
                continue
            c = raw['Close'].squeeze()
            ma20 = calculate_ma(c, 20)
            ma50 = calculate_ma(c, 50)
            rsi_s = calculate_rsi(c, 14)
            last_rsi = float(rsi_s.iloc[-1]) if not pd.isna(rsi_s.iloc[-1]) else 50.0
            last_ma20 = float(ma20.iloc[-1]) if not pd.isna(ma20.iloc[-1]) else 0.0
            last_ma50 = float(ma50.iloc[-1]) if not pd.isna(ma50.iloc[-1]) else 0.0
            if last_ma20 > last_ma50 and last_rsi > 50:
                trend = "↑ Bullish"
            elif last_ma20 < last_ma50 and last_rsi < 50:
                trend = "↓ Bearish"
            else:
                trend = "→ Neutral"
            rows.append({
                "Tidshorisont": label,
                "Trend": trend,
                "RSI": f"{last_rsi:.1f}",
                "MA20 vs MA50": "MA20 > MA50" if last_ma20 > last_ma50 else "MA20 < MA50",
            })
        except Exception:
            rows.append({"Tidshorisont": label, "Trend": "—", "RSI": "—", "MA20 vs MA50": "—"})
    return rows


def render(watchlist: list[str]) -> None:
    st.header("Swing Trading")

    if not watchlist:
        st.warning("Tilføj aktier til din watchlist i sidebaren.")
        return

    ticker = st.selectbox("Vælg aktie", watchlist)

    with st.spinner(f"Henter data for {ticker}..."):
        df = fetch_ohlcv(ticker)

    if df is None or df.empty:
        st.error(f"Kunne ikke hente data for {ticker}.")
        return

    close = df['Close'].squeeze()
    volume = df['Volume'].squeeze()
    rsi = calculate_rsi(close, 14)
    macd_line, signal_line, _ = calculate_macd(close)
    spike = detect_volume_spike(volume)

    scored = score_signal(df)
    levels = calculate_trade_levels(df)
    atr = float(calculate_atr(df).iloc[-1])
    adx = scored['adx']

    st.plotly_chart(
        build_price_chart(df, ticker, stop_loss=levels['stop_loss']),
        use_container_width=True,
    )

    selected_indicator = st.radio(
        "Indikator",
        INDICATOR_OPTIONS,
        horizontal=True,
        label_visibility="collapsed",
    )
    st.plotly_chart(
        build_indicator_chart(df, selected_indicator),
        use_container_width=True,
    )

    label = scored['label']
    score = scored['score']

    if label == 'KØB' and adx >= 25:
        st.success(f"**Signal: {label}** — Score: {score}/9 · ADX: {adx:.1f}")
    elif label == 'KØB' and adx < 25:
        st.warning(f"**Signal: KØB (ADX {adx:.1f} < 25 — svag trend, afvent)** — Score: {score}/9")
    elif label == 'SÆLG':
        st.error(f"**Signal: {label}** — Score: {score}/9 · ADX: {adx:.1f}")
    else:
        st.info(f"**Signal: Neutral** — Score: {score}/9 · ADX: {adx:.1f} — afvent klarere signal")

    with st.expander("Score-detaljer"):
        for condition, points in scored['breakdown'].items():
            icon = "✅" if points > 0 else "⬜"
            st.write(f"{icon} {condition}: **{points}**")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("RSI (14)", f"{rsi.iloc[-1]:.1f}" if not pd.isna(rsi.iloc[-1]) else "N/A")
    col2.metric("ADX", f"{adx:.1f}")
    col3.metric("MACD", "Bullish" if float(macd_line.iloc[-1]) > float(signal_line.iloc[-1]) else "Bearish")
    col4.metric("Volumen-spike", "Ja" if spike.iloc[-1] else "Nej")
    col5.metric("ATR", f"${atr:.2f}")

    if label == 'KØB' and adx >= 25:
        st.divider()
        st.subheader("Handelsstrategi")
        rr = levels['rr']
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Entry zone", f"${levels['entry_low']:.2f} – ${levels['entry_high']:.2f}")
        c2.metric("Stop-loss (2×ATR)", f"${levels['stop_loss']:.2f}")
        c3.metric("Target 1 (50% profit)", f"${levels['t1']:.2f}",
                  delta=f"+{(levels['t1'] - levels['entry_mid']) / levels['entry_mid'] * 100:.1f}%")
        c4.metric("Target 2 (trailing)", f"${levels['t2']:.2f}",
                  delta=f"+{(levels['t2'] - levels['entry_mid']) / levels['entry_mid'] * 100:.1f}%")
        c5.metric("Risk/Reward", f"1:{rr}", delta="✅ Anbefalet" if rr >= 1.5 else "⚠️ Lav R:R")
        if rr < 1.0:
            st.warning("R:R under 1.0 — ikke anbefalet entry.")

    # Multi-timeframe confirmation
    st.divider()
    st.subheader("Multi-timeframe bekræftelse")
    with st.spinner("Henter timeframe-data..."):
        mtf = _get_mtf_signals(ticker)
    st.dataframe(pd.DataFrame(mtf), use_container_width=True, hide_index=True)
    daily_trend = next((r['Trend'] for r in mtf if r['Tidshorisont'] == 'Daglig'), '—')
    weekly_trend = next((r['Trend'] for r in mtf if r['Tidshorisont'] == 'Ugentlig'), '—')
    if 'Bullish' in daily_trend and 'Bullish' in weekly_trend:
        st.success("Daglig + ugentlig peger begge op — stærkt signal.")
    elif 'Bearish' in daily_trend and 'Bearish' in weekly_trend:
        st.error("Daglig + ugentlig peger begge ned.")
    else:
        st.info("Blandet timeframe — afvent alignment.")
