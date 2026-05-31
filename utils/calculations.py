import pandas as pd
import numpy as np


def calculate_ma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(window=period).mean()


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def detect_volume_spike(volume: pd.Series, multiplier: float = 1.5) -> pd.Series:
    avg_volume = volume.rolling(window=20).mean()
    return (volume > avg_volume * multiplier).astype(bool)


def calculate_macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    close = df['Close'].squeeze()
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def get_signal(rsi: pd.Series, ma20: pd.Series, ma50: pd.Series) -> str | None:
    last_rsi = rsi.iloc[-1]
    last_ma20 = ma20.iloc[-1]
    last_ma50 = ma50.iloc[-1]
    if pd.isna(last_rsi) or pd.isna(last_ma20) or pd.isna(last_ma50):
        return None
    if last_rsi < 50 and last_ma20 > last_ma50:
        return "Bullish"
    if last_rsi > 50 and last_ma20 < last_ma50:
        return "Bearish"
    return "Neutral"


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    close = df['Close'].squeeze()

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr_wilder = tr.ewm(alpha=1/period, adjust=False).mean()

    plus_di = 100 * plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_wilder
    minus_di = 100 * minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_wilder

    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, float('nan')) * 100
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx


def calculate_obv(df: pd.DataFrame) -> pd.Series:
    close = df['Close'].squeeze()
    volume = df['Volume'].squeeze()
    direction = np.sign(close.diff())
    obv = (direction * volume).fillna(0).cumsum()
    return obv


