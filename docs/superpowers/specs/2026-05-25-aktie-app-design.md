# Aktie App — Design Spec
**Dato:** 2026-05-25
**Status:** Godkendt

## Overblik

En Streamlit-baseret aktie-app til personlig brug med deling via Streamlit Cloud. Fire faner: Swing Trading, Earnings Kalender, Reddit Sentiment og en Saxo Bank-placeholder. Modulær arkitektur designet til nem tilslutning af Saxo Bank API til automatisk paper trading.

## Arkitektur

### Filstruktur

```
Aktier APP/
├── app.py                          # Streamlit entry point, tab-routing
├── .env                            # Lokale secrets (gitignored)
├── .env.example                    # Template til deling
├── requirements.txt
├── .gitignore
├── .streamlit/
│   └── secrets.toml.example        # Template til Streamlit Cloud secrets
├── modules/
│   ├── swing_trading.py            # Tab 1 UI + logik
│   ├── earnings.py                 # Tab 2 UI + logik
│   ├── reddit_sentiment.py         # Tab 3 UI + logik
│   └── saxo_placeholder.py         # Tab 4 "Kommer snart"
├── services/
│   ├── yfinance_service.py         # Data-hentning med st.cache_data
│   ├── claude_service.py           # Anthropic API, fejler gracefully
│   └── reddit_service.py           # PRAW-integration
└── components/
    ├── charts.py                   # Plotly-charts: kurs + RSI + MA
    └── watchlist.py                # Watchlist-widget (session_state)
```

### Secrets-håndtering

Services tjekker `st.secrets` først, falder tilbage på `.env` via `python-dotenv`. Samme kodebase virker lokalt og på Streamlit Cloud.

```python
# Mønster brugt i alle services
import streamlit as st
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = st.secrets.get("KEY_NAME") or os.getenv("KEY_NAME")
```

### Watchlist Persistence

- **Lokalt:** Gemmes i `watchlist.json` (gitignored), indlæses ved opstart.
- **Streamlit Cloud:** Gemmes kun i `st.session_state`. En note i UI'et forklarer at ændringer ikke er permanente. Brugeren kan hardkode en default-liste i koden som fallback.

## Faner

### Tab 1 — Swing Trading

**Data:** 6 måneders daglige OHLCV-data via `yfinance`. Beregninger med pandas (ingen TA-biblioteker).

**Indikatorer:**
- MA20 og MA50: Rolling mean over 20/50 perioder på Close-prisen.
- RSI(14): Beregnes manuelt — gennemsnitlig gain/loss over 14 perioder, Wilder's smoothing.
- Volumen-spike: Spike defineres som daglig volumen > 1.5× 20-dages gennemsnit.

**Signal-logik:**
- Bullish: RSI < 50 (momentum nedad, ikke udmattet) OG MA20 > MA50 (optrend bekræftet)
- Bearish: RSI > 50 (momentum opad mod overstimulering) OG MA20 < MA50 (nedtrend bekræftet)
- Neutral: alt andet (inkl. RSI i ekstreme zoner med modstridende MA-signal)

**UI:**
- Dropdown til aktievalg (fra watchlist)
- Plotly-chart: kursline + MA20 + MA50 øverst, RSI i subplot nedenunder med røde/grønne zoner ved 30/70
- Statusboks: Signal (farvekodet) + volumen-spike-indikator

**Caching:** `@st.cache_data(ttl=3600)` på yfinance-kald.

### Tab 2 — Earnings Kalender

**Data:** `yfinance.Ticker.calendar` for alle aktier på watchlisten.

**UI:**
- Sorteret tabel: Ticker, Firmanavn, Earnings-dato, Estimeret EPS
- Datoer inden for 7 dage fremhæves med gul baggrund (pandas Styler)
- Spinner under datahentning

**Fejlhåndtering:** Aktier uden earnings-data springes over — ingen crash.

### Tab 3 — Reddit Sentiment

**Data:** Top-20 hot posts fra r/wallstreetbets og r/stocks via PRAW.

**UI:**
1. Tabel: Titel, Score, Kommentarer, Subreddit
2. AI-resumé-sektion: Kalder Claude Haiku med dansk prompt. Viser resumé i en info-boks.

**Prompt til Claude Haiku:**
> "Her er de 20 mest populære posts fra r/wallstreetbets og r/stocks lige nu. Lav et kort resumé på dansk af de vigtigste tendenser og stemninger i markedet baseret på disse posts."

**Fejlhåndtering:** Hvis PRAW-kald fejler → `st.warning("Kunne ikke hente Reddit-data")`. Hvis Claude-kald fejler → tabellen vises uden resumé, ingen exception propageres.

**Caching:** Reddit-posts caches i 15 minutter. Claude-resumé caches per unik post-samling (hash af titler).

### Tab 4 — Saxo Bank (Placeholder)

- Titel og kort beskrivelse: "Automatisk paper trading på Saxo Bank demo-konto"
- Liste over planlagte features: ordreafgivelse, porteføljeoverblik, trade-log
- "Kommer snart"-badge
- Ingen logik eller API-kald

## Deployment

### Lokalt

```bash
pip install -r requirements.txt
cp .env.example .env
# Udfyld .env med dine nøgler
streamlit run app.py
```

### Streamlit Cloud

1. Push kode til GitHub (`.env` og `watchlist.json` er i `.gitignore`)
2. Opret app på share.streamlit.io og forbind til repo
3. Gå til Settings → Secrets og tilføj nøgler fra `.env.example`
4. Deploy

## API-nøgler (`.env.example`)

```env
# Reddit (PRAW) — opret app på reddit.com/prefs/apps
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=aktie-app/1.0

# Anthropic — hent på console.anthropic.com
ANTHROPIC_API_KEY=
```

## Pakker (`requirements.txt`)

```
streamlit
yfinance
pandas
anthropic
praw
python-dotenv
plotly
```

## Fejlhåndteringskontrakt

Alle services returnerer data eller `None` — aldrig en exception til UI-laget. Modulerne viser `st.warning()` hvis data mangler. Reddit og Claude kan fejle uafhængigt uden at tage appen ned.

## Fremtidig Saxo Bank Integration

For at tilslutte Saxo Bank API:
1. Tilføj `services/saxo_service.py` med auth + ordre-logik
2. Erstat `modules/saxo_placeholder.py` med fuld `modules/saxo_trading.py`
3. Tilføj `SAXO_CLIENT_ID` og `SAXO_CLIENT_SECRET` til `.env.example`

Ingen eksisterende moduler skal ændres.
