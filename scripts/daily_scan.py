"""
Daily portfolio scan — runs via GitHub Actions, no Streamlit required.
Loads portfolio from Supabase, checks SL/T2 on open positions,
scans the full universe for new KØB signals, saves back to Supabase.
"""
import sys
import os
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

# Make project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ── Supabase (uses env vars set by GitHub Actions secrets) ────────────────────

def _supabase_creds():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return (url.rstrip("/"), key) if url and key else None


def load_portfolio() -> dict:
    import requests
    creds = _supabase_creds()
    if not creds:
        log.error("SUPABASE_URL / SUPABASE_KEY not set")
        sys.exit(1)
    url, key = creds
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    r = requests.get(f"{url}/rest/v1/portfolio", headers=headers,
                     params={"id": "eq.1", "select": "data"}, timeout=15)
    r.raise_for_status()
    rows = r.json()
    if rows:
        return rows[0]["data"]
    return {"start_date": "2026-05-31", "start_capital": 100000,
            "position_size": 10000, "positions": [], "scan_offset": 0}


def save_portfolio(portfolio: dict) -> None:
    import requests
    creds = _supabase_creds()
    if not creds:
        return
    url, key = creds
    headers = {"apikey": key, "Authorization": f"Bearer {key}",
               "Content-Type": "application/json",
               "Prefer": "resolution=merge-duplicates"}
    r = requests.post(f"{url}/rest/v1/portfolio", headers=headers,
                      json={"id": 1, "data": portfolio}, timeout=15)
    r.raise_for_status()
    log.info("Saved portfolio to Supabase")


# ── OHLCV fetch with fallback ─────────────────────────────────────────────────

def fetch_ohlcv(ticker: str) -> pd.DataFrame | None:
    for attempt in range(2):
        try:
            if attempt == 0:
                df = yf.download(ticker, period="6mo", progress=False, auto_adjust=True)
            else:
                df = yf.Ticker(ticker).history(period="6mo", auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.loc[:, ~df.columns.duplicated()]
            if not df.empty and len(df) >= 50:
                return df
        except Exception:
            pass
    return None


def fetch_ohlcv_range(ticker: str, start: str) -> pd.DataFrame | None:
    try:
        df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.loc[:, ~df.columns.duplicated()]
        return df if not df.empty else None
    except Exception:
        return None


# ── Position management ───────────────────────────────────────────────────────

def backfill_positions(portfolio: dict) -> bool:
    """Close positions that hit SL or T2 since last check. Returns True if changed."""
    from utils.calculations import calculate_trade_levels
    changed = False
    for pos in portfolio["positions"]:
        if pos["status"] != "active":
            continue
        df = fetch_ohlcv_range(pos["ticker"], pos["entry_date"])
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
                log.info(f"  {pos['ticker']} → stop-loss ramt {date_str}")
                changed = True
                break
            if high >= pos["t2"]:
                pos.update(status="closed", close_price=pos["t2"],
                           close_date=date_str, close_reason="t2")
                log.info(f"  {pos['ticker']} → T2 ramt {date_str}")
                changed = True
                break
    return changed


# ── Full universe scan ────────────────────────────────────────────────────────

def full_scan(universe: list[str], portfolio: dict) -> list[dict]:
    from utils.calculations import score_signal, calculate_trade_levels

    max_positions = portfolio["start_capital"] // portfolio["position_size"]
    active_tickers = {p["ticker"] for p in portfolio["positions"] if p["status"] == "active"}
    open_slots = max_positions - len(active_tickers)

    if open_slots <= 0:
        log.info("Portefølje fuld — ingen nye positioner mulige")
        return []

    today = str(pd.Timestamp.now(tz="UTC").date())
    candidates = []
    checked = 0

    for i, ticker in enumerate(universe):
        if ticker in active_tickers:
            continue

        # Throttle to avoid Yahoo Finance rate limiting
        if i > 0 and i % 50 == 0:
            log.info(f"  {i}/{len(universe)} tickers scannet...")
            time.sleep(3)

        df = fetch_ohlcv(ticker)
        if df is None:
            continue

        checked += 1
        try:
            signal = score_signal(df)
            if signal["label"] != "KØB":
                continue
            levels = calculate_trade_levels(df)
            candidates.append((signal["score"], {
                "ticker": ticker,
                "source": "Portefølje-scan (daglig)",
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
        except Exception:
            continue

    log.info(f"Scannet {checked} tickers — {len(candidates)} KØB-kandidater fundet")
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [pos for _, pos in candidates[:open_slots]]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=== Daglig portefølje-scan starter ===")

    from services.market_universe import get_us_tickers, get_european_tickers
    universe = sorted(set(get_us_tickers() + get_european_tickers()))
    log.info(f"Univers: {len(universe)} tickers")

    portfolio = load_portfolio()
    log.info(f"Portfolio loaded — {len(portfolio.get('positions', []))} positioner")

    # 1. Check existing positions for SL/T2 hits
    log.info("Checker åbne positioner for stop-loss / T2...")
    changed = backfill_positions(portfolio)

    # 2. Full universe scan
    log.info("Scanner hele universet for nye KØB-signaler...")
    new_positions = full_scan(universe, portfolio)

    if new_positions:
        active_tickers = {p["ticker"] for p in portfolio["positions"] if p["status"] == "active"}
        added = []
        for pos in new_positions:
            if pos["ticker"] not in active_tickers:
                portfolio["positions"].append(pos)
                active_tickers.add(pos["ticker"])
                added.append(pos["ticker"])
                log.info(f"  Ny position: {pos['ticker']} @ ${pos['entry_price']:.2f}")
        if added:
            changed = True

    # 3. Reset scan_offset (full scan done)
    portfolio["scan_offset"] = 0

    # 4. Record last scan time
    portfolio["last_scan"] = datetime.now(timezone.utc).isoformat()

    if changed or True:  # always save to update last_scan timestamp
        save_portfolio(portfolio)

    active = [p for p in portfolio["positions"] if p["status"] == "active"]
    closed = [p for p in portfolio["positions"] if p["status"] == "closed"]
    log.info(f"=== Færdig — {len(active)} aktive, {len(closed)} lukkede positioner ===")


if __name__ == "__main__":
    main()
