# modules/portfolio.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from services.portfolio_service import (
    load_portfolio, save_portfolio, backfill_positions,
    scan_watchlist_for_signals, calculate_pnl,
    get_current_price, get_performance_data,
)


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


def render(watchlist: list[str]) -> None:
    st.header("📈 Modelportefølje")
    st.caption("Lanceret 01.06.2025 · 100.000 kr. startkapital · Følger automatisk KØB-signaler")

    with st.spinner("Opdaterer portefølje..."):
        portfolio = load_portfolio()
        portfolio = backfill_positions(portfolio)

        if watchlist:
            new_positions = scan_watchlist_for_signals(watchlist, portfolio)
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
        if price:
            current_prices[pos["ticker"]] = price

    # P&L for all positions
    all_pnl_kr = sum(
        calculate_pnl(pos, current_prices.get(pos["ticker"], pos["entry_price"]), position_size)["pnl_kr"]
        for pos in active
    ) + sum(
        calculate_pnl(pos, pos["close_price"] or pos["entry_price"], position_size)["pnl_kr"]
        for pos in closed
    )
    portfolio_value = portfolio["start_capital"] + all_pnl_kr
    total_return_pct = all_pnl_kr / portfolio["start_capital"]

    # Get performance data to derive SPY return for outperformance
    with st.spinner("Henter historisk kursdata..."):
        dates, pvals, svals = get_performance_data(portfolio)

    # Compute SPY return from svals (derived from get_performance_data)
    spy_return_pct = (svals[-1] / svals[0] - 1) if len(svals) >= 2 else 0.0
    outperformance = total_return_pct - spy_return_pct

    # --- KPI row ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Samlet afkast",
        f"{'+' if total_return_pct >= 0 else ''}{total_return_pct * 100:.1f}%",
        f"{'+' if all_pnl_kr >= 0 else ''}{all_pnl_kr:,.0f} kr.",
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

    st.divider()

    # --- Performance chart ---
    if dates:
        st.plotly_chart(_build_chart(dates, pvals, svals), use_container_width=True)
    else:
        st.caption("Ikke nok data til at vise performance-kurve endnu.")

    st.divider()

    # --- Active positions ---
    if active:
        st.subheader("Aktive positioner")
        st.caption("Aktie · Kilde · Indgang · Nuv. · Afkast% · Afkast kr. · Stop-loss · T1/T2 · Status")
        for pos in active:
            current = current_prices.get(pos["ticker"], pos["entry_price"])
            pnl = calculate_pnl(pos, current, position_size)
            status = _status_label(pos, current)
            status_color = "green" if status == "Aktiv" else ("orange" if "T1" in status else "red")

            with st.container():
                c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([1.5, 1.5, 1.2, 1.2, 1, 1, 1, 1, 1.2])
                c1.write(f"**{pos['ticker']}**")
                c2.caption(pos["source"])
                c3.write(f"${pos['entry_price']:.2f}")
                c4.write(f"${current:.2f}")
                c5.write(_fmt_pct(pnl["pnl_pct"]))
                c6.write(_fmt_kr(pnl["pnl_kr"]))
                c7.write(f":red[${pos['stop_loss']:.2f}]")
                c8.write(f"${pos['t1']:.2f} / ${pos['t2']:.2f}")
                c9_col, c10_col = c9.columns(2)
                c9_col.write(f":{status_color}[{status}]")
                if c10_col.button("Luk", key=f"close_{pos['ticker']}"):
                    pos.update(
                        status="closed",
                        close_price=current,
                        close_date=str(pd.Timestamp.now(tz="UTC").date()),
                        close_reason="manual",
                    )
                    save_portfolio(portfolio)
                    st.rerun()
    else:
        st.info("Ingen aktive positioner. Tilføj aktier til din watchlist for at starte scanning.")

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
