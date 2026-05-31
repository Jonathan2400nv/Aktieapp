import pandas as pd
import pytest
import numpy as np
from utils.calculations import (
    calculate_rsi, calculate_ma, detect_volume_spike, get_signal,
    calculate_adx, calculate_obv, calculate_bollinger,
    calculate_stoch_rsi, calculate_vwap, detect_rsi_divergence,
)


def make_close(values):
    return pd.Series(values, dtype=float)


def make_volume(values):
    return pd.Series(values, dtype=float)


def make_ohlcv(n=60):
    np.random.seed(42)
    close = pd.Series(100 + np.cumsum(np.random.randn(n)), dtype=float)
    high = close + abs(np.random.randn(n)) * 0.5
    low = close - abs(np.random.randn(n)) * 0.5
    volume = pd.Series(np.random.randint(1_000_000, 5_000_000, n), dtype=float)
    df = pd.DataFrame({'High': high, 'Low': low, 'Close': close, 'Volume': volume})
    return df


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


class TestCalculateADX:
    def test_returns_series_same_length(self):
        df = make_ohlcv()
        result = calculate_adx(df)
        assert len(result) == len(df)

    def test_values_between_0_and_100(self):
        df = make_ohlcv(100)
        result = calculate_adx(df).dropna()
        assert (result >= 0).all() and (result <= 100).all()


class TestCalculateOBV:
    def test_returns_series_same_length(self):
        df = make_ohlcv()
        result = calculate_obv(df)
        assert len(result) == len(df)

    def test_obv_increases_on_up_day(self):
        df = pd.DataFrame({
            'Close': [10.0, 11.0],
            'Volume': [1000.0, 1000.0],
            'High': [11.0, 12.0], 'Low': [9.0, 10.0],
        })
        result = calculate_obv(df)
        assert result.iloc[1] > result.iloc[0]

    def test_obv_decreases_on_down_day(self):
        df = pd.DataFrame({
            'Close': [11.0, 10.0],
            'Volume': [1000.0, 1000.0],
            'High': [12.0, 11.0], 'Low': [10.0, 9.0],
        })
        result = calculate_obv(df)
        assert result.iloc[1] < result.iloc[0]


class TestCalculateBollinger:
    def test_returns_two_series(self):
        df = make_ohlcv()
        pct_b, bandwidth = calculate_bollinger(df['Close'])
        assert len(pct_b) == len(df)
        assert len(bandwidth) == len(df)

    def test_pct_b_near_zero_at_lower_band(self):
        # Flat price at lower band — %B should be near 0
        close = pd.Series([100.0] * 19 + [90.0])
        pct_b, _ = calculate_bollinger(close)
        assert pct_b.iloc[-1] < 0.3


class TestCalculateStochRSI:
    def test_returns_k_and_d(self):
        df = make_ohlcv(80)
        k, d = calculate_stoch_rsi(df['Close'])
        assert len(k) == len(df)
        assert len(d) == len(df)

    def test_k_between_0_and_1(self):
        df = make_ohlcv(80)
        k, _ = calculate_stoch_rsi(df['Close'])
        valid = k.dropna()
        assert (valid >= 0).all() and (valid <= 1).all()


class TestCalculateVWAP:
    def test_returns_series_same_length(self):
        df = make_ohlcv()
        result = calculate_vwap(df)
        assert len(result) == len(df)

    def test_vwap_between_low_and_high(self):
        df = make_ohlcv(30)
        result = calculate_vwap(df).dropna()
        assert (result >= df['Low'].min()).all()
        assert (result <= df['High'].max()).all()


class TestDetectRSIDivergence:
    def test_returns_dict_with_bullish_and_bearish(self):
        df = make_ohlcv(60)
        close = df['Close']
        from utils.calculations import calculate_rsi
        rsi = calculate_rsi(close)
        result = detect_rsi_divergence(close, rsi)
        assert 'bullish' in result
        assert 'bearish' in result
        assert isinstance(result['bullish'], bool)
        assert isinstance(result['bearish'], bool)
