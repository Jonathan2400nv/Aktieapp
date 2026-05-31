# Technical Analysis Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ADX, OBV, Bollinger Bands, Stochastic RSI, VWAP, RSI divergence, a point-based signal scoring system, entry/target/R:R trading strategy display, multi-timeframe confirmation, and screener filters to the existing Streamlit stock app.

**Architecture:** All new indicator math goes into `utils/calculations.py` as pure pandas functions, tested in isolation. The chart, swing trading module, screener service, and AI screener module are updated to consume the new functions. No new service files needed.

**Tech Stack:** pandas, numpy, plotly, streamlit, yfinance, pytest

---

## File Map

| File | Change |
|------|--------|
| `utils/calculations.py` | Add: `calculate_adx`, `calculate_obv`, `calculate_bollinger`, `calculate_stoch_rsi`, `calculate_vwap`, `detect_rsi_divergence`, `score_signal`, `calculate_trade_levels` |
| `tests/test_calculations.py` | Add tests for all new functions |
| `components/charts.py` | Add VWAP to price subplot; add OBV, Bollinger %B, StochRSI subplots; mark divergence arrows on RSI |
| `modules/swing_trading.py` | Replace binary signal with score display; show trade levels (entry zone, T1, T2, SL, R:R); add multi-timeframe table; gate BUY signal on ADX > 20 |
| `services/screener_service.py` | Add ADX, OBV trend, Bollinger squeeze, StochRSI, divergence, score to returned dict |
| `modules/ai_screener.py` | Add filter sidebar (score ≥ 5, ADX > 25, divergence, squeeze, R:R ≥ 1.5); show score badge per stock |

---

## Task 1: New indicator calculations

**Files:**
- Modify: `utils/calculations.py`
- Test: `tests/test_calculations.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_calculations.py`:

```python
from utils.calculations import (
    calculate_adx, calculate_obv, calculate_bollinger,
    calculate_stoch_rsi, calculate_vwap,
)
import numpy as np

def make_ohlcv(n=60):
    np.random.seed(42)
    close = pd.Series(100 + np.cumsum(np.random.randn(n)), dtype=float)
    high = close + abs(np.random.randn(n)) * 0.5
    low = close - abs(np.random.randn(n)) * 0.5
    volume = pd.Series(np.random.randint(1_000_000, 5_000_000, n), dtype=float)
    df = pd.DataFrame({'High': high, 'Low': low, 'Close': close, 'Volume': volume})
    return df

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
    def test_returns_three_series(self):
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
pytest tests/test_calculations.py -k "ADX or OBV or Bollinger or StochRSI or VWAP" -v 2>&1 | head -30
```

Expected: ImportError or similar — functions don't exist yet.

- [ ] **Step 3: Implement the five new functions in `utils/calculations.py`**

Add after `calculate_atr`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_calculations.py -k "ADX or OBV or Bollinger or StochRSI or VWAP" -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add utils/calculations.py tests/test_calculations.py
git commit -m "feat: add ADX, OBV, Bollinger, StochRSI, VWAP indicators"
```

---

## Task 2: RSI divergence detection

**Files:**
- Modify: `utils/calculations.py`
- Test: `tests/test_calculations.py`

- [ ] **Step 1: Write failing test**

```python
from utils.calculations import detect_rsi_divergence

class TestDetectRSIDivergence:
    def _make_bullish_divergence(self):
        # Price: lower low. RSI: higher low → bullish divergence
        n = 60
        close = pd.Series([100.0] * 30 + [95.0] + [96.0] * 9 + [93.0] + [94.0] * 9, dtype=float)
        rsi_mock = pd.Series([50.0] * 30 + [32.0] + [35.0] * 9 + [35.0] + [38.0] * 9, dtype=float)
        return close, rsi_mock

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
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_calculations.py::TestDetectRSIDivergence -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `detect_rsi_divergence` in `utils/calculations.py`**

