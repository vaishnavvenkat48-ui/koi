"""Ingestion service: freshness checks, normalisation and persistence of connector output."""

from __future__ import annotations

import threading
from typing import Any

from . import companies, db, reference
from .config import settings
from .connectors.base import FundamentalsBundle, SourceUnavailable

_connector = None
_connector_lock = threading.Lock()

# Plausibility limits used to reject obviously broken values from a source.
_MAX_ABS_INR = 1e15          # 1 quadrillion INR; larger than any Indian company's balance sheet
_MAX_ABS_SHARES = 1e12


def connector():
    global _connector
    with _connector_lock:
        if _connector is None:
            from .connectors.yfinance_conn import YFinanceConnector
            _connector = YFinanceConnector()
        return _connector


def freshness(symbol: str) -> dict[str, Any]:
    c = companies.get(symbol) or {}
    last = db.query_one(
        "SELECT status, message, finished_at FROM data_ingestion_logs WHERE symbol=? AND kind='fundamentals' "
        "ORDER BY id DESC LIMIT 1", (symbol,))
    age = db.age_hours(c.get("info_updated_at"))
    latest = db.query_one(
        "SELECT MAX(period_end) AS annual FROM financial_facts WHERE symbol=? AND period_type='annual'", (symbol,))
    latest_q = db.query_one(
        "SELECT MAX(period_end) AS q FROM financial_facts WHERE symbol=? AND period_type='quarterly'", (symbol,))
    return {
        "retrieved_at": c.get("info_updated_at"),
        "age_hours": None if age is None else round(age, 1),
        "stale": age is None or age > settings.fundamentals_ttl_h,
        "has_data": bool(latest and latest["annual"]),
        "latest_annual_period": latest["annual"] if latest else None,
        "latest_quarterly_period": latest_q["q"] if latest_q else None,
        "last_attempt": last,
        "ttl_hours": settings.fundamentals_ttl_h,
    }


def needs_refresh(symbol: str) -> bool:
    return freshness(symbol)["stale"]


def ingest_company(symbol: str, force: bool = False) -> dict[str, Any]:
    """Fetch and store fundamentals, snapshot and prices for one company."""
    symbol = companies.normalise_symbol(symbol)
    if not force and not needs_refresh(symbol):
        return {"symbol": symbol, "status": "fresh"}
    started = db.now_iso()
    try:
        bundle = connector().fetch(symbol)
    except SourceUnavailable as e:
        db.log_ingestion(symbol, "yfinance", "fundamentals", "error", str(e), started_at=started)
        return {"symbol": symbol, "status": "error", "message": str(e)}
    except Exception as e:  # network errors, parser changes in the source, etc.
        db.log_ingestion(symbol, "yfinance", "fundamentals", "error", f"{type(e).__name__}: {e}", started_at=started)
        return {"symbol": symbol, "status": "error", "message": f"{type(e).__name__}: {e}"}
    counts = store_bundle(symbol, bundle, "yfinance")
    status = "ok" if counts["facts_total"] else "partial"
    msg = "; ".join([f"{k}={v}" for k, v in counts.items()] + bundle.warnings)
    db.log_ingestion(symbol, "yfinance", "fundamentals", status, msg, counts["facts_total"], started)
    return {"symbol": symbol, "status": status, **counts, "warnings": bundle.warnings}


