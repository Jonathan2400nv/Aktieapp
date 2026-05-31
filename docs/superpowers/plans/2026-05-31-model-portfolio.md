# Modelportefølje Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Saxo Bank tab with a live-tracked model portfolio that automatically adds KØB-signals from the watchlist and tracks performance vs. S&P 500.

**Architecture:** `services/portfolio_service.py` holds all business logic (no Streamlit dependency); `modules/portfolio.py` is the Streamlit UI. Positions persist in `portfolio.json` at the project root. On tab open, active positions are backfilled by downloading daily OHLC data from yfinance and checking stop-loss/T2 hit day by day — so the portfolio is always accurate even if the user hasn't opened the app in days.

**Tech Stack:** Python 3.11, yfinance, pandas, plotly, streamlit, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `services/portfolio_service.py` | Create | All logic: load/save, P&L, backfill, scan, performance curve |
| `tests/test_portfolio_service.py` | Create | Unit tests for portfolio_service |
| `portfolio.json` | Create | Persistent storage — initial empty state |
| `modules/portfolio.py` | Create | Streamlit UI: KPI dashboard, chart, tables |
| `app.py` | Modify | Swap Saxo tab for Portfolio tab |
| `modules/saxo_trading.py` | Delete | Replaced |
| `modules/saxo_placeholder.py` | Delete | Replaced |
| `services/saxo_service.py` | Delete | Replaced |

---

## Task 1: portfolio_service.py — persistence and P&L

**Files:**
- Create: `services/portfolio_service.py`
- Create: `tests/test_portfolio_service.py`

### Context
`portfolio.json` lives at the project root (same directory as `app.py`). Portfolio structure:
```json
{
  "start_date": "2025-06-01",
  "start_capital": 100000,
  "position_size": 10000,
  "positions": []
}
```
Each position:
```json
{
  "ticker": "ADBE",
  "source": "Portefølje-scan",
  "entry_price": 245.00,
  "entry_date": "2025-06-01",
  "stop_loss": 239.82,
  "t1": 270.00,
  "t2": 290.00,
  "status": "active",
  "t1_hit": false,
  "close_price": null,
  "close_date": null,
  "close_reason": null
}
```

- [ ] **Step 1: Write failing tests**

```python
# tests/test_portfolio_service.py
import importlib
import json
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from pathlib import Path


_DEFAULT = {
    "start_date": "2025-06-01",
    "start_capital": 100000,
    "position_size": 10000,
    "positions": [],
}


def _make_pos(ticker="AAPL", status="active", entry=100.0, stop=90.0, t1=115.0, t2=130.0,
              close_price=None, close_date=None, close_reason=None):
    return {
        "ticker": ticker,
        "source": "Portefølje-scan",
        "entry_price": entry,
        "entry_date": "2025-06-01",
        "stop_loss": stop,
        "t1": t1,
        "t2": t2,
        "status": status,
        "t1_hit": False,
        "close_price": close_price,
        "close_date": close_date,
        "close_reason": close_reason,
    }


class TestLoadPortfolio:
    def test_returns_default_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTFOLIO_PATH", str(tmp_path / "portfolio.json"))
        from services import portfolio_service
        importlib.reload(portfolio_service)
        result = portfolio_service.load_portfolio()
        assert result["start_capital"] == 100000
        assert result["positions"] == []

    def test_roundtrip(self, tmp_path, monkeypatch):
        import importlib
        path = tmp_path / "portfolio.json"
        monkeypatch.setenv("PORTFOLIO_PATH", str(path))
        from services import portfolio_service
        importlib.reload(portfolio_service)
        data = {**_DEFAULT, "positions": [_make_pos()]}
        portfolio_service.save_portfolio(data)
        loaded = portfolio_service.load_portfolio()
        assert loaded["positions"][0]["ticker"] == "AAPL"


class TestCalculatePnl:
    def test_active_position_uses_current_price(self):
        from services.portfolio_service import calculate_pnl
        pos = _make_pos(entry=100.0, status="active")
        result = calculate_pnl(pos, current_price=110.0, position_size=10000)
        assert abs(result["pnl_pct"] - 0.10) < 0.0001
        assert abs(result["pnl_kr"] - 1000.0) < 0.01

    def test_closed_position_uses_close_price(self):
        from services.portfolio_service import calculate_pnl
        pos = _make_pos(entry=100.0, status="closed", close_price=95.0)
        result = calculate_pnl(pos, current_price=80.0, position_size=10000)
        assert abs(result["pnl_pct"] - (-0.05)) < 0.0001
        assert abs(result["pnl_kr"] - (-500.0)) < 0.01

    def test_negative_return(self):
        from services.portfolio_service import calculate_pnl
        pos = _make_pos(entry=100.0, status="active")
        result = calculate_pnl(pos, current_price=92.0, position_size=10000)
        assert result["pnl_kr"] < 0


class TestPortfolioValue:
    def test_total_value_sums_all_pnl(self):
        from services.portfolio_service import calculate_portfolio_value
        portfolio = {
            **_DEFAULT,
            "positions": [
                _make_pos("AAPL", status="active"),
                _make_pos("MSFT", status="closed", close_price=110.0),
            ],
        }
        current_prices = {"AAPL": 110.0}
        value = calculate_portfolio_value(portfolio, current_prices)
        # AAPL: +10%, +1000 kr.  MSFT: +10%, +1000 kr.
        assert abs(value - 102000.0) < 1.0

    def test_empty_portfolio_equals_start_capital(self):
        from services.portfolio_service import calculate_portfolio_value
        value = calculate_portfolio_value(_DEFAULT, {})
        assert value == 100000
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -m pytest tests/test_portfolio_service.py -v 2>&1 | head -30
```
Expected: ImportError or ModuleNotFoundError for `portfolio_service`

