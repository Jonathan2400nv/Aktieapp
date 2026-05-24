import pandas as pd
import pytest
from utils.calculations import calculate_rsi, calculate_ma, detect_volume_spike, get_signal


def make_close(values):
    return pd.Series(values, dtype=float)


def make_volume(values):
    return pd.Series(values, dtype=float)


class TestCalculateMA:
    def test_ma20_returns_nan_for_insufficient_data(self):
        close = make_close(range(19))
        result = calculate_ma(close, 20)
        assert result.isna().all()

    def test_ma20_correct_value(self):
        close = make_close([float(i) for i in range(1, 21)])
        result = calculate_ma(close, 20)
        assert abs(result.iloc[-1] - 10.5) < 0.001

    def test_ma_period_1_equals_close(self):
        close = make_close([1.0, 2.0, 3.0])
        result = calculate_ma(close, 1)
        pd.testing.assert_series_equal(result, close, check_names=False)


class TestCalculateRSI:
    def test_rsi_returns_series_same_length(self):
        close = make_close([float(i) for i in range(1, 50)])
        result = calculate_rsi(close, period=14)
        assert len(result) == len(close)

    def test_rsi_values_between_0_and_100(self):
        close = make_close([float(i) for i in range(1, 50)])
        result = calculate_rsi(close, period=14)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_rsi_rising_prices_above_50(self):
        close = make_close([float(i) for i in range(1, 60)])
        result = calculate_rsi(close, period=14)
        assert result.iloc[-1] > 50

    def test_rsi_falling_prices_below_50(self):
        close = make_close([float(60 - i) for i in range(60)])
        result = calculate_rsi(close, period=14)
        assert result.iloc[-1] < 50


class TestDetectVolumeSpike:
    def test_spike_detected_when_above_threshold(self):
        volume = make_volume([100.0] * 19 + [200.0])
        result = detect_volume_spike(volume)
        assert bool(result.iloc[-1]) is True

    def test_no_spike_when_below_threshold(self):
        volume = make_volume([100.0] * 20)
        result = detect_volume_spike(volume)
        assert bool(result.iloc[-1]) is False

    def test_returns_boolean_series(self):
        volume = make_volume([100.0] * 20)
        result = detect_volume_spike(volume)
        assert result.dtype == bool


class TestGetSignal:
    def _series(self, last_value, length=50):
        data = [50.0] * length
        data[-1] = last_value
        return pd.Series(data, dtype=float)

    def test_bullish_signal(self):
        assert get_signal(
            rsi=self._series(40.0),
            ma20=self._series(110.0),
            ma50=self._series(100.0),
        ) == "Bullish"

    def test_bearish_signal(self):
        assert get_signal(
            rsi=self._series(60.0),
            ma20=self._series(90.0),
            ma50=self._series(100.0),
        ) == "Bearish"

    def test_neutral_when_indicators_conflict(self):
        # RSI > 50 (bearish) men MA20 > MA50 (bullish) → konflikt → Neutral
        assert get_signal(
            rsi=self._series(60.0),
            ma20=self._series(110.0),
            ma50=self._series(100.0),
        ) == "Neutral"

    def test_returns_none_when_rsi_is_nan(self):
        import math
        rsi = self._series(float('nan'))
        ma20 = self._series(110.0)
        ma50 = self._series(100.0)
        assert get_signal(rsi=rsi, ma20=ma20, ma50=ma50) is None
