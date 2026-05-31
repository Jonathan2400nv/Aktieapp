import pandas as pd


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

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm.abs()) & (minus_dm > 0), 0.0)

    atr = calculate_atr(df, period)
    plus_di = 100 * plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr

    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, float('nan')) * 100
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx


def calculate_obv(df: pd.DataFrame) -> pd.Series:
    close = df['Close'].squeeze()
    volume = df['Volume'].squeeze()
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (direction * volume).cumsum()


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
