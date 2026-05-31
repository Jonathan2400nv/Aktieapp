import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.calculations import (
    calculate_ma, calculate_rsi, calculate_macd,
    calculate_bollinger, calculate_stoch_rsi, calculate_vwap,
    detect_rsi_divergence,
)

INDICATOR_OPTIONS = ["RSI", "MACD", "Bollinger %B", "Stoch RSI"]


def build_price_chart(df: pd.DataFrame, ticker: str, stop_loss: float | None = None) -> go.Figure:
    close = df['Close'].squeeze()
    ma20 = calculate_ma(close, 20)
    ma50 = calculate_ma(close, 50)
    vwap = calculate_vwap(df)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=close, name="Kurs",
                             line=dict(color="#00b4d8", width=1.5)))
    fig.add_trace(go.Scatter(x=df.index, y=ma20, name="MA20",
                             line=dict(color="#f77f00", width=1.2, dash="dot")))
    fig.add_trace(go.Scatter(x=df.index, y=ma50, name="MA50",
                             line=dict(color="#9b5de5", width=1.2, dash="dash")))
    fig.add_trace(go.Scatter(x=df.index, y=vwap, name="VWAP",
                             line=dict(color="#ffd166", width=1.0, dash="dot")))
    if stop_loss is not None:
        fig.add_hline(y=stop_loss, line_color="#ff4d4d", line_dash="dash", line_width=1.2,
                      annotation_text=f"SL {stop_loss:.2f}", annotation_position="bottom right")
    fig.update_layout(
        title=f"{ticker} — Kurs · MA20 · MA50 · VWAP",
        height=420,
        template="plotly_dark",
        legend=dict(orientation="h", y=1.06),
        margin=dict(t=50, b=10, l=10, r=10),
        hovermode="x unified",
    )
    return fig


def build_indicator_chart(df: pd.DataFrame, indicator: str) -> go.Figure:
    close = df['Close'].squeeze()
    fig = go.Figure()

    if indicator == "RSI":
        rsi = calculate_rsi(close, 14)
        divergence = detect_rsi_divergence(close, rsi)
        fig.add_trace(go.Scatter(x=df.index, y=rsi, name="RSI",
                                 line=dict(color="#e9c46a", width=1.5)))
        fig.add_hrect(y0=70, y1=100, fillcolor="red",   opacity=0.08, line_width=0)
        fig.add_hrect(y0=0,  y1=30,  fillcolor="green", opacity=0.08, line_width=0)
        fig.add_hline(y=70, line_color="red",   line_dash="dash", line_width=0.8)
        fig.add_hline(y=30, line_color="green", line_dash="dash", line_width=0.8)
        if divergence['bullish']:
            min_idx = rsi.iloc[-20:].idxmin()
            fig.add_annotation(x=min_idx, y=float(rsi.loc[min_idx]) - 5,
                               text="▲ Bull div", font=dict(color="#2ecc71", size=10), showarrow=False)
        if divergence['bearish']:
            max_idx = rsi.iloc[-20:].idxmax()
            fig.add_annotation(x=max_idx, y=float(rsi.loc[max_idx]) + 5,
                               text="▼ Bear div", font=dict(color="#e74c3c", size=10), showarrow=False)
        fig.update_yaxes(range=[0, 100])

    elif indicator == "MACD":
        macd_line, signal_line, histogram = calculate_macd(close)
        colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in histogram]
        fig.add_trace(go.Bar(x=df.index, y=histogram, name="Histogram",
                             marker_color=colors, opacity=0.7))
        fig.add_trace(go.Scatter(x=df.index, y=macd_line, name="MACD",
                                 line=dict(color="#00b4d8", width=1.2)))
        fig.add_trace(go.Scatter(x=df.index, y=signal_line, name="Signal",
                                 line=dict(color="#f77f00", width=1.2)))

    elif indicator == "Bollinger %B":
        pct_b, _ = calculate_bollinger(close)
        fig.add_trace(go.Scatter(x=df.index, y=pct_b, name="%B",
                                 line=dict(color="#a8dadc", width=1.2)))
        fig.add_hline(y=1.0, line_color="red",   line_dash="dash", line_width=0.8)
        fig.add_hline(y=0.0, line_color="green", line_dash="dash", line_width=0.8)
        fig.add_hline(y=0.5, line_color="gray",  line_dash="dot",  line_width=0.6)

    elif indicator == "Stoch RSI":
        stoch_k, stoch_d = calculate_stoch_rsi(close)
        fig.add_trace(go.Scatter(x=df.index, y=stoch_k * 100, name="%K",
                                 line=dict(color="#e9c46a", width=1.2)))
        fig.add_trace(go.Scatter(x=df.index, y=stoch_d * 100, name="%D",
                                 line=dict(color="#f77f00", width=1.0, dash="dot")))
        fig.add_hrect(y0=80, y1=100, fillcolor="red",   opacity=0.08, line_width=0)
        fig.add_hrect(y0=0,  y1=20,  fillcolor="green", opacity=0.08, line_width=0)
        fig.add_hline(y=80, line_color="red",   line_dash="dash", line_width=0.8)
        fig.add_hline(y=20, line_color="green", line_dash="dash", line_width=0.8)
        fig.update_yaxes(range=[0, 100])

    fig.update_layout(
        title=indicator,
        height=220,
        template="plotly_dark",
        legend=dict(orientation="h", y=1.12),
        margin=dict(t=40, b=10, l=10, r=10),
        hovermode="x unified",
        barmode="relative",
    )
    return fig


# Keep old name as alias so any other callers don't break
def build_swing_chart(df: pd.DataFrame, ticker: str, stop_loss: float | None = None) -> go.Figure:
    return build_price_chart(df, ticker, stop_loss)
