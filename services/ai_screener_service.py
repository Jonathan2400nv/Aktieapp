import os
import anthropic
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

_MODEL = "claude-haiku-4-5-20251001"


def _fmt(val, suffix="", decimals=1, scale=1):
    if val is None:
        return "—"
    try:
        return f"{float(val) * scale:.{decimals}f}{suffix}"
    except Exception:
        return "—"


def get_garp_analysis(data: dict) -> str | None:
    try:
        api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    except Exception:
        api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        margin_of_safety = None
        if data.get('dcf_fair_value') and data.get('current_price'):
            margin_of_safety = round(
                (data['dcf_fair_value'] - data['current_price']) / data['current_price'] * 100, 1
            )

        macd_signal = "bullish crossover" if (
            data.get('macd') and data.get('macd_signal') and data['macd'] > data['macd_signal']
        ) else "bearish" if (
            data.get('macd') and data.get('macd_signal') and data['macd'] < data['macd_signal']
        ) else "neutral"

        ma_signal = "over MA50 (optrend)" if (
            data.get('ma20') and data.get('ma50') and data['ma20'] > data['ma50']
        ) else "under MA50 (nedtrend)" if (
            data.get('ma20') and data.get('ma50')
        ) else "—"

        prompt = f"""Du er en GARP-investor (Growth at a Reasonable Price) der analyserer følgende aktie:

**{data['ticker']} — {data['name']}**
Sektor: {data.get('sector', '—')}

FUNDAMENTALE NØGLETAL:
- Kurs: {_fmt(data.get('current_price'), '$', 2)}
- P/E (trailing): {_fmt(data.get('pe'), '', 1)}
- Forward P/E: {_fmt(data.get('fwd_pe'), '', 1)}
- P/S: {_fmt(data.get('ps'), 'x', 1)}
- ROE (proxy ROIC): {_fmt(data.get('roe'), '%', 1, 100)}
- Gæld/Egenkapital: {_fmt(data.get('de_ratio'), '', 1)}
- Omsætningsvækst: {_fmt(data.get('rev_growth'), '%', 1, 100)}
- EPS-vækst: {_fmt(data.get('eps_growth'), '%', 1, 100)}
- FCF Yield: {_fmt(data.get('fcf_yield'), '%', 2)}

VÆRDIANSÆTTELSE:
- Analytiker kursmål: {_fmt(data.get('analyst_target'), '$', 2)}
- DCF Fair Value (estimat): {_fmt(data.get('dcf_fair_value'), '$', 2)}
- Margin of Safety: {f'{margin_of_safety}%' if margin_of_safety is not None else '—'}

TEKNISKE INDIKATORER:
- RSI (14): {_fmt(data.get('rsi'), '', 1)}
- MA20 vs MA50: {ma_signal}
- MACD: {macd_signal}
- Foreslået stop-loss (2×ATR): {_fmt(data.get('stop_loss'), '$', 2)}

Analyser ud fra GARP-filosofien og svar på dansk med præcis denne struktur:

**Anbefaling:** BUY / HOLD / SELL

**GARP-vurdering:** (Er væksten attraktivt prissat? Er P/E og Forward P/E rimelige ift. vækstraten?)

**Styrker:** (Max 3 punkter)

**Risici:** (Max 3 punkter)

**Konklusion:** (2-3 sætninger — hvornår giver det mening at gå ind, og hvad skal man holde øje med?)"""

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=_MODEL,
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception:
        return None