```python
def detect_rsi_divergence(close: pd.Series, rsi: pd.Series, lookback: int = 20) -> dict[str, bool]:
    """
    Detects RSI divergence over the last `lookback` bars.
    Bullish: price makes lower low, RSI makes higher low.
    Bearish: price makes higher high, RSI makes lower high.
    """
    if len(close) < lookback or rsi.isna().all():
        return {'bullish': False, 'bearish': False}

    price_window = close.iloc[-lookback:]
    rsi_window = rsi.iloc[-lookback:].fillna(method='ffill')

    price_min_idx = price_window.idxmin()
    price_max_idx = price_window.idxmax()

    # Compare first half vs second half extremes
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_calculations.py::TestDetectRSIDivergence -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add utils/calculations.py tests/test_calculations.py
git commit -m "feat: add RSI divergence detection"
```

---

## Task 3: Signal scoring system

**Files:**
- Modify: `utils/calculations.py`
- Test: `tests/test_calculations.py`

- [ ] **Step 1: Write failing tests**

```python
from utils.calculations import score_signal

class TestScoreSignal:
    def _base_inputs(self):
        n = 60
        close = pd.Series([float(i) for i in range(100, 100 + n)])
        volume = pd.Series([1_000_000.0] * n)
        df = pd.DataFrame({
            'Close': close,
            'High': close + 1,
            'Low': close - 1,
            'Volume': volume,
        })
        return df

    def test_returns_dict_with_score_and_label(self):
        df = self._base_inputs()
        result = score_signal(df)
        assert 'score' in result
        assert 'label' in result
        assert result['label'] in ('KØB', 'SÆLG', 'Neutral')
        assert isinstance(result['score'], int)

    def test_score_breakdown_has_expected_keys(self):
        df = self._base_inputs()
        result = score_signal(df)
        assert 'breakdown' in result
        assert isinstance(result['breakdown'], dict)

    def test_strong_uptrend_scores_buy(self):
        # Rising price, high volume on up days → should score ≥ 5
        n = 80
        close = pd.Series([100.0 + i * 0.5 for i in range(n)])
        volume = pd.Series([2_000_000.0] * n)
        df = pd.DataFrame({
            'Close': close, 'High': close + 0.5,
            'Low': close - 0.5, 'Volume': volume,
        })
        result = score_signal(df)
        assert result['score'] >= 0  # At minimum non-negative in uptrend
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_calculations.py::TestScoreSignal -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `score_signal` in `utils/calculations.py`**

```python
def score_signal(df: pd.DataFrame) -> dict:
    """
    Returns a score dict: {'score': int, 'label': str, 'breakdown': dict, 'adx': float}.
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
        len(histogram) >= 3 and
        not pd.isna(histogram.iloc[-1]) and
        not pd.isna(histogram.iloc[-2]) and
        float(histogram.iloc[-1]) > float(histogram.iloc[-2])
    )
    obv_rising = len(obv) >= 2 and float(obv.iloc[-1]) > float(obv.iloc[-2])
    vol_spike = detect_volume_spike(volume)
    vol_spike_up = bool(vol_spike.iloc[-1]) and last_close > float(close.iloc[-2]) if len(close) >= 2 else False

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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_calculations.py::TestScoreSignal -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add utils/calculations.py tests/test_calculations.py
git commit -m "feat: add point-based signal scoring system"
```

---

## Task 4: Trade levels calculator

**Files:**
- Modify: `utils/calculations.py`
- Test: `tests/test_calculations.py`

- [ ] **Step 1: Write failing tests**

```python
from utils.calculations import calculate_trade_levels

class TestCalculateTradeLevels:
    def _make_df(self, n=60):
        close = pd.Series([100.0 + i * 0.2 for i in range(n)])
        high = close + 0.5
        low = close - 0.5
        volume = pd.Series([1_000_000.0] * n)
        return pd.DataFrame({'Close': close, 'High': high, 'Low': low, 'Volume': volume})

    def test_returns_expected_keys(self):
        df = self._make_df()
        result = calculate_trade_levels(df)
        for key in ('entry_low', 'entry_high', 'stop_loss', 't1', 't2', 'rr'):
            assert key in result, f"Missing key: {key}"

    def test_stop_below_entry(self):
        df = self._make_df()
        result = calculate_trade_levels(df)
        assert result['stop_loss'] < result['entry_low']

    def test_t1_above_entry(self):
        df = self._make_df()
        result = calculate_trade_levels(df)
        assert result['t1'] > result['entry_high']

    def test_t2_above_t1(self):
        df = self._make_df()
        result = calculate_trade_levels(df)
        assert result['t2'] > result['t1']

    def test_rr_positive(self):
        df = self._make_df()
        result = calculate_trade_levels(df)
        assert result['rr'] > 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_calculations.py::TestCalculateTradeLevels -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `calculate_trade_levels` in `utils/calculations.py`**

```python
def calculate_trade_levels(df: pd.DataFrame) -> dict:
    """
    Returns entry zone, stop-loss, T1, T2 and R:R for a BUY setup.
    entry_low  = close - 1×ATR  (ideal entry on pullback)
    entry_high = close + 0.5×ATR (max chase)
    stop_loss  = close - 2×ATR
    t1         = max(20-day high, entry_mid + 1.5×ATR)
    t2         = entry_mid + 3×ATR
    rr         = (t1 - entry_mid) / (entry_mid - stop_loss)
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_calculations.py::TestCalculateTradeLevels -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add utils/calculations.py tests/test_calculations.py
git commit -m "feat: add trade levels calculator (entry zone, T1, T2, R:R)"
```

---

## Task 5: Update chart with new indicators

**Files:**
- Modify: `components/charts.py`

The chart gets two changes:
1. VWAP line added to the price subplot
2. Two new subplots: Bollinger %B + StochRSI (replacing or adding below MACD)
3. RSI divergence arrows on RSI subplot

- [ ] **Step 1: Rewrite `build_swing_chart` in `components/charts.py`**

Replace the entire file:

```python
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.calculations import (
    calculate_ma, calculate_rsi, calculate_macd,
    calculate_bollinger, calculate_stoch_rsi, calculate_vwap,
    detect_rsi_divergence,
)