- [ ] **Step 3: Create `services/portfolio_service.py` with persistence and P&L**

```python
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
    path.write_text(json.dumps(portfolio, indent=2, default=str), encoding="utf-8")


def calculate_pnl(position: dict, current_price: float, position_size: int) -> dict:
    entry = position["entry_price"]
    ref_price = position["close_price"] if position["status"] == "closed" and position["close_price"] else current_price
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
        return float(price) if price else None
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -m pytest tests/test_portfolio_service.py::TestLoadPortfolio tests/test_portfolio_service.py::TestCalculatePnl tests/test_portfolio_service.py::TestPortfolioValue -v
```
Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
git add services/portfolio_service.py tests/test_portfolio_service.py
git commit -m "feat: add portfolio_service with persistence and P&L"
```

---

## Task 2: portfolio_service.py — backfill

**Files:**
- Modify: `services/portfolio_service.py`
- Modify: `tests/test_portfolio_service.py`

### Context
`backfill_positions(portfolio)` downloads OHLC data from `entry_date` to today for each active position. It then walks day by day checking if `Low <= stop_loss` (→ close at stop_loss price) or `High >= t2` (→ close at t2 price). Stop-loss takes priority if both trigger on the same day. Returns the updated portfolio dict and saves it if anything changed.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_portfolio_service.py` (the `import pandas as pd` is already at the top from Task 1):

