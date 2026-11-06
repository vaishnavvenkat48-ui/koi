"""Deterministic analysis pipeline: one call returns everything the dashboard and agent need."""

from __future__ import annotations

from typing import Any

from .. import companies, db, ingest
from . import forecast as F
from . import metrics as M
from . import peers as P
from . import scoring as S
from . import valuation as V
from .data import load


PLAIN_OUTLOOK = {
    1: "Financially strong, based on past results",
    2: "Financially healthy, based on past results",
    3: "Mixed picture: needs more research",
    4: "Getting weaker",
    5: "Serious financial problems",
}

VALUATION_PLAIN = {
    "attractive": "The price looks low compared with its profits, competitors and its own past.",
    "reasonable": "The price is neither clearly cheap nor clearly expensive.",
    "expensive": "The price is high compared with its profits, competitors or its own past.",
    "unavailable": "Not enough data yet to judge the price.",
}


# Bump whenever analysis logic changes, so cached results computed by older code are recomputed.
ENGINE_VERSION = "2"


def cache_key(symbol: str) -> str:
    """Changes whenever the company's or any peer's stored data changes."""
    from .. import workers
    peers = companies.peers_for(symbol)
    parts = [f"engine={ENGINE_VERSION}", ingest.data_version(symbol)]
    for p in peers["p1"] + peers["p2"]:
        st = workers.queue.status(p)
        # A peer's job state matters too: a peer that fails must clear a cached "pending".
        parts.append(f"{p}={ingest.data_version(p)}:{st['status'] if st else '-'}")
    return "|".join(parts)


def run_cached(symbol: str) -> dict[str, Any]:
    """Full analysis, served from cached_analysis while no input has changed."""
    import json
    key = cache_key(symbol)
    row = db.query_one("SELECT data_version, payload FROM cached_analysis WHERE symbol=? AND kind='full'", (symbol,))
    if row and row["data_version"] == key:
        return json.loads(row["payload"])
    result = run(symbol)
    if result.get("ready"):
        db.execute(
            "INSERT INTO cached_analysis (symbol, kind, data_version, computed_at, payload) VALUES (?,?,?,?,?) "
            "ON CONFLICT(symbol, kind) DO UPDATE SET data_version=excluded.data_version, "
            "computed_at=excluded.computed_at, payload=excluded.payload",
            (symbol, "full", key, db.now_iso(), json.dumps(result, default=str)))
    return result


