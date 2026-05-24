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


def get_signal(rsi: pd.Series, ma20: pd.Series, ma50: pd.Series) -> str:
    last_rsi = rsi.iloc[-1]
    last_ma20 = ma20.iloc[-1]
    last_ma50 = ma50.iloc[-1]
    if last_rsi < 50 and last_ma20 > last_ma50:
        return "Bullish"
    if last_rsi > 50 and last_ma20 < last_ma50:
        return "Bearish"
    return "Neutral"
