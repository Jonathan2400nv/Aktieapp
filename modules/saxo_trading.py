import threading
import time
import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

from services.saxo_service import (
    get_auth_url,
    exchange_code,
    get_accounts,
    get_positions,
    get_balance,
    find_uic,
    place_order,
)
from utils.calculations import calculate_ma, calculate_rsi, get_signal
from services.market_universe import get_us_tickers, get_european_tickers

_STOP_LOSS_PCT = 0.03
_TAKE_PROFIT_PCT = 0.06
_TRADE_AMOUNT = 1
_SCAN_INTERVAL_SECONDS = 300  # scan hvert 5. minut
_BATCH_SIZE = 50               # antal tickers per yfinance-batch


def _log(msg: str) -> None:
    if "trade_log" not in st.session_state:
        st.session_state.trade_log = []
    entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    st.session_state.trade_log.insert(0, entry)
    st.session_state.trade_log = st.session_state.trade_log[:200]


def _scan_and_trade(access_token: str, account_key: str, tickers: list[str]) -> None:
    """Kører i en baggrundstråd. Scanner tickers i batches og trader signaler."""
    traded_today: set[str] = set()

    while st.session_state.get("auto_trading_active"):
        _log(f"Starter scan af {len(tickers)} tickers...")
        signals_found = 0

        for i in range(0, len(tickers), _BATCH_SIZE):
            if not st.session_state.get("auto_trading_active"):
                break

            batch = tickers[i:i + _BATCH_SIZE]
            try:
                df_all = yf.download(
                    batch,
                    period="3mo",
                    progress=False,
                    auto_adjust=True,
                    group_by="ticker",
                    threads=True,
                )
            except Exception:
                continue

            for ticker in batch:
                if ticker in traded_today:
                    continue
                try:
                    if len(batch) == 1:
                        df = df_all
                    else:
                        df = df_all[ticker] if ticker in df_all.columns.get_level_values(0) else None

                    if df is None or df.empty or len(df) < 50:
                        continue

                    close = df["Close"].squeeze()
                    if close.isna().all():
                        continue

                    ma20 = calculate_ma(close, 20)
                    ma50 = calculate_ma(close, 50)
                    rsi = calculate_rsi(close, 14)
                    signal = get_signal(rsi, ma20, ma50)

                    if signal not in ("Bullish", "Bearish"):
                        continue

                    price = float(close.iloc[-1])
                    buy = signal == "Bullish"
                    stop = round(price * (1 - _STOP_LOSS_PCT if buy else 1 + _STOP_LOSS_PCT), 2)
                    tp = round(price * (1 + _TAKE_PROFIT_PCT if buy else 1 - _TAKE_PROFIT_PCT), 2)

                    uic = find_uic(access_token, ticker.split(".")[0])
                    if not uic:
                        continue

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
                        direction = "KØBT" if buy else "SOLGT"
                        _log(f"{direction} {ticker} @ ${price:.2f} | SL ${stop:.2f} | TP ${tp:.2f}")
                        traded_today.add(ticker)
                        signals_found += 1
                    else:
                        err = result.get("error", "?") if result else "ingen respons"
                        _log(f"Ordre fejl {ticker}: {err}")

                except Exception as e:
                    continue

        _log(f"Scan færdig — {signals_found} handler afgivet. Næste scan om {_SCAN_INTERVAL_SECONDS//60} min.")

        # Nulstil handled_today ved midnat
        if datetime.now().hour == 0:
            traded_today.clear()

        for _ in range(_SCAN_INTERVAL_SECONDS):
            if not st.session_state.get("auto_trading_active"):
                break
            time.sleep(1)

    _log("Auto-trading stoppet.")


