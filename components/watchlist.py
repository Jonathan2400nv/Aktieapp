import json
import os
import re
import streamlit as st

_DEFAULT_WATCHLIST = ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN"]
_WATCHLIST_PATH = "watchlist.json"


def parse_tickers(text: str) -> list[str]:
    parts = re.split(r"[,\n\s]+", text)
    return [p.strip().upper() for p in parts if p.strip() and re.match(r'^[A-Z0-9.\-]{1,10}$', p.strip().upper())]


def format_tickers(tickers: list[str]) -> str:
    return "\n".join(tickers)


def load_watchlist(path: str = _WATCHLIST_PATH) -> list[str]:
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            return data
    except Exception:
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

    with st.sidebar:
        st.markdown("### Watchlist")

        wl = st.session_state.watchlist
        if wl:
            for ticker in wl:
                col_name, col_btn = st.columns([5, 1])
                col_name.markdown(
                    f'<div style="line-height:2;font-size:13px;font-weight:500">{ticker}</div>',
                    unsafe_allow_html=True,
                )
                if col_btn.button("✕", key=f"rm_{ticker}", help=f"Fjern {ticker}"):
                    st.session_state.watchlist = [t for t in wl if t != ticker]
                    save_watchlist(st.session_state.watchlist)
                    st.rerun()
        else:
            st.caption("Ingen aktier endnu.")

        st.divider()

        new = st.text_input(
            "Tilføj ticker",
            placeholder="f.eks. AAPL, NOVO-B.CO",
            key="new_ticker_input",
            label_visibility="collapsed",
        )
        if st.button("＋ Tilføj", use_container_width=True, type="primary"):
            tickers = parse_tickers(new)
            if tickers:
                existing = set(st.session_state.watchlist)
                added = [t for t in tickers if t not in existing]
                if added:
                    st.session_state.watchlist = st.session_state.watchlist + added
                    save_watchlist(st.session_state.watchlist)
                    st.rerun()
                else:
                    st.warning("Allerede på listen.")
            else:
                st.warning("Ugyldig ticker.")

        if not os.access(".", os.W_OK):
            st.caption("⚠️ Watchlist nulstilles ved reload på Streamlit Cloud.")

    return st.session_state.watchlist
