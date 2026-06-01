import streamlit as st
import yfinance as yf
import pandas as pd


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    # Drop duplicate columns that can appear after flattening
    df = df.loc[:, ~df.columns.duplicated()]
    return df


@st.cache_data(ttl=3600)
def fetch_ohlcv(ticker: str, period: str = "6mo") -> pd.DataFrame | None:
    # Try yf.download first, fall back to Ticker.history
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if not df.empty:
            return _normalize_df(df)
    except Exception:
        pass

    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        if not df.empty:
            return _normalize_df(df)
    except Exception:
        pass

    return None


@st.cache_data(ttl=3600)
def fetch_earnings_for_ticker(ticker: str) -> dict | None:
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        name = info.get('longName', ticker)

        earnings_date = None
        try:
            cal = t.calendar
            if isinstance(cal, dict) and cal:
                dates = cal.get('Earnings Date', [])
                earnings_date = dates[0] if dates else None
            elif hasattr(cal, 'loc') and not cal.empty:
                if 'Earnings Date' in cal.index:
                    earnings_date = cal.loc['Earnings Date'].iloc[0]
        except Exception:
            pass

        return {'ticker': ticker, 'name': name, 'earnings_date': earnings_date}
    except Exception:
        return None
