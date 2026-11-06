# KOI — Autonomous Financial Intelligence for Indian Companies

KOI researches NSE-listed companies. It answers one question: **is this company financially strong and potentially
worth investing in for the long term?** It also shows the evidence behind every conclusion.

It is a research and decision-support tool, not a personalised financial adviser. It issues no buy/sell orders.

- **Three interface modes.** Beginner gives plain language and "What does this mean for me?". Intermediate adds
  metrics with explanations, peers and valuation. Advanced adds statements, DuPont, working capital, ROIC, DCF with
  editable assumptions, model backtests, the agent trace and CSV export.
- **Deterministic analysis.** Every number and score comes from Python. The optional local LLM only rephrases
  computed facts. Any narrative containing a number not present in those facts is rejected.
- **Separate verdicts.** Business quality, financial health, growth, valuation and risk are scored separately. A
  strong company at an expensive price is flagged as such.
- **Zero cost.** Uses SQLite, local Python workers, and optional Ollama. No paid APIs or cloud services.
- **Honest about thin evidence.**
  - A missing score never counts in a company's favour.
  - The positive outlooks are held at "Mixed" when there are fewer than 4 years of results.
  - Banks, NBFCs and insurers are also held at "Mixed" while their key sector metrics (asset quality, capital
    adequacy, solvency) are unavailable.
  - Confidence is capped at Medium when history is under 5 years, competitor data is incomplete, or the
    consolidation basis is unknown.
  - The rule behind each rating is shown on the page.
- **Cached analysis.** Results are reused until the company's data, a competitor's data or `ENGINE_VERSION`
  changes. While competitors are still loading, the price score shows "waiting for competitors" rather than a
  blank.

## Architecture

```
frontend/  Next.js 16 + React 19 + TypeScript + Tailwind 4 + Recharts + Lightweight Charts
backend/   FastAPI + pandas/numpy + LangGraph + SQLite
  koi/
    api.py              REST API
    config.py           env-driven settings
    db.py               schema, upserts with restatement tracking, ingestion log
    reference.py        curated sector groups, peer lists, analysis profiles (classification data only)
    companies.py        company master (NSE EQUITY_L.csv), search by name/symbol/ISIN, peer resolution
    ingest.py           freshness checks, normalisation, plausibility checks, persistence
    workers.py          single-thread priority queue: P0 company, P1 main peers, P2 wider sector
    connectors/         base interface + rate limiter; yfinance; NSE master; DATA_SOURCES registry
    analysis/
      data.py           loads stored facts
      metrics.py        35 metric definitions, per-period series with formula + input evidence
      valuation.py      P/E (TTM when 4 consecutive quarters exist), P/B, EV/EBITDA, history, two-stage DCF
      forecast.py       naive/drift/trend models, rolling-origin backtest, bear/base/bull, 68% bands
      sector_rules.py   per-profile thresholds and weights (bank, nbfc, insurance, it_services, fmcg, ...)
      scoring.py        sub-scores, outlook rules, confidence, key factors, METHODOLOGY
      peers.py          peer table, medians, ranks
      engine.py         one call -> full analysis
    agent/
      graph.py          LangGraph orchestrator + analysts + synthesiser + narrator
      tools.py          signal detection and investigation tools
      llm.py            Ollama client with number validation
    report.py           15-section report, mode filtering, saved reports and diff
  tests/                unit tests on synthetic fixtures
```

### Agent workflow (LangGraph)

```
load_data -> financial_analyst -> valuation_analyst -> peer_analyst -> risk_analyst
          -> investigate (loops while signals pending; concerns queue follow-ups) -> synthesiser -> narrator
```

The risk analyst detects these signals: rising debt, margin compression, weak cash conversion, negative FCF, revenue
slowdown, earnings drop, valuation premium, receivable build-up and low data confidence. Each signal goes to an
investigation tool.

Investigations can queue follow-ups. For example, a concerning debt finding triggers a cash-quality check. Each node
logs its tools and timings, and Advanced mode shows this trace.

## Data sources

| Source | Used for | Terms note |
|---|---|---|
| NSE `EQUITY_L.csv` | Company master: symbol, name, ISIN, listing date | Public archive file. NSE site terms restrict automated and commercial use; KOI fetches it at most weekly. |
| Yahoo Finance via `yfinance` | Statements (~4 annual, ~5 quarterly), prices, market cap, beta, sector, insider/institutional % | Unofficial. Yahoo's terms allow personal, non-commercial use only. KOI rate-limits it to ≥1.5 s between calls. |
| NSE/BSE XBRL filings | **Planned** connector for official, longer history and standalone/consolidated data | Not yet implemented. Endpoints need session cookies, and the terms need review first. |

