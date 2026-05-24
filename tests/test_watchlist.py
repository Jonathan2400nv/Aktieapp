import json
import os
import tempfile
import pytest
from components.watchlist import parse_tickers, format_tickers, load_watchlist, save_watchlist


class TestParseTickers:
    def test_comma_separated(self):
        assert parse_tickers("AAPL, MSFT, TSLA") == ["AAPL", "MSFT", "TSLA"]

    def test_newline_separated(self):
        assert parse_tickers("AAPL\nMSFT\nTSLA") == ["AAPL", "MSFT", "TSLA"]

    def test_mixed_separators(self):
        assert parse_tickers("AAPL, MSFT\nTSLA") == ["AAPL", "MSFT", "TSLA"]

    def test_strips_whitespace_and_uppercases(self):
        assert parse_tickers(" aapl , msft ") == ["AAPL", "MSFT"]

    def test_ignores_empty_entries(self):
        assert parse_tickers("AAPL,,MSFT") == ["AAPL", "MSFT"]

    def test_empty_string_returns_empty_list(self):
        assert parse_tickers("") == []


class TestFormatTickers:
    def test_newline_separated(self):
        assert format_tickers(["AAPL", "MSFT", "TSLA"]) == "AAPL\nMSFT\nTSLA"

    def test_empty_list(self):
        assert format_tickers([]) == ""


class TestLoadSaveWatchlist:
    def test_roundtrip(self):
        tickers = ["AAPL", "MSFT", "TSLA"]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_watchlist(tickers, path=path)
            assert load_watchlist(path=path) == tickers
        finally:
            os.unlink(path)

    def test_returns_default_when_file_missing(self):
        result = load_watchlist(path="/tmp/no_such_watchlist_xyz123.json")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_returns_default_on_corrupt_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w') as f:
            f.write("not valid json{{{")
            path = f.name
        try:
            result = load_watchlist(path=path)
            assert isinstance(result, list)
        finally:
            os.unlink(path)
