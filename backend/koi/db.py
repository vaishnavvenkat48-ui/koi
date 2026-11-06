"""SQLite storage layer.

Design notes
------------
* Financial statement values are stored in long format in ``financial_facts`` (one row per
  company / statement / metric / period / consolidation / source). Views named
  ``income_statements``, ``balance_sheets`` and ``cash_flows`` expose each statement.
  Long format keeps per-value provenance (source, unit, revision) and migrates cleanly
  to PostgreSQL.
* Restatements: when a source re-publishes a different value for the same key, the old
  value is copied to ``financial_fact_revisions`` and ``revision`` is incremented.
* Only standard SQL types and ``ON CONFLICT`` upserts are used, both of which PostgreSQL supports.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Iterable, Iterator

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS sectors (
    key          TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    profile      TEXT NOT NULL,
    description  TEXT
);

CREATE TABLE IF NOT EXISTS companies (
    symbol           TEXT PRIMARY KEY,           -- NSE symbol, e.g. TCS
    name             TEXT NOT NULL,
    isin             TEXT,
    series           TEXT,
    listing_date     TEXT,
    bse_code         TEXT,
    sector_key       TEXT REFERENCES sectors(key),
    sector           TEXT,                       -- sector label from source
    industry         TEXT,
    profile          TEXT,                       -- analysis profile (bank, nbfc, it_services, ...)
    yf_symbol        TEXT,
    website          TEXT,
    description      TEXT,
    currency         TEXT,
    master_source    TEXT,
    master_updated_at TEXT,
    info_source      TEXT,
    info_updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS ix_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS ix_companies_isin ON companies(isin);

CREATE TABLE IF NOT EXISTS sector_peers (
    sector_key  TEXT NOT NULL REFERENCES sectors(key),
    symbol      TEXT NOT NULL,
    rank        INTEGER NOT NULL,               -- lower = larger / more relevant peer
    PRIMARY KEY (sector_key, symbol)
);

CREATE TABLE IF NOT EXISTS financial_facts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol           TEXT NOT NULL,
    statement        TEXT NOT NULL CHECK (statement IN ('income','balance','cashflow')),
    metric           TEXT NOT NULL,             -- normalised KOI metric key
    source_label     TEXT,                      -- label as published by the source
    period_end       TEXT NOT NULL,             -- ISO date
    period_type      TEXT NOT NULL CHECK (period_type IN ('annual','quarterly')),
    consolidation    TEXT NOT NULL,             -- consolidated | standalone | unspecified
    value            REAL NOT NULL,
    currency         TEXT,
    unit             TEXT NOT NULL,             -- e.g. INR, INR/share, shares
    source           TEXT NOT NULL,
    publication_date TEXT,                      -- filing date when the source provides it
    retrieved_at     TEXT NOT NULL,
    revision         INTEGER NOT NULL DEFAULT 0,
    UNIQUE (symbol, statement, metric, period_end, period_type, consolidation, source)
);
CREATE INDEX IF NOT EXISTS ix_facts_symbol ON financial_facts(symbol, period_type, period_end);

CREATE TABLE IF NOT EXISTS financial_fact_revisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id     INTEGER NOT NULL REFERENCES financial_facts(id),
    old_value   REAL NOT NULL,
    new_value   REAL NOT NULL,
    changed_at  TEXT NOT NULL
);

CREATE VIEW IF NOT EXISTS income_statements AS SELECT * FROM financial_facts WHERE statement = 'income';
CREATE VIEW IF NOT EXISTS balance_sheets    AS SELECT * FROM financial_facts WHERE statement = 'balance';
CREATE VIEW IF NOT EXISTS cash_flows        AS SELECT * FROM financial_facts WHERE statement = 'cashflow';

CREATE TABLE IF NOT EXISTS financial_ratios (
    symbol       TEXT NOT NULL,
    metric       TEXT NOT NULL,
    period_end   TEXT NOT NULL,
    period_type  TEXT NOT NULL,
    value        REAL,
    formula      TEXT,
    computed_at  TEXT NOT NULL,
    PRIMARY KEY (symbol, metric, period_end, period_type)
);

CREATE TABLE IF NOT EXISTS market_snapshot (
    symbol              TEXT PRIMARY KEY,
    price               REAL,
    market_cap          REAL,
    shares_outstanding  REAL,
    beta                REAL,
    currency            TEXT,
    held_insiders_pct   REAL,                   -- source: insiders (closest public proxy for promoters)
    held_institutions_pct REAL,
    as_of               TEXT NOT NULL,
    source              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shareholding (
    symbol      TEXT NOT NULL,
    as_of       TEXT NOT NULL,
    category    TEXT NOT NULL,                  -- promoter | promoter_pledged | fii | dii | public | ...
    pct         REAL NOT NULL,
    source      TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    PRIMARY KEY (symbol, as_of, category, source)
);

CREATE TABLE IF NOT EXISTS market_prices (
    symbol   TEXT NOT NULL,
    date     TEXT NOT NULL,
    open     REAL, high REAL, low REAL, close REAL, volume REAL,
    source   TEXT NOT NULL,
    PRIMARY KEY (symbol, date, source)
);

CREATE TABLE IF NOT EXISTS company_filings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT NOT NULL,
    filing_type  TEXT NOT NULL,
    period_end   TEXT,
    consolidation TEXT,
    url          TEXT,
    published_at TEXT,
    source       TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    UNIQUE (symbol, filing_type, period_end, consolidation, source)
);

CREATE TABLE IF NOT EXISTS data_sources (
    key          TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    url          TEXT,
    coverage     TEXT,
    terms_note   TEXT,
    enabled      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS data_ingestion_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT,
    source       TEXT NOT NULL,
    kind         TEXT NOT NULL,
    status       TEXT NOT NULL,                 -- ok | partial | error | skipped
    message      TEXT,
    rows         INTEGER,
    started_at   TEXT NOT NULL,
    finished_at  TEXT
);
CREATE INDEX IF NOT EXISTS ix_ingest_symbol ON data_ingestion_logs(symbol, started_at);

CREATE TABLE IF NOT EXISTS analysis_reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    outlook     TEXT,
    title       TEXT,
    payload     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlists (
    name      TEXT NOT NULL DEFAULT 'default',
    symbol    TEXT NOT NULL,
    added_at  TEXT NOT NULL,
    PRIMARY KEY (name, symbol)
);

CREATE TABLE IF NOT EXISTS recent_views (
    symbol     TEXT PRIMARY KEY,
    viewed_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cached_analysis (
    symbol       TEXT NOT NULL,
    kind         TEXT NOT NULL,
    data_version TEXT NOT NULL,                 -- hash of inputs; recompute when it changes
    computed_at  TEXT NOT NULL,
    payload      TEXT NOT NULL,
    PRIMARY KEY (symbol, kind)
);

CREATE TABLE IF NOT EXISTS kv_cache (
    key         TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    stored_at   TEXT NOT NULL
);
"""

