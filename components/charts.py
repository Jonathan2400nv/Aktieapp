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

    # Row 1: Price + MAs + VWAP + stop-loss
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

    # Row 2: RSI + divergence markers
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

    # Row 3: MACD
    colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in histogram]
    fig.add_trace(go.Bar(x=df.index, y=histogram, name="MACD Hist",
                         marker_color=colors, opacity=0.7), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=macd_line, name="MACD",
                             line=dict(color="#00b4d8", width=1.2)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=signal_line, name="Signal",
                             line=dict(color="#f77f00", width=1.2)), row=3, col=1)

    # Row 4: Bollinger %B
    fig.add_trace(go.Scatter(x=df.index, y=pct_b, name="%B",
                             line=dict(color="#a8dadc", width=1.2)), row=4, col=1)
    fig.add_hline(y=1.0, line_color="red",   line_dash="dash", line_width=0.8, row=4, col=1)
    fig.add_hline(y=0.0, line_color="green", line_dash="dash", line_width=0.8, row=4, col=1)
    fig.add_hline(y=0.5, line_color="gray",  line_dash="dot",  line_width=0.6, row=4, col=1)

    # Row 5: Stochastic RSI
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
    fig.update_yaxes(title_text="RSI",      range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="MACD",                     row=3, col=1)
    fig.update_yaxes(title_text="%B",                       row=4, col=1)
    fig.update_yaxes(title_text="StochRSI", range=[0, 100], row=5, col=1)
    return fig