```python
def _make_ohlcv(dates, lows, highs, closes=None):
    """Helper: build a fake OHLCV DataFrame."""
    if closes is None:
        closes = highs
    idx = pd.to_datetime(dates)
    return pd.DataFrame({
        "Open": highs,
        "High": highs,
        "Low": lows,
        "Close": closes,
        "Volume": [1_000_000] * len(dates),
    }, index=idx)


class TestBackfill:
    def test_backfill_closes_at_stop_loss(self):
        from services.portfolio_service import backfill_positions
        portfolio = {
            **_DEFAULT,
            "positions": [_make_pos(entry=100.0, stop=90.0, t2=130.0, entry_date="2025-06-01")],
        }
        # On 2025-06-03 the low dips below stop_loss
        fake_df = _make_ohlcv(
            dates=["2025-06-01", "2025-06-02", "2025-06-03"],
            lows=[98.0, 95.0, 88.0],
            highs=[102.0, 103.0, 104.0],
        )
        with patch("services.portfolio_service._fetch_ohlcv_range", return_value=fake_df):
            with patch("services.portfolio_service.save_portfolio"):
                result = backfill_positions(portfolio)
        pos = result["positions"][0]
        assert pos["status"] == "closed"
        assert pos["close_reason"] == "stop_loss"
        assert pos["close_price"] == 90.0
        assert pos["close_date"] == "2025-06-03"

    def test_backfill_closes_at_t2(self):
        from services.portfolio_service import backfill_positions
        portfolio = {
            **_DEFAULT,
            "positions": [_make_pos(entry=100.0, stop=90.0, t2=130.0, entry_date="2025-06-01")],
        }
        fake_df = _make_ohlcv(
            dates=["2025-06-01", "2025-06-02", "2025-06-03"],
            lows=[98.0, 99.0, 100.0],
            highs=[102.0, 105.0, 135.0],
        )
        with patch("services.portfolio_service._fetch_ohlcv_range", return_value=fake_df):
            with patch("services.portfolio_service.save_portfolio"):
                result = backfill_positions(portfolio)
        pos = result["positions"][0]
        assert pos["status"] == "closed"
        assert pos["close_reason"] == "t2"
        assert pos["close_price"] == 130.0

    def test_backfill_stop_loss_priority_over_t2(self):
        from services.portfolio_service import backfill_positions
        portfolio = {
            **_DEFAULT,
            "positions": [_make_pos(entry=100.0, stop=90.0, t2=130.0, entry_date="2025-06-01")],
        }
        # Same day: both SL and T2 triggered
        fake_df = _make_ohlcv(
            dates=["2025-06-01"],
            lows=[85.0],
            highs=[135.0],
        )
        with patch("services.portfolio_service._fetch_ohlcv_range", return_value=fake_df):
            with patch("services.portfolio_service.save_portfolio"):
                result = backfill_positions(portfolio)
        pos = result["positions"][0]
        assert pos["close_reason"] == "stop_loss"

    def test_backfill_skips_closed_positions(self):
        from services.portfolio_service import backfill_positions
        portfolio = {
            **_DEFAULT,
            "positions": [_make_pos(status="closed", close_price=95.0, close_date="2025-06-02", close_reason="stop_loss")],
        }
        with patch("services.portfolio_service._fetch_ohlcv_range") as mock_fetch:
            with patch("services.portfolio_service.save_portfolio"):
                backfill_positions(portfolio)
        mock_fetch.assert_not_called()

    def test_backfill_no_trigger_keeps_active(self):
        from services.portfolio_service import backfill_positions
        portfolio = {
            **_DEFAULT,
            "positions": [_make_pos(entry=100.0, stop=90.0, t2=130.0, entry_date="2025-06-01")],
        }
        fake_df = _make_ohlcv(
            dates=["2025-06-01", "2025-06-02"],
            lows=[95.0, 96.0],
            highs=[105.0, 106.0],
        )
        with patch("services.portfolio_service._fetch_ohlcv_range", return_value=fake_df):
            with patch("services.portfolio_service.save_portfolio"):
                result = backfill_positions(portfolio)
        assert result["positions"][0]["status"] == "active"
```

Also update `_make_pos` to accept `entry_date` parameter — replace the existing `_make_pos` in the test file:

```python
def _make_pos(ticker="AAPL", status="active", entry=100.0, stop=90.0, t1=115.0, t2=130.0,
              close_price=None, close_date=None, close_reason=None, entry_date="2025-06-01"):
    return {
        "ticker": ticker,
        "source": "Portefølje-scan",
        "entry_price": entry,
        "entry_date": entry_date,
        "stop_loss": stop,
        "t1": t1,
        "t2": t2,
        "status": status,
        "t1_hit": False,
        "close_price": close_price,
        "close_date": close_date,
        "close_reason": close_reason,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -m pytest tests/test_portfolio_service.py::TestBackfill -v 2>&1 | head -20
```
Expected: ImportError or AttributeError — `backfill_positions` not defined yet

- [ ] **Step 3: Implement `_fetch_ohlcv_range` and `backfill_positions`**

Add to `services/portfolio_service.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -m pytest tests/test_portfolio_service.py::TestBackfill -v
```
Expected: 5 tests PASS

- [ ] **Step 5: Run full suite**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -m pytest tests/ -v 2>&1 | tail -10
```
Expected: all passing

- [ ] **Step 6: Commit**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
git add services/portfolio_service.py tests/test_portfolio_service.py
git commit -m "feat: add portfolio backfill logic with stop-loss and T2 detection"
```

---

## Task 3: portfolio_service.py — scan for new signals

**Files:**
- Modify: `services/portfolio_service.py`
- Modify: `tests/test_portfolio_service.py`

### Context
`scan_watchlist_for_signals(watchlist, portfolio)` iterates the watchlist and skips any ticker that already has an active position. For each remaining ticker it fetches OHLCV (6 months, daily), calls `score_signal(df)` from `utils/calculations.py`, and if `label == "KØB"` also calls `calculate_trade_levels(df)`. Returns a list of new position dicts to add. Entry date is today (UTC).

