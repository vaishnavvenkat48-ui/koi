"""FastAPI application. Run: uv run uvicorn koi.api:app --reload --port 8000"""

from __future__ import annotations

import csv
import io
import logging
import math
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import companies, db, ingest, reference, report, workers
from .agent import llm
from .analysis import engine
from .analysis import metrics as M
from .analysis.scoring import METHODOLOGY
from .analysis.sector_rules import PROFILES
from .config import settings
from .connectors import DATA_SOURCES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("koi.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    companies.seed_reference()
    _seed_sources()
    workers.queue.start()
    workers.master_refresh_async()
    yield
    workers.queue.stop()


app = FastAPI(title="KOI API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"],
                   allow_headers=["*"])


def _seed_sources() -> None:
    with db.tx() as conn:
        for s in DATA_SOURCES:
            conn.execute(
                "INSERT INTO data_sources (key, name, url, coverage, terms_note) VALUES (?,?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET name=excluded.name, url=excluded.url, coverage=excluded.coverage, "
                "terms_note=excluded.terms_note", (s["key"], s["name"], s["url"], s["coverage"], s["terms_note"]))


def _clean(x: Any) -> Any:
    """JSON-safe: NaN/inf become null."""
    if isinstance(x, float):
        return None if math.isnan(x) or math.isinf(x) else x
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_clean(v) for v in x]
    return x


def ok(payload: Any) -> JSONResponse:
    return JSONResponse(_clean(payload))


def _symbol(symbol: str) -> str:
    try:
        return companies.normalise_symbol(symbol)
    except ValueError:
        raise HTTPException(422, "Invalid NSE symbol") from None


def _mode(mode: str) -> str:
    if mode not in report.MODES:
        raise HTTPException(422, f"mode must be one of {report.MODES}")
    return mode


# ------------------------------------------------------------------ system


@app.get("/api/health")
def health() -> JSONResponse:
    n = db.query_one("SELECT COUNT(*) AS n FROM companies")["n"]
    return ok({"status": "ok", "companies": n, "llm": llm.status(), "worker": workers.queue.snapshot(),
               "master_stale": companies.master_is_stale()})


@app.get("/api/methodology")
def methodology() -> JSONResponse:
    return ok({"scoring": METHODOLOGY, "profiles": {k: v for k, v in PROFILES.items()},
               "metrics": {k: d.__dict__ for k, d in M.DEFS.items()}, "data_sources": DATA_SOURCES})


@app.get("/api/sources")
def sources() -> JSONResponse:
    logs = db.query("SELECT * FROM data_ingestion_logs ORDER BY id DESC LIMIT 50")
    return ok({"sources": DATA_SOURCES, "recent_ingestion": logs})


# ------------------------------------------------------------------ discovery


@app.get("/api/search")
def search(q: str = Query(..., min_length=1, max_length=60)) -> JSONResponse:
    return ok({"results": companies.search(q)})


def _cards(symbols: list[str]) -> list[dict[str, Any]]:
    out = []
    for s in symbols:
        c = companies.get(s)
        if not c:
            continue
        snap = db.query_one("SELECT price, market_cap, as_of FROM market_snapshot WHERE symbol=?", (s,)) or {}
        cached = db.query_one("SELECT payload FROM cached_analysis WHERE symbol=? AND kind='summary'", (s,))
        import json
        out.append({"symbol": s, "name": c["name"], "sector": c.get("sector"), "sector_key": c.get("sector_key"),
                    "industry": c.get("industry"), **snap, "summary": json.loads(cached["payload"]) if cached else None})
    return out


@app.get("/api/home")
def home() -> JSONResponse:
    recent = [r["symbol"] for r in db.query("SELECT symbol FROM recent_views ORDER BY viewed_at DESC LIMIT 8")]
    watch = [r["symbol"] for r in db.query("SELECT symbol FROM watchlists WHERE name='default' ORDER BY added_at DESC")]
    return ok({
        "popular": _cards(reference.POPULAR),
        "recent": _cards(recent),
        "watchlist": _cards(watch),
        "reports": report.list_saved()[:8],
        "sectors": sectors_list(),
    })