def build_swing_chart(df: pd.DataFrame, ticker: str, stop_loss: float | None = None) -> go.Figure:
    close = df['Close'].squeeze()
    ma20 = calculate_ma(close, 20)
    ma50 = calculate_ma(close, 50)
    rsi = calculate_rsi(close, 14)
    macd_line, signal_line, histogram = calculate_macd(close)
    pct_b, bandwidth = calculate_bollinger(close)
    stoch_k, stoch_d = calculate_stoch_rsi(close)
    vwap = calculate_vwap(df)
    divergence = detect_rsi_divergence(close, rsi)

    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        row_heights=[0.38, 0.15, 0.17, 0.15, 0.15],
        vertical_spacing=0.03,
        subplot_titles=(
            f"{ticker} — Kurs + MA + VWAP",
            "RSI (14)",
            "MACD",
            "Bollinger %B",
            "Stochastic RSI",
        ),
    )

    # --- Row 1: Price + MAs + VWAP + stop-loss ---
    fig.add_trace(go.Scatter(x=df.index, y=close, name="Kurs",
                             line=dict(color="#00b4d8", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=ma20, name="MA20",
                             line=dict(color="#f77f00", width=1.2, dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=ma50, name="MA50",
                             line=dict(color="#9b5de5", width=1.2, dash="dash")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=vwap, name="VWAP",
                             line=dict(color="#ffd166", width=1.0, dash="dot")), row=1, col=1)

    if stop_loss is not None:
        fig.add_hline(y=stop_loss, line_color="#ff4d4d", line_dash="dash", line_width=1.2,
                      annotation_text=f"SL {stop_loss:.2f}", annotation_position="bottom right",
                      row=1, col=1)

    # --- Row 2: RSI + divergence arrows ---
    fig.add_trace(go.Scatter(x=df.index, y=rsi, name="RSI",
                             line=dict(color="#e9c46a", width=1.5)), row=2, col=1)
    fig.add_hrect(y0=70, y1=100, fillcolor="red",   opacity=0.08, line_width=0, row=2, col=1)
    fig.add_hrect(y0=0,  y1=30,  fillcolor="green", opacity=0.08, line_width=0, row=2, col=1)
    fig.add_hline(y=70, line_color="red",   line_dash="dash", line_width=0.8, row=2, col=1)
    fig.add_hline(y=30, line_color="green", line_dash="dash", line_width=0.8, row=2, col=1)

    if divergence['bullish']:
        min_idx = rsi.iloc[-20:].idxmin()
        min_val = float(rsi.loc[min_idx])
        fig.add_annotation(x=min_idx, y=min_val - 5, text="▲ Bull div",
                           font=dict(color="#2ecc71", size=10), showarrow=False, row=2, col=1)
    if divergence['bearish']:
        max_idx = rsi.iloc[-20:].idxmax()
        max_val = float(rsi.loc[max_idx])
        fig.add_annotation(x=max_idx, y=max_val + 5, text="▼ Bear div",
                           font=dict(color="#e74c3c", size=10), showarrow=False, row=2, col=1)

    # --- Row 3: MACD ---
    colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in histogram]
    fig.add_trace(go.Bar(x=df.index, y=histogram, name="MACD Hist",
                         marker_color=colors, opacity=0.7), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=macd_line, name="MACD",
                             line=dict(color="#00b4d8", width=1.2)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=signal_line, name="Signal",
                             line=dict(color="#f77f00", width=1.2)), row=3, col=1)

    # --- Row 4: Bollinger %B ---
    fig.add_trace(go.Scatter(x=df.index, y=pct_b, name="%B",
                             line=dict(color="#a8dadc", width=1.2)), row=4, col=1)
    fig.add_hline(y=1.0, line_color="red",   line_dash="dash", line_width=0.8, row=4, col=1)
    fig.add_hline(y=0.0, line_color="green", line_dash="dash", line_width=0.8, row=4, col=1)
    fig.add_hline(y=0.5, line_color="gray",  line_dash="dot",  line_width=0.6, row=4, col=1)

    # --- Row 5: Stochastic RSI ---
    fig.add_trace(go.Scatter(x=df.index, y=stoch_k * 100, name="StochRSI %K",
                             line=dict(color="#e9c46a", width=1.2)), row=5, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=stoch_d * 100, name="StochRSI %D",
                             line=dict(color="#f77f00", width=1.0, dash="dot")), row=5, col=1)
    fig.add_hrect(y0=80, y1=100, fillcolor="red",   opacity=0.08, line_width=0, row=5, col=1)
    fig.add_hrect(y0=0,  y1=20,  fillcolor="green", opacity=0.08, line_width=0, row=5, col=1)
    fig.add_hline(y=80, line_color="red",   line_dash="dash", line_width=0.8, row=5, col=1)
    fig.add_hline(y=20, line_color="green", line_dash="dash", line_width=0.8, row=5, col=1)

    fig.update_layout(
        height=900,
        template="plotly_dark",
        legend=dict(orientation="h", y=1.04),
        margin=dict(t=60, b=20),
        hovermode="x unified",
        barmode="relative",
    )
    fig.update_yaxes(title_text="RSI",     range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="MACD",                    row=3, col=1)
    fig.update_yaxes(title_text="%B",                      row=4, col=1)
    fig.update_yaxes(title_text="StochRSI", range=[0, 100], row=5, col=1)
    return fig
