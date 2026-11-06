"""Company identification: master list, search and sector/peer resolution."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from . import db, reference
from .config import settings
from .connectors.base import SourceUnavailable
from .connectors.nse_master import fetch_equity_master

ISIN_RE = re.compile(r"^IN[A-Z0-9]{9}[0-9]$")
SYMBOL_RE = re.compile(r"^[A-Z0-9&\-]{1,20}$")


def seed_reference() -> None:
    """Load curated sector groups and seed names. Idempotent."""
    ts = db.now_iso()
    with db.tx() as conn:
        for g in reference.SECTOR_GROUPS:
            conn.execute(
                "INSERT INTO sectors (key, name, profile, description) VALUES (?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET name=excluded.name, profile=excluded.profile, description=excluded.description",
                (g["key"], g["name"], g["profile"], g["description"]),
            )
            for rank, sym in enumerate(g["symbols"]):
                conn.execute(
                    "INSERT INTO sector_peers (sector_key, symbol, rank) VALUES (?,?,?) "
                    "ON CONFLICT(sector_key, symbol) DO UPDATE SET rank=excluded.rank",
                    (g["key"], sym, rank),
                )
                conn.execute(
                    """INSERT INTO companies (symbol, name, sector_key, profile, yf_symbol, master_source, master_updated_at)
                       VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(symbol) DO UPDATE SET sector_key=excluded.sector_key, profile=excluded.profile""",
                    (sym, reference.SEED_NAMES.get(sym, sym), g["key"], g["profile"], f"{sym}.NS", "koi_seed", ts),
                )


def master_is_stale() -> bool:
    row = db.query_one("SELECT MAX(master_updated_at) AS ts FROM companies WHERE master_source='nse_equity_master'")
    age = db.age_hours(row["ts"] if row else None)
    return age is None or age > settings.company_master_ttl_h


def refresh_master() -> int:
    """Download NSE's equity list and upsert it. Returns the number of companies stored."""
    started = db.now_iso()
    try:
        rows = fetch_equity_master()
    except SourceUnavailable as e:
        db.log_ingestion(None, "nse_equity_master", "company_master", "error", str(e), started_at=started)
        return 0
    ts = db.now_iso()
    with db.tx() as conn:
        for r in rows:
            listing = _parse_listing_date(r["listing_date"])
            conn.execute(
                """INSERT INTO companies (symbol, name, isin, series, listing_date, yf_symbol, master_source, master_updated_at)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(symbol) DO UPDATE SET name=excluded.name, isin=excluded.isin, series=excluded.series,
                   listing_date=excluded.listing_date, master_source=excluded.master_source,
                   master_updated_at=excluded.master_updated_at""",
                (r["symbol"], _title(r["name"]), r["isin"] or None, r["series"], listing, f"{r['symbol']}.NS",
                 "nse_equity_master", ts),
            )
    db.log_ingestion(None, "nse_equity_master", "company_master", "ok", f"{len(rows)} securities", len(rows), started)
    return len(rows)


def _parse_listing_date(s: str) -> str | None:
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _title(name: str) -> str:
    # NSE names are upper-case; keep acronyms short words upper-case.
    words = []
    for w in name.split():
        words.append(w if len(w) <= 3 and w.isalpha() and w not in {"AND", "OF", "THE"} else w.capitalize())
    return " ".join(words).replace(" And ", " and ").replace(" Of ", " of ")


def search(q: str, limit: int = 12) -> list[dict[str, Any]]:
    q = (q or "").strip()
    if not q:
        return []
    if len(q) > 60:
        q = q[:60]
    uq = q.upper()
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(rows: list[dict[str, Any]], match: str) -> None:
        for r in rows:
            if r["symbol"] not in seen and len(results) < limit:
                seen.add(r["symbol"])
                results.append({**r, "match": match})

    cols = "symbol, name, isin, sector, industry, sector_key, bse_code"
    if ISIN_RE.match(uq):
        add(db.query(f"SELECT {cols} FROM companies WHERE isin=?", (uq,)), "isin")
    if uq.isdigit():
        add(db.query(f"SELECT {cols} FROM companies WHERE bse_code=?", (uq,)), "bse_code")
    add(db.query(f"SELECT {cols} FROM companies WHERE symbol=?", (uq,)), "symbol")
    add(db.query(f"SELECT {cols} FROM companies WHERE symbol LIKE ? ORDER BY length(symbol) LIMIT ?", (f"{uq}%", limit)), "symbol")
    like = f"%{q}%"
    add(db.query(
        f"""SELECT {cols} FROM companies WHERE name LIKE ? COLLATE NOCASE
            ORDER BY (CASE WHEN name LIKE ? COLLATE NOCASE THEN 0 ELSE 1 END), (sector_key IS NULL), length(name) LIMIT ?""",
        (like, f"{q}%", limit)), "name")
    return results


def get(symbol: str) -> dict[str, Any] | None:
    return db.query_one("SELECT * FROM companies WHERE symbol=?", (symbol.upper(),))


def normalise_symbol(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    if s.endswith(".NS"):
        s = s[:-3]
    if not SYMBOL_RE.match(s):
        raise ValueError("Invalid NSE symbol")
    return s


def peers_for(symbol: str) -> dict[str, list[str]]:
    """P1 = 3-5 closest peers; P2 = remaining relevant sector companies."""
    c = get(symbol) or {}
    ordered: list[str] = []
    if c.get("sector_key"):
        ordered = [r["symbol"] for r in db.query(
            "SELECT symbol FROM sector_peers WHERE sector_key=? AND symbol<>? ORDER BY rank", (c["sector_key"], symbol))]
    elif c.get("industry"):
        ordered = [r["symbol"] for r in db.query(
            "SELECT symbol FROM companies WHERE industry=? AND symbol<>? LIMIT 12", (c["industry"], symbol))]
    return {"p1": ordered[:5], "p2": ordered[5:12]}


def profile_of(symbol: str) -> str:
    c = get(symbol) or {}
    if c.get("profile"):
        return c["profile"]
    return reference.profile_for_industry(c.get("sector"), c.get("industry"))


def record_view(symbol: str) -> None:
    db.execute(
        "INSERT INTO recent_views (symbol, viewed_at) VALUES (?,?) ON CONFLICT(symbol) DO UPDATE SET viewed_at=excluded.viewed_at",
        (symbol, db.now_iso()),
    )
