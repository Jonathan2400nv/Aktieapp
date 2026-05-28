import streamlit as st
import pandas as pd
from services.saxo_service import (
    get_auth_url,
    exchange_code,
    refresh_access_token,
    get_accounts,
    get_positions,
    get_balance,
    find_uic,
    place_order,
)
from services.yfinance_service import fetch_ohlcv
from utils.calculations import calculate_ma, calculate_rsi, get_signal

_STOP_LOSS_PCT = 0.03
_TAKE_PROFIT_PCT = 0.06
_TRADE_AMOUNT = 1  # antal aktier per ordre


def _get_token() -> str | None:
    return st.session_state.get("saxo_access_token")


def _get_client_key() -> str | None:
    return st.session_state.get("saxo_client_key")


def _get_account_key() -> str | None:
    return st.session_state.get("saxo_account_key")


def _handle_oauth_callback() -> None:
    params = st.query_params
    code = params.get("code")
    state = params.get("state")
    if not code or state != "saxo_auth":
        return

    with st.spinner("Logger ind på Saxo..."):
        tokens = exchange_code(code)

    if not tokens or "access_token" not in tokens:
        st.error("Login mislykkedes — prøv igen.")
        return

    st.session_state.saxo_access_token = tokens["access_token"]
    st.session_state.saxo_refresh_token = tokens.get("refresh_token")

    accounts = get_accounts(tokens["access_token"])
    if accounts:
        st.session_state.saxo_client_key = accounts[0].get("ClientKey")
        st.session_state.saxo_account_key = accounts[0].get("AccountKey")

    st.query_params.clear()
    st.rerun()


def _render_login() -> None:
    st.markdown("### Log ind på Saxo Simulation")
    st.info(
        "Du kobles til Saxo Banks simulation-miljø (ingen rigtige penge). "
        "Klik knappen herunder for at logge ind med din Saxo-konto."
    )
    auth_url = get_auth_url()
    st.link_button("Log ind med Saxo Bank", auth_url, type="primary")


def _render_portfolio() -> None:
    access_token = _get_token()
    client_key = _get_client_key()

    col_left, col_right = st.columns([3, 1])
    with col_right:
        if st.button("Log ud"):
            for k in ["saxo_access_token", "saxo_refresh_token", "saxo_client_key", "saxo_account_key"]:
                st.session_state.pop(k, None)
            st.rerun()

    # --- Saldo ---
    balance = get_balance(access_token, client_key)
    if balance:
        b1, b2, b3 = st.columns(3)
        b1.metric("Samlet værdi", f"${balance.get('TotalValue', 0):,.2f}")
        b2.metric("Kontanter", f"${balance.get('CashBalance', 0):,.2f}")
        b3.metric("Urealiseret P/L", f"${balance.get('UnrealizedPositionsValue', 0):,.2f}")

    st.divider()

    # --- Positioner ---
    st.subheader("Åbne positioner")
    positions = get_positions(access_token, client_key)
    if not positions:
        st.info("Ingen åbne positioner.")
    else:
        rows = []
        for p in positions:
            base = p.get("PositionBase", {})
            view = p.get("PositionView", {})
            fmt = p.get("DisplayAndFormat", {})
            rows.append({
                "Symbol": fmt.get("Symbol", "—"),
                "Navn": fmt.get("Description", "—"),
                "Antal": base.get("Amount", 0),
                "Indgang": f"${base.get('OpenPrice', 0):.2f}",
                "Nuværende": f"${view.get('CurrentPrice', 0):.2f}",
                "P/L": f"${view.get('ProfitLossOnTrade', 0):.2f}",
                "P/L %": f"{view.get('ProfitLossOnTradeInBaseCurrency', 0) / max(base.get('OpenPrice', 1) * base.get('Amount', 1), 1) * 100:.1f}%",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_auto_trade(watchlist: list[str]) -> None:
    st.subheader("Auto-trading baseret på swing signaler")
    st.caption(f"Stop-loss: {_STOP_LOSS_PCT*100:.0f}% under indgang  •  Take-profit: {_TAKE_PROFIT_PCT*100:.0f}% over indgang  •  {_TRADE_AMOUNT} aktie(r) per ordre")

    if not watchlist:
        st.warning("Tilføj aktier til watchlisten i sidebaren.")
        return

    with st.spinner("Beregner signaler..."):
        signal_rows = []
        for ticker in watchlist:
            df = fetch_ohlcv(ticker)
            if df is None or df.empty or len(df) < 50:
                continue
            close = df["Close"].squeeze()
            ma20 = calculate_ma(close, 20)
            ma50 = calculate_ma(close, 50)
            rsi = calculate_rsi(close, 14)
            signal = get_signal(rsi, ma20, ma50)
            current_price = float(close.iloc[-1])
            signal_rows.append({
                "ticker": ticker,
                "signal": signal,
                "price": current_price,
                "rsi": round(float(rsi.iloc[-1]), 1),
            })

    if not signal_rows:
        st.warning("Kunne ikke hente data for nogen aktier.")
        return

    for row in signal_rows:
        ticker = row["ticker"]
        signal = row["signal"]
        price = row["price"]
        rsi_val = row["rsi"]

        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 2])
        col1.write(f"**{ticker}**")
        col2.write(signal or "Neutral")
        col3.write(f"${price:.2f}")
        col4.write(f"RSI {rsi_val}")

        if signal == "Bullish":
            stop = round(price * (1 - _STOP_LOSS_PCT), 2)
            tp = round(price * (1 + _TAKE_PROFIT_PCT), 2)
            if col5.button(f"Køb {ticker}", key=f"buy_{ticker}", type="primary"):
                _execute_trade(ticker, buy=True, price=price, stop=stop, tp=tp)
        elif signal == "Bearish":
            stop = round(price * (1 + _STOP_LOSS_PCT), 2)
            tp = round(price * (1 - _TAKE_PROFIT_PCT), 2)
            if col5.button(f"Sælg {ticker}", key=f"sell_{ticker}"):
                _execute_trade(ticker, buy=False, price=price, stop=stop, tp=tp)
        else:
            col5.write("—")


def _execute_trade(ticker: str, buy: bool, price: float, stop: float, tp: float) -> None:
    access_token = _get_token()
    account_key = _get_account_key()

    with st.spinner(f"Finder UIC for {ticker}..."):
        uic = find_uic(access_token, ticker)

    if not uic:
        st.error(f"Kunne ikke finde {ticker} på Saxo — prøv et andet symbol.")
        return

    with st.spinner(f"Placerer ordre for {ticker}..."):
        result = place_order(
            access_token=access_token,
            account_key=account_key,
            uic=uic,
            buy=buy,
            amount=_TRADE_AMOUNT,
            stop_loss_price=stop,
            take_profit_price=tp,
        )

    if result and "error" not in result:
        direction = "Købt" if buy else "Solgt"
        st.success(
            f"{direction} {_TRADE_AMOUNT} stk. {ticker} @ ~${price:.2f}  |  "
            f"Stop-loss: ${stop:.2f}  |  Take-profit: ${tp:.2f}"
        )
    else:
        err = result.get("error", "Ukendt fejl") if result else "Ingen respons fra Saxo"
        st.error(f"Ordre fejlede: {err}")


def render(watchlist: list[str]) -> None:
    st.header("Saxo Bank Simulation Trading")

    _handle_oauth_callback()

    if not _get_token():
        _render_login()
        return

    _render_portfolio()
    st.divider()
    _render_auto_trade(watchlist)
