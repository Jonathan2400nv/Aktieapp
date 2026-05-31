import streamlit as st
import yfinance as yf
import pandas as pd
from utils.calculations import (
    calculate_rsi, calculate_ma, calculate_macd, calculate_atr,
    calculate_adx, calculate_obv, calculate_bollinger,
    calculate_stoch_rsi, detect_rsi_divergence, score_signal,
    calculate_trade_levels,
)


@st.cache_data(ttl=3600)
def fetch_screener_data(ticker: str) -> dict | None:
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        df = yf.download(ticker, period="6mo", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        close = df['Close'].squeeze() if not df.empty else None

        rsi_val = None
        ma20_val = ma50_val = None
        macd_val = macd_sig_val = None
        stop_loss = None

        adx_val = obv_rising = bollinger_squeeze = stoch_val = None
        rsi_divergence_bullish = False
        signal_score = 0
        signal_label = 'Neutral'
        rr = None
        entry_low = entry_high = t1 = t2 = None

        if close is not None and len(close) > 50:
            rsi_series = calculate_rsi(close)
            rsi_val = round(float(rsi_series.iloc[-1]), 1) if not pd.isna(rsi_series.iloc[-1]) else None
            ma20_val = float(calculate_ma(close, 20).iloc[-1])
            ma50_val = float(calculate_ma(close, 50).iloc[-1])
            macd_line, signal_line, _ = calculate_macd(close)
            macd_val = float(macd_line.iloc[-1])
            macd_sig_val = float(signal_line.iloc[-1])
            atr = calculate_atr(df).iloc[-1]
            if current_price and not pd.isna(atr):
                stop_loss = round(current_price - 2 * float(atr), 2)

            obv_series = calculate_obv(df)
            obv_rising = bool(float(obv_series.iloc[-1]) > float(obv_series.iloc[-5])) if len(obv_series) >= 5 else None

            _, bandwidth = calculate_bollinger(close)
            bw_val = float(bandwidth.iloc[-1]) if not pd.isna(bandwidth.iloc[-1]) else None
            bollinger_squeeze = bool(bw_val is not None and bw_val < 0.1)

            stoch_k, _ = calculate_stoch_rsi(close)
            stoch_val = round(float(stoch_k.iloc[-1]) * 100, 1) if not pd.isna(stoch_k.iloc[-1]) else None

            div = detect_rsi_divergence(close, rsi_series)

            scored = score_signal(df)
            signal_score = scored['score']
            signal_label = scored['label']
            adx_val = round(scored['adx'], 1)

            levels = calculate_trade_levels(df)
            rr = levels['rr']
            entry_low = levels['entry_low']
            entry_high = levels['entry_high']
            t1 = levels['t1']
            t2 = levels['t2']
            rsi_divergence_bullish = div['bullish']

        # DCF: simplified — FCF yield proxy
        free_cashflow = info.get('freeCashflow')
        market_cap = info.get('marketCap')
        fcf_yield = None
        dcf_fair_value = None
        if free_cashflow and market_cap and market_cap > 0:
            fcf_yield = round(free_cashflow / market_cap * 100, 2)
            rev_growth = info.get('revenueGrowth') or 0
            growth_rate = min(max(rev_growth, 0.03), 0.30)
            discount_rate = 0.10
            terminal_growth = 0.03
            # 5-year DCF
            projected_fcf = free_cashflow
            pv_sum = 0.0
            for yr in range(1, 6):
                projected_fcf *= (1 + growth_rate)
                pv_sum += projected_fcf / (1 + discount_rate) ** yr
            terminal_value = projected_fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)
            pv_terminal = terminal_value / (1 + discount_rate) ** 5
            shares = info.get('sharesOutstanding') or 1
            dcf_fair_value = round((pv_sum + pv_terminal) / shares, 2) if shares else None

        return {
            'ticker': ticker,
            'name': info.get('longName', ticker),
            'sector': info.get('sector', '—'),
            'current_price': current_price,
            'analyst_target': info.get('targetMeanPrice'),
            'dcf_fair_value': dcf_fair_value,
            'pe': info.get('trailingPE'),
            'fwd_pe': info.get('forwardPE'),
            'ps': info.get('priceToSalesTrailingTwelveMonths'),
            'roe': info.get('returnOnEquity'),
            'de_ratio': info.get('debtToEquity'),
            'rev_growth': info.get('revenueGrowth'),
            'eps_growth': info.get('earningsGrowth'),
            'fcf_yield': fcf_yield,
            'market_cap': market_cap,
            'rsi': rsi_val,
            'ma20': ma20_val,
            'ma50': ma50_val,
            'macd': macd_val,
            'macd_signal': macd_sig_val,
            'stop_loss': stop_loss,
            'adx': adx_val,
            'obv_rising': obv_rising,
            'bollinger_squeeze': bollinger_squeeze,
            'stoch_rsi': stoch_val,
            'rsi_divergence_bullish': rsi_divergence_bullish,
            'signal_score': signal_score,
            'signal_label': signal_label,
            'rr': rr,
            'entry_low': entry_low,
            'entry_high': entry_high,
            't1': t1,
            't2': t2,
        }
    except Exception:
        return None
