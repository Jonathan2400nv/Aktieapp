import pandas as pd
import pytest
from unittest.mock import patch, MagicMock


def _make_ohlcv_df():
    idx = pd.date_range('2024-01-01', periods=5, freq='B')
    return pd.DataFrame({
        'Open': [100.0] * 5,
        'High': [105.0] * 5,
        'Low':  [98.0]  * 5,
        'Close': [102.0] * 5,
        'Volume': [1_000_000] * 5,
    }, index=idx)


class TestFetchOHLCV:
    def test_returns_dataframe_on_success(self):
        from services.yfinance_service import fetch_ohlcv
        with patch('yfinance.download', return_value=_make_ohlcv_df()):
            result = fetch_ohlcv('AAPL')
        assert isinstance(result, pd.DataFrame)
        assert not result.empty

    def test_returns_none_on_empty_dataframe(self):
        from services.yfinance_service import fetch_ohlcv
        with patch('yfinance.download', return_value=pd.DataFrame()):
            result = fetch_ohlcv('INVALID')
        assert result is None

    def test_returns_none_on_exception(self):
        from services.yfinance_service import fetch_ohlcv
        with patch('yfinance.download', side_effect=Exception("network error")):
            result = fetch_ohlcv('AAPL')
        assert result is None


class TestFetchEarningsForTicker:
    def test_returns_dict_with_correct_keys(self):
        from services.yfinance_service import fetch_earnings_for_ticker
        mock_ticker = MagicMock()
        mock_ticker.info = {'longName': 'Apple Inc.'}
        mock_ticker.calendar = {'Earnings Date': [pd.Timestamp('2025-01-28')]}
        with patch('yfinance.Ticker', return_value=mock_ticker):
            result = fetch_earnings_for_ticker('AAPL')
        assert result is not None
        assert result['ticker'] == 'AAPL'
        assert result['name'] == 'Apple Inc.'
        assert result['earnings_date'] == pd.Timestamp('2025-01-28')

    def test_returns_none_earnings_date_when_calendar_empty(self):
        from services.yfinance_service import fetch_earnings_for_ticker
        mock_ticker = MagicMock()
        mock_ticker.info = {'longName': 'Apple Inc.'}
        mock_ticker.calendar = {}
        with patch('yfinance.Ticker', return_value=mock_ticker):
            result = fetch_earnings_for_ticker('AAPL')
        assert result is not None
        assert result['earnings_date'] is None

    def test_returns_none_on_exception(self):
        from services.yfinance_service import fetch_earnings_for_ticker
        with patch('yfinance.Ticker', side_effect=Exception("network error")):
            result = fetch_earnings_for_ticker('AAPL')
        assert result is None