Known limitations:
- **History depth.** History is about 4 years, short of the 5–10 year target. KOI lowers its confidence score and
  says so on the page.
- **Consolidation.** Yahoo does not state the consolidation basis, so it is stored as `unspecified`.
- **Missing sector metrics.** Bank NPA/CAR/NIM, insurer VNB/solvency, promoter pledge and the FII/DII split are not
  available from the current source. KOI lists them as unavailable rather than estimating them.

Each stored value keeps:
- symbol, metric, source label
- period and period type
- consolidation basis
- value, currency, unit
- source and retrieval time
- revision count

Restatements are logged in `financial_fact_revisions`. Missing values are never stored as zero.

## Database

SQLite at `backend/data/koi.db`. The schema is written to migrate to PostgreSQL.

Tables:
- `companies`, `sectors`, `sector_peers`
- `financial_facts`, exposed through the views `income_statements`, `balance_sheets` and `cash_flows`
- `financial_fact_revisions`, `financial_ratios`
- `market_snapshot`, `market_prices`, `shareholding`
- `company_filings`, `data_sources`, `data_ingestion_logs`
- `analysis_reports`, `watchlists`, `recent_views`, `cached_analysis`, `kv_cache`

## Installation

Requirements:
- Python 3.12 managed by [uv](https://docs.astral.sh/uv/)
- Node 20.9+
- Optional: [Ollama](https://ollama.com)

Backend:

```powershell
cd backend
uv sync --python 3.12
uv run uvicorn koi.api:app --port 8000
```

Frontend, in a second terminal:

```powershell
cd frontend
npm install
npm run dev        # or: npm run build; npm start
```

Then open http://localhost:3000.

Optional AI narrative:

```powershell
ollama pull llama3.1:8b
```

Any local model works; set `KOI_OLLAMA_MODEL`. KOI is fully functional without Ollama.

Tests:

```powershell
cd backend
uv run pytest
```

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | DB, worker and LLM status |
| GET | `/api/search?q=` | Search by name, NSE symbol or ISIN |
| GET | `/api/home` | Popular, recent, watchlist, reports, sectors |
| GET | `/api/market/overview` | NIFTY 50, SENSEX, NIFTY Bank, NIFTY IT (cached 15 min) |
| POST | `/api/companies/{s}/analyze?force=` | Queue the company (P0) and its peers (P1/P2) |
| GET | `/api/companies/{s}/status` | Job state, freshness, peer loading |
| GET | `/api/companies/{s}/analysis` | Full deterministic analysis |
| GET | `/api/companies/{s}/report?mode=&llm_narrative=` | Agent-generated 15-section report |
| POST | `/api/companies/{s}/dcf` | DCF with custom assumptions |
| GET | `/api/companies/{s}/financials?period=` | Statements with provenance |
| GET | `/api/companies/{s}/prices` | Daily prices |
| GET | `/api/companies/{s}/export.csv?period=` | Raw facts export |
| POST/GET/DELETE | `/api/companies/{s}/reports`, `/api/reports`, `/api/reports/{id}` | Saved reports |
| GET | `/api/reports/compare?a=&b=` | Diff two saved reports |
| GET/POST/DELETE | `/api/watchlist[/{s}]` | Watchlist |
| GET/POST | `/api/sectors`, `/api/sectors/{key}`, `/api/sectors/{key}/load` | Sector discovery |
| GET | `/api/compare?symbols=` | Cross-company comparison |
| GET | `/api/methodology`, `/api/sources` | Scoring rules, thresholds, metric definitions, ingestion log |

## Development notes

- **Adding a connector.** Implement `fetch(symbol) -> FundamentalsBundle` (see `connectors/base.py`), register it in
  `DATA_SOURCES`, and call it from `ingest.py`. Facts from different sources coexist because `source` is part of the
  unique key.
- **Changing scoring.** Edit `analysis/sector_rules.py`. The Methodology page reflects the change automatically.
- **Next.js 16.** Dynamic routes use a server `page.tsx` that awaits `params` inside `<Suspense>` and renders a client
  `Client.tsx`.
- **Test data.** Tests use synthetic fixtures labelled as such. No mock data is used in the application.
