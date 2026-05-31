# Modelportefølje — Design Spec

## Oversigt

En ny fane i Aktie App'en der erstatter Saxo Bank-integrationen. Porteføljen tracker appens egne KØB-anbefalinger automatisk som en live papir-portefølje med startdato 01.06.2025 og startkapital 100.000 kr. Formålet er at dokumentere appens reelle performance, hvis en bruger følger hvert signal.

## Arkitektur

**Ny fane:** `modules/portfolio.py` erstatter `modules/saxo_trading.py` i `app.py`.

**Persistent data:** `portfolio.json` i projektets rod. Indeholder positioner og historik. Committes til GitHub så deployed app altid ser seneste data.

**Dataopdatering:** On-demand ved tab-åbning. Henter daglige OHLC-data (yfinance) for alle aktive positioner siden indgangsdato og backfiller historisk — stop-loss og T2-hits registreres på den korrekte dato, uanset hvornår brugeren sidst åbnede appen.

**Benchmark:** SPY ETF hentes dagligt fra yfinance (samme startdato) og vises som grå stiplet kurve mod porteføljens grønne kurve.

## Filer

| Fil | Handling | Ansvar |
|-----|----------|--------|
| `modules/portfolio.py` | Opret | Streamlit UI: dashboard, tabeller, chart |
| `services/portfolio_service.py` | Opret | Forretningslogik: scan, backfill, lukning, persistens |
| `portfolio.json` | Opret | Persistens: positioner og lukket historik |
| `app.py` | Modificer | Erstat Saxo-fane med Modelportefølje-fane |
| `modules/saxo_trading.py` | Slet | Erstattes af portfolio.py |
| `services/saxo_service.py` | Slet | Ikke længere nødvendig |

## Data Model (`portfolio.json`)

```json
{
  "start_date": "2025-06-01",
  "start_capital": 100000,
  "position_size": 10000,
  "positions": [
    {
      "ticker": "ADBE",
      "source": "AI Screener",
      "entry_price": 245.00,
      "entry_date": "2025-06-01",
      "stop_loss": 239.82,
      "t1": 270.00,
      "t2": 290.00,
      "status": "active",
      "t1_hit": false,
      "close_price": null,
      "close_date": null,
      "close_reason": null
    }
  ]
}
```

`status` kan være: `"active"` | `"closed"`

`close_reason` kan være: `"stop_loss"` | `"t2"` | `"manual"` | `null`

## Porteføljelogik

### Positionsstørrelse
Hver position allokerer fast 10.000 kr. af de 100.000 kr. (10%). Op til 10 samtidige positioner.

### Automatisk tilføjelse af ny position
Trigger: en aktie på watchlisten scorer ≥ 5 (KØB-signal fra `score_signal()`).

Regler:
- Hvis aktien allerede har en aktiv position: spring over (ingen dobbeltpositioner)
- Indgangspris: `entry_mid` fra `calculate_trade_levels()`
- Stop-loss, T1, T2: fra `calculate_trade_levels()`
- Kilde: `"Portefølje-scan"` — alle auto-tilføjede positioner bruger samme kilde, da portfolio_service scanner alle watchlist-aktier i én omgang
- Indgangsdato: handelsdagens dato (UTC)

### Historisk backfill ved tab-åbning
For hver aktiv position:
1. Download daglige OHLC-data fra `entry_date` til i dag (yfinance)
2. Iterer dag for dag i kronologisk rækkefølge:
   - Hvis `low <= stop_loss`: luk positionen, `close_price = stop_loss`, `close_reason = "stop_loss"`, `close_date = den dag`
   - Hvis `high >= t2`: luk positionen, `close_price = t2`, `close_reason = "t2"`, `close_date = den dag`
   - Hvis begge på samme dag: stop-loss prioriteres
3. Opdater `portfolio.json` med eventuelle lukkede positioner

### P&L-beregning
- Aktiv position: `pnl_pct = (current_price - entry_price) / entry_price`
- Lukket position: `pnl_pct = (close_price - entry_price) / entry_price`
- P&L i kr.: `pnl_kr = position_size * pnl_pct` (10.000 kr. × afkast%)
- Samlet porteføljeværdi: `100.000 + sum(pnl_kr for alle positioner)`
- Samlet afkast %: `(porteføljeværdi - 100.000) / 100.000 * 100`

