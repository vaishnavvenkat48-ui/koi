"""Deterministic investigation tools used by the agent.

Each tool reads the computed analysis (never raw text from the internet) and returns a finding:
  {tool, signal, severity: info|watch|concern, title, explanation, evidence: [...]}
All numbers come from the analysis engine; tools only compare and explain them.
"""

from __future__ import annotations

from typing import Any, Callable

Finding = dict[str, Any]


def _series(a: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [p for p in a["series"].get(key, []) if p["value"] is not None]


def _sig(a: dict[str, Any], key: str) -> float | None:
    return a["signals"].get(key, {}).get("value")


def _sentence(parts: list[str]) -> str:
    """Join clauses into one sentence; uppercase only the first letter (keeps acronyms like CAGR)."""
    text = "; ".join(parts)
    return (text[:1].upper() + text[1:] + ".") if text else ""


def _pts(a: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [{"metric": key, "period": p["period"], "value": p["value"]} for p in _series(a, key)]


# --------------------------------------------------------------------------- signal detection


def detect_signals(a: dict[str, Any]) -> list[dict[str, Any]]:
    """Signals that warrant deeper investigation. Order = investigation order."""
    out = []
    lenders = a["profile"] in ("bank", "nbfc", "insurance")
    de = _series(a, "debt_to_equity")
    debt = _series(a, "total_debt")
    if not lenders and len(de) >= 2:
        rise = de[-1]["value"] - de[0]["value"]
        debt_growth = (debt[-1]["value"] / debt[-2]["value"] - 1) if len(debt) >= 2 and debt[-2]["value"] > 0 else None
        if (rise > 0.15 or (debt_growth is not None and debt_growth > 0.25)) and de[-1]["value"] > 0.1:
            out.append({"signal": "rising_debt", "reason": f"D/E moved from {de[0]['value']:.2f} to {de[-1]['value']:.2f}"
                        + (f"; borrowings grew {debt_growth:.0%} in the latest year" if debt_growth else "")})
    mc = _sig(a, "margin_change")
    if mc is not None and mc < -0.02 and not lenders:
        out.append({"signal": "margin_compression", "reason": f"operating margin {mc * 100:+.1f} pp vs prior average"})
    cc = _sig(a, "cash_conversion_avg")
    if cc is not None and cc < 0.8 and not lenders:
        out.append({"signal": "weak_cash_conversion", "reason": f"3-year average cash conversion {cc:.2f}x"})
    fcf = _series(a, "free_cash_flow")
    if fcf and fcf[-1]["value"] < 0 and not lenders:
        out.append({"signal": "negative_fcf", "reason": f"free cash flow negative in {fcf[-1]['period']}"})
    rg = _series(a, "revenue_growth")
    rc = a["cagr"]["revenue"].get("value")
    if rg and (rg[-1]["value"] < 0 or (rc is not None and rg[-1]["value"] < rc - 0.05)):
        out.append({"signal": "revenue_slowdown", "reason": f"latest revenue growth {rg[-1]['value']:.1%}"
                    + (f" vs CAGR {rc:.1%}" if rc is not None else "")})
    ng = _series(a, "net_income_growth")
    if ng and ng[-1]["value"] < -0.10:
        out.append({"signal": "earnings_drop", "reason": f"net profit fell {ng[-1]['value']:.0%} in {ng[-1]['period']}"})
    pvp, pvh = _sig(a, "pe_vs_peers"), _sig(a, "pe_vs_history")
    if (pvp is not None and pvp > 1.3) or (pvh is not None and pvh > 1.3):
        out.append({"signal": "valuation_premium", "reason": "P/E well above peers or its own history"})
    rd = _series(a, "receivable_days")
    if len(rd) >= 2 and rd[-1]["value"] - rd[0]["value"] > 15:
        out.append({"signal": "receivable_buildup",
                    "reason": f"receivable days rose from {rd[0]['value']:.0f} to {rd[-1]['value']:.0f}"})
    if a["confidence"]["level"] == "Low":
        out.append({"signal": "low_data_confidence", "reason": "; ".join(a["confidence"]["notes"]) or "limited data"})
    return out


# --------------------------------------------------------------------------- investigations


def investigate_debt(a: dict[str, Any]) -> Finding:
    ic = _series(a, "interest_coverage")
    ocf = _series(a, "operating_cf")
    debt = _series(a, "total_debt")
    ev = _pts(a, "total_debt") + _pts(a, "debt_to_equity") + _pts(a, "interest_coverage") + _pts(a, "operating_cf")
    reasons, severity = [], "watch"
    if ic:
        last = ic[-1]["value"]
        if last < 3:
            severity = "concern"
            reasons.append(f"interest coverage is only {last:.1f}x, leaving little room if profits fall")
        else:
            reasons.append(f"interest coverage remains {last:.1f}x, so interest is comfortably serviceable")
    else:
        reasons.append("interest coverage could not be computed")
    if ocf and debt and debt[-1]["value"] > 0:
        years_to_repay = debt[-1]["value"] / ocf[-1]["value"] if ocf[-1]["value"] > 0 else None
        if years_to_repay is None:
            severity = "concern"
            reasons.append("operating cash flow is negative, so debt cannot be repaid from operations")
        else:
            reasons.append(f"debt equals {years_to_repay:.1f} years of operating cash flow")
            if years_to_repay > 4:
                severity = "concern"
    if len(ocf) >= 2 and len(debt) >= 2:
        if ocf[-1]["value"] > ocf[0]["value"]:
            reasons.append("operating cash flow has also grown, which suggests borrowing may be funding expansion")
        else:
            reasons.append("operating cash flow has not grown alongside debt")
            severity = "concern"
    return {"tool": "investigate_debt", "signal": "rising_debt", "severity": severity,
            "title": "Rising debt" + (" looks concerning" if severity == "concern" else " looks manageable so far"),
            "explanation": _sentence(reasons), "evidence": ev}


def investigate_margins(a: dict[str, Any]) -> Finding:
    om = _series(a, "operating_margin")
    gm_ev = _pts(a, "ebitda_margin")
    rg = _series(a, "revenue_growth")
    reasons = []
    if len(om) >= 2:
        reasons.append(f"operating margin went from {om[0]['value']:.1%} ({om[0]['period'][:4]}) to "
                       f"{om[-1]['value']:.1%} ({om[-1]['period'][:4]})")
    if rg and rg[-1]["value"] < 0.03:
        reasons.append("revenue growth is also weak, so fixed costs weigh more on margins")
    elif rg:
        reasons.append("revenue is still growing, so the squeeze points to cost pressure or pricing")
    severity = "concern" if om and om[-1]["value"] < 0.05 else "watch"
    return {"tool": "investigate_margins", "signal": "margin_compression", "severity": severity,
            "title": "Operating margins are under pressure", "explanation": _sentence(reasons),
            "evidence": _pts(a, "operating_margin") + gm_ev + _pts(a, "revenue_growth")}


def investigate_cash_quality(a: dict[str, Any]) -> Finding:
    cc = _series(a, "cash_conversion")
    rd = _series(a, "receivable_days")
    acc = _series(a, "accruals_ratio")
    reasons = []
    if cc:
        weak = [p for p in cc if p["value"] < 0.8]
        reasons.append(f"cash conversion was below 0.8x in {len(weak)} of {len(cc)} years")
    if len(rd) >= 2:
        reasons.append(f"receivable days moved from {rd[0]['value']:.0f} to {rd[-1]['value']:.0f}")
    if acc and acc[-1]["value"] > 0.05:
        reasons.append("accruals are high, meaning profits rely on non-cash items")
    severity = "concern" if cc and sum(p["value"] for p in cc[-3:]) / len(cc[-3:]) < 0.6 else "watch"
    return {"tool": "investigate_cash_quality", "signal": "weak_cash_conversion", "severity": severity,
            "title": "Profits are not fully converting into cash", "explanation": _sentence(reasons),
            "evidence": _pts(a, "cash_conversion") + _pts(a, "receivable_days") + _pts(a, "accruals_ratio")}


def investigate_fcf(a: dict[str, Any]) -> Finding:
    ocf = _series(a, "operating_cf")
    ci = _series(a, "capex_intensity")
    reasons, severity = [], "watch"
    if ocf and ocf[-1]["value"] < 0:
        severity = "concern"
        reasons.append("operating cash flow itself is negative")
    elif ocf:
        reasons.append("operating cash flow is positive, so negative FCF comes from capital spending")
    if len(ci) >= 2:
        reasons.append(f"capex was {ci[-1]['value']:.1%} of revenue versus {ci[0]['value']:.1%} earlier")
    return {"tool": "investigate_fcf", "signal": "negative_fcf", "severity": severity,
            "title": "Free cash flow turned negative", "explanation": _sentence(reasons),
            "evidence": _pts(a, "operating_cf") + _pts(a, "free_cash_flow") + _pts(a, "capex_intensity")}


def investigate_growth(a: dict[str, Any]) -> Finding:
    rg = _series(a, "revenue_growth")
    ng = _series(a, "net_income_growth")
    reasons = []
    if rg:
        reasons.append(f"revenue grew {rg[-1]['value']:.1%} in the latest year")
    rc = a["cagr"]["revenue"]
    if rc.get("value") is not None:
        reasons.append(f"versus a {rc['value']:.1%} CAGR from {rc['from'][:4]} to {rc['to'][:4]}")
    if ng:
        reasons.append(f"profit growth was {ng[-1]['value']:.1%}")
    severity = "concern" if rg and rg[-1]["value"] < 0 else "watch"
    return {"tool": "investigate_growth", "signal": "revenue_slowdown", "severity": severity,
            "title": "Growth is slowing", "explanation": _sentence(reasons),
            "evidence": _pts(a, "revenue_growth") + _pts(a, "net_income_growth")}


def investigate_earnings_drop(a: dict[str, Any]) -> Finding:
    ng = _series(a, "net_income_growth")
    nm = _series(a, "net_margin")
    rg = _series(a, "revenue_growth")
    reasons = []
    if ng:
        reasons.append(f"net profit changed {ng[-1]['value']:.1%} in {ng[-1]['period'][:4]}")
    if rg and ng:
        reasons.append("revenue fell too, so the drop is demand-driven" if rg[-1]["value"] < 0
                       else "revenue still grew, so the drop came from costs, interest, tax or one-off items")
    if len(nm) >= 2:
        reasons.append(f"net margin moved from {nm[-2]['value']:.1%} to {nm[-1]['value']:.1%}")
    return {"tool": "investigate_earnings_drop", "signal": "earnings_drop", "severity": "concern",
            "title": "Profit declined in the latest year", "explanation": _sentence(reasons),
            "evidence": _pts(a, "net_income_growth") + _pts(a, "net_margin") + _pts(a, "revenue_growth")}


def investigate_valuation(a: dict[str, Any]) -> Finding:
    cur = a["valuation"]["current"]
    pe = cur.get("pe", {}).get("value")
    med_peer = a["peers"]["medians"].get("pe")
    med_hist = a["valuation"]["historical"].get("median_pe")
    eps_cagr = a["cagr"]["eps_diluted"].get("value") or a["cagr"]["net_income"].get("value")
    reasons = []
    if pe and med_peer:
        reasons.append(f"P/E of {pe:.1f} compares with a peer median of {med_peer:.1f}")
    if pe and med_hist:
        reasons.append(f"and its own historical median of {med_hist:.1f}")
    severity = "watch"
    if pe and eps_cagr and eps_cagr > 0:
        peg = pe / (eps_cagr * 100)
        reasons.append(f"relative to {eps_cagr:.1%} historical earnings growth the PEG ratio is {peg:.1f}")
        if peg > 2.5:
            severity = "concern"
    elif pe:
        reasons.append("earnings have not grown, so the premium is not supported by past growth")
        severity = "concern"
    return {"tool": "investigate_valuation", "signal": "valuation_premium", "severity": severity,
            "title": "The share trades at a premium", "explanation": _sentence(reasons),
            "evidence": [{"metric": "pe", "value": pe}, {"metric": "peer_median_pe", "value": med_peer},
                         {"metric": "historical_median_pe", "value": med_hist},
                         {"metric": "eps_cagr", "value": eps_cagr}]}


def investigate_receivables(a: dict[str, Any]) -> Finding:
    rd = _series(a, "receivable_days")
    rg = _series(a, "revenue_growth")
    reasons = [f"customers now take about {rd[-1]['value']:.0f} days to pay, up from {rd[0]['value']:.0f}"] if rd else []
    if rg:
        reasons.append("this happened while revenue grew" if rg[-1]["value"] > 0 else "this happened while revenue fell")
    return {"tool": "investigate_receivables", "signal": "receivable_buildup", "severity": "watch",
            "title": "Customers are taking longer to pay", "explanation": _sentence(reasons),
            "evidence": _pts(a, "receivable_days") + _pts(a, "revenue_growth")}


def investigate_data(a: dict[str, Any]) -> Finding:
    return {"tool": "investigate_data", "signal": "low_data_confidence", "severity": "watch",
            "title": "Conclusions rest on limited data", "explanation": " ".join(a["confidence"]["notes"]) or
            "Data coverage is limited.", "evidence": [{"metric": "confidence", "value": a["confidence"]["value"]}]}


TOOLS: dict[str, Callable[[dict[str, Any]], Finding]] = {
    "rising_debt": investigate_debt,
    "margin_compression": investigate_margins,
    "weak_cash_conversion": investigate_cash_quality,
    "negative_fcf": investigate_fcf,
    "revenue_slowdown": investigate_growth,
    "earnings_drop": investigate_earnings_drop,
    "valuation_premium": investigate_valuation,
    "receivable_buildup": investigate_receivables,
    "low_data_confidence": investigate_data,
}
