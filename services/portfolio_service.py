# services/portfolio_service.py
import json
import os
from pathlib import Path
import pandas as pd
import yfinance as yf

_PORTFOLIO_PATH = Path(os.getenv("PORTFOLIO_PATH", Path(__file__).parent.parent / "portfolio.json"))

_DEFAULT_PORTFOLIO = {
    "start_date": "2025-06-01",
    "start_capital": 100000,
    "position_size": 10000,
    "positions": [],
}


def load_portfolio() -> dict:
    path = Path(os.getenv("PORTFOLIO_PATH", str(_PORTFOLIO_PATH)))
    if not path.exists():
        return dict(_DEFAULT_PORTFOLIO)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(_DEFAULT_PORTFOLIO)


def save_portfolio(portfolio: dict) -> None:
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