### Daglig porteføljeværdi (til kurve)
Rekonstrueres fra positionsdata:
1. For hver kalenderdag fra `start_date` til i dag
2. Identificer alle positioner aktive den dag (entry_date ≤ dag ≤ close_date eller stadig åben)
3. Hent closing-kurs den dag (allerede hentet via backfill)
4. Beregn P&L for alle positioner → summér til daglig porteføljeværdi
5. Dage uden positioner: porteføljeværdi = forrige dags værdi

### Benchmark (S&P 500)
- Hent SPY daglige close fra `start_date` til i dag
- Normaliser til 100.000 kr. på startdato
- Beregn løbende benchmarkværdi: `100.000 * (spy_close / spy_start_close)`
- Outperformance: `portefølje_afkast_pct - spy_afkast_pct`

## UI (modules/portfolio.py)

### Dashboard (øverst)
4 KPI-bokse i en række:
- Samlet afkast: `+X,X%` og `+XX.XXX kr.` (grøn/rød)
- Porteføljeværdi: `XXX.XXX kr.`
- vs. S&P 500: `+X,X pp` outperformance (gul)
- Positioner: `X aktive | X lukkede`

### Performance-kurve
Plotly linjegraf:
- Grøn kurve: daglig porteføljeværdi fra startdato
- Grå stiplet kurve: S&P 500 (SPY) normaliseret til samme startkapital
- X-akse: dato, Y-akse: kr.

### Aktive positioner (tabel)
Kolonner: Aktie, Kilde, Indgang ($), Nuv. kurs ($), Afkast %, Afkast kr., Stop-loss, T1, T2, Status

Status-logik:
- `● Aktiv` (grøn)
- `● T1 nær` (gul) — når nuværende kurs ≥ 90% af vejen fra entry til T1
- `● SL nær` (rød) — når nuværende kurs ≤ entry + 30% af (entry - stop_loss)

### Lukkede positioner (tabel)
Kolonner: Aktie, Kilde, Indgang, Udgang, Afkast %, Afkast kr., Årsag, Dato

Årsag-visning:
- `T2 ramt ✅` (grøn)
- `Stop-loss ❌` (rød)
- `Manuel lukket` (grå)

### Manuel lukning
Knap ved hver aktiv position: "Luk position" → sætter `close_price = current_price`, `close_reason = "manual"`, `close_date = i dag`.

## Scanning for nye signaler

`portfolio_service.py` eksponerer `scan_watchlist_for_signals(watchlist, portfolio)`:
- Itererer watchlist
- Henter OHLCV (yfinance, 6 måneder, dagligt)
- Kalder `score_signal(df)` — hvis `label == "KØB"` og ticker ikke allerede aktiv i porteføljen
- Returnerer liste af nye positioner at tilføje
- Kaldes fra `portfolio.py` ved tab-åbning (cached 15 min med `@st.cache_data(ttl=900)`)

## Sletning af Saxo Bank

- `modules/saxo_trading.py` slettes
- `services/saxo_service.py` slettes
- `app.py`: `saxo_trading`-import fjernes, tab5 skifter navn til `"📈 Modelportefølje"` og kalder `portfolio.render(watchlist)`
- `modules/saxo_placeholder.py` slettes (eksisterer allerede som placeholder)

## Test

`tests/test_portfolio_service.py`:
- `test_backfill_closes_at_stop_loss` — mock OHLCV med en dag where low < SL
- `test_backfill_closes_at_t2` — mock OHLCV med en dag where high > T2
- `test_backfill_stop_loss_priority` — SL og T2 ramt samme dag → stop_loss
- `test_no_duplicate_positions` — samme ticker tilføjes ikke to gange
- `test_pnl_calculation` — verificer P&L kr. og % for aktiv og lukket position
- `test_portfolio_value` — totalværdi med mix af vinder og taber
- `test_scan_returns_new_positions_only` — aktier allerede i portefølje springes over

## Afgrænsning (ikke inkluderet)

- Valutakurs DKK/USD-konvertering (afkast trackes i % af DKK-allokering)
- Per-bruger porteføljer (fælles modelportefølje for alle besøgende)
- T1-halvering (position lukkes fuldt ved T2 — T1 bruges kun som statusindikator)
- Push-notifikationer ved stop-loss/T2
