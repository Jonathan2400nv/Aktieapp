# modules/portfolio.py
import json
from datetime import date, timedelta
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from services.portfolio_service import (
    load_portfolio, save_portfolio, backfill_positions,
    backfill_historical_signals, scan_watchlist_for_signals,
    calculate_pnl, get_current_price, get_performance_data,
)
from services.market_universe import get_us_tickers, get_european_tickers


@st.cache_data(ttl=900)
def _cached_universe() -> tuple[str, ...]:
    return tuple(sorted(set(get_us_tickers() + get_european_tickers())))


@st.cache_data(ttl=900)
def _cached_scan(portfolio_json: str) -> list[dict]:
    import json as _json
    portfolio = _json.loads(portfolio_json)
    universe = list(_cached_universe())
    return scan_watchlist_for_signals(universe, portfolio)


@st.cache_data(ttl=900)
def _cached_performance(portfolio_json: str) -> tuple[list[str], list[float], list[float]]:
    import json as _json
    portfolio = _json.loads(portfolio_json)
    return get_performance_data(portfolio)


def _status_label(pos: dict, current: float) -> str:
    entry = pos["entry_price"]
    t1 = pos["t1"]
    sl = pos["stop_loss"]
    if current >= entry + 0.9 * (t1 - entry):
        return "T1 nær ✅"
    if sl < entry and current <= entry + 0.7 * (sl - entry):
        return "⚠️ SL nær"
    return "Aktiv"


def _fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v * 100:.1f}%"


def _fmt_kr(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:,.0f} kr."


def _build_chart(dates: list, portfolio_vals: list, spy_vals: list) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=portfolio_vals,
        mode="lines", name="Modelportefølje",
        line=dict(color="#4caf50", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=spy_vals,
        mode="lines", name="S&P 500 (SPY)",
        line=dict(color="#888888", width=1.5, dash="dash"),
    ))
    fig.update_layout(
        template="plotly_dark",
        height=280,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        yaxis=dict(tickformat=",.0f", ticksuffix=" kr."),
        xaxis=dict(showgrid=False),
        hovermode="x unified",
    )
    return fig


def _status_badge(status: str) -> str:
    if "T1" in status:
        bg, color = "#2a2000", "#ffc107"
    elif "SL" in status:
        bg, color = "#2a0000", "#f44336"
    else:
        bg, color = "#0a2a0a", "#4caf50"
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}33;'
        f'border-radius:4px;padding:2px 8px;font-size:11px;white-space:nowrap">{status}</span>'
    )


def _render_active_table(active: list, current_prices: dict, position_size: int) -> None:
    th = "padding:10px 12px;text-align:left;color:#666;font-size:11px;font-weight:500;border-bottom:1px solid #222;white-space:nowrap"
    td_base = "padding:10px 12px;border-bottom:1px solid #1a1a1a;font-size:13px;vertical-align:middle"

    rows_html = ""
    for pos in active:
        current = current_prices.get(pos["ticker"], pos["entry_price"])
        pnl = calculate_pnl(pos, current, position_size)
        status = _status_label(pos, current)

        pct = pnl["pnl_pct"]
        kr = pnl["pnl_kr"]
        pct_color = "#4caf50" if pct >= 0 else "#f44336"
        pct_str = f"{'+' if pct >= 0 else ''}{pct * 100:.1f}%"
        kr_str = f"{'+' if kr >= 0 else ''}{kr:,.0f} kr."

        move = current - pos["entry_price"]
        move_color = "#4caf50" if move >= 0 else "#f44336"
        move_arrow = "▲" if move >= 0 else "▼"

        sim_tag = ""
        if pos.get("simulated"):
            sim_tag = ' <span style="color:#555;font-size:10px">sim</span>'

        rows_html += f"""
        <tr>
          <td style="{td_base}">
            <span style="font-weight:600;color:#fff;font-size:14px">{pos['ticker']}</span>{sim_tag}
            <div style="color:#555;font-size:10px;margin-top:2px">{pos['entry_date']}</div>
          </td>
          <td style="{td_base};color:#888;font-size:11px">{pos['source']}</td>
          <td style="{td_base};color:#aaa;font-family:monospace">${pos['entry_price']:.2f}</td>
          <td style="{td_base};font-family:monospace">
            <span style="color:{move_color}">{move_arrow} ${current:.2f}</span>
          </td>
          <td style="{td_base};font-weight:600;color:{pct_color};font-family:monospace">{pct_str}</td>
          <td style="{td_base};color:{pct_color};font-family:monospace">{kr_str}</td>
          <td style="{td_base};color:#f44336;font-family:monospace">${pos['stop_loss']:.2f}</td>
          <td style="{td_base};font-family:monospace">
            <span style="color:#ffc107">${pos['t1']:.2f}</span>
            <span style="color:#444"> / </span>
            <span style="color:#4caf50">${pos['t2']:.2f}</span>
          </td>
          <td style="{td_base}">{_status_badge(status)}</td>
        </tr>"""

    html = f"""
    <table style="width:100%;border-collapse:collapse;font-family:'Source Sans Pro',sans-serif">
      <thead>
        <tr>
          <th style="{th}">Aktie</th>
          <th style="{th}">Kilde</th>
          <th style="{th}">Indgang</th>
          <th style="{th}">Nuværende</th>
          <th style="{th}">Afkast %</th>
          <th style="{th}">Afkast kr.</th>
          <th style="{th}">Stop-loss</th>
          <th style="{th}">T1 / T2</th>
          <th style="{th}">Status</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    """
    st.markdown(html, unsafe_allow_html=True)