def sectors_list() -> list[dict[str, Any]]:
    rows = db.query("SELECT s.key, s.name, s.profile, s.description, COUNT(p.symbol) AS companies FROM sectors s "
                    "LEFT JOIN sector_peers p ON p.sector_key = s.key GROUP BY s.key ORDER BY s.name")
    return rows


@app.get("/api/sectors")
def sectors() -> JSONResponse:
    return ok({"sectors": sectors_list()})


@app.get("/api/sectors/{key}")
def sector(key: str) -> JSONResponse:
    s = db.query_one("SELECT * FROM sectors WHERE key=?", (key,))
    if not s:
        raise HTTPException(404, "Unknown sector")
    syms = [r["symbol"] for r in db.query("SELECT symbol FROM sector_peers WHERE sector_key=? ORDER BY rank", (key,))]
    from .analysis.peers import snapshot_row
    return ok({"sector": s, "companies": [snapshot_row(x) for x in syms]})


@app.post("/api/sectors/{key}/load")
def sector_load(key: str) -> JSONResponse:
    syms = [r["symbol"] for r in db.query("SELECT symbol FROM sector_peers WHERE sector_key=? ORDER BY rank", (key,))]
    if not syms:
        raise HTTPException(404, "Unknown sector")
    return ok({"queued": [workers.queue.submit(s, workers.P2)["status"] for s in syms]})


INDEX_TTL_H = 0.25


@app.get("/api/market/overview")
def market_overview() -> JSONResponse:
    out = []
    for idx in reference.MARKET_INDICES:
        key = f"index:{idx['key']}"
        cached = db.kv_get(key)
        data = None
        if cached and (db.age_hours(cached[1]) or 99) < INDEX_TTL_H:
            data = cached[0]
        else:
            try:
                data = ingest.connector().fetch_index(idx["yf_symbol"])
            except Exception as e:  # network
                log.warning("index fetch failed: %s", e)
            if data:
                db.kv_set(key, data)
            elif cached:
                data = cached[0]   # serve stale rather than nothing; flagged below
        if not data or not data["series"]:
            out.append({**idx, "available": False})
            continue
        s = data["series"]
        last, prev = s[-1][1], s[-2][1] if len(s) > 1 else None
        out.append({**idx, "available": True, "last": last, "as_of": s[-1][0],
                    "change_1d": (last / prev - 1) if prev else None,
                    "change_1y": (last / s[0][1] - 1) if s[0][1] else None,
                    "spark": [v for _, v in s[-120:]], "source": "yfinance"})
    return ok({"indices": out})


# ------------------------------------------------------------------ company


@app.post("/api/companies/{symbol}/analyze")
def analyze(symbol: str, force: bool = False) -> JSONResponse:
    s = _symbol(symbol)
    if not companies.get(s):
        # Unknown to the master list: still try the source; ingestion validates the symbol.
        log.info("symbol %s not in company master; attempting source lookup", s)
    companies.record_view(s)
    return ok(workers.request_company(s, force=force))


@app.get("/api/companies/{symbol}/status")
def status(symbol: str) -> JSONResponse:
    s = _symbol(symbol)
    peers = companies.peers_for(s)
    st = workers.queue.status(s)
    fresh = ingest.freshness(s)
    return ok({"symbol": s, "job": st, "freshness": fresh,
               "peers": [{"symbol": p, "tier": "P1" if p in peers["p1"] else "P2",
                          "job": workers.queue.status(p), "has_data": ingest.freshness(p)["has_data"]}
                         for p in peers["p1"] + peers["p2"]],
               "worker": workers.queue.snapshot()})