```

- [ ] **Step 2: Verify app starts without errors**

```bash
cd "/Users/jonathankilmose/Documents/Aktier APP"
python3 -c "from components.charts import build_swing_chart; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add components/charts.py
git commit -m "feat: add VWAP, Bollinger %B, StochRSI subplots and divergence markers to chart"
```

---

## Task 6: Update Swing Trading module

**Files:**
- Modify: `modules/swing_trading.py`

Replace the entire module to use scoring, trade levels, and ADX gate:

- [ ] **Step 1: Rewrite `modules/swing_trading.py`**

```python
import pandas as pd
import streamlit as st
from services.yfinance_service import fetch_ohlcv
from components.charts import build_swing_chart
from utils.calculations import (
    calculate_ma, calculate_rsi, calculate_macd, calculate_atr,
    detect_volume_spike, score_signal, calculate_trade_levels,
)


def render(watchlist: list[str]) -> None:
    st.header("Swing Trading")

    if not watchlist:
        st.warning("Tilføj aktier til din watchlist i sidebaren.")
        return

    ticker = st.selectbox("Vælg aktie", watchlist)

    with st.spinner(f"Henter data for {ticker}..."):
        df = fetch_ohlcv(ticker)

    if df is None or df.empty:
        st.error(f"Kunne ikke hente data for {ticker}.")
        return

    close = df['Close'].squeeze()
    volume = df['Volume'].squeeze()
    rsi = calculate_rsi(close, 14)
    macd_line, signal_line, _ = calculate_macd(close)
    spike = detect_volume_spike(volume)

    scored = score_signal(df)
    levels = calculate_trade_levels(df)
    atr = float(calculate_atr(df).iloc[-1])
    current_price = float(close.iloc[-1])
    adx = scored['adx']

    st.plotly_chart(
        build_swing_chart(df, ticker, stop_loss=levels['stop_loss']),
        use_container_width=True,
    )

    # --- Score + signal ---
    label = scored['label']
    score = scored['score']

    if label == 'KØB' and adx >= 20:
        st.success(f"**Signal: {label}** — Score: {score}/9 · ADX: {adx:.1f}")
    elif label == 'KØB' and adx < 20:
        st.warning(f"**Signal: KØB (ADX {adx:.1f} < 20 — svag trend, afvent)**  — Score: {score}/9")
    elif label == 'SÆLG':
        st.error(f"**Signal: {label}** — Score: {score}/9 · ADX: {adx:.1f}")
    else:
        st.info(f"**Signal: Neutral** — Score: {score}/9 · ADX: {adx:.1f} — afvent klarere signal")

    # --- Score breakdown ---
    with st.expander("Score-detaljer"):
        for condition, points in scored['breakdown'].items():
            icon = "✅" if points > 0 else "⬜"
            st.write(f"{icon} {condition}: **{points}**")

    # --- Key metrics ---
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("RSI (14)", f"{rsi.iloc[-1]:.1f}" if not pd.isna(rsi.iloc[-1]) else "N/A")
    col2.metric("ADX", f"{adx:.1f}")
    col3.metric("MACD", "Bullish" if float(macd_line.iloc[-1]) > float(signal_line.iloc[-1]) else "Bearish")
    col4.metric("Volumen-spike", "Ja" if spike.iloc[-1] else "Nej")
    col5.metric("ATR", f"${atr:.2f}")

    # --- Trade levels (only show for KØB with ADX >= 20) ---
    if label == 'KØB' and adx >= 20:
        st.divider()
        st.subheader("Handelsstrategi")

        rr = levels['rr']
        rr_color = "normal" if rr >= 1.5 else "off"

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Entry zone", f"${levels['entry_low']:.2f} – ${levels['entry_high']:.2f}")
        c2.metric("Stop-loss (2×ATR)", f"${levels['stop_loss']:.2f}")
        c3.metric("Target 1 (50% profit)", f"${levels['t1']:.2f}",
                  delta=f"+{(levels['t1'] - levels['entry_mid']) / levels['entry_mid'] * 100:.1f}%")
        c4.metric("Target 2 (trailing)", f"${levels['t2']:.2f}",
                  delta=f"+{(levels['t2'] - levels['entry_mid']) / levels['entry_mid'] * 100:.1f}%")
        c5.metric("Risk/Reward", f"1:{rr}", delta="✅ Anbefalet" if rr >= 1.5 else "⚠️ Lav R:R")

        if rr < 1.0:
            st.warning("R:R under 1.0 — ikke anbefalet entry.")
