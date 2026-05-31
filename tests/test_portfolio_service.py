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


class TestLoadPortfolio:
    def test_returns_default_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTFOLIO_PATH", str(tmp_path / "portfolio.json"))
        from services import portfolio_service
        importlib.reload(portfolio_service)
        result = portfolio_service.load_portfolio()
        assert result["start_capital"] == 100000
        assert result["positions"] == []

    def test_roundtrip(self, tmp_path, monkeypatch):
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