def run(symbol: str, dcf_overrides: dict[str, float] | None = None) -> dict[str, Any]:
    fd = load(symbol)
    fresh = ingest.freshness(symbol)
    base = {"symbol": symbol, "company": _company_view(fd), "freshness": fresh, "profile": fd.profile}
    if not fd.has_annual():
        return {**base, "ready": False,
                "reason": "No annual financial statements stored yet for this company."}

    series = M.compute_series(fd)
    head = M.headline(fd, series)
    vals = V.current_multiples(fd)
    hist = V.historical_multiples(fd)
    fc = F.forecast(fd, series)
    growth = fc["revenue"]["scenarios"]["base"]["growth"] if fc["revenue"].get("available") else None
    dcf = V.dcf(fd, growth, **(dcf_overrides or {}))
    peer = P.compare(symbol)
    ctx = {"fd": fd, "headline": head, "series": series, "valuation": vals, "historical": hist,
           "peer_medians": peer["medians"], "dcf": dcf}
    scored = S.score_all(ctx)
    q_trend = M.trend(series.get("roce") or series.get("roe") or [])["direction"]
    gate = S.evidence_gate(fd.profile, len(fd.annual_periods))
    outlook = S.classify(scored["scores"], q_trend, gate)
    outlook["plain_label"] = PLAIN_OUTLOOK[outlook["code"]]
    outlook["valuation_plain"] = VALUATION_PLAIN[outlook["valuation_verdict"]]
    conf = S.confidence(scored["scores"], len(fd.annual_periods), peer["p1_loaded"], len(peer["p1"]),
                        fd.consolidation)
    factors = S.key_factors(scored)
    # Peers still loading: say so rather than presenting a blank valuation as a result.
    peers_loading = sum(1 for r in peer["peers"] if not r.get("has_data") and r.get("status") in ("queued", "running"))
    if scored["scores"]["valuation"]["value"] is None and peers_loading:
        scored["scores"]["valuation"]["pending"] = True
        outlook["valuation_verdict"] = "pending"
        outlook["valuation_plain"] = f"Waiting for {peers_loading} competitor(s) to load before judging the price."
    summary = {
        "headline": outlook["plain_label"],
        "main_reason": factors["positives"][0]["plain"] if factors["positives"] else None,
        # When the rating is held back, the missing evidence is the main worry.
        "main_worry": (outlook["cap_reasons"][0] if outlook.get("capped")
                       else factors["concerns"][0]["plain"] if factors["concerns"]
                       else (gate[0] if gate else (conf["notes"][0] if conf["notes"] else None))),
        "price": outlook["valuation_plain"],
        "years": len(fd.annual_periods),
        "first_year": fd.annual_periods[0] if fd.annual_periods else None,
        "last_year": fd.annual_periods[-1] if fd.annual_periods else None,
    }
    cagr = {m: M.cagr(fd, m) for m in ("revenue", "net_income", "eps_diluted", "operating_cf", "total_equity")}
    return {
        **base,
        "ready": True,
        "periods": {"annual": fd.annual_periods, "quarterly": fd.quarterly_periods},
        "consolidation": sorted(fd.consolidation),
        "headline": head,
        "series": _strip_inputs(series),
        "cagr": cagr,
        "consistency": {"revenue_growth": M.consistency(series.get("revenue_growth", [])),
                        "net_income_growth": M.consistency(series.get("net_income_growth", []))},
        "valuation": {"current": vals, "historical": hist, "dcf": dcf},
        "forecast": fc,
        "peers": peer,
        "scores": scored["scores"],
        "signals": scored["signals"],
        "outlook": outlook,
        "summary": summary,
        "peers_loading": peers_loading,
        "confidence": conf,
        "factors": factors,
        "ownership": _ownership(fd),
        "unavailable_sector_metrics": S.unavailable_sector_metrics(fd.profile),
        "data_limitations": _limitations(fd, conf),
    }


def _company_view(fd) -> dict[str, Any]:
    c = fd.company
    snap = fd.snapshot or {}
    return {k: c.get(k) for k in ("symbol", "name", "isin", "sector", "industry", "sector_key", "website",
                                  "description", "listing_date", "bse_code", "currency")} | {
        "price": snap.get("price"), "market_cap": snap.get("market_cap"), "price_as_of": snap.get("as_of"),
        "market_source": snap.get("source")}


def _ownership(fd) -> dict[str, Any]:
    snap = fd.snapshot or {}
    return {
        "insiders_pct": snap.get("held_insiders_pct"),
        "institutions_pct": snap.get("held_institutions_pct"),
        "source": snap.get("source"), "as_of": snap.get("as_of"),
        "note": "From Yahoo Finance: 'insiders' approximates promoter holding for Indian companies; "
                "'institutions' combines FII and DII. Promoter pledging and the FII/DII split require "
                "the NSE shareholding-pattern filings connector (planned).",
        "unavailable": ["Promoter pledge %", "FII holding %", "DII holding %", "Quarterly shareholding changes",
                        "Auditor qualifications"],
    }


def _limitations(fd, conf) -> list[str]:
    out = list(conf["notes"])
    out.append("Source: Yahoo Finance via yfinance (unofficial). Figures can differ from the company's filed "
               "results; verify important numbers against NSE/BSE filings and annual reports.")
    if not fd.quarterly_periods:
        out.append("No quarterly data stored.")
    return out


def _strip_inputs(series: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Series for charts keep inputs (they are small) so any point can be traced."""
    return series


def company_ready(symbol: str) -> bool:
    return bool(companies.get(symbol)) and load(symbol).has_annual()