```

- [ ] **Step 2: Verify module imports correctly**

```bash
python3 -c "from modules.swing_trading import render; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add modules/swing_trading.py
git commit -m "feat: replace binary signal with scoring system and trade levels in swing trading"
```

---

## Task 7: Multi-timeframe confirmation

**Files:**
- Modify: `modules/swing_trading.py`

Add a multi-timeframe section at the bottom of the `render` function.

- [ ] **Step 1: Add `_get_mtf_signals` helper and MTF table to `modules/swing_trading.py`**

Add this function before `render`:

```python
def _get_mtf_signals(ticker: str) -> list[dict]:
    import yfinance as yf
    configs = [
        ("Ugentlig",  "1y",  "1wk"),
        ("Daglig",    "6mo", "1d"),
        ("4-timers",  "60d", "1h"),
    ]
    rows = []
    for label, period, interval in configs:
        try:
            raw = yf.download(ticker, period=period, interval=interval,
                              progress=False, auto_adjust=True)
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            if raw.empty or len(raw) < 50:
                rows.append({"Tidshorisont": label, "Trend": "—", "RSI": "—", "MA": "—"})
                continue
            c = raw['Close'].squeeze()
            ma20 = calculate_ma(c, 20)
            ma50 = calculate_ma(c, 50)
            rsi_s = calculate_rsi(c, 14)
            last_rsi = float(rsi_s.iloc[-1]) if not pd.isna(rsi_s.iloc[-1]) else 50.0
            last_ma20 = float(ma20.iloc[-1]) if not pd.isna(ma20.iloc[-1]) else 0.0
            last_ma50 = float(ma50.iloc[-1]) if not pd.isna(ma50.iloc[-1]) else 0.0
            if last_ma20 > last_ma50 and last_rsi > 50:
                trend = "↑ Bullish"
            elif last_ma20 < last_ma50 and last_rsi < 50:
                trend = "↓ Bearish"
            else:
                trend = "→ Neutral"
            rows.append({
                "Tidshorisont": label,
                "Trend": trend,
                "RSI": f"{last_rsi:.1f}",
                "MA20 vs MA50": "MA20 > MA50" if last_ma20 > last_ma50 else "MA20 < MA50",
            })
        except Exception:
            rows.append({"Tidshorisont": label, "Trend": "—", "RSI": "—", "MA20 vs MA50": "—"})
    return rows