def store_bundle(symbol: str, b: FundamentalsBundle, source: str) -> dict[str, int]:
    ts = db.now_iso()
    counts = {"inserted": 0, "unchanged": 0, "revised": 0, "rejected": 0, "facts_total": 0, "prices": 0}
    with db.tx() as conn:
        existing = conn.execute("SELECT symbol, sector_key, profile FROM companies WHERE symbol=?", (symbol,)).fetchone()
        group = reference.group_for_symbol(symbol)
        profile = (group or {}).get("profile") or reference.profile_for_industry(b.profile.sector, b.profile.industry)
        if existing is None:
            conn.execute(
                "INSERT INTO companies (symbol, name, yf_symbol, master_source, master_updated_at) VALUES (?,?,?,?,?)",
                (symbol, b.profile.name or symbol, f"{symbol}.NS", source, ts))
        conn.execute(
            """UPDATE companies SET name=COALESCE(?, name), sector=?, industry=?, website=?, description=?, currency=?,
               profile=COALESCE(profile, ?), info_source=?, info_updated_at=? WHERE symbol=?""",
            (b.profile.name, b.profile.sector, b.profile.industry, b.profile.website, b.profile.description,
             b.profile.currency, profile, source, ts, symbol))
        s = b.snapshot
        conn.execute(
            """INSERT INTO market_snapshot (symbol, price, market_cap, shares_outstanding, beta, currency,
               held_insiders_pct, held_institutions_pct, as_of, source) VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(symbol) DO UPDATE SET price=excluded.price, market_cap=excluded.market_cap,
               shares_outstanding=excluded.shares_outstanding, beta=excluded.beta, currency=excluded.currency,
               held_insiders_pct=excluded.held_insiders_pct, held_institutions_pct=excluded.held_institutions_pct,
               as_of=excluded.as_of, source=excluded.source""",
            (symbol, s.price, s.market_cap, s.shares_outstanding, s.beta, s.currency, s.held_insiders_pct,
             s.held_institutions_pct, ts, source))
        for f in b.facts:
            limit = _MAX_ABS_SHARES if f.unit == "shares" else _MAX_ABS_INR
            if abs(f.value) > limit:
                counts["rejected"] += 1
                continue
            result = db.upsert_fact(conn, {
                "symbol": symbol, "statement": f.statement, "metric": f.metric, "source_label": f.source_label,
                "period_end": f.period_end, "period_type": f.period_type, "consolidation": f.consolidation,
                "value": f.value, "currency": f.currency, "unit": f.unit, "source": source,
                "publication_date": f.publication_date, "retrieved_at": ts,
            })
            counts[result] += 1
            counts["facts_total"] += 1
        for p in b.prices:
            conn.execute(
                """INSERT INTO market_prices (symbol, date, open, high, low, close, volume, source) VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(symbol, date, source) DO UPDATE SET open=excluded.open, high=excluded.high,
                   low=excluded.low, close=excluded.close, volume=excluded.volume""",
                (symbol, p["date"], p["open"], p["high"], p["low"], p["close"], p["volume"], source))
            counts["prices"] += 1
        if s.held_insiders_pct is not None:
            conn.execute(
                """INSERT INTO shareholding (symbol, as_of, category, pct, source, retrieved_at) VALUES (?,?,?,?,?,?)
                   ON CONFLICT(symbol, as_of, category, source) DO UPDATE SET pct=excluded.pct""",
                (symbol, ts[:10], "insiders", s.held_insiders_pct, source, ts))
        if s.held_institutions_pct is not None:
            conn.execute(
                """INSERT INTO shareholding (symbol, as_of, category, pct, source, retrieved_at) VALUES (?,?,?,?,?,?)
                   ON CONFLICT(symbol, as_of, category, source) DO UPDATE SET pct=excluded.pct""",
                (symbol, ts[:10], "institutions", s.held_institutions_pct, source, ts))
    return counts


def data_version(symbol: str) -> str:
    """Changes whenever stored inputs change; used to invalidate cached analysis."""
    row = db.query_one(
        "SELECT COUNT(*) AS n, COALESCE(SUM(revision),0) AS r, MAX(retrieved_at) AS t FROM financial_facts WHERE symbol=?",
        (symbol,))
    snap = db.query_one("SELECT as_of FROM market_snapshot WHERE symbol=?", (symbol,))
    return f"{row['n']}:{row['r']}:{row['t']}:{snap['as_of'] if snap else ''}"
