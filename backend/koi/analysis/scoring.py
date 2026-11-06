"""Deterministic scores, outlook classification, key factors and confidence.

No score is produced by a language model. See METHODOLOGY for the published rules.
"""

from __future__ import annotations

import statistics
from typing import Any

from . import metrics as M
from .sector_rules import UNAVAILABLE_SECTOR_METRICS, rules_for

OUTLOOKS = {
    1: "Strong long-term fundamentals",
    2: "Positive investment outlook",
    3: "Mixed fundamentals — further research required",
    4: "Weakening fundamentals",
    5: "Significant financial concerns",
}

METHODOLOGY = {
    "component_scoring": "Each component maps a metric linearly from a 'bad' threshold (0) to a 'good' threshold "
                         "(100), clipped to 0-100. Thresholds depend on the company's sector profile.",
    "sub_scores": {
        "quality": "Fundamental (business) quality: returns on capital, margins and margin stability.",
        "health": "Financial health: leverage, interest coverage, liquidity and cash backing of profits.",
        "growth": "Growth: revenue, profit and EPS CAGR plus consistency of growth.",
        "valuation": "Valuation attractiveness: P/E versus peers and own history, earnings yield, EV/EBITDA, DCF.",
        "risk": "Risk (higher = riskier): 100 minus a safety score built from deteriorating trends, cash-flow "
                "weakness, earnings volatility, accruals, coverage and data depth.",
    },
    "missing_data": "A component with no data is excluded and its weight is not counted. If less than half of a "
                    "sub-score's weight has data, that sub-score is reported as unavailable.",
    "fundamentals_composite": "0.4 x quality + 0.3 x health + 0.3 x growth (valuation and risk are kept separate).",
    "outlook_rules": [
        "Significant financial concerns: health < 30 or risk >= 70.",
        "Weakening fundamentals: risk >= 55, or growth < 35 while quality is deteriorating.",
        "Strong long-term fundamentals: quality >= 70, health >= 65, growth >= 50 and risk <= 40.",
        "Positive investment outlook: fundamentals composite >= 55 and risk <= 50.",
        "Otherwise: Mixed fundamentals — further research required.",
    ],
    "evidence_gate": "A missing quality, health, growth or risk score blocks the two positive outlooks. The positive "
                     "outlooks are also held at 'Mixed' when fewer than 4 years of annual results exist, or for "
                     "banks, NBFCs and insurers while their sector-critical metrics (asset quality, capital "
                     "adequacy, solvency) are unavailable.",
    "confidence_caps": "Confidence is capped at Medium when history is under 5 years, competitor data is incomplete "
                       "or the consolidation basis is unknown, and at Low below 4 years.",
    "valuation_verdict": "Reported separately from the outlook: >= 65 attractive, 40-65 reasonable, < 40 expensive. "
                         "A strong business at an expensive price is flagged as such.",
    "confidence": "Average of data coverage (share of scoring weight with data), history depth (5+ years = full) "
                  "and peer coverage (peers with data / 4). High >= 0.75, Medium >= 0.5, otherwise Low.",
}


def _avg_last(series: list[dict[str, Any]], n: int = 3) -> float | None:
    v = M.values(series)[-n:]
    return sum(v) / len(v) if v else None


