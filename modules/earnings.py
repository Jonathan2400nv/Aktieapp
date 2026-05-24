import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from services.yfinance_service import fetch_earnings_for_ticker


def render(watchlist: list[str]) -> None:
    st.header("Earnings Kalender")

    if not watchlist:
        st.warning("Tilføj aktier til din watchlist i sidebaren.")
        return

    with st.spinner("Henter earnings-datoer..."):
        rows = [fetch_earnings_for_ticker(t) for t in watchlist]
        rows = [r for r in rows if r is not None]

    if not rows:
        st.warning("Ingen earnings-data tilgængelig for din watchlist.")
        return

    df = pd.DataFrame(rows)
    df.columns = ['Ticker', 'Navn', 'Earnings Dato']
    df = df.sort_values('Earnings Dato', na_position='last').reset_index(drop=True)

    now = datetime.now()
    soon = now + timedelta(days=7)

    def highlight_soon(row):
        try:
            date = pd.Timestamp(row['Earnings Dato'])
            if not pd.isna(date) and now.date() <= date.date() <= soon.date():
                return ['background-color: #7d6608'] * len(row)
        except Exception:
            pass
        return [''] * len(row)

    st.dataframe(df.style.apply(highlight_soon, axis=1), use_container_width=True)
    st.caption("Gul baggrund = earnings inden for 7 dage")