def calculate_bollinger(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> tuple[pd.Series, pd.Series]:
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    band_range = (upper - lower).replace(0, float('nan'))
    pct_b = (close - lower) / band_range
    bandwidth = band_range / mid.replace(0, float('nan'))
    return pct_b, bandwidth


def calculate_stoch_rsi(close: pd.Series, rsi_period: int = 14, stoch_period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> tuple[pd.Series, pd.Series]:
    rsi = calculate_rsi(close, rsi_period)
    rsi_min = rsi.rolling(stoch_period).min()
    rsi_max = rsi.rolling(stoch_period).max()
    stoch = (rsi - rsi_min) / (rsi_max - rsi_min).replace(0, float('nan'))
    k = stoch.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k, d


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df['High'].squeeze() + df['Low'].squeeze() + df['Close'].squeeze()) / 3
    volume = df['Volume'].squeeze()
    cum_tp_vol = (typical * volume).cumsum()
    cum_vol = volume.cumsum().replace(0, float('nan'))
    return cum_tp_vol / cum_vol


def detect_rsi_divergence(close: pd.Series, rsi: pd.Series, lookback: int = 20) -> dict[str, bool]:
    """
    Detects RSI divergence over the last `lookback` bars.
    Bullish: price makes lower low, RSI makes higher low.
    Bearish: price makes higher high, RSI makes lower high.
    """
    if len(close) < lookback or rsi.isna().all():
        return {'bullish': False, 'bearish': False}

    price_window = close.iloc[-lookback:]
    rsi_window = rsi.iloc[-lookback:].ffill()

    mid = len(price_window) // 2
    first_half_p = price_window.iloc[:mid]
    second_half_p = price_window.iloc[mid:]
    first_half_r = rsi_window.iloc[:mid]
    second_half_r = rsi_window.iloc[mid:]

    bullish = (
        second_half_p.min() < first_half_p.min() and
        second_half_r.min() > first_half_r.min()
    )
    bearish = (
        second_half_p.max() > first_half_p.max() and
        second_half_r.max() < first_half_r.max()
    )
    return {'bullish': bool(bullish), 'bearish': bool(bearish)}


def calculate_trade_levels(df: pd.DataFrame) -> dict:
    """
    Returns BUY trade levels based on ATR.
    T1 uses the higher of 20-day resistance or entry_mid + 1.5×ATR.
    entry_mid is skewed below current price (conservative entry zone).
    """
    close = df['Close'].squeeze()
    atr_series = calculate_atr(df)
    atr = float(atr_series.iloc[-1])
    current = float(close.iloc[-1])

    entry_low = round(current - atr, 2)
    entry_high = round(current + 0.5 * atr, 2)
    entry_mid = round((entry_low + entry_high) / 2, 2)
    stop_loss = round(current - 2 * atr, 2)

    resistance_20d = float(df['High'].squeeze().iloc[-20:].max()) if len(df) >= 20 else current + 1.5 * atr
    t1 = round(max(resistance_20d, entry_mid + 1.5 * atr), 2)
    t2 = round(entry_mid + 3 * atr, 2)

    risk = entry_mid - stop_loss
    reward = t1 - entry_mid
    rr = round(reward / risk, 2) if risk > 0 else 0.0

    return {
        'entry_low': entry_low,
        'entry_high': entry_high,
        'entry_mid': entry_mid,
        'stop_loss': stop_loss,
        't1': t1,
        't2': t2,
        'rr': rr,
        'atr': round(atr, 2),
    }


def score_signal(df: pd.DataFrame) -> dict:
    """
    Returns score dict: {'score': int, 'label': str, 'breakdown': dict, 'adx': float}.
    label: 'KØB' if score >= 5, 'SÆLG' if score <= -3, else 'Neutral'.
    """
    close = df['Close'].squeeze()
    volume = df['Volume'].squeeze()

    ma20 = calculate_ma(close, 20)
    ma50 = calculate_ma(close, 50)
    rsi = calculate_rsi(close, 14)
    macd_line, signal_line, histogram = calculate_macd(close)
    adx_series = calculate_adx(df)
    obv = calculate_obv(df)
    divergence = detect_rsi_divergence(close, rsi)

    last_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
    last_ma20 = float(ma20.iloc[-1]) if not pd.isna(ma20.iloc[-1]) else 0.0
    last_ma50 = float(ma50.iloc[-1]) if not pd.isna(ma50.iloc[-1]) else 0.0
    last_close = float(close.iloc[-1])
    last_adx = float(adx_series.iloc[-1]) if not pd.isna(adx_series.iloc[-1]) else 0.0
    last_macd = float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else 0.0
    last_signal = float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else 0.0

    hist_rising = (
        len(histogram) >= 2 and
        not pd.isna(histogram.iloc[-1]) and
        not pd.isna(histogram.iloc[-2]) and
        float(histogram.iloc[-1]) > float(histogram.iloc[-2])
    )
    obv_rising = len(obv) >= 2 and float(obv.iloc[-1]) > float(obv.iloc[-2])
    vol_spike = detect_volume_spike(volume)
    vol_spike_up = (
        bool(vol_spike.iloc[-1]) and
        len(close) >= 2 and
        last_close > float(close.iloc[-2])
    )

    breakdown = {
        'Kurs > MA20 > MA50 (+2)': 2 if (last_close > last_ma20 > last_ma50 > 0) else 0,
        'MACD over signal (+1)': 1 if last_macd > last_signal else 0,
        'MACD hist stigende (+1)': 1 if hist_rising else 0,
        'RSI 40-65 (+1)': 1 if 40 <= last_rsi <= 65 else 0,
        'RSI < 35 oversold (+1)': 1 if last_rsi < 35 else 0,
        'ADX > 25 (+1)': 1 if last_adx > 25 else 0,
        'OBV stiger (+1)': 1 if obv_rising else 0,
        'Volumen-spike op (+1)': 1 if vol_spike_up else 0,
        'Bullish RSI-divergens (+2)': 2 if divergence['bullish'] else 0,
    }

    score = sum(breakdown.values())
    if score >= 5:
        label = 'KØB'
    elif score <= -3:
        label = 'SÆLG'
    else:
        label = 'Neutral'

    return {'score': score, 'label': label, 'breakdown': breakdown, 'adx': last_adx}
