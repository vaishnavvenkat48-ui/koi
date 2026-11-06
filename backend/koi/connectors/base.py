"""Connector interface. Every external data source implements one or more of these methods.

Connectors return normalised records; they never write to the database themselves.
The ingestion service (koi/ingest.py) owns persistence, deduplication and logging.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..config import settings


class SourceUnavailable(Exception):
    """Raised when a source cannot serve a request (network, blocked, symbol unknown)."""


@dataclass
class FactRecord:
    statement: str            # income | balance | cashflow
    metric: str               # normalised KOI metric key
    source_label: str         # label as published by the source
    period_end: str           # ISO date
    period_type: str          # annual | quarterly
    value: float
    unit: str
    currency: str | None
    consolidation: str = "unspecified"
    publication_date: str | None = None


@dataclass
class CompanyProfile:
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    website: str | None = None
    description: str | None = None
    currency: str | None = None


@dataclass
class MarketSnapshot:
    price: float | None = None
    market_cap: float | None = None
    shares_outstanding: float | None = None
    beta: float | None = None
    currency: str | None = None
    held_insiders_pct: float | None = None
    held_institutions_pct: float | None = None


@dataclass
class FundamentalsBundle:
    profile: CompanyProfile
    snapshot: MarketSnapshot
    facts: list[FactRecord] = field(default_factory=list)
    prices: list[dict[str, Any]] = field(default_factory=list)   # {date, open, high, low, close, volume}
    warnings: list[str] = field(default_factory=list)


class FundamentalsConnector(Protocol):
    key: str

    def fetch(self, symbol: str) -> FundamentalsBundle: ...


class RateLimiter:
    """Serialises calls to one source and enforces a minimum interval between them."""

    def __init__(self, min_interval_s: float | None = None) -> None:
        self.min_interval_s = settings.source_min_interval_s if min_interval_s is None else min_interval_s
        self._lock = threading.Lock()
        self._last = 0.0

    def __enter__(self) -> "RateLimiter":
        self._lock.acquire()
        wait = self.min_interval_s - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        return self

    def __exit__(self, *exc: object) -> None:
        self._last = time.monotonic()
        self._lock.release()