@app.get("/api/companies/{symbol}")
def company(symbol: str) -> JSONResponse:
    s = _symbol(symbol)
    c = companies.get(s)
    if not c:
        raise HTTPException(404, "Company not found")
    return ok({"company": c, "freshness": ingest.freshness(s), "peers": companies.peers_for(s)})


@app.get("/api/companies/{symbol}/analysis")
def analysis(symbol: str) -> JSONResponse:
    s = _symbol(symbol)
    a = engine.run_cached(s)
    if a.get("ready"):
        _cache_summary(s, a)
    return ok(a)


def _cache_summary(s: str, a: dict[str, Any]) -> None:
    import json
    summary = {"outlook": a["outlook"]["label"], "code": a["outlook"]["code"],
               "fundamentals": a["scores"]["fundamentals"]["value"], "valuation": a["outlook"]["valuation_verdict"]}
    db.execute("INSERT INTO cached_analysis (symbol, kind, data_version, computed_at, payload) VALUES (?,?,?,?,?) "
               "ON CONFLICT(symbol, kind) DO UPDATE SET data_version=excluded.data_version, "
               "computed_at=excluded.computed_at, payload=excluded.payload",
               (s, "summary", ingest.data_version(s), db.now_iso(), json.dumps(summary)))


class DCFParams(BaseModel):
    risk_free: float | None = Field(None, ge=0, le=0.2)
    erp: float | None = Field(None, ge=0, le=0.2)
    terminal_growth: float | None = Field(None, ge=-0.02, le=0.1)
    beta: float | None = Field(None, ge=0.1, le=3)


@app.post("/api/companies/{symbol}/dcf")
def dcf(symbol: str, params: DCFParams) -> JSONResponse:
    s = _symbol(symbol)
    from .analysis import forecast as F
    from .analysis import valuation as V
    from .analysis.data import load
    fd = load(s)
    if not fd.has_annual():
        raise HTTPException(409, "No financial data stored yet")
    fc = F.forecast(fd, M.compute_series(fd))
    g = fc["revenue"]["scenarios"]["base"]["growth"] if fc["revenue"].get("available") else None
    return ok(V.dcf(fd, g, **params.model_dump(exclude_none=True)))


@app.get("/api/companies/{symbol}/financials")
def financials(symbol: str, period: str = Query("annual", pattern="^(annual|quarterly)$")) -> JSONResponse:
    s = _symbol(symbol)
    rows = db.query(
        "SELECT statement, metric, source_label, period_end, consolidation, value, unit, currency, source, "
        "publication_date, retrieved_at, revision FROM financial_facts WHERE symbol=? AND period_type=? "
        "ORDER BY statement, metric, period_end", (s, period))
    periods = sorted({r["period_end"] for r in rows})
    statements: dict[str, dict[str, Any]] = {}
    for r in rows:
        st = statements.setdefault(r["statement"], {})
        m = st.setdefault(r["metric"], {"metric": r["metric"], "label": r["source_label"], "unit": r["unit"],
                                       "source": r["source"], "consolidation": r["consolidation"], "values": {},
                                       "revisions": {}})
        m["values"][r["period_end"]] = r["value"]
        if r["revision"]:
            m["revisions"][r["period_end"]] = r["revision"]
    from .connectors.yfinance_conn import METRIC_MAP

    def ordered(st: str, rows: dict[str, Any]) -> list[dict[str, Any]]:
        # Accounting order (revenue first, net income near the end), not alphabetical.
        order = list(METRIC_MAP.get(st, {}).keys())
        return sorted(rows.values(), key=lambda m: order.index(m["metric"]) if m["metric"] in order else len(order))

    return ok({"symbol": s, "period_type": period, "periods": periods,
               "statements": {k: ordered(k, v) for k, v in statements.items()}})


@app.get("/api/companies/{symbol}/prices")
def prices(symbol: str, days: int = Query(1825, ge=30, le=4000)) -> JSONResponse:
    s = _symbol(symbol)
    rows = db.query("SELECT date, open, high, low, close, volume FROM market_prices WHERE symbol=? "
                    "ORDER BY date DESC LIMIT ?", (s, days))
    return ok({"symbol": s, "prices": list(reversed(rows)), "source": "yfinance"})


