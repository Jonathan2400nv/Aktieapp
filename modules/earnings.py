import html
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from services.yfinance_service import fetch_earnings_for_ticker


def _days_label(date, now) -> tuple[str, str]:
    try:
        d = pd.Timestamp(date).date()
        delta = (d - now.date()).days
        if delta < 0:
            return f"for {abs(delta)}d siden", "#666"
        if delta == 0:
            return "I dag 🔔", "#f44336"
        if delta <= 7:
            return f"om {delta} dag{'e' if delta != 1 else ''} ⚡", "#ffc107"
        if delta <= 30:
            return f"om {delta} dage", "#4caf50"
        return f"{d.strftime('%d. %b %Y')}", "#888"
    except Exception:
        return "Ukendt", "#888"


def _card(row, now) -> str:
    label, color = _days_label(row["Earnings Dato"], now)
    try:
        date_str = pd.Timestamp(row["Earnings Dato"]).strftime("%d. %b %Y")
    except Exception:
        date_str = "—"
    ticker = html.escape(str(row["Ticker"]))
    name = html.escape(str(row["Navn"]))
    yf_url = f"https://finance.yahoo.com/quote/{row['Ticker']}/financials/"
    return (
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'padding:12px 16px;border-radius:10px;border:1px solid rgba(128,128,128,0.15);'
        f'margin-bottom:8px">'
        f'<div style="flex:1">'
        f'<span style="font-weight:600;font-size:15px">{ticker}</span>'
        f'<span style="color:#888;font-size:12px;margin-left:8px">{name}</span>'
        f'</div>'
        f'<div style="text-align:right;margin-right:16px">'
        f'<div style="font-size:12px;color:#888">{date_str}</div>'
        f'<div style="font-size:11px;font-weight:500;color:{color}">{label}</div>'
        f'</div>'
        f'<a href="{yf_url}" target="_blank" style="'
        f'text-decoration:none;white-space:nowrap;font-size:12px;font-weight:500;'
        f'padding:6px 12px;border-radius:6px;'
        f'border:1px solid rgba(128,128,128,0.35);color:#ccc;'
        f'background:rgba(128,128,128,0.08);'
        f'transition:background 0.15s">📊 Seneste earnings</a>'
        f'</div>'
    )


def render(watchlist: list[str]) -> None:
    st.header("📅 Earnings Kalender")
    st.caption("Næste rapporteringsdato for dine watchlist-aktier")

    if not watchlist:
        st.info("Tilføj aktier til din watchlist i sidebaren.")
        return

    with st.spinner("Henter earnings-datoer..."):
        rows = [fetch_earnings_for_ticker(t) for t in watchlist]
        rows = [r for r in rows if r is not None]

    if not rows:
        st.warning("Ingen earnings-data tilgængelig — prøv at klikke 'Genindlæs data' i sidebaren.")
        return

    df = pd.DataFrame(rows)
    df.columns = ["Ticker", "Navn", "Earnings Dato"]
    df = df.sort_values("Earnings Dato", na_position="last").reset_index(drop=True)

    now = datetime.now()
    soon_cutoff = now + timedelta(days=7)

    soon = []
    upcoming = []
    past = []
    unknown = []

    for _, row in df.iterrows():
        try:
            d = pd.Timestamp(row["Earnings Dato"]).date()
            if d < now.date():
                past.append(row)
            elif d <= soon_cutoff.date():
                soon.append(row)
            else:
                upcoming.append(row)
        except Exception:
            unknown.append(row)

    if soon:
        st.markdown("#### ⚡ Inden for 7 dage")
        st.markdown("".join(_card(r, now) for r in soon), unsafe_allow_html=True)

    if upcoming:
        st.markdown("#### 📆 Kommende")
        st.markdown("".join(_card(r, now) for r in upcoming), unsafe_allow_html=True)

    if past:
        st.markdown("#### 🕐 Senest rapporteret")
        st.markdown("".join(_card(r, now) for r in past), unsafe_allow_html=True)

    if unknown:
        st.markdown("#### ❓ Dato ukendt")
        st.markdown("".join(_card(r, now) for r in unknown), unsafe_allow_html=True)