_local = threading.local()
_init_lock = threading.Lock()
_initialised = False


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _connect() -> sqlite3.Connection:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db() -> None:
    global _initialised
    with _init_lock:
        if _initialised:
            return
        conn = _connect()
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()
        _initialised = True


def get_conn() -> sqlite3.Connection:
    init_db()
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    return conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def query(sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in get_conn().execute(sql, tuple(params)).fetchall()]


def query_one(sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    row = get_conn().execute(sql, tuple(params)).fetchone()
    return dict(row) if row else None


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    with tx() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.lastrowid or cur.rowcount


# ---------------------------------------------------------------- helpers


def upsert_fact(conn: sqlite3.Connection, fact: dict[str, Any]) -> str:
    """Insert a financial fact. Returns 'inserted', 'unchanged' or 'revised'."""
    key = (
        fact["symbol"], fact["statement"], fact["metric"], fact["period_end"],
        fact["period_type"], fact["consolidation"], fact["source"],
    )
    existing = conn.execute(
        """SELECT id, value FROM financial_facts WHERE symbol=? AND statement=? AND metric=?
           AND period_end=? AND period_type=? AND consolidation=? AND source=?""",
        key,
    ).fetchone()
    if existing is None:
        conn.execute(
            """INSERT INTO financial_facts (symbol, statement, metric, source_label, period_end, period_type,
               consolidation, value, currency, unit, source, publication_date, retrieved_at, revision)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
            (
                fact["symbol"], fact["statement"], fact["metric"], fact.get("source_label"),
                fact["period_end"], fact["period_type"], fact["consolidation"], fact["value"],
                fact.get("currency"), fact["unit"], fact["source"], fact.get("publication_date"),
                fact["retrieved_at"],
            ),
        )
        return "inserted"
    old = existing["value"]
    # Duplicate detection: identical value (within float noise) is not a revision.
    if abs(old - fact["value"]) <= max(1e-6, abs(old) * 1e-9):
        conn.execute("UPDATE financial_facts SET retrieved_at=? WHERE id=?", (fact["retrieved_at"], existing["id"]))
        return "unchanged"
    conn.execute(
        "INSERT INTO financial_fact_revisions (fact_id, old_value, new_value, changed_at) VALUES (?,?,?,?)",
        (existing["id"], old, fact["value"], fact["retrieved_at"]),
    )
    conn.execute(
        """UPDATE financial_facts SET value=?, retrieved_at=?, publication_date=COALESCE(?, publication_date),
           unit=?, currency=?, source_label=COALESCE(?, source_label), revision = revision + 1 WHERE id=?""",
        (fact["value"], fact["retrieved_at"], fact.get("publication_date"), fact["unit"], fact.get("currency"),
         fact.get("source_label"), existing["id"]),
    )
    return "revised"


def log_ingestion(symbol: str | None, source: str, kind: str, status: str, message: str = "",
                  rows: int | None = None, started_at: str | None = None) -> None:
    execute(
        """INSERT INTO data_ingestion_logs (symbol, source, kind, status, message, rows, started_at, finished_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (symbol, source, kind, status, message[:2000], rows, started_at or now_iso(), now_iso()),
    )


def kv_get(key: str) -> tuple[Any, str] | None:
    row = query_one("SELECT payload, stored_at FROM kv_cache WHERE key=?", (key,))
    if not row:
        return None
    return json.loads(row["payload"]), row["stored_at"]


def kv_set(key: str, payload: Any) -> None:
    execute(
        "INSERT INTO kv_cache (key, payload, stored_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, stored_at=excluded.stored_at",
        (key, json.dumps(payload, default=str), now_iso()),
    )


def age_hours(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        ts = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return (datetime.now(UTC) - ts).total_seconds() / 3600
