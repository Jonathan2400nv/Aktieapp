import pandas as pd
import streamlit as st


@st.cache_data(ttl=86400)
def get_universe() -> list[str]:
    tickers = set()

    sources = [
        # US
        ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", 0, "Symbol"),
        ("https://en.wikipedia.org/wiki/Nasdaq-100", 4, "Ticker"),
        # Europe
        ("https://en.wikipedia.org/wiki/DAX", 4, "Ticker"),
        ("https://en.wikipedia.org/wiki/CAC_40", 4, "Ticker"),
        ("https://en.wikipedia.org/wiki/FTSE_100_Index", 4, "EPIC"),
        ("https://en.wikipedia.org/wiki/EURO_STOXX_50", 4, "Ticker"),
    ]

    for url, table_idx, col in sources:
        try:
            tables = pd.read_html(url)
            for t in tables:
                if col in t.columns:
                    vals = t[col].dropna().astype(str).tolist()
                    tickers.update(vals)
                    break
        except Exception:
            pass

    cleaned = set()
    for t in tickers:
        t = t.strip().replace("\xa0", "").replace(" ", "")
        if not t or len(t) > 10 or t.lower() in ("ticker", "symbol", "epic"):
            continue
        # Fix London Stock Exchange tickers — Wikipedia uses plain symbol, yfinance needs .L
        # We detect them heuristically after FTSE fetch by checking they're not in the US set
        cleaned.add(t)

    return sorted(cleaned)


@st.cache_data(ttl=86400)
def get_us_tickers() -> list[str]:
    tickers = set()
    for url, idx, col in [
        ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", 0, "Symbol"),
        ("https://en.wikipedia.org/wiki/Nasdaq-100", 4, "Ticker"),
    ]:
        try:
            tables = pd.read_html(url)
            for t in tables:
                if col in t.columns:
                    tickers.update(t[col].dropna().astype(str).tolist())
                    break
        except Exception:
            pass
    return sorted({t.strip().replace(".", "-") for t in tickers if t.strip()})


@st.cache_data(ttl=86400)
def get_european_tickers() -> list[str]:
    """Returns European tickers with yfinance suffixes."""
    result = set()

    # DAX — Frankfurt (.DE)
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/DAX")
        for t in tables:
            if "Ticker" in t.columns:
                for val in t["Ticker"].dropna().astype(str):
                    val = val.strip()
                    if val and not val.lower().startswith("ticker"):
                        result.add(val if "." in val else val + ".DE")
                break
    except Exception:
        pass

    # CAC 40 — Paris (.PA)
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/CAC_40")
        for t in tables:
            if "Ticker" in t.columns:
                for val in t["Ticker"].dropna().astype(str):
                    val = val.strip()
                    if val and not val.lower().startswith("ticker"):
                        result.add(val if "." in val else val + ".PA")
                break
    except Exception:
        pass

    # FTSE 100 — London (.L)
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/FTSE_100_Index")
        for t in tables:
            if "EPIC" in t.columns:
                for val in t["EPIC"].dropna().astype(str):
                    val = val.strip()
                    if val and not val.lower().startswith("epic"):
                        result.add(val + ".L")
                break
    except Exception:
        pass

    # EURO STOXX 50 (mix of exchanges — use .AS/.PA/.DE/.MI etc already in ticker)
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/EURO_STOXX_50")
        for t in tables:
            if "Ticker" in t.columns:
                for val in t["Ticker"].dropna().astype(str):
                    val = val.strip()
                    if val and not val.lower().startswith("ticker") and len(val) <= 12:
                        result.add(val)
                break
    except Exception:
        pass

    # C25 — Copenhagen (.CO)
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/OMX_Copenhagen_25")
        for t in tables:
            for col in ("Ticker", "Symbol", "Company"):
                if col in t.columns:
                    for val in t[col].dropna().astype(str):
                        val = val.strip()
                        if val and len(val) <= 10 and not val.lower() in (col.lower(), "ticker", "symbol"):
                            result.add(val + ".CO")
                    break
    except Exception:
        pass

    return sorted(result)