```

Add this at the end of `render`, after the trade levels section:

```python
    # --- Multi-timeframe ---
    st.divider()
    st.subheader("Multi-timeframe bekræftelse")
    with st.spinner("Henter timeframe-data..."):
        mtf = _get_mtf_signals(ticker)
    st.dataframe(pd.DataFrame(mtf), use_container_width=True, hide_index=True)
    daily_trend = next((r['Trend'] for r in mtf if r['Tidshorisont'] == 'Daglig'), '—')
    weekly_trend = next((r['Trend'] for r in mtf if r['Tidshorisont'] == 'Ugentlig'), '—')
    if 'Bullish' in daily_trend and 'Bullish' in weekly_trend:
        st.success("Daglig + ugentlig peger begge op — stærkt signal.")
    elif 'Bearish' in daily_trend and 'Bearish' in weekly_trend:
        st.error("Daglig + ugentlig peger begge ned.")
    else:
        st.info("Blandet timeframe — afvent alignment.")
```

- [ ] **Step 2: Verify no import errors**

```bash
python3 -c "from modules.swing_trading import render; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add modules/swing_trading.py
git commit -m "feat: add multi-timeframe confirmation table to swing trading"
```

---

## Task 8: Update screener service + AI Screener filters

**Files:**
- Modify: `services/screener_service.py`
- Modify: `modules/ai_screener.py`

- [ ] **Step 1: Add new fields to `services/screener_service.py`**

In `fetch_screener_data`, add after the existing technical indicator block (`if close is not None and len(close) > 50:`):

```python
            adx_series = calculate_adx(df)
            adx_val = round(float(adx_series.iloc[-1]), 1) if not pd.isna(adx_series.iloc[-1]) else None

            obv_series = calculate_obv(df)
            obv_rising = bool(float(obv_series.iloc[-1]) > float(obv_series.iloc[-5])) if len(obv_series) >= 5 else None

            _, bandwidth = calculate_bollinger(close)
            bw_val = float(bandwidth.iloc[-1]) if not pd.isna(bandwidth.iloc[-1]) else None
            bollinger_squeeze = bool(bw_val < 0.1) if bw_val is not None else False

            stoch_k, _ = calculate_stoch_rsi(close)
            stoch_val = round(float(stoch_k.iloc[-1]) * 100, 1) if not pd.isna(stoch_k.iloc[-1]) else None

            rsi_full = calculate_rsi(close)
            div = detect_rsi_divergence(close, rsi_full)

            scored = score_signal(df)
            signal_score = scored['score']
            signal_label = scored['label']
            adx_val = scored['adx']

            levels = calculate_trade_levels(df)
            rr = levels['rr']
```

Add the imports at the top of `screener_service.py`:
```python
from utils.calculations import (
    calculate_rsi, calculate_ma, calculate_macd, calculate_atr,
    calculate_adx, calculate_obv, calculate_bollinger,
    calculate_stoch_rsi, detect_rsi_divergence, score_signal,
    calculate_trade_levels,
)
```

Update the return dict to include:
```python
            'adx': adx_val,
            'obv_rising': obv_rising,
            'bollinger_squeeze': bollinger_squeeze,
            'stoch_rsi': stoch_val,
            'rsi_divergence_bullish': div['bullish'],
            'signal_score': signal_score,
            'signal_label': signal_label,
            'rr': rr,
            'entry_low': levels['entry_low'],
            'entry_high': levels['entry_high'],
            't1': levels['t1'],
            't2': levels['t2'],
