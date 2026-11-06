# KOI — work tracker

Status key: `[ ]` open · `[~]` partly done · `[x]` done.
Priority: **P0** = conclusions may be wrong or misleading without it · **P1** = important gap · **P2** = quality / scale.
Last updated: 2026-11-02.

---

## P0 — Data depth and correctness

- [ ] **NSE/BSE XBRL filings connector.** This is the real fix for having only ~4 years of data.
  - Official quarterly and annual results under SEBI LODR, 10+ years where filed.
  - Standalone **and** consolidated basis, which removes the "consolidation unspecified" caveat.
  - First step: review NSE/BSE terms of use for automated access, then prototype one company (TCS) end to end.
  - Hooks already in place: `connectors/base.py` (`FundamentalsConnector`), `FactRecord.consolidation`, and the `source`
    column in the unique key, so it can sit alongside yfinance.
- [ ] **Shareholding-pattern connector** (NSE quarterly XBRL): promoter %, **promoter pledge %**, FII %, DII %, and
  quarter-on-quarter changes. Today only Yahoo's "insiders" / "institutions" approximations are shown.
- [ ] **Bank / NBFC metrics:** gross and net NPA, capital adequacy (CRAR), NIM, CASA, provision coverage. Until these
  exist, lenders stay capped at "Mixed" (by design).
- [ ] **Insurer metrics:** VNB and margin, solvency ratio, persistency, combined ratio, embedded value.
- [ ] **Golden tests on real companies.** Hand-check KOI's ratios for 3 companies (an IT company, a bank, a
  manufacturer) against their published annual reports, and freeze them as test fixtures. This catches field-mapping
  errors that the synthetic tests cannot.
- [ ] **Audit other foreign-currency reporters.** Infosys reports in USD on Yahoo (fixed: converted at period-end FX).
  Scan the whole stored universe for `financialCurrency != INR` and verify the converted figures for one more company.
- [ ] **Renamed / delisted peer symbols.** Check every curated symbol in `reference.py` (e.g. LTIM was still "loading" in
  the peer table) and fix or remove stale ones. Show "unavailable" instead of "loading" when a peer job has failed.

## P1 — Product gaps

- [ ] **Beginner wording on the other tabs.** Overview is beginner-first; Valuation, Peers, Scenarios and Metrics still
  use mostly technical labels.
- [ ] **Ollama narrative, live test.** The no-LLM path is tested; the LLM path (number validation, rejection) has never
  run against a real model. Run `ollama pull llama3.1:8b` and try it on 3 companies.
- [ ] **Score history and alerts.** Store a score snapshot on every refresh, and flag watchlist companies whose
  outlook or scores change after new results.
- [ ] **Screener.** Crawl the NSE universe slowly in the background and rank companies by sector-adjusted quality,
  health and growth ("top 10 in cement").
- [ ] **Backtest KOI's own method** once 10-year data exists: did high fundamentals scores go on to outperform peers?
- [ ] **Visual review of the remaining screens after the redesign.** Reviewed so far:
  - Home and Overview: Beginner mode at 1440, 768 and 390 px.
  - Every company tab: Advanced or Intermediate mode at 1440 px.

  Not yet reviewed:
  - [ ] Research report tab: a screenshot was taken but never looked at
  - [ ] Sectors list and sector detail pages
  - [ ] Compare page
  - [ ] Saved reports list, a single saved report, and report comparison
  - [ ] Methodology page
  - [ ] Every tab on a phone (390px)
- [ ] **Statement line items:** EPS rows still show "₹" plus "Cr" style formatting in places, and per-share and
  share-count rows need their own number formats.

## P2 — Engineering and scale

- [ ] **First git commit.** The repository is initialised but nothing is committed yet.
- [ ] **Frontend tests** (Playwright): search, then company page, then mode switch, then evidence drill-down.
- [ ] **CI** (GitHub Actions, free tier): backend pytest, frontend type-check, lint and build.
- [ ] **Worker resilience:** single in-process thread today. Persist the queue so jobs survive a restart, and add a
  retry with backoff for source errors.
- [ ] **Memory:** the machine has had low-memory kills. Measure the backend's footprint with 50+ companies loaded, and
  consider weekly instead of daily price history for peers.
- [ ] **Cache housekeeping:** prune `cached_analysis` and `kv_cache` entries for companies not viewed in 30 days.
- [ ] **PostgreSQL migration path:** the schema is portable; add an env switch and a migration script when needed.

---

## Done

### 2026-11-02 — trust and redesign round (after the advisor review)
- [x] Missing quality/health/growth/risk scores no longer count as a pass for the top outlooks.
- [x] Evidence gate: positive outlooks are held at "Mixed" below 4 years of data, or for lenders and insurers missing
  their sector metrics; the rule is shown on the page.
- [x] Confidence is capped (Medium below 5 years, with missing peers, or with an unknown consolidation basis; Low below
  4 years).
- [x] CAGR needs a span of 2 years or more and is labelled with its length.
- [x] DCF cost of debt uses interest and debt from the same year; the basis is shown.
- [x] Backtests with fewer than 3 points are labelled "illustrative".
- [x] Full-analysis cache keyed on company and peer data versions, peer job state, and `ENGINE_VERSION`.
- [x] The price score shows "waiting for competitors" instead of a blank while peers load.
- [x] 8 new tests: rules, caps, API endpoints, input validation, no-LLM path. 17 tests in total.
- [x] **Infosys USD bug:** foreign-currency financials are converted to INR at each period-end FX rate, and each
  converted value records its rate.
- [x] Frontend redesign (data-terminal style, seed 895773176):
  - Plain verdict first, with a 5-step outlook scale and reason / worry / price lines.
  - Scores with words, a visible disclaimer, and a beginner checklist.
  - Table-based home page, icon rail, phone bottom bar.
- [x] Charts drawn without animation, with short axis ticks, legends on multi-line charts, and one accent hue.
- [x] `?mode=` and `?tab=` URL parameters, so views can be linked.
- [x] Statement rows in accounting order; lender metrics shown only for lenders.

### 2026-11-02 — initial build
- [x] Phases 1–10: data layer, analysis engine, LangGraph agent, reports, API, frontend, README.
