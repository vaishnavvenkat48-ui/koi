"""Peer benchmarking from locally stored data (peers are prefetched by the background worker)."""

from __future__ import annotations

import statistics
from typing import Any

from .. import companies, workers
from . import metrics as M
from . import valuation as V
from .data import load

COLUMNS = [
    ("market_cap", "Market cap", "INR"),
    ("revenue", "Revenue (latest FY)", "INR"),
    ("revenue_cagr", "Revenue CAGR", "pct"),
    ("revenue_growth", "Revenue growth (latest)", "pct"),
    ("net_income_cagr", "Profit CAGR", "pct"),
    ("operating_margin", "Operating margin", "pct"),
    ("net_margin", "Net margin", "pct"),
    ("roe", "ROE", "pct"),
    ("roce", "ROCE", "pct"),
    ("roa", "ROA", "pct"),
    ("debt_to_equity", "Debt-to-equity", "x"),
    ("growth_consistency", "Years with revenue growth", "pct"),
    ("pe", "P/E", "x"),
    ("pb", "P/B", "x"),
    ("ev_ebitda", "EV/EBITDA", "x"),
]


def snapshot_row(symbol: str) -> dict[str, Any]:
    fd = load(symbol)
    c = fd.company
    row: dict[str, Any] = {"symbol": symbol, "name": c.get("name", symbol), "has_data": fd.has_annual(),
                           "latest_period": fd.annual_periods[-1] if fd.annual_periods else None}
    if not fd.has_annual():
        st = workers.queue.status(symbol)
        row["status"] = st["status"] if st else "not_requested"
        return row
    s = M.compute_series(fd)
    h = M.headline(fd, s)
    vals = V.current_multiples(fd)
    for k in ("revenue_growth", "operating_margin", "net_margin", "roe", "roce", "roa", "debt_to_equity"):
        row[k] = h[k]["value"] if h.get(k, {}).get("available") else None
    row["revenue"] = h["revenue"]["value"] if h["revenue"].get("available") else None
    row["revenue_cagr"] = M.cagr(fd, "revenue")["value"]
    row["net_income_cagr"] = M.cagr(fd, "net_income")["value"]
    row["growth_consistency"] = M.consistency(s.get("revenue_growth", []))["positive_share"]
    row["market_cap"] = vals.get("market_cap")
    for k in ("pe", "pb", "ev_ebitda"):
        row[k] = vals.get(k, {}).get("value")
    row["status"] = "ready"
    return row


def compare(symbol: str, self_row: dict[str, Any] | None = None) -> dict[str, Any]:
    groups = companies.peers_for(symbol)
    peer_syms = groups["p1"] + groups["p2"]
    rows = [snapshot_row(p) for p in peer_syms]
    me = self_row or snapshot_row(symbol)
    ready = [r for r in rows if r.get("has_data")]
    medians: dict[str, float | None] = {}
    for key, _, _ in COLUMNS:
        vals = [r[key] for r in ready if r.get(key) is not None]
        if key in ("pe", "pb", "ev_ebitda"):
            vals = [v for v in vals if v > 0]
        medians[key] = statistics.median(vals) if vals else None
    ranks: dict[str, Any] = {}
    for key, _, _ in COLUMNS:
        if me.get(key) is None:
            continue
        pool = [r[key] for r in ready if r.get(key) is not None] + [me[key]]
        if len(pool) < 2:
            continue
        better = M.DEFS.get(key).better if key in M.DEFS else ("lower" if key in ("pe", "pb", "ev_ebitda") else "higher")
        ordered = sorted(pool, reverse=(better != "lower"))
        ranks[key] = {"rank": ordered.index(me[key]) + 1, "of": len(pool)}
    return {
        "company": me, "peers": rows, "medians": medians, "ranks": ranks, "columns": [
            {"key": k, "label": lbl, "unit": u} for k, lbl, u in COLUMNS],
        "p1": groups["p1"], "p2": groups["p2"],
        "loaded": len(ready), "expected": len(peer_syms),
        "p1_loaded": sum(1 for r in rows if r["symbol"] in groups["p1"] and r.get("has_data")),
    }