_PERIOD_OPTIONS = {
    "Seneste måned": 30,
    "3 måneder": 90,
    "6 måneder": 180,
    "År til dato": None,  # special case
    "Seneste år": 365,
    "Alt": 0,  # 0 = no filter
}


def _filter_series(dates: list[str], pvals: list[float], svals: list[float], period_label: str) -> tuple[list[str], list[float], list[float]]:
    if not dates:
        return dates, pvals, svals
    today = date.today()
    days = _PERIOD_OPTIONS[period_label]
    if days == 0:
        return dates, pvals, svals
    if days is None:  # År til dato
        cutoff = date(today.year, 1, 1)
    else:
        cutoff = today - timedelta(days=days)
    filtered = [(d, p, s) for d, p, s in zip(dates, pvals, svals) if date.fromisoformat(d) >= cutoff]
    if not filtered:
        return dates, pvals, svals
    fd, fp, fs = zip(*filtered)
    return list(fd), list(fp), list(fs)


def _period_kpis(pvals: list[float], svals: list[float], start_capital: float) -> tuple[float, float, float]:
    """Returns (period_return_pct, period_pnl_kr, outperformance_pp) for the filtered window."""
    if len(pvals) < 2:
        return 0.0, 0.0, 0.0
    p_start, p_end = pvals[0], pvals[-1]
    s_start, s_end = svals[0], svals[-1]
    period_return = (p_end - p_start) / p_start if p_start else 0.0
    spy_return = (s_end - s_start) / s_start if s_start else 0.0
    pnl_kr = p_end - p_start
    return period_return, pnl_kr, period_return - spy_return