def _start_auto_trading() -> None:
    token = st.session_state.get("saxo_access_token")
    account_key = st.session_state.get("saxo_account_key")
    if not token or not account_key:
        st.error("Ikke logget ind.")
        return

    with st.spinner("Henter aktie-univers..."):
        us = get_us_tickers()
        eu = get_european_tickers()
        all_tickers = list(dict.fromkeys(us + eu))  # deduplicate

    st.session_state.auto_trading_active = True
    st.session_state.universe_size = len(all_tickers)
    _log(f"Auto-trading startet. Univers: {len(all_tickers)} aktier (US + Europa).")

    t = threading.Thread(
        target=_scan_and_trade,
        args=(token, account_key, all_tickers),
        daemon=True,
    )
    t.start()
    st.session_state.auto_trading_thread = t


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
        "Kobler til Saxo Banks simulation-miljø (ingen rigtige penge). "
        "Klik herunder for at logge ind."
    )
    st.link_button("Log ind med Saxo Bank", get_auth_url(), type="primary")


def _render_portfolio() -> None:
    access_token = st.session_state.get("saxo_access_token")
    client_key = st.session_state.get("saxo_client_key")

    balance = get_balance(access_token, client_key)
    if balance:
        c1, c2, c3 = st.columns(3)
        c1.metric("Samlet værdi", f"${balance.get('TotalValue', 0):,.2f}")
        c2.metric("Kontanter", f"${balance.get('CashBalance', 0):,.2f}")
        c3.metric("Urealiseret P/L", f"${balance.get('UnrealizedPositionsValue', 0):,.2f}")

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
                "Navn": fmt.get("Description", "—")[:30],
                "Antal": base.get("Amount", 0),
                "Indgang": f"${base.get('OpenPrice', 0):.2f}",
                "Nu": f"${view.get('CurrentPrice', 0):.2f}",
                "P/L": f"${view.get('ProfitLossOnTrade', 0):.2f}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render(watchlist: list[str]) -> None:
    st.header("Saxo Bank — Auto Trading")

    _handle_oauth_callback()

    if not st.session_state.get("saxo_access_token"):
        _render_login()
        return

    col_header, col_logout = st.columns([5, 1])
    with col_logout:
        if st.button("Log ud"):
            st.session_state.auto_trading_active = False
            for k in ["saxo_access_token", "saxo_refresh_token", "saxo_client_key",
                      "saxo_account_key", "trade_log", "universe_size"]:
                st.session_state.pop(k, None)
            st.rerun()

    _render_portfolio()
    st.divider()

    # --- Auto-trading styring ---
    st.subheader("Auto-trading")

    is_active = st.session_state.get("auto_trading_active", False)
    universe_size = st.session_state.get("universe_size", 0)

    if is_active:
        st.success(f"Auto-trading kører — scanner {universe_size} aktier (US + Europa) hvert {_SCAN_INTERVAL_SECONDS//60}. minut")
        if st.button("Stop auto-trading", type="secondary"):
            st.session_state.auto_trading_active = False
            st.rerun()
    else:
        st.caption(
            f"Scanner S&P 500 + NASDAQ 100 + DAX + FTSE 100 + CAC 40 + EURO STOXX 50. "
            f"Handler automatisk ved Bullish/Bearish signal. "
            f"Stop-loss {_STOP_LOSS_PCT*100:.0f}% · Take-profit {_TAKE_PROFIT_PCT*100:.0f}% · {_TRADE_AMOUNT} stk. per ordre."
        )
        if st.button("Start auto-trading", type="primary"):
            _start_auto_trading()
            st.rerun()

    # --- Trade log ---
    st.divider()
    st.subheader("Trade log")

    col_refresh, col_clear = st.columns([1, 1])
    with col_refresh:
        if st.button("Opdater"):
            st.rerun()
    with col_clear:
        if st.button("Ryd log"):
            st.session_state.trade_log = []
            st.rerun()

    log = st.session_state.get("trade_log", [])
    if not log:
        st.info("Ingen handler endnu.")
    else:
        for entry in log:
            if "KØBT" in entry:
                st.success(entry)
            elif "SOLGT" in entry:
                st.error(entry)
            elif "fejl" in entry.lower():
                st.warning(entry)
            else:
                st.caption(entry)
