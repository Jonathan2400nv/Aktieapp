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
