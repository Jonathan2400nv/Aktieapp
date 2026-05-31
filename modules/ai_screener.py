import streamlit as st
import pandas as pd
from services.screener_service import fetch_screener_data
from services.ai_screener_service import get_garp_analysis


def _fmt(val, suffix="", decimals=1, scale=1):
    if val is None:
        return "—"
    try:
        return f"{float(val) * scale:.{decimals}f}{suffix}"
    except Exception:
        return "—"


def _market_cap_str(val):
    if val is None:
        return "—"
    if val >= 1e12:
        return f"${val/1e12:.1f}T"
    if val >= 1e9:
        return f"${val/1e9:.1f}B"
    return f"${val/1e6:.0f}M"


def _recommendation_color(text: str) -> str:
    if not text:
        return "gray"
    t = text.upper()
    if "BUY" in t:
        return "green"
    if "SELL" in t:
        return "red"
    return "orange"


def render(watchlist: list[str]) -> None:
    st.header("AI Stock Screener")
    st.caption("GARP-analyse (Growth at a Reasonable Price) — Buy/Hold/Sell med begrundelse, DCF og stop-loss")

    if not watchlist:
        st.warning("Tilføj aktier til din watchlist i sidebaren.")
        return

    selected = st.multiselect(
        "Vælg aktier at analysere",
        options=watchlist,
        default=watchlist[:5] if len(watchlist) >= 5 else watchlist,
    )

    if not selected:
        return

    with st.expander("Filtre", expanded=False):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            filter_score = st.checkbox("Score ≥ 5 (KØB-kandidater)", value=False)
            filter_adx = st.checkbox("ADX > 25 (aktier i reel trend)", value=False)
            filter_divergence = st.checkbox("Bullish RSI-divergens", value=False)
        with f_col2:
            filter_squeeze = st.checkbox("Bollinger Squeeze", value=False)
            filter_rr = st.checkbox("R:R ≥ 1.5", value=False)

    if st.button("Kør AI Screener", type="primary"):
        st.session_state.screener_results = {}
        progress = st.progress(0, text="Henter data...")

        for i, ticker in enumerate(selected):
            progress.progress((i + 1) / len(selected), text=f"Analyserer {ticker}...")
            data = fetch_screener_data(ticker)
            if data:
                st.session_state.screener_results[ticker] = data

        progress.empty()

    if not st.session_state.get("screener_results"):
        return

    results = st.session_state.screener_results

    # --- Oversigtstabel ---
    st.subheader("Oversigt")
    rows = []
    for ticker, d in results.items():
        mos = None
        if d.get('dcf_fair_value') and d.get('current_price'):
            mos = round((d['dcf_fair_value'] - d['current_price']) / d['current_price'] * 100, 1)
        rows.append({
            "Ticker": ticker,
            "Navn": d.get('name', ticker)[:30],
            "Sektor": d.get('sector', '—'),
            "Kurs": _fmt(d.get('current_price'), '$', 2),
            "P/E": _fmt(d.get('pe'), '', 1),
            "Fwd P/E": _fmt(d.get('fwd_pe'), '', 1),
            "P/S": _fmt(d.get('ps'), 'x', 1),
            "ROE": _fmt(d.get('roe'), '%', 1, 100),
            "Rev. vækst": _fmt(d.get('rev_growth'), '%', 1, 100),
            "DCF Fair Value": _fmt(d.get('dcf_fair_value'), '$', 2),
            "Margin of Safety": f"{mos}%" if mos is not None else "—",
            "RSI": _fmt(d.get('rsi'), '', 1),
            "Stop-loss": _fmt(d.get('stop_loss'), '$', 2),
            "Market Cap": _market_cap_str(d.get('market_cap')),
            "Score": d.get('signal_score', '—'),
            "Signal": d.get('signal_label', '—'),
            "R:R": _fmt(d.get('rr'), '', 2),
        })

    if filter_score:
        rows = [r for r in rows if results.get(r['Ticker'], {}).get('signal_score', 0) >= 5]
    if filter_adx:
        rows = [r for r in rows if (results.get(r['Ticker'], {}).get('adx') or 0) > 25]
    if filter_divergence:
        rows = [r for r in rows if results.get(r['Ticker'], {}).get('rsi_divergence_bullish', False)]
    if filter_squeeze:
        rows = [r for r in rows if results.get(r['Ticker'], {}).get('bollinger_squeeze', False)]
    if filter_rr:
        rows = [r for r in rows if (results.get(r['Ticker'], {}).get('rr') or 0) >= 1.5]

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # --- Individuel AI-analyse ---
    st.subheader("AI-analyse per aktie")

    for ticker, d in results.items():
        with st.expander(f"**{ticker}** — {d.get('name', '')} ({d.get('sector', '—')})", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Kurs", _fmt(d.get('current_price'), '$', 2))
            col2.metric("DCF Fair Value", _fmt(d.get('dcf_fair_value'), '$', 2))

            mos = None
            if d.get('dcf_fair_value') and d.get('current_price'):
                mos = round((d['dcf_fair_value'] - d['current_price']) / d['current_price'] * 100, 1)
            col3.metric("Margin of Safety", f"{mos}%" if mos is not None else "—",
                        delta=f"{mos}%" if mos is not None else None)
            col4.metric("Stop-loss (2×ATR)", _fmt(d.get('stop_loss'), '$', 2))

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("P/E", _fmt(d.get('pe'), '', 1))
            c2.metric("Fwd P/E", _fmt(d.get('fwd_pe'), '', 1))
            c3.metric("P/S", _fmt(d.get('ps'), 'x', 1))
            c4.metric("ROE", _fmt(d.get('roe'), '%', 1, 100))
            c5.metric("Rev. vækst", _fmt(d.get('rev_growth'), '%', 1, 100))

            with st.spinner(f"Claude analyserer {ticker}..."):
                analysis = get_garp_analysis(d)

            if analysis:
                first_line = analysis.split('\n')[0].upper()
                if "BUY" in first_line:
                    st.success(analysis)
                elif "SELL" in first_line:
                    st.error(analysis)
                else:
                    st.warning(analysis)
            else:
                st.caption("AI-analyse ikke tilgængelig — tjek ANTHROPIC_API_KEY.")
