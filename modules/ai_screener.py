import streamlit as st
import pandas as pd
from services.screener_service import fetch_screener_data
from services.ai_screener_service import get_stock_analysis


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


def render(watchlist: list[str]) -> None:
    st.header("🔍 AI Stock Screener")
    st.caption("Multi-framework analyse — aktie-klassificering, Fair Value interval og bull/bear case")

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
            filter_score = st.checkbox("Momentum-score ≥ 5 (KØB-kandidater)", value=False)
            filter_adx = st.checkbox("ADX > 25 (aktier i reel trend)", value=False)
            filter_divergence = st.checkbox("Bullish RSI-divergens", value=False)
        with f_col2:
            filter_squeeze = st.checkbox("Bollinger Squeeze", value=False)
            filter_rr = st.checkbox("R:R ≥ 1.5", value=False)

    if st.button("Kør AI Screener", type="primary"):
        st.session_state.screener_results = {}
        st.session_state.screener_failed = []
        progress = st.progress(0, text="Henter data...")

        for i, ticker in enumerate(selected):
            progress.progress((i + 1) / len(selected), text=f"Henter {ticker}...")
            data = fetch_screener_data(ticker)
            if data:
                st.session_state.screener_results[ticker] = data
            else:
                st.session_state.screener_failed.append(ticker)

        progress.empty()

    failed = st.session_state.get("screener_failed", [])
    if failed:
        st.warning(f"Kunne ikke hente data for: {', '.join(failed)} — prøv 'Genindlæs data' i sidebaren.")

    if not st.session_state.get("screener_results"):
        return

    results = st.session_state.screener_results

    # --- Oversigtstabel ---
    st.subheader("Oversigt")
    rows = []
    for ticker, d in results.items():
        rows.append({
            "Ticker": ticker,
            "Navn": d.get('name', ticker)[:28],
            "Sektor": d.get('sector', '—'),
            "Kurs": _fmt(d.get('current_price'), '$', 2),
            "P/E": _fmt(d.get('pe'), '', 1),
            "EV/EBITDA": _fmt(d.get('ev_ebitda'), 'x', 1),
            "P/FCF": _fmt(d.get('price_to_fcf'), 'x', 1),
            "ROE": _fmt(d.get('roe'), '%', 1, 100),
            "Bruttomargin": _fmt(d.get('gross_margin'), '%', 1, 100),
            "Rev. vækst": _fmt(d.get('rev_growth'), '%', 1, 100),
            "DCF Base": _fmt(d.get('dcf_fair_value'), '$', 2),
            "Analytiker mål": _fmt(d.get('analyst_target'), '$', 2),
            "Momentum": f"{d.get('signal_score', '—')}/7",
            "Signal": d.get('signal_label', '—'),
            "R:R": _fmt(d.get('rr'), '', 2),
            "Market Cap": _market_cap_str(d.get('market_cap')),
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
        with st.expander(f"**{ticker}** — {d.get('name', '')} · {d.get('sector', '—')}", expanded=True):
            # Metrics row 1: valuation
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Kurs", _fmt(d.get('current_price'), '$', 2))
            c2.metric("DCF Bear / Base / Bull",
                      f"{_fmt(d.get('dcf_bear'), '$', 0)} – {_fmt(d.get('dcf_fair_value'), '$', 0)} – {_fmt(d.get('dcf_bull'), '$', 0)}")
            c3.metric("Analytiker mål", _fmt(d.get('analyst_target'), '$', 2),
                      f"{d.get('analyst_count', '—')} analytikere")
            c4.metric("EV/EBITDA", _fmt(d.get('ev_ebitda'), 'x', 1))
            c5.metric("P/FCF", _fmt(d.get('price_to_fcf'), 'x', 1))

            # Metrics row 2: quality
            q1, q2, q3, q4, q5 = st.columns(5)
            q1.metric("ROE", _fmt(d.get('roe'), '%', 1, 100))
            q2.metric("Bruttomargin", _fmt(d.get('gross_margin'), '%', 1, 100))
            q3.metric("FCF-konv.", _fmt(d.get('fcf_conversion'), 'x', 2))
            q4.metric("Gæld/EBITDA", _fmt(d.get('debt_ebitda'), 'x', 1))
            q5.metric("Momentum", f"{d.get('signal_score', '—')}/7 — {d.get('signal_label', '—')}")

            st.divider()

            with st.spinner(f"Claude analyserer {ticker}..."):
                analysis = get_stock_analysis(d)

            if analysis:
                st.markdown(analysis)
            else:
                st.caption("AI-analyse ikke tilgængelig — tjek at ANTHROPIC_API_KEY er konfigureret.")
