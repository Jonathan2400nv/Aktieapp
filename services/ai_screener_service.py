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


def get_stock_analysis(data: dict) -> str | None:
    try:
        api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    except Exception:
        api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        macd_signal = "bullish crossover" if (
            data.get('macd') and data.get('macd_signal') and data['macd'] > data['macd_signal']
        ) else "bearish" if (
            data.get('macd') and data.get('macd_signal') and data['macd'] < data['macd_signal']
        ) else "neutral"

        ma_signal = (
            "over MA50 (optrend)" if (data.get('ma20') and data.get('ma50') and data['ma20'] > data['ma50'])
            else "under MA50 (nedtrend)" if (data.get('ma20') and data.get('ma50'))
            else "—"
        )

        momentum_score_raw = data.get('signal_score', 0)
        if momentum_score_raw >= 5:
            momentum_label = "Stærk (≥5/7)"
        elif momentum_score_raw >= 3:
            momentum_label = "Moderat (3-4/7)"
        else:
            momentum_label = "Svag (<3/7)"

        prompt = f"""Du er en erfaren aktiestrateg der analyserer aktier med et multi-framework. Analyser denne aktie og svar KUN på dansk.

**{data['ticker']} — {data['name']}**
Sektor: {data.get('sector', '—')} | Branche: {data.get('industry', '—')}

═══ FUNDAMENTALE NØGLETAL ═══
Kurs: {_fmt(data.get('current_price'), '$', 2)}
Markedsværdi: {_fmt(data.get('market_cap'), '', 0)} USD

Vækst:
- Omsætningsvækst (YoY): {_fmt(data.get('rev_growth'), '%', 1, 100)}
- EPS-vækst: {_fmt(data.get('eps_growth'), '%', 1, 100)}
- Udbytte: {_fmt(data.get('dividend_yield'), '%', 2, 100)}

Kvalitet:
- ROE: {_fmt(data.get('roe'), '%', 1, 100)}
- Bruttomargin: {_fmt(data.get('gross_margin'), '%', 1, 100)}
- FCF-konvertering (FCF/nettoindkomst): {_fmt(data.get('fcf_conversion'), '', 2)}
- Gæld/EBITDA: {_fmt(data.get('debt_ebitda'), 'x', 1)}
- Gæld/Egenkapital: {_fmt(data.get('de_ratio'), '', 1)}

═══ MULTIMETODE VÆRDIANSÆTTELSE ═══
1. DCF (base): {_fmt(data.get('dcf_fair_value'), '$', 2)} | Bull: {_fmt(data.get('dcf_bull'), '$', 2)} | Bear: {_fmt(data.get('dcf_bear'), '$', 2)}
2. EV/EBITDA: {_fmt(data.get('ev_ebitda'), 'x', 1)} (sammenlign med sektorgennemsnit)
3. Price/FCF: {_fmt(data.get('price_to_fcf'), 'x', 1)}
4. P/E (trailing): {_fmt(data.get('pe'), '', 1)} | Forward P/E: {_fmt(data.get('fwd_pe'), '', 1)} | PEG: {_fmt(data.get('peg_ratio'), '', 2)}
5. Analytiker konsensus: {_fmt(data.get('analyst_target'), '$', 2)} ({data.get('analyst_count', '—')} analytikere, anbefaling: {data.get('recommendation_key', '—')})

═══ TEKNISK MOMENTUM ═══
RSI (14): {_fmt(data.get('rsi'), '', 1)} | MA: {ma_signal} | MACD: {macd_signal}
Momentum-score: {momentum_score_raw}/7 — {momentum_label}
Signal: {data.get('signal_label', '—')}
Stop-loss (2×ATR): {_fmt(data.get('stop_loss'), '$', 2)}

═══ DIN OPGAVE ═══

Svar med PRÆCIS denne struktur (brug overskrifterne som angivet):

**AKTIE-TYPE:** [Vækstaktie / Value / GARP / Cyklisk / Udbytteaktie — og begrund i én sætning ud fra tallene]

**FAIR VALUE INTERVAL:** $[lav]–$[høj] (vægtet gennemsnit af DCF bull/bear, EV/EBITDA, P/FCF, P/E og analytiker-konsensus — angiv det samlede interval, ikke ét enkelt tal)

**TRE SCORER:**
- Kvalitetsscore: [X/10] — [1 linje begrundelse: ROE, FCF-konvertering, margin, gæld]
- Vækstsscore: [X/10] — [1 linje begrundelse: omsætningsvækst, EPS, analytiker-revisioner]
- Momentum-score: [X/10] — [1 linje begrundelse baseret på teknisk score og RSI/MACD]
- Samlet: [aktien scorer godt på X af 3 — interessant/ikke interessant]

**BULL CASE:** [2-3 sætninger — hvad skal gå rigtigt, og hvad er det realistiske upside i %]

**BEAR CASE:** [2-3 sætninger — de reelle risici der kan sende kursen ned, og potentielt downside i %]

**HVAD MARKEDET PRISER IND:** [1-2 sætninger — forklar gabet mellem din Fair Value og markedskursen. Hvad siger markedet implicit om vækst og margin?]

**HANDELSZONE:** Interessant at købe i $[X]–$[Y]. Stop-loss under ${_fmt(data.get('stop_loss'), '', 2)}. Næste modstand ved $[Z].

Hold svaret præcist og konkret. Undgå generiske vendinger. Brug tallene aktivt."""

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=_MODEL,
            max_tokens=900,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception:
        return None


# Keep old name as alias so nothing breaks if imported elsewhere
get_garp_analysis = get_stock_analysis