`score_signal` signature: `score_signal(df: pd.DataFrame) -> dict` where dict has `{'score': int, 'label': str, 'breakdown': dict, 'adx': float}`.

`calculate_trade_levels` signature: `calculate_trade_levels(df: pd.DataFrame) -> dict` where dict has `{'entry_low', 'entry_high', 'entry_mid', 'stop_loss', 't1', 't2', 'rr', 'atr'}`.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_portfolio_service.py`:

```python
class TestScanWatchlist:
    def _make_df(self, n=100):
        """Minimal OHLCV df with enough rows for score_signal."""
        import numpy as np
        idx = pd.date_range("2024-01-01", periods=n, freq="B")
        price = 100 + np.cumsum(np.random.randn(n) * 0.5)
        return pd.DataFrame({
            "Open": price,
            "High": price * 1.01,
            "Low": price * 0.99,
            "Close": price,
            "Volume": np.ones(n) * 1_000_000,
        }, index=idx)

    def test_skips_tickers_with_active_position(self):
        from services.portfolio_service import scan_watchlist_for_signals
        portfolio = {**_DEFAULT, "positions": [_make_pos("AAPL", status="active")]}
        with patch("services.portfolio_service._fetch_ohlcv_for_scan", return_value=self._make_df()):
            with patch("services.portfolio_service.score_signal", return_value={"label": "KØB", "score": 6, "breakdown": {}, "adx": 30.0}):
                with patch("services.portfolio_service.calculate_trade_levels", return_value={"entry_mid": 105.0, "stop_loss": 95.0, "t1": 115.0, "t2": 125.0, "rr": 1.5, "atr": 5.0, "entry_low": 100.0, "entry_high": 110.0}):
                    result = scan_watchlist_for_signals(["AAPL"], portfolio)
        assert result == []

    def test_adds_buy_signal(self):
        from services.portfolio_service import scan_watchlist_for_signals
        portfolio = {**_DEFAULT, "positions": []}
        with patch("services.portfolio_service._fetch_ohlcv_for_scan", return_value=self._make_df()):
            with patch("services.portfolio_service.score_signal", return_value={"label": "KØB", "score": 6, "breakdown": {}, "adx": 30.0}):
                with patch("services.portfolio_service.calculate_trade_levels", return_value={"entry_mid": 105.0, "stop_loss": 95.0, "t1": 115.0, "t2": 125.0, "rr": 1.5, "atr": 5.0, "entry_low": 100.0, "entry_high": 110.0}):
                    result = scan_watchlist_for_signals(["MSFT"], portfolio)
        assert len(result) == 1
        assert result[0]["ticker"] == "MSFT"
        assert result[0]["entry_price"] == 105.0
        assert result[0]["status"] == "active"
        assert result[0]["source"] == "Portefølje-scan"

    def test_skips_neutral_signal(self):
        from services.portfolio_service import scan_watchlist_for_signals
        portfolio = {**_DEFAULT, "positions": []}
        with patch("services.portfolio_service._fetch_ohlcv_for_scan", return_value=self._make_df()):
            with patch("services.portfolio_service.score_signal", return_value={"label": "Neutral", "score": 3, "breakdown": {}, "adx": 20.0}):
                result = scan_watchlist_for_signals(["MSFT"], portfolio)
        assert result == []

    def test_skips_short_dataframe(self):
        from services.portfolio_service import scan_watchlist_for_signals
        portfolio = {**_DEFAULT, "positions": []}
        with patch("services.portfolio_service._fetch_ohlcv_for_scan", return_value=self._make_df(n=10)):
            result = scan_watchlist_for_signals(["MSFT"], portfolio)
        assert result == []

    def test_skips_none_dataframe(self):
        from services.portfolio_service import scan_watchlist_for_signals
        portfolio = {**_DEFAULT, "positions": []}
        with patch("services.portfolio_service._fetch_ohlcv_for_scan", return_value=None):
            result = scan_watchlist_for_signals(["MSFT"], portfolio)
        assert result == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -m pytest tests/test_portfolio_service.py::TestScanWatchlist -v 2>&1 | head -20