def derived(ctx: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """All scoring signals with their evidence. Value None means unavailable."""
    h, s, fd = ctx["headline"], ctx["series"], ctx["fd"]
    val, hist, peers, dcf = ctx["valuation"], ctx["historical"], ctx["peer_medians"], ctx.get("dcf") or {}
    out: dict[str, dict[str, Any]] = {}

    def put(key: str, value: float | None, evidence: str, refs: list | None = None) -> None:
        out[key] = {"value": value, "evidence": evidence, "inputs": refs or []}

    for k in ("roce", "roe", "roa", "operating_margin", "debt_to_equity", "current_ratio", "interest_coverage",
              "equity_to_assets"):
        m = h.get(k, {})
        if m.get("available"):
            put(k, m["value"], f"{m['label']} for period ending {m['period']}", m.get("inputs"))
        else:
            put(k, None, m.get("reason", "unavailable"))

    om = M.values(s.get("operating_margin", []))
    put("margin_stability", statistics.pstdev(om) if len(om) >= 3 else None,
        f"standard deviation of operating margin over {len(om)} years")
    cc = _avg_last(s.get("cash_conversion", []))
    put("cash_conversion_avg", cc, "average operating cash flow / net profit, last 3 years")

    for key, metric in (("revenue_cagr", "revenue"), ("net_income_cagr", "net_income"), ("eps_cagr", "eps_diluted")):
        c = M.cagr(fd, metric)
        put(key, c["value"], f"{metric} CAGR {c.get('from', '')} to {c.get('to', '')}" if c["value"] is not None
            else c["note"], c.get("inputs"))
    cons = M.consistency(s.get("revenue_growth", []))
    put("growth_consistency", cons["positive_share"], f"{cons['n']} annual growth observations")

    pe = val.get("pe", {}).get("value")
    pb = val.get("pb", {}).get("value")
    put("earnings_yield", val.get("earnings_yield", {}).get("value"), "current net profit / market cap")
    put("ev_ebitda", val.get("ev_ebitda", {}).get("value"), "current EV/EBITDA")
    put("pb", pb, "current price to book")
    put("pe_vs_peers", pe / peers["pe"] if pe and peers.get("pe") else None,
        f"P/E {pe:.1f} vs peer median {peers['pe']:.1f}" if pe and peers.get("pe") else "peer P/E unavailable")
    put("pb_vs_peers", pb / peers["pb"] if pb and peers.get("pb") else None,
        f"P/B {pb:.2f} vs peer median {peers['pb']:.2f}" if pb and peers.get("pb") else "peer P/B unavailable")
    put("pe_vs_history", pe / hist["median_pe"] if pe and hist.get("median_pe") else None,
        f"P/E {pe:.1f} vs own historical median {hist['median_pe']:.1f}" if pe and hist.get("median_pe")
        else "historical P/E unavailable")
    put("dcf_margin_of_safety", dcf.get("margin_of_safety") if dcf.get("available") else None,
        "DCF value per share / price - 1" if dcf.get("available") else dcf.get("reason", "DCF unavailable"))

    de = [p for p in s.get("debt_to_equity", []) if p["value"] is not None]
    put("leverage_change", de[-1]["value"] - de[0]["value"] if len(de) >= 2 else None,
        f"D/E {de[0]['period']} to {de[-1]['period']}" if len(de) >= 2 else "needs two D/E observations")
    tr = M.trend(s.get("operating_margin", []))
    put("margin_change", tr["change"], f"latest operating margin vs prior average ({tr['direction']})")
    fcf = M.values(s.get("free_cash_flow", []))
    put("negative_fcf_share", sum(1 for v in fcf if v < 0) / len(fcf) if fcf else None, f"{len(fcf)} years of FCF")
    nig = M.values(s.get("net_income_growth", []))
    put("earnings_volatility", statistics.pstdev(nig) if len(nig) >= 2 else None,
        f"std. dev. of {len(nig)} annual profit growth rates")
    put("accruals_avg", _avg_last(s.get("accruals_ratio", [])), "average accruals ratio, last 3 years")
    roa_tr = M.trend(s.get("roa", []))
    put("roa_change", roa_tr["change"], f"latest ROA vs prior average ({roa_tr['direction']})")
    put("data_years", float(len(fd.annual_periods)), f"{len(fd.annual_periods)} annual periods stored")
    return out


def _component(value: float | None, bad: float, good: float) -> float | None:
    if value is None:
        return None
    if good == bad:
        return 50.0
    x = (value - bad) / (good - bad)
    return max(0.0, min(100.0, x * 100))


def score_all(ctx: dict[str, Any]) -> dict[str, Any]:
    sig = derived(ctx)
    rules = rules_for(ctx["fd"].profile)
    scores: dict[str, Any] = {}
    for name, comp_rules in rules.items():
        comps, wsum, wavail, acc = [], 0.0, 0.0, 0.0
        for key, label, bad, good, w in comp_rules:
            sv = sig.get(key, {"value": None, "evidence": "not computed"})
            cs = _component(sv["value"], bad, good)
            wsum += w
            if cs is not None:
                wavail += w
                acc += cs * w
            comps.append({"signal": key, "label": label, "value": sv["value"], "score": cs, "weight": w,
                          "bad": bad, "good": good, "evidence": sv["evidence"], "inputs": sv.get("inputs", [])})
        coverage = wavail / wsum if wsum else 0
        value = acc / wavail if wavail and coverage >= 0.5 else None
        if name == "risk" and value is not None:
            value = 100 - value
        scores[name] = {"value": None if value is None else round(value, 1), "coverage": round(coverage, 2),
                        "components": comps}
    q, hl, g = (scores[k]["value"] for k in ("quality", "health", "growth"))
    parts = [(q, 0.4), (hl, 0.3), (g, 0.3)]
    avail = [(v, w) for v, w in parts if v is not None]
    composite = (sum(v * w for v, w in avail) / sum(w for _, w in avail)) if len(avail) >= 2 else None
    scores["fundamentals"] = {"value": None if composite is None else round(composite, 1),
                              "formula": METHODOLOGY["fundamentals_composite"]}
    return {"scores": scores, "signals": sig}


LENDER_PROFILES = {"bank", "nbfc", "insurance"}
MIN_YEARS_FOR_VERDICT = 4


def evidence_gate(profile: str, years: int) -> list[str]:
    """Reasons the data cannot support a positive outlook. Empty list = no cap."""
    reasons = []
    if years < MIN_YEARS_FOR_VERDICT:
        reasons.append(f"Only {years} year(s) of annual results are available; at least "
                       f"{MIN_YEARS_FOR_VERDICT} are needed to judge long-term strength.")
    if profile in LENDER_PROFILES:
        missing = ", ".join(UNAVAILABLE_SECTOR_METRICS.get(profile, [])[:3])
        reasons.append(f"The metrics that matter most for this kind of company ({missing}) are not available "
                       "from the current data source, so its strength cannot be confirmed.")
    return reasons


def classify(scores: dict[str, Any], quality_trend: str, gate: list[str] | None = None) -> dict[str, Any]:
    """Outlook from scores. A missing score never counts in a company's favour."""
    q, hl, g, v, r, f = (scores[k]["value"] for k in ("quality", "health", "growth", "valuation", "risk",
                                                      "fundamentals"))
    gate = gate or []
    core_missing = [name for name, val in (("quality", q), ("health", hl), ("growth", g), ("risk", r))
                    if val is None]
    if f is None:
        code, rule = 3, "Insufficient data to score fundamentals."
    elif (hl is not None and hl < 30) or (r is not None and r >= 70):
        code, rule = 5, METHODOLOGY["outlook_rules"][0]
    elif (r is not None and r >= 55) or (g is not None and g < 35 and quality_trend == "deteriorating"):
        code, rule = 4, METHODOLOGY["outlook_rules"][1]
    elif core_missing:
        code, rule = 3, f"Cannot rate above 'Mixed': no {', '.join(core_missing)} score (missing data never counts as a pass)."
    elif q >= 70 and hl >= 65 and g >= 50 and r <= 40:
        code, rule = 1, METHODOLOGY["outlook_rules"][2]
    elif f >= 55 and r <= 50:
        code, rule = 2, METHODOLOGY["outlook_rules"][3]
    else:
        code, rule = 3, METHODOLOGY["outlook_rules"][4]
    capped = False
    if gate and code in (1, 2):
        code, capped = 3, True
        rule = "Held at 'Mixed' because the evidence is too thin for a positive rating: " + " ".join(gate)
    if v is None:
        verdict = "unavailable"
    elif v >= 65:
        verdict = "attractive"
    elif v >= 40:
        verdict = "reasonable"
    else:
        verdict = "expensive"
    return {"code": code, "label": OUTLOOKS[code], "rule": rule, "valuation_verdict": verdict,
            "capped": capped, "cap_reasons": gate if capped else []}


def confidence(scores: dict[str, Any], years: int, peers_with_data: int, peers_expected: int,
               consolidation: set[str]) -> dict[str, Any]:
    cov = [scores[k]["coverage"] for k in ("quality", "health", "growth", "valuation", "risk")]
    data_cov = sum(cov) / len(cov)
    depth = min(years / 5, 1.0)
    peer_cov = min(peers_with_data / max(min(peers_expected, 4), 1), 1.0) if peers_expected else 0.5
    value = (data_cov + depth + peer_cov) / 3
    level = "High" if value >= 0.75 else "Medium" if value >= 0.5 else "Low"
    # Hard caps: a warning about the evidence and a "High" label cannot appear together.
    notes, caps = [], []
    if years < 5:
        notes.append(f"Only {years} years of results: enough for a first view, not a full business cycle.")
        caps.append("Low" if years < 4 else "Medium")
    if peers_expected and peers_with_data < min(peers_expected, 4):
        notes.append(f"Competitor data loaded for {peers_with_data} of {min(peers_expected, 4)} main competitors.")
        caps.append("Medium")
    if consolidation == {"unspecified"}:
        notes.append("The source does not say whether figures cover the whole group or the parent company only.")
        caps.append("Medium")
    order = ["Low", "Medium", "High"]
    for cap in caps:
        if order.index(cap) < order.index(level):
            level = cap
    return {"level": level, "value": round(value, 2), "data_coverage": round(data_cov, 2),
            "history_depth": round(depth, 2), "peer_coverage": round(peer_cov, 2), "notes": notes,
            "capped_by": sorted(set(caps))}


# ------------------------------------------------------------- key factors (positives / concerns)

PLAIN_POS = {
    "roce": "The business earns high returns on the capital invested in it.",
    "roe": "It generates strong profits on shareholders' money.",
    "roa": "It earns a healthy return on its assets.",
    "operating_margin": "It keeps a large share of each rupee of sales as operating profit.",
    "margin_stability": "Its profit margins have been steady over the years.",
    "debt_to_equity": "It carries little debt relative to its own capital.",
    "interest_coverage": "Profits cover interest payments many times over.",
    "current_ratio": "It has enough short-term assets to pay near-term bills.",
    "cash_conversion_avg": "Reported profits are backed by real cash.",
    "revenue_cagr": "Sales have grown steadily.",
    "net_income_cagr": "Profits have grown well.",
    "eps_cagr": "Earnings per share have grown well.",
    "growth_consistency": "Sales have grown in almost every year.",
    "pe_vs_peers": "The share is priced cheaper than similar companies relative to profits.",
    "pe_vs_history": "The share is priced below its usual level relative to profits.",
    "pb_vs_peers": "The share is priced below peers relative to book value.",
    "earnings_yield": "The price looks reasonable relative to current profits.",
    "ev_ebitda": "The business looks reasonably priced relative to operating cash profit.",
    "dcf_margin_of_safety": "A cash-flow valuation suggests the price is below estimated value.",
    "equity_to_assets": "It holds a solid capital cushion.",
}
PLAIN_NEG = {
    "roce": "Returns on invested capital are low.",
    "roe": "Profit on shareholders' money is weak.",
    "roa": "Return on assets is weak.",
    "operating_margin": "Operating margins are thin.",
    "margin_stability": "Profit margins swing a lot from year to year.",
    "debt_to_equity": "The company relies heavily on borrowed money.",
    "interest_coverage": "Profits only just cover interest payments.",
    "current_ratio": "Short-term assets may not comfortably cover near-term bills.",
    "cash_conversion_avg": "Profits are not fully turning into cash.",
    "revenue_cagr": "Sales growth has been slow or negative.",
    "net_income_cagr": "Profit growth has been weak.",
    "eps_cagr": "Earnings per share have barely grown.",
    "growth_consistency": "Sales have fallen in several years.",
    "pe_vs_peers": "The share is priced richer than similar companies relative to profits.",
    "pe_vs_history": "The share is priced above its usual level relative to profits.",
    "pb_vs_peers": "The share is priced above peers relative to book value.",
    "earnings_yield": "The price is high relative to current profits.",
    "ev_ebitda": "The business is priced richly relative to operating cash profit.",
    "dcf_margin_of_safety": "A cash-flow valuation suggests the price is above estimated value.",
    "leverage_change": "Debt has been rising faster than equity.",
    "margin_change": "Operating margins have recently declined.",
    "negative_fcf_share": "The company often spends more cash than it generates.",
    "earnings_volatility": "Profits have been volatile.",
    "accruals_avg": "Accounting profits are running ahead of cash flow.",
    "data_years": "Limited financial history is available.",
    "equity_to_assets": "The capital cushion is thin.",
    "roa_change": "Return on assets has declined recently.",
}


def key_factors(result: dict[str, Any], n: int = 3) -> dict[str, list[dict[str, Any]]]:
    comps = []
    for name in ("quality", "health", "growth", "valuation", "risk"):
        for c in result["scores"][name]["components"]:
            if c["score"] is None:
                continue
            comps.append({**c, "dimension": name})
    seen: set[str] = set()
    pos, neg = [], []
    for c in sorted(comps, key=lambda c: (-c["score"], -c["weight"])):
        if c["score"] >= 70 and c["signal"] in PLAIN_POS and c["signal"] not in seen and len(pos) < n:
            seen.add(c["signal"])
            pos.append(_factor(c, PLAIN_POS[c["signal"]]))
    for c in sorted(comps, key=lambda c: (c["score"], -c["weight"])):
        if c["score"] <= 35 and c["signal"] in PLAIN_NEG and c["signal"] not in seen and len(neg) < n:
            seen.add(c["signal"])
            neg.append(_factor(c, PLAIN_NEG[c["signal"]]))
    return {"positives": pos, "concerns": neg}


def _factor(c: dict[str, Any], plain: str) -> dict[str, Any]:
    return {"signal": c["signal"], "dimension": c["dimension"], "label": c["label"], "plain": plain,
            "value": c["value"], "score": round(c["score"], 1), "evidence": c["evidence"], "inputs": c["inputs"],
            "thresholds": {"bad": c["bad"], "good": c["good"]}}


def unavailable_sector_metrics(profile: str) -> list[str]:
    return UNAVAILABLE_SECTOR_METRICS.get(profile, [])
