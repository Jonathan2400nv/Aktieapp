import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.calculations import calculate_ma, calculate_rsi


def build_swing_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    close = df['Close'].squeeze()

    ma20 = calculate_ma(close, 20)
    ma50 = calculate_ma(close, 50)
    rsi = calculate_rsi(close, 14)

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.05,
        subplot_titles=(f"{ticker} — Kurs + MA", "RSI (14)"),
    )

    fig.add_trace(go.Scatter(
        x=df.index, y=close, name="Kurs",
        line=dict(color="#00b4d8", width=1.5),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=ma20, name="MA20",
        line=dict(color="#f77f00", width=1.2, dash="dot"),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=ma50, name="MA50",
        line=dict(color="#9b5de5", width=1.2, dash="dash"),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=rsi, name="RSI",
        line=dict(color="#e9c46a", width=1.5),
    ), row=2, col=1)

    fig.add_hrect(y0=70, y1=100, fillcolor="red",   opacity=0.08, line_width=0, row=2, col=1)
    fig.add_hrect(y0=0,  y1=30,  fillcolor="green", opacity=0.08, line_width=0, row=2, col=1)
    fig.add_hline(y=70, line_color="red",   line_dash="dash", line_width=0.8, row=2, col=1)
    fig.add_hline(y=30, line_color="green", line_dash="dash", line_width=0.8, row=2, col=1)

    fig.update_layout(
        height=580,
        template="plotly_dark",
        legend=dict(orientation="h", y=1.08),
        margin=dict(t=60, b=20),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    return fig
