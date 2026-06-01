import streamlit as st
import yfinance as yf
import pandas as pd
from utils.calculations import (
    calculate_rsi, calculate_ma, calculate_macd, calculate_atr,
    calculate_adx, calculate_obv, calculate_bollinger,
    calculate_stoch_rsi, detect_rsi_divergence, score_signal,
    calculate_trade_levels,
)


def _dcf(free_cashflow: float, growth_rate: float, shares: int) -> float | None:
    if not free_cashflow or not shares:
        return None
    discount_rate = 0.10
    terminal_growth = 0.03
    projected_fcf = free_cashflow
    pv_sum = 0.0
    for yr in range(1, 6):
        projected_fcf *= (1 + growth_rate)
        pv_sum += projected_fcf / (1 + discount_rate) ** yr
    terminal_value = projected_fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)
    pv_terminal = terminal_value / (1 + discount_rate) ** 5
    return round((pv_sum + pv_terminal) / shares, 2)


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

        rsi_val = ma20_val = ma50_val = None
        macd_val = macd_sig_val = None
        stop_loss = None
        adx_val = obv_rising = bollinger_squeeze = stoch_val = None
        rsi_divergence_bullish = False
        signal_score = 0
        signal_label = 'Neutral'
        rr = entry_low = entry_high = t1 = t2 = None

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

        # --- Fundamental data ---
        free_cashflow = info.get('freeCashflow')
        market_cap = info.get('marketCap')
        shares = info.get('sharesOutstanding') or 1
        ebitda = info.get('ebitda')
        total_debt = info.get('totalDebt')
        rev_growth = info.get('revenueGrowth') or 0
        gross_margin = info.get('grossMargins')
        net_income = info.get('netIncomeToCommon')

        fcf_yield = None
        price_to_fcf = None
        if free_cashflow and market_cap and market_cap > 0:
            fcf_yield = round(free_cashflow / market_cap * 100, 2)
            price_to_fcf = round(market_cap / free_cashflow, 1) if free_cashflow > 0 else None

        debt_ebitda = None
        if total_debt and ebitda and ebitda > 0:
            debt_ebitda = round(total_debt / ebitda, 1)

        fcf_conversion = None
        if free_cashflow and net_income and net_income > 0:
            fcf_conversion = round(free_cashflow / net_income, 2)

        # DCF — base / bull / bear
        growth_rate_base = min(max(rev_growth, 0.03), 0.30)
        dcf_base = _dcf(free_cashflow, growth_rate_base, shares)
        dcf_bull = _dcf(free_cashflow, min(growth_rate_base * 1.5, 0.40), shares)
        dcf_bear = _dcf(free_cashflow, max(growth_rate_base * 0.5, 0.02), shares)

        return {
            'ticker': ticker,
            'name': info.get('longName', ticker),
            'sector': info.get('sector', '—'),
            'industry': info.get('industry', '—'),
            'current_price': current_price,
            'analyst_target': info.get('targetMeanPrice'),
            'analyst_count': info.get('numberOfAnalystOpinions'),
            'recommendation_key': info.get('recommendationKey', '—'),
            'dcf_fair_value': dcf_base,
            'dcf_bull': dcf_bull,
            'dcf_bear': dcf_bear,
            'pe': info.get('trailingPE'),
            'fwd_pe': info.get('forwardPE'),
            'ps': info.get('priceToSalesTrailingTwelveMonths'),
            'ev_ebitda': info.get('enterpriseToEbitda'),
            'price_to_fcf': price_to_fcf,
            'peg_ratio': info.get('pegRatio'),
            'roe': info.get('returnOnEquity'),
            'de_ratio': info.get('debtToEquity'),
            'debt_ebitda': debt_ebitda,
            'gross_margin': gross_margin,
            'fcf_conversion': fcf_conversion,
            'rev_growth': info.get('revenueGrowth'),
            'eps_growth': info.get('earningsGrowth'),
            'fcf_yield': fcf_yield,
            'dividend_yield': info.get('dividendYield'),
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
