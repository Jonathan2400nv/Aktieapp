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
