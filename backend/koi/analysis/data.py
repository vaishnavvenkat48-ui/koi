"""Loads stored facts into an in-memory structure for analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .. import companies, db


@dataclass
class FinData:
    symbol: str
    company: dict[str, Any]
    profile: str
    annual: dict[str, dict[str, float]] = field(default_factory=dict)      # metric -> {period: value}
    quarterly: dict[str, dict[str, float]] = field(default_factory=dict)
    annual_periods: list[str] = field(default_factory=list)                # ascending ISO dates
    quarterly_periods: list[str] = field(default_factory=list)
    provenance: dict[str, dict[str, Any]] = field(default_factory=dict)    # metric -> source info
    snapshot: dict[str, Any] | None = None
    consolidation: set[str] = field(default_factory=set)

    def a(self, metric: str, period: str | None) -> float | None:
        if period is None:
            return None
        return self.annual.get(metric, {}).get(period)

    def q(self, metric: str, period: str) -> float | None:
        return self.quarterly.get(metric, {}).get(period)

    def has_annual(self) -> bool:
        return bool(self.annual_periods)


def load(symbol: str) -> FinData:
    c = companies.get(symbol) or {"symbol": symbol, "name": symbol}
    fd = FinData(symbol=symbol, company=c, profile=companies.profile_of(symbol))
    rows = db.query(
        """SELECT statement, metric, source_label, period_end, period_type, consolidation, value, unit, currency,
                  source, retrieved_at, revision
           FROM financial_facts WHERE symbol=? ORDER BY period_end""", (symbol,))
    for r in rows:
        target = fd.annual if r["period_type"] == "annual" else fd.quarterly
        target.setdefault(r["metric"], {})[r["period_end"]] = r["value"]
        fd.consolidation.add(r["consolidation"])
        fd.provenance.setdefault(r["metric"], {
            "statement": r["statement"], "source_label": r["source_label"], "unit": r["unit"],
            "currency": r["currency"], "source": r["source"], "retrieved_at": r["retrieved_at"],
            "consolidation": r["consolidation"],
        })
    fd.annual_periods = sorted({p for m in fd.annual.values() for p in m})
    fd.quarterly_periods = sorted({p for m in fd.quarterly.values() for p in m})
    fd.snapshot = db.query_one("SELECT * FROM market_snapshot WHERE symbol=?", (symbol,))
    return fd


def days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def consecutive_years(a: str, b: str) -> bool:
    return 300 <= days_between(a, b) <= 430


def price_on_or_before(symbol: str, day: str) -> tuple[str, float] | None:
    row = db.query_one(
        "SELECT date, close FROM market_prices WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT 1", (symbol, day))
    if not row:
        return None
    # Reject if the nearest price is more than 10 days before the requested date (gap in history).
    if days_between(row["date"], day) > 10:
        return None
    return row["date"], row["close"]
