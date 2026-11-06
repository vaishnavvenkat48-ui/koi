"""Research report assembly (15 sections) and saved-report comparison."""

from __future__ import annotations

import json
from typing import Any

from . import db
from .agent.graph import fmt, run_agent
from .analysis import metrics as M
from .connectors import DATA_SOURCES

MODES = ("beginner", "intermediate", "advanced")


def _metric_line(a: dict[str, Any], key: str) -> dict[str, Any] | None:
    m = a["headline"].get(key)
    if not m or not m.get("available"):
        return None
    tr = m.get("trend", {})
    return {"plain": f"{m['label']}: {fmt(m['value'], m['unit'])} - {m['plain']}",
            "detail": f"{m['label']} = {fmt(m['value'], m['unit'])} for period ending {m['period']} "
                      f"({m['formula']}); trend {tr.get('direction', 'n/a')}.",
            "metric": key, "evidence": m.get("inputs", [])}


def _lines(a: dict[str, Any], keys: list[str]) -> list[dict[str, Any]]:
    return [x for x in (_metric_line(a, k) for k in keys) if x]


def build(symbol: str, use_llm: bool = False, mode: str = "beginner") -> dict[str, Any]:
    st = run_agent(symbol, mode=mode, use_llm=use_llm)
    a = st["analysis"]
    if not a.get("ready"):
        return {"symbol": symbol, "ready": False, "reason": a.get("reason"), "freshness": a.get("freshness")}
    th, statements, findings = st["thesis"], st.get("statements", []), st.get("findings", [])
    c = a["company"]
    stm = {s["metric"]: s for s in statements}

    def stmt(key: str) -> list[dict[str, Any]]:
        s = stm.get(key)
        return [{"plain": s["plain"], "detail": s["detail"], "metric": key, "evidence": s["evidence"]}] if s else []

    peers = a["peers"]
    fc = a["forecast"]
    sections = [
        {"id": "overview", "title": "Company overview",
         "summary": f"{c['name']} ({symbol}) - {c.get('industry') or c.get('sector') or 'sector unknown'}.",
         "points": [{"plain": (c.get("description") or "No business description available from the source.")[:900],
                     "detail": f"ISIN {c.get('isin') or 'n/a'}; listed {c.get('listing_date') or 'n/a'}; "
                               f"market cap {fmt(c.get('market_cap'), 'INR')}; analysis profile '{a['profile']}'."}]},
        {"id": "business_quality", "title": "Business quality",
         "summary": th["what_makes_it_attractive"],
         "points": stmt("roce") + stmt("roe") + stmt("roa") + _lines(a, ["operating_margin", "roic"])},
        {"id": "performance", "title": "Financial performance",
         "summary": f"{len(a['periods']['annual'])} annual and {len(a['periods']['quarterly'])} quarterly periods analysed.",
         "points": _lines(a, ["revenue", "net_income", "eps_growth"])},
        {"id": "trends", "title": "Revenue and profit trends",
         "summary": _cagr_text(a),
         "points": stmt("revenue") + stmt("net_income") + stmt("operating_margin") + _lines(a, ["revenue_growth",
                                                                                                "net_income_growth"])},
        {"id": "health", "title": "Financial health",
         "summary": f"Financial health score {a['scores']['health']['value']} / 100.",
         "points": _lines(a, ["debt_to_equity", "interest_coverage", "current_ratio", "equity_to_assets", "total_debt"])},
        {"id": "cash_flow", "title": "Cash flow quality",
         "summary": "Whether profits turn into cash.",
         "points": stmt("free_cash_flow") + _lines(a, ["operating_cf", "cash_conversion", "fcf_margin",
                                                       "accruals_ratio"])},
        {"id": "valuation", "title": "Valuation analysis",
         "summary": f"Valuation looks {a['outlook']['valuation_verdict']} (score {a['scores']['valuation']['value']}).",
         "points": [s for s in statements if s["analyst"] == "valuation_analyst"] + _valuation_points(a)},
        {"id": "sector", "title": "Sector comparison",
         "summary": f"Compared with {peers['loaded']} peer(s) with data out of {peers['expected']} identified.",
         "points": [s for s in statements if s["analyst"] == "peer_analyst"], "table": {
             "columns": peers["columns"], "rows": [peers["company"]] + [p for p in peers["peers"] if p.get("has_data")],
             "medians": peers["medians"]}},
        {"id": "positives", "title": "Positive factors", "summary": "",
         "points": [{"plain": f["plain"], "detail": f"{f['label']}: {f['evidence']} (score {f['score']})",
                     "evidence": f["inputs"]} for f in a["factors"]["positives"]]},
        {"id": "red_flags", "title": "Financial red flags", "summary": "" if findings else "No red-flag signals were "
                                                                                           "triggered.",
         "points": [{"plain": x["title"] + ".", "detail": x["explanation"], "severity": x["severity"],
                     "evidence": x["evidence"], "trigger": x.get("trigger")} for x in findings]
                   + [{"plain": f["plain"], "detail": f"{f['label']}: {f['evidence']} (score {f['score']})",
                       "evidence": f["inputs"]} for f in a["factors"]["concerns"]]},
        {"id": "growth", "title": "Future growth opportunities",
         "summary": "Derived from historical trends; not a prediction.",
         "points": [{"plain": t} for t in th["future_drivers"][:1]]},
        {"id": "scenarios", "title": "Bear / base / bull scenarios", "summary": fc["disclaimer"],
         "points": _scenario_points(fc), "forecast": fc},
        {"id": "outlook", "title": "Investment outlook", "summary": a["outlook"]["label"],
         "points": [{"plain": th["should_i_consider"]["plain"], "detail": th["should_i_consider"]["detail"]}]
                   + [{"plain": c_} for c_ in th["conflicts"]]},
        {"id": "monitor", "title": "Key metrics to monitor", "summary": "",
         "points": [{"plain": f"{m['label']} - {m['why']}"} for m in th["monitor"]]},
        {"id": "limitations", "title": "Data limitations and sources", "summary": "",
         "points": [{"plain": x} for x in a["data_limitations"]]
                   + [{"plain": f"Not available from current source: {', '.join(a['unavailable_sector_metrics'])}."}
                      if a["unavailable_sector_metrics"] else None]
                   + [{"plain": f"{s['name']}: {s['coverage']}", "detail": f"{s['url']} - {s['terms_note']}"}
                      for s in DATA_SOURCES]},
    ]
    for s in sections:
        s["points"] = [p for p in s["points"] if p]
    return {
        "symbol": symbol, "ready": True, "company": c, "generated_at": db.now_iso(),
        "outlook": a["outlook"], "scores": {k: v["value"] for k, v in a["scores"].items()},
        "confidence": a["confidence"], "thesis": th, "sections": sections,
        "statements": statements, "findings": findings, "trace": st.get("trace", []),
        "narrative": st.get("narrative"), "freshness": a["freshness"],
        "key_metrics": {k: a["headline"][k].get("value") for k in
                        ("revenue", "net_income", "revenue_growth", "operating_margin", "roe", "roce",
                         "debt_to_equity", "cash_conversion") if a["headline"].get(k, {}).get("available")},
        "valuation": {k: a["valuation"]["current"].get(k, {}).get("value") for k in ("pe", "pb", "ev_ebitda")},
    }


