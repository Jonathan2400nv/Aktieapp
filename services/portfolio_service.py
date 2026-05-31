# services/portfolio_service.py
import copy
import json
import os
from datetime import date
from pathlib import Path
import pandas as pd
import yfinance as yf
from utils.calculations import score_signal, calculate_trade_levels

_PORTFOLIO_PATH = Path(os.getenv("PORTFOLIO_PATH", Path(__file__).parent.parent / "portfolio.json"))

_DEFAULT_PORTFOLIO = {
    "start_date": "2025-06-01",
    "start_capital": 100000,
    "position_size": 10000,
    "positions": [],
}


def load_portfolio() -> dict:
    from services.supabase_client import load_from_supabase
    data = load_from_supabase()
    if data is not None:
        return data

    path = Path(os.getenv("PORTFOLIO_PATH", str(_PORTFOLIO_PATH)))
    if not path.exists():
        return copy.deepcopy(_DEFAULT_PORTFOLIO)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return copy.deepcopy(_DEFAULT_PORTFOLIO)


def save_portfolio(portfolio: dict) -> None:
    from services.supabase_client import save_to_supabase
    if save_to_supabase(portfolio):
        return

    path = Path(os.getenv("PORTFOLIO_PATH", str(_PORTFOLIO_PATH)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(portfolio, indent=2, default=str), encoding="utf-8")


def calculate_pnl(position: dict, current_price: float, position_size: int) -> dict:
    entry = position["entry_price"]
    ref_price = position["close_price"] if position["status"] == "closed" and position["close_price"] is not None else current_price
    pnl_pct = (ref_price - entry) / entry if entry else 0.0
    pnl_kr = position_size * pnl_pct
    return {"pnl_pct": pnl_pct, "pnl_kr": pnl_kr}


def calculate_portfolio_value(portfolio: dict, current_prices: dict[str, float]) -> float:
    position_size = portfolio["position_size"]
    total_pnl = 0.0
    for pos in portfolio["positions"]:
        current = current_prices.get(pos["ticker"], pos["entry_price"])
        total_pnl += calculate_pnl(pos, current, position_size)["pnl_kr"]
    return portfolio["start_capital"] + total_pnl


def get_current_price(ticker: str) -> float | None:
    try:
        info = yf.Ticker(ticker).fast_info
        price = getattr(info, "last_price", None)
        return float(price) if price is not None else None
    except Exception:
        return None


def _fetch_ohlcv_range(ticker: str, start: str) -> pd.DataFrame | None:
    try:
        df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df if not df.empty else None
    except Exception:
        return None


def _fetch_ohlcv_for_scan(ticker: str) -> pd.DataFrame | None:
    try:
        df = yf.download(ticker, period="6mo", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df if not df.empty else None
    except Exception:
        return None


def backfill_historical_signals(portfolio: dict, universe: list[str]) -> dict:
    """One-time simulation: walks weekly from start_date to first live scan,
    adding KØB signals based on data available on each date (no look-ahead bias).
    Marks all retroactively added positions with simulated=True."""
    if portfolio.get("historical_backfill_complete"):
        return portfolio

    start_str = portfolio["start_date"]
    max_positions = portfolio["start_capital"] // portfolio["position_size"]

    real_dates = [p["entry_date"] for p in portfolio["positions"] if not p.get("simulated")]
    cutoff_str = min(real_dates) if real_dates else str(pd.Timestamp.now(tz="UTC").date())

    try:
        all_ticker_dfs: dict[str, pd.DataFrame] = {}
        batch_size = 100
        for i in range(0, len(universe), batch_size):
            batch = universe[i:i + batch_size]
            try:
                raw = yf.download(batch, start=start_str, end=cutoff_str,
                                  progress=False, auto_adjust=True)
            except Exception:
                continue
            if raw.empty:
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                for ticker in batch:
                    try:
                        t_df = raw.xs(ticker, axis=1, level=1).dropna(subset=["Close"])
                        if len(t_df) >= 50:
                            all_ticker_dfs[ticker] = t_df
                    except KeyError:
                        continue
            elif len(batch) == 1:
                raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
                t_df = raw.dropna(subset=["Close"])
                if len(t_df) >= 50:
                    all_ticker_dfs[batch[0]] = t_df

        if not all_ticker_dfs:
            portfolio["historical_backfill_complete"] = True
            portfolio["backfill_date"] = cutoff_str
            save_portfolio(portfolio)
            return portfolio

        all_dates = sorted(set().union(*[set(df.index) for df in all_ticker_dfs.values()]))
        simulated_positions: list[dict] = []

        for i, ts in enumerate(all_dates):
            day_str = str(ts.date())
            if day_str >= cutoff_str:
                break

            # Daily: check SL/T2 for active simulated positions
            for pos in simulated_positions:
                if pos["status"] != "active":
                    continue
                t_df = all_ticker_dfs.get(pos["ticker"])
                if t_df is None or ts not in t_df.index:
                    continue
                row = t_df.loc[ts]
                if float(row["Low"]) <= pos["stop_loss"]:
                    pos.update(status="closed", close_price=pos["stop_loss"],
                               close_date=day_str, close_reason="stop_loss")
                elif float(row["High"]) >= pos["t2"]:
                    pos.update(status="closed", close_price=pos["t2"],
                               close_date=day_str, close_reason="t2")

            # Weekly: scan for new signals (after 50-day warmup)
            if i < 50 or i % 5 != 0:
                continue

            active_tickers = {p["ticker"] for p in simulated_positions if p["status"] == "active"}
            open_slots = max_positions - len(active_tickers)
            if open_slots <= 0:
                continue

            candidates = []
            for ticker, t_df in all_ticker_dfs.items():
                if ticker in active_tickers:
                    continue
                window = t_df[t_df.index <= ts].iloc[-126:]
                if len(window) < 50:
                    continue
                try:
                    signal = score_signal(window)
                    if signal["label"] != "KØB":
                        continue
                    levels = calculate_trade_levels(window)
                    candidates.append((signal["score"], ticker, levels))
                except Exception:
                    continue

            candidates.sort(key=lambda x: x[0], reverse=True)
            for _, ticker, levels in candidates[:open_slots]:
                simulated_positions.append({
                    "ticker": ticker,
                    "source": "Portefølje-scan",
                    "entry_price": levels["entry_mid"],
                    "entry_date": day_str,
                    "stop_loss": levels["stop_loss"],
                    "t1": levels["t1"],
                    "t2": levels["t2"],
                    "status": "active",
                    "t1_hit": False,
                    "close_price": None,
                    "close_date": None,
                    "close_reason": None,
                    "simulated": True,
                })

        portfolio["positions"] = simulated_positions + portfolio["positions"]

    except Exception:
        pass

    portfolio["historical_backfill_complete"] = True
    portfolio["backfill_date"] = cutoff_str
    save_portfolio(portfolio)
    return portfolio


def scan_watchlist_for_signals(watchlist: list[str], portfolio: dict) -> list[dict]:
    max_positions = portfolio["start_capital"] // portfolio["position_size"]
    active_tickers = {p["ticker"] for p in portfolio["positions"] if p["status"] == "active"}
    open_slots = max_positions - len(active_tickers)
    if open_slots <= 0:
        return []

    today = str(pd.Timestamp.now(tz="UTC").date())
    candidates = []
    for ticker in watchlist:
        if ticker in active_tickers:
            continue
        df = _fetch_ohlcv_for_scan(ticker)
        if df is None or len(df) < 50:
            continue
        signal = score_signal(df)
        if signal["label"] != "KØB":
            continue
        levels = calculate_trade_levels(df)
        candidates.append((signal["score"], {
            "ticker": ticker,
            "source": "Portefølje-scan",
            "entry_price": levels["entry_mid"],
            "entry_date": today,
            "stop_loss": levels["stop_loss"],
            "t1": levels["t1"],
            "t2": levels["t2"],
            "status": "active",
            "t1_hit": False,
            "close_price": None,
            "close_date": None,
            "close_reason": None,
        }))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [pos for _, pos in candidates[:open_slots]]


def get_performance_data(portfolio: dict) -> tuple[list[str], list[float], list[float]]:
    try:
        start_str = portfolio["start_date"]
        start_capital = portfolio["start_capital"]
        position_size = portfolio["position_size"]

        tickers = list({p["ticker"] for p in portfolio["positions"]})
        all_tickers = tickers + ["SPY"]

        df_all = yf.download(all_tickers, start=start_str, progress=False, auto_adjust=True)
        if isinstance(df_all.columns, pd.MultiIndex):
            close_all = df_all["Close"]
        else:
            # Single ticker — yfinance returns flat columns
            close_all = df_all[["Close"]]
            close_all.columns = all_tickers

        if close_all.empty:
            return [], [], []

        # Normalize SPY to start_capital
        if "SPY" in close_all.columns:
            spy_prices = close_all["SPY"].dropna()
            spy_start = float(spy_prices.iloc[0]) if not spy_prices.empty else 1.0
        else:
            spy_prices = pd.Series(dtype=float)
            spy_start = 1.0

        dates_out: list[str] = []
        portfolio_vals: list[float] = []
        spy_vals: list[float] = []

        for ts in close_all.index:
            d = ts.date()
            total_pnl = 0.0

            for pos in portfolio["positions"]:
                entry_date = date.fromisoformat(pos["entry_date"])
                if d < entry_date:
                    continue
                close_date = date.fromisoformat(pos["close_date"]) if pos["close_date"] else None
                if close_date and d > close_date:
                    pnl_pct = (pos["close_price"] - pos["entry_price"]) / pos["entry_price"]
                else:
                    ticker = pos["ticker"]
                    if ticker in close_all.columns and ts in close_all.index:
                        price = close_all.loc[ts, ticker]
                        price = float(price) if not pd.isna(price) else pos["entry_price"]
                    else:
                        price = pos["entry_price"]
                    pnl_pct = (price - pos["entry_price"]) / pos["entry_price"]
                total_pnl += position_size * pnl_pct

            dates_out.append(str(d))
            portfolio_vals.append(start_capital + total_pnl)

            if "SPY" in close_all.columns and ts in spy_prices.index:
                spy_val = start_capital * float(spy_prices.loc[ts]) / spy_start
            else:
                spy_val = start_capital
            spy_vals.append(spy_val)

        return dates_out, portfolio_vals, spy_vals
    except Exception:
        return [], [], []


def backfill_positions(portfolio: dict) -> dict:
    changed = False
    for pos in portfolio["positions"]:
        if pos["status"] != "active":
            continue
        df = _fetch_ohlcv_range(pos["ticker"], pos["entry_date"])
        if df is None:
            continue
        entry_ts = pd.Timestamp(pos["entry_date"])
        for ts, row in df.iterrows():
            if pd.Timestamp(ts) < entry_ts:
                continue
            low = float(row["Low"])
            high = float(row["High"])
            date_str = str(pd.Timestamp(ts).date())
            if low <= pos["stop_loss"]:
                pos.update(status="closed", close_price=pos["stop_loss"],
                           close_date=date_str, close_reason="stop_loss")
                changed = True
                break
            if high >= pos["t2"]:
                pos.update(status="closed", close_price=pos["t2"],
                           close_date=date_str, close_reason="t2")
                changed = True
                break
    if changed:
        save_portfolio(portfolio)
    return portfolio