@app.get("/api/companies/{symbol}/export.csv")
def export_csv(symbol: str, period: str = Query("annual", pattern="^(annual|quarterly)$")) -> StreamingResponse:
    s = _symbol(symbol)
    rows = db.query(
        "SELECT symbol, statement, metric, source_label, period_end, period_type, consolidation, value, currency, "
        "unit, source, publication_date, retrieved_at, revision FROM financial_facts WHERE symbol=? AND period_type=? "
        "ORDER BY statement, metric, period_end", (s, period))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()) if rows else ["symbol"])
    w.writeheader()
    w.writerows(rows)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{s}_{period}_financials.csv"'})


# ------------------------------------------------------------------ reports & agent


@app.get("/api/companies/{symbol}/report")
def company_report(symbol: str, mode: str = "beginner", llm_narrative: bool = False) -> JSONResponse:
    s = _symbol(symbol)
    r = report.build(s, use_llm=llm_narrative, mode=_mode(mode))
    return ok(report.for_mode(r, mode))


class SaveReq(BaseModel):
    llm_narrative: bool = False


@app.post("/api/companies/{symbol}/reports")
def save_report(symbol: str, body: SaveReq | None = None) -> JSONResponse:
    s = _symbol(symbol)
    r = report.build(s, use_llm=bool(body and body.llm_narrative), mode="advanced")
    if not r.get("ready"):
        raise HTTPException(409, r.get("reason") or "No data")
    return ok({"id": report.save(r)})


@app.get("/api/reports")
def reports(symbol: str | None = None) -> JSONResponse:
    return ok({"reports": report.list_saved(_symbol(symbol) if symbol else None)})


@app.get("/api/reports/compare")
def reports_compare(a: int, b: int) -> JSONResponse:
    res = report.compare(a, b)
    if not res:
        raise HTTPException(404, "Report not found")
    return ok(res)


@app.get("/api/reports/{report_id}")
def report_get(report_id: int, mode: str = "advanced") -> JSONResponse:
    r = report.get_saved(report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    return ok(report.for_mode(r, _mode(mode)))


@app.delete("/api/reports/{report_id}")
def report_delete(report_id: int) -> JSONResponse:
    db.execute("DELETE FROM analysis_reports WHERE id=?", (report_id,))
    return ok({"deleted": report_id})


# ------------------------------------------------------------------ watchlist & compare


@app.get("/api/watchlist")
def watchlist() -> JSONResponse:
    syms = [r["symbol"] for r in db.query("SELECT symbol FROM watchlists WHERE name='default' ORDER BY added_at DESC")]
    return ok({"items": _cards(syms)})


@app.post("/api/watchlist/{symbol}")
def watch_add(symbol: str) -> JSONResponse:
    s = _symbol(symbol)
    db.execute("INSERT OR IGNORE INTO watchlists (name, symbol, added_at) VALUES ('default', ?, ?)", (s, db.now_iso()))
    return ok({"added": s})


@app.delete("/api/watchlist/{symbol}")
def watch_remove(symbol: str) -> JSONResponse:
    s = _symbol(symbol)
    db.execute("DELETE FROM watchlists WHERE name='default' AND symbol=?", (s,))
    return ok({"removed": s})


@app.get("/api/compare")
def compare(symbols: str = Query(..., max_length=200)) -> JSONResponse:
    from .analysis.peers import COLUMNS, snapshot_row
    syms = [_symbol(x) for x in symbols.split(",") if x.strip()][:6]
    for s in syms:
        workers.queue.submit(s, workers.P1)
    return ok({"columns": [{"key": k, "label": lbl, "unit": u} for k, lbl, u in COLUMNS],
               "rows": [snapshot_row(s) for s in syms]})