def render(watchlist: list[str]) -> None:
    st.header("📈 Modelportefølje")
    st.caption("Lanceret 01.06.2025 · 100.000 kr. startkapital · Scanner S&P 500, NASDAQ, DAX, CAC 40, FTSE 100, EURO STOXX 50 og C25")

    with st.spinner("Opdaterer portefølje..."):
        portfolio = load_portfolio()

        if not portfolio.get("historical_backfill_complete"):
            universe = list(_cached_universe())
            with st.spinner("Simulerer historisk performance fra 01.06.2025 (kører én gang — tager 1-2 min)..."):
                portfolio = backfill_historical_signals(portfolio, universe)

        portfolio = backfill_positions(portfolio)

        new_positions = _cached_scan(json.dumps(portfolio, default=str))
        if new_positions:
            active_tickers = {p["ticker"] for p in portfolio["positions"] if p["status"] == "active"}
            for pos in new_positions:
                if pos["ticker"] not in active_tickers:
                    portfolio["positions"].append(pos)
                    active_tickers.add(pos["ticker"])
            save_portfolio(portfolio)

    active = [p for p in portfolio["positions"] if p["status"] == "active"]
    closed = [p for p in portfolio["positions"] if p["status"] == "closed"]
    position_size = portfolio["position_size"]

    # Current prices for active positions
    current_prices: dict[str, float] = {}
    for pos in active:
        price = get_current_price(pos["ticker"])
        if price is not None:
            current_prices[pos["ticker"]] = price

    # Full performance data (all time)
    with st.spinner("Henter historisk kursdata..."):
        dates, pvals, svals = _cached_performance(json.dumps(portfolio, default=str))

    # --- Period selector ---
    period_cols = st.columns(len(_PERIOD_OPTIONS))
    if "portfolio_period" not in st.session_state:
        st.session_state.portfolio_period = "Alt"
    for i, label in enumerate(_PERIOD_OPTIONS):
        if period_cols[i].button(
            label,
            use_container_width=True,
            type="primary" if st.session_state.portfolio_period == label else "secondary",
        ):
            st.session_state.portfolio_period = label
            st.rerun()

    selected_period = st.session_state.portfolio_period
    fdates, fpvals, fsvals = _filter_series(dates, pvals, svals, selected_period)

    # KPIs for the selected period
    period_return_pct, period_pnl_kr, outperformance = _period_kpis(fpvals, fsvals, portfolio["start_capital"])
    portfolio_value = fpvals[-1] if fpvals else portfolio["start_capital"]

    # --- KPI row ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        f"Afkast ({selected_period.lower()})",
        f"{'+' if period_return_pct >= 0 else ''}{period_return_pct * 100:.1f}%",
        f"{'+' if period_pnl_kr >= 0 else ''}{period_pnl_kr:,.0f} kr.",
    )
    col2.metric("Porteføljeværdi", f"{portfolio_value:,.0f} kr.")
    col3.metric(
        "vs. S&P 500",
        f"{'+' if outperformance >= 0 else ''}{outperformance * 100:.1f} pp",
    )
    col4.metric(
        "Positioner",
        f"{len(active)} aktive",
        f"{len(closed)} lukkede",
        delta_color="off",
    )

    # --- Disclaimer ---
    if portfolio.get("historical_backfill_complete") and portfolio.get("backfill_date"):
        with st.expander("ℹ️ Om den historiske performance"):
            st.markdown(
                f"""
**Dele af denne performance er simuleret.**

Positioner fra **01.06.2025** til **{portfolio['backfill_date']}** er rekonstrueret
baseret på de tekniske signaler der var tilgængelige på de pågældende datoer.
Ingen fremtidig data er brugt *(ingen look-ahead bias)*.

**Forbehold:**
- Scanningen kørte ugentligt i simuleringen — ikke dagligt som i live-drift
- Aktiver der er udgået af indeksene siden 2025 er ikke medtaget *(survivorship bias)*
- Indgangspris er closing-kurs på signaldagen, ikke næste dags åbningskurs

Dette er **ikke professionel backtesting** — det er en indikation af strategiens historiske adfærd.
                """
            )

    st.divider()

    # --- Performance chart ---
    if fdates:
        st.plotly_chart(_build_chart(fdates, fpvals, fsvals), use_container_width=True)
    else:
        st.caption("Ikke nok data til at vise performance-kurve endnu.")

    st.divider()

    # --- Active positions ---
    if active:
        st.subheader("Aktive positioner")
        _render_active_table(active, current_prices, position_size)
    else:
        st.info("Ingen aktive positioner endnu — scanner S&P 500, NASDAQ, DAX, CAC 40, FTSE 100, EURO STOXX 50 og C25 automatisk.")

    st.divider()

    # --- Closed positions ---
    if closed:
        st.subheader("Lukkede positioner")
        rows = []
        for pos in closed:
            pnl = calculate_pnl(pos, pos["close_price"] or pos["entry_price"], position_size)
            reason_map = {
                "stop_loss": "Stop-loss ❌",
                "t2": "T2 ramt ✅",
                "manual": "Manuel lukket",
            }
            rows.append({
                "Aktie": pos["ticker"],
                "Kilde": pos["source"],
                "Indgang": f"${pos['entry_price']:.2f}",
                "Udgang": f"${pos['close_price']:.2f}" if pos["close_price"] else "—",
                "Afkast %": _fmt_pct(pnl["pnl_pct"]),
                "Afkast kr.": _fmt_kr(pnl["pnl_kr"]),
                "Årsag": reason_map.get(pos.get("close_reason", ""), "—"),
                "Dato": pos.get("close_date", "—"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