def _cagr_text(a: dict[str, Any]) -> str:
    r, n = a["cagr"]["revenue"], a["cagr"]["net_income"]
    parts = []
    if r.get("value") is not None:
        parts.append(f"Revenue CAGR {r['value']:.1%} ({r['from'][:4]}-{r['to'][:4]})")
    if n.get("value") is not None:
        parts.append(f"profit CAGR {n['value']:.1%}")
    return "; ".join(parts) + "." if parts else "CAGR unavailable."


def _valuation_points(a: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for k in ("pe", "pb", "ev_ebitda", "earnings_yield"):
        m = a["valuation"]["current"].get(k, {})
        if m.get("value") is None:
            out.append({"plain": f"{m.get('label', k)}: unavailable ({m.get('reason', '')}).", "detail": ""})
            continue
        v = f"{m['value']:.1%}" if k == "earnings_yield" else f"{m['value']:.1f}"
        med = a["peers"]["medians"].get(k)
        out.append({"plain": f"{m['label']}: {v}" + (f" (peer median {med:.1f})" if med else ""),
                    "detail": m["formula"], "evidence": m["inputs"]})
    return out


def _scenario_points(fc: dict[str, Any]) -> list[dict[str, Any]]:
    r = fc["revenue"]
    if not r.get("available"):
        return [{"plain": f"Revenue scenarios unavailable: {r.get('reason')}."}]
    pts = []
    for k in ("bear", "base", "bull"):
        s = r["scenarios"][k]
        e = fc["earnings"]["scenarios"][k] if fc["earnings"].get("available") else None
        pts.append({"plain": f"{k.title()} case: revenue grows {s['growth']:.1%} a year to "
                             f"{fmt(s['path'][-1], 'INR')} in {fc['horizon_years']} years"
                             + (f"; profit about {fmt(e['path'][-1], 'INR')} at a {e['margin']:.1%} margin" if e else "")
                             + ".",
                    "detail": r["assumptions"]["base" if k == "base" else "bear_bull"]})
    return pts


def for_mode(report: dict[str, Any], mode: str) -> dict[str, Any]:
    """Beginner: plain text only. Intermediate: plus details. Advanced: everything incl. evidence and trace."""
    if mode == "advanced" or not report.get("ready"):
        return report
    out = json.loads(json.dumps(report, default=str))
    for s in out["sections"]:
        for p in s["points"]:
            p.pop("evidence", None)
            if mode == "beginner":
                p.pop("detail", None)
        if mode == "beginner":
            s.pop("forecast", None)
    out.pop("trace", None)
    for st in out.get("statements", []):
        st.pop("evidence", None)
    return out


# -------------------------------------------------------------- saved reports


def save(report: dict[str, Any]) -> int:
    return db.execute(
        "INSERT INTO analysis_reports (symbol, created_at, outlook, title, payload) VALUES (?,?,?,?,?)",
        (report["symbol"], report["generated_at"], report["outlook"]["label"],
         f"{report['company']['name']} research report", json.dumps(report, default=str)))


def list_saved(symbol: str | None = None) -> list[dict[str, Any]]:
    if symbol:
        return db.query("SELECT id, symbol, created_at, outlook, title FROM analysis_reports WHERE symbol=? "
                        "ORDER BY id DESC", (symbol,))
    return db.query("SELECT id, symbol, created_at, outlook, title FROM analysis_reports ORDER BY id DESC LIMIT 100")


def get_saved(report_id: int) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM analysis_reports WHERE id=?", (report_id,))
    if not row:
        return None
    return {"id": row["id"], "created_at": row["created_at"], **json.loads(row["payload"])}


def compare(a_id: int, b_id: int) -> dict[str, Any] | None:
    a, b = get_saved(a_id), get_saved(b_id)
    if not a or not b:
        return None
    score_diff = {k: {"old": a["scores"].get(k), "new": b["scores"].get(k),
                      "change": None if a["scores"].get(k) is None or b["scores"].get(k) is None
                      else round(b["scores"][k] - a["scores"][k], 1)} for k in b["scores"]}
    metric_diff = {}
    for k in set(a.get("key_metrics", {})) | set(b.get("key_metrics", {})):
        o, n = a["key_metrics"].get(k), b["key_metrics"].get(k)
        metric_diff[k] = {"label": M.DEFS[k].label if k in M.DEFS else k, "unit": M.DEFS[k].unit if k in M.DEFS else "",
                          "old": o, "new": n}
    return {
        "old": {"id": a["id"], "created_at": a["created_at"], "symbol": a["symbol"], "outlook": a["outlook"]},
        "new": {"id": b["id"], "created_at": b["created_at"], "symbol": b["symbol"], "outlook": b["outlook"]},
        "outlook_changed": a["outlook"]["code"] != b["outlook"]["code"],
        "scores": score_diff, "metrics": metric_diff,
        "valuation": {k: {"old": a["valuation"].get(k), "new": b["valuation"].get(k)} for k in b["valuation"]},
        "new_findings": [f["title"] for f in b["findings"] if f["title"] not in {x["title"] for x in a["findings"]}],
        "resolved_findings": [f["title"] for f in a["findings"] if f["title"] not in {x["title"] for x in b["findings"]}],
    }
