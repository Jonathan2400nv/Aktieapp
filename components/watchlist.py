import json
import os
import re
import streamlit as st

_DEFAULT_WATCHLIST = ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN"]
_WATCHLIST_PATH = "watchlist.json"


def parse_tickers(text: str) -> list[str]:
    parts = re.split(r"[,\n]+", text)
    return [p.strip().upper() for p in parts if p.strip()]


def format_tickers(tickers: list[str]) -> str:
    return "\n".join(tickers)


def load_watchlist(path: str = _WATCHLIST_PATH) -> list[str]:
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            return data
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        pass
    return list(_DEFAULT_WATCHLIST)


def save_watchlist(tickers: list[str], path: str = _WATCHLIST_PATH) -> None:
    try:
        with open(path, "w") as f:
            json.dump(tickers, f)
    except Exception:
        pass


def render_watchlist_sidebar() -> list[str]:
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = load_watchlist()

    st.sidebar.header("Watchlist")
    text = st.sidebar.text_area(
        "Aktier (én per linje eller kommasepareret)",
        value=format_tickers(st.session_state.watchlist),
        height=200,
        key="watchlist_input",
    )

    if st.sidebar.button("Gem watchlist"):
        tickers = parse_tickers(text)
        if tickers:
            st.session_state.watchlist = tickers
            save_watchlist(tickers)
            st.sidebar.success(f"{len(tickers)} aktier gemt.")
        else:
            st.sidebar.warning("Ingen gyldige tickers fundet.")

    if not os.access(".", os.W_OK):
        st.sidebar.caption(
            "Streamlit Cloud: Watchlist nulstilles ved reload. "
            "Hardkod din liste i `_DEFAULT_WATCHLIST` for permanent gemmelse."
        )

    return st.session_state.watchlist