```
Expected: ImportError — `scan_watchlist_for_signals` not defined

- [ ] **Step 3: Implement `_fetch_ohlcv_for_scan` and `scan_watchlist_for_signals`**

Add to `services/portfolio_service.py` at the top imports:
```python
from utils.calculations import score_signal, calculate_trade_levels
```

Add these functions:
```python
def _fetch_ohlcv_for_scan(ticker: str) -> pd.DataFrame | None:
    try:
        df = yf.download(ticker, period="6mo", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df if not df.empty else None
    except Exception:
        return None


def scan_watchlist_for_signals(watchlist: list[str], portfolio: dict) -> list[dict]:
    active_tickers = {p["ticker"] for p in portfolio["positions"] if p["status"] == "active"}
    today = str(pd.Timestamp.now(tz="UTC").date())
    new_positions = []
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
        new_positions.append({
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
        })
    return new_positions
```

- [ ] **Step 4: Run tests**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -m pytest tests/test_portfolio_service.py::TestScanWatchlist -v
```
Expected: 5 tests PASS

- [ ] **Step 5: Run full suite**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -m pytest tests/ -v 2>&1 | tail -10
```
Expected: all passing

- [ ] **Step 6: Commit**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
git add services/portfolio_service.py tests/test_portfolio_service.py
git commit -m "feat: add scan_watchlist_for_signals to portfolio_service"
```

---

## Task 4: portfolio_service.py — performance curve data

**Files:**
- Modify: `services/portfolio_service.py`

### Context
`get_performance_data(portfolio)` returns `(dates, portfolio_values, spy_values)` — three parallel lists used for the Plotly chart. It downloads historical Close prices for all tickers + SPY from `start_date` to today. For each trading day it reconstructs portfolio value: sum P&L for positions active that day. Closed positions contribute their fixed P&L after their close date. SPY is normalized to `start_capital` on the first trading day.

No tests for this function — it requires mocking yfinance multi-ticker downloads which is disproportionately complex. Manual verification on the chart is sufficient.

- [ ] **Step 1: Implement `get_performance_data`**

Add to `services/portfolio_service.py`:

```python
from datetime import date


def get_performance_data(portfolio: dict) -> tuple[list[str], list[float], list[float]]:
    start_str = portfolio["start_date"]
    start_capital = portfolio["start_capital"]
    position_size = portfolio["position_size"]

    tickers = list({p["ticker"] for p in portfolio["positions"]})
    all_tickers = tickers + ["SPY"]

    try:
        df_all = yf.download(all_tickers, start=start_str, progress=False, auto_adjust=True)
        if isinstance(df_all.columns, pd.MultiIndex):
            close_all = df_all["Close"]
        else:
            # Single ticker
            close_all = df_all[["Close"]]
            close_all.columns = all_tickers
    except Exception:
        return [], [], []

    if close_all.empty:
        return [], [], []

    # Normalize SPY to start_capital
    spy_col = close_all.get("SPY") if "SPY" in close_all.columns else None
    if spy_col is not None:
        spy_prices = spy_col.dropna()
        spy_start = float(spy_prices.iloc[0]) if not spy_prices.empty else 1.0
    else:
        spy_prices = pd.Series(dtype=float)
        spy_start = 1.0

    dates_out: list[str] = []
    portfolio_vals: list[float] = []
    spy_vals: list[float] = []

    for ts in close_all.index:
        d = ts.date()
        d_str = str(d)
        total_pnl = 0.0

        for pos in portfolio["positions"]:
            entry_date = date.fromisoformat(pos["entry_date"])
            if d < entry_date:
                continue
            close_date = date.fromisoformat(pos["close_date"]) if pos["close_date"] else None
            if close_date and d > close_date:
                # Use locked-in P&L
                pnl_pct = (pos["close_price"] - pos["entry_price"]) / pos["entry_price"]
            else:
                ticker = pos["ticker"]
                if ticker in close_all.columns:
                    price = close_all.loc[ts, ticker]
                    price = float(price) if not pd.isna(price) else pos["entry_price"]
                else:
                    price = pos["entry_price"]
                pnl_pct = (price - pos["entry_price"]) / pos["entry_price"]
            total_pnl += position_size * pnl_pct

        dates_out.append(d_str)
        portfolio_vals.append(start_capital + total_pnl)

        if spy_col is not None and ts in spy_prices.index:
            spy_val = start_capital * float(spy_prices.loc[ts]) / spy_start
        else:
            spy_val = start_capital
        spy_vals.append(spy_val)

    return dates_out, portfolio_vals, spy_vals
```

- [ ] **Step 2: Verify no import errors**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -c "from services.portfolio_service import get_performance_data; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Run full suite to confirm nothing broke**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -m pytest tests/ -v 2>&1 | tail -10
```
Expected: all passing

- [ ] **Step 4: Commit**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
git add services/portfolio_service.py
git commit -m "feat: add get_performance_data for portfolio chart"
```

---

## Task 5: modules/portfolio.py — Streamlit UI

**Files:**
- Create: `modules/portfolio.py`

### Context
The UI calls portfolio_service functions in sequence: load → backfill → scan → add new positions → display. KPI metrics use `st.columns(4)`. The performance chart uses Plotly. Active positions table has a "Luk" button per row for manual close. Status column uses colored text: green for Aktiv, yellow for T1 nær, red for SL nær.

Status logic:
- `T1 nær` when `current >= entry + 0.9 * (t1 - entry)`
- `SL nær` when `current <= entry + 0.7 * (stop_loss - entry)` (70% of the way down to stop_loss)

No Streamlit unit tests for this module — UI is tested manually.

- [ ] **Step 1: Create `modules/portfolio.py`**

```python
# modules/portfolio.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from services.portfolio_service import (
    load_portfolio, save_portfolio, backfill_positions,
    scan_watchlist_for_signals, calculate_pnl, calculate_portfolio_value,
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

    # SPY return for outperformance
    try:
        import yfinance as yf
        spy_raw = yf.download("SPY", start=portfolio["start_date"], progress=False, auto_adjust=True)
        if isinstance(spy_raw.columns, pd.MultiIndex):
            spy_raw.columns = spy_raw.columns.get_level_values(0)
        spy_close = spy_raw["Close"].squeeze().dropna()
        spy_return_pct = float(spy_close.iloc[-1] / spy_close.iloc[0] - 1) if len(spy_close) >= 2 else 0.0
    except Exception:
        spy_return_pct = 0.0

    outperformance = total_return_pct - spy_return_pct

    # --- KPI row ---
    col1, col2, col3, col4 = st.columns(4)
    pct_color = "green" if total_return_pct >= 0 else "red"
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
    with st.spinner("Henter historisk kursdata..."):
        dates, pvals, svals = get_performance_data(portfolio)

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
```

- [ ] **Step 2: Verify import works**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -c "from modules.portfolio import render; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Run full test suite**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -m pytest tests/ -v 2>&1 | tail -10
```
Expected: all passing

- [ ] **Step 4: Commit**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
git add modules/portfolio.py
git commit -m "feat: add portfolio UI module"
```

---

## Task 6: Wire up app.py, initialize portfolio.json, delete Saxo files

**Files:**
- Modify: `app.py`
- Create: `portfolio.json`
- Delete: `modules/saxo_trading.py`, `modules/saxo_placeholder.py`, `services/saxo_service.py`

- [ ] **Step 1: Create initial `portfolio.json`**

```bash
cat > "/Users/jonathankilmose/Documents/Aktier APP/portfolio.json" << 'EOF'
{
  "start_date": "2025-06-01",
  "start_capital": 100000,
  "position_size": 10000,
  "positions": []
}
EOF
```

- [ ] **Step 2: Update `app.py`**

Replace the full content of `app.py` with:

```python
import streamlit as st
from components.watchlist import render_watchlist_sidebar
from modules import swing_trading, earnings, reddit_sentiment, ai_screener, portfolio

st.set_page_config(
    page_title="Aktie App",
    page_icon="📈",
    layout="wide",
)

watchlist = render_watchlist_sidebar()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Swing Trading",
    "🔍 AI Screener",
    "📅 Earnings Kalender",
    "💬 Marked Sentiment",
    "📈 Modelportefølje",
])

with tab1:
    swing_trading.render(watchlist)

with tab2:
    ai_screener.render(watchlist)

with tab3:
    earnings.render(watchlist)

with tab4:
    reddit_sentiment.render()

with tab5:
    portfolio.render(watchlist)
```

- [ ] **Step 3: Delete Saxo files**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
rm modules/saxo_trading.py modules/saxo_placeholder.py services/saxo_service.py
```

- [ ] **Step 4: Run full test suite**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -m pytest tests/ -v 2>&1 | tail -15
```
Expected: all passing (saxo tests no longer exist; no new failures)

- [ ] **Step 5: Verify app imports cleanly**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -c "import app" 2>&1 | head -5
```
Expected: no output (or only streamlit warnings, no ImportError)

- [ ] **Step 6: Commit**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
git add app.py portfolio.json
git rm modules/saxo_trading.py modules/saxo_placeholder.py services/saxo_service.py
git commit -m "feat: replace Saxo Bank tab with Modelportefølje, delete saxo files"
```