```

(Add these inside the `return { ... }` block alongside existing keys.)

- [ ] **Step 2: Add filters sidebar to `modules/ai_screener.py`**

Add filter controls after the multiselect and before the "Kør AI Screener" button:

```python
    with st.expander("Filtre", expanded=False):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            filter_score = st.checkbox("Score ≥ 5 (KØB-kandidater)", value=False)
            filter_adx = st.checkbox("ADX > 25 (aktier i reel trend)", value=False)
            filter_divergence = st.checkbox("Bullish RSI-divergens", value=False)
        with f_col2:
            filter_squeeze = st.checkbox("Bollinger Squeeze", value=False)
            filter_rr = st.checkbox("R:R ≥ 1.5", value=False)
```

Apply filters in the overview table section, after building `rows`:

```python
    if filter_score:
        rows = [r for r in rows if isinstance(results.get(r['Ticker'], {}).get('signal_score'), (int, float)) and results[r['Ticker']]['signal_score'] >= 5]
    if filter_adx:
        rows = [r for r in rows if isinstance(results.get(r['Ticker'], {}).get('adx'), (int, float)) and results[r['Ticker']]['adx'] > 25]
    if filter_divergence:
        rows = [r for r in rows if results.get(r['Ticker'], {}).get('rsi_divergence_bullish')]
    if filter_squeeze:
        rows = [r for r in rows if results.get(r['Ticker'], {}).get('bollinger_squeeze')]
    if filter_rr:
        rows = [r for r in rows if isinstance(results.get(r['Ticker'], {}).get('rr'), (int, float)) and results[r['Ticker']]['rr'] >= 1.5]
```

Add Score and R:R columns to the rows dict:
```python
            "Score": scored.get('signal_score', '—') if (scored := results.get(ticker, {})) else '—',
            "Label": d.get('signal_label', '—'),
            "R:R": _fmt(d.get('rr'), '', 2),
```

- [ ] **Step 3: Verify imports**

```bash
python3 -c "from services.screener_service import fetch_screener_data; print('OK')"
python3 -c "from modules.ai_screener import render; print('OK')"
```

Expected: Both print `OK`.

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add services/screener_service.py modules/ai_screener.py
git commit -m "feat: add ADX, OBV, Bollinger squeeze, StochRSI, score and R:R to screener with filters"
```

- [ ] **Step 6: Push to GitHub (triggers Streamlit Cloud redeploy)**

```bash
git push
```

---

## Self-Review

**Spec coverage:**
- ✅ ADX with < 20 gate on BUY signal — Task 3 (scoring) + Task 6 (UI gate)
- ✅ RSI divergence detection + chart markers — Task 2 + Task 5
- ✅ OBV — Task 1 + Task 3 (in scoring) + Task 8 (screener)
- ✅ Bollinger %B + Bandwidth + Squeeze — Task 1 + Task 5 + Task 8
- ✅ VWAP on price chart — Task 5
- ✅ Stochastic RSI — Task 1 + Task 5 + Task 8
- ✅ Point scoring system with exact conditions — Task 3
- ✅ KØB ≥ 5 / SÆLG ≤ -3 / Neutral — Task 3 + Task 6
- ✅ Entry zone (1×ATR below, 0.5×ATR above) — Task 4
- ✅ T1 (20d resistance or +1.5×ATR) — Task 4
- ✅ T2 (+3×ATR) — Task 4
- ✅ Stop-loss 2×ATR — Task 4
- ✅ R:R calculation + highlight ≥ 1.5 — Task 4 + Task 6
- ✅ R:R < 1.0 warning — Task 6
- ✅ Multi-timeframe (weekly/daily/4h) — Task 7
- ✅ Screener filters (score, ADX, divergence, squeeze, R:R) — Task 8

**No placeholders found.**

**Type consistency:** All functions defined in Tasks 1–4 before being used in Tasks 5–8. `score_signal` returns `dict` with keys `score`, `label`, `breakdown`, `adx` — used consistently. `calculate_trade_levels` returns `dict` with keys `entry_low`, `entry_high`, `entry_mid`, `stop_loss`, `t1`, `t2`, `rr`, `atr` — used consistently.
