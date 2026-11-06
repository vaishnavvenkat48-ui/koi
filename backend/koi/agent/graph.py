"""KOI research agent, orchestrated with LangGraph.

Graph
-----
  load_data -> financial_analyst -> valuation_analyst -> peer_analyst -> risk_analyst
            -> [investigate]* (loops while signals are pending; tools may queue follow-ups)
            -> synthesiser -> narrator -> END

Specialist "analysts" are deterministic Python functions. Investigation is adaptive: the risk
analyst detects signals, the orchestrator routes each to an investigation tool, and a tool can
queue follow-up investigations (e.g. a concerning debt finding triggers a cash-quality check).
The narrator optionally asks a local LLM to phrase validated facts; it never computes numbers.
"""

from __future__ import annotations

import operator
import time
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from ..analysis import engine
from ..analysis import metrics as M
from . import llm
from .tools import TOOLS, detect_signals

MAX_INVESTIGATIONS = 10


class State(TypedDict, total=False):
    symbol: str
    mode: str
    use_llm: bool
    analysis: dict[str, Any]
    statements: Annotated[list[dict[str, Any]], operator.add]
    findings: Annotated[list[dict[str, Any]], operator.add]
    trace: Annotated[list[dict[str, Any]], operator.add]
    pending: list[dict[str, Any]]
    investigated: list[str]
    thesis: dict[str, Any]
    narrative: dict[str, Any]


def fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "n/a"
    if unit == "pct":
        return f"{value * 100:.1f}%"
    if unit == "x":
        return f"{value:.2f}x"
    if unit == "days":
        return f"{value:.0f} days"
    if unit == "INR":
        return f"₹{value / 1e7:,.0f} Cr"
    return f"{value:,.2f}"


def _fy(period: str) -> str:
    return f"FY{period[2:4]}" if period[5:7] in ("03", "06") else period


def _t(node: str, started: float, **extra: Any) -> dict[str, Any]:
    return {"node": node, "ms": round((time.perf_counter() - started) * 1000, 1), **extra}


# ------------------------------------------------------------------- trend statements

PLAIN_TREND = {
    "revenue": {"up": "Sales have grown over the period.", "down": "Sales have shrunk.",
                "flat": "Sales have been roughly flat."},
    "net_income": {"up": "Profits have grown over the period.", "down": "Profits have fallen.",
                   "flat": "Profits have been roughly flat."},
    "roce": {"up": "The company is becoming more efficient at generating profits from the money invested "
                          "in its business.",
             "down": "The company is earning less profit on the money invested in its business than before.",
             "flat": "Returns on the money invested in the business have held steady."},
    "roe": {"up": "Profitability for shareholders has improved.",
            "down": "Profitability for shareholders has weakened.",
            "flat": "Profitability for shareholders has been steady."},
    "operating_margin": {"up": "The company keeps more of each rupee of sales as profit than before.",
                         "down": "The company keeps less of each rupee of sales as profit than before.",
                         "flat": "Profit margins have been steady."},
    "roa": {"up": "Returns on the lender's assets have improved.",
            "down": "Returns on the lender's assets have weakened.", "flat": "Returns on assets are steady."},
    "debt_to_equity": {"up": "Borrowing has risen relative to the company's own capital.",
                       "down": "The company relies less on borrowed money than before.",
                       "flat": "Borrowing relative to the company's own capital has been steady."},
    "free_cash_flow": {"up": "Cash left after investment has increased.",
                       "down": "Cash left after investment has decreased.",
                       "flat": "Cash left after investment has been steady."},
}


def trend_statement(a: dict[str, Any], key: str, analyst: str) -> dict[str, Any] | None:
    pts = [p for p in a["series"].get(key, []) if p["value"] is not None]
    if len(pts) < 2:
        return None
    d = M.DEFS[key]
    tr = M.trend(a["series"][key])
    move = {"improving": "up", "deteriorating": "down", "stable": "flat"}.get(tr["direction"])
    if move is None:
        return None
    # Sentiment depends on whether higher is better for this metric.
    if move == "flat" or d.better == "neutral":
        sentiment = "neutral"
    else:
        sentiment = "positive" if (move == "up") == (d.better == "higher") else "negative"
    first, last = pts[0], pts[-1]
    return {
        "analyst": analyst, "metric": key, "direction": move, "sentiment": sentiment,
        "plain": PLAIN_TREND[key][move],
        "detail": f"{d.label} moved from {fmt(first['value'], d.unit)} ({_fy(first['period'])}) to "
                  f"{fmt(last['value'], d.unit)} ({_fy(last['period'])}) across {len(pts)} reporting periods.",
        "formula": d.formula,
        "evidence": [{"period": p["period"], "value": p["value"], "inputs": p["inputs"], "note": p["note"]} for p in pts],
    }


# ------------------------------------------------------------------- nodes


def load_data(state: State) -> State:
    t = time.perf_counter()
    a = engine.run_cached(state["symbol"])
    return {"analysis": a, "investigated": [], "pending": [],
            "trace": [_t("load_data", t, tool="analysis_engine.run", ready=a.get("ready"))]}


def financial_analyst(state: State) -> State:
    t = time.perf_counter()
    a = state["analysis"]
    keys = ["revenue", "net_income", "operating_margin", "roce", "roe", "free_cash_flow"]
    if a["profile"] in ("bank", "nbfc", "insurance"):
        keys = ["revenue", "net_income", "roe", "roa"]
    stmts = [s for s in (trend_statement(a, k, "financial_analyst") for k in keys) if s]
    return {"statements": stmts, "trace": [_t("financial_analyst", t, tools=["metrics.trend"] * len(keys),
                                                statements=len(stmts))]}


def valuation_analyst(state: State) -> State:
    t = time.perf_counter()
    a = state["analysis"]
    cur, hist, dcf = a["valuation"]["current"], a["valuation"]["historical"], a["valuation"]["dcf"]
    stmts = []
    pe = cur.get("pe", {})
    if pe.get("value") and hist.get("median_pe"):
        rel = pe["value"] / hist["median_pe"]
        word = "below" if rel < 0.9 else "above" if rel > 1.1 else "close to"
        stmts.append({"analyst": "valuation_analyst", "metric": "pe",
                      "plain": f"The share price relative to profits is {word} its usual level of recent years.",
                      "detail": f"P/E {pe['value']:.1f} ({pe['formula']}) vs historical median {hist['median_pe']:.1f}.",
                      "formula": pe["formula"], "evidence": pe["inputs"] + [{"historical": hist["points"]}]})
    if dcf.get("available"):
        mos = dcf.get("margin_of_safety")
        if mos is not None:
            word = "above" if mos > 0.1 else "below" if mos < -0.1 else "close to"
            stmts.append({"analyst": "valuation_analyst", "metric": "dcf",
                          "plain": f"A cash-flow based estimate of value is {word} the current share price.",
                          "detail": f"DCF value ₹{dcf['value_per_share']:,.0f}/share vs price ₹{dcf['price']:,.0f} "
                                    f"(WACC {dcf['assumptions']['wacc']:.1%}, terminal growth "
                                    f"{dcf['assumptions']['terminal_growth']:.1%}).",
                          "formula": "Two-stage FCFF DCF", "evidence": [dcf["assumptions"]]})
    return {"statements": stmts, "trace": [_t("valuation_analyst", t, tools=["valuation.current_multiples",
                                                                              "valuation.historical_multiples",
                                                                              "valuation.dcf"])]}


def peer_analyst(state: State) -> State:
    t = time.perf_counter()
    a = state["analysis"]
    p = a["peers"]
    stmts = []
    for key, good_plain, bad_plain in (
        ("roe", "It earns better returns on shareholder money than most competitors.",
         "Competitors earn better returns on shareholder money."),
        ("revenue_cagr", "It has grown faster than most competitors.", "Most competitors have grown faster."),
        ("pe", "It is priced cheaper than most competitors relative to profits.",
         "It is priced richer than most competitors relative to profits."),
    ):
        r = p["ranks"].get(key)
        if not r or r["of"] < 3:
            continue
        top = r["rank"] <= max(1, r["of"] // 3)
        bottom = r["rank"] > r["of"] - max(1, r["of"] // 3)
        if not (top or bottom):
            continue
        unit = next(c["unit"] for c in p["columns"] if c["key"] == key)
        stmts.append({"analyst": "peer_analyst", "metric": key, "plain": good_plain if top else bad_plain,
                      "detail": f"Ranks {r['rank']} of {r['of']} on {key.upper().replace('_', ' ')} "
                                f"({fmt(p['company'].get(key), unit)} vs peer median {fmt(p['medians'].get(key), unit)}).",
                      "formula": "rank among loaded peers", "evidence": [
                          {"symbol": row["symbol"], "value": row.get(key)} for row in [p["company"]] + p["peers"]
                          if row.get("has_data")]})
    return {"statements": stmts, "trace": [_t("peer_analyst", t, tool="peers.compare", peers_loaded=p["loaded"])]}


def risk_analyst(state: State) -> State:
    t = time.perf_counter()
    sigs = detect_signals(state["analysis"])
    return {"pending": sigs, "trace": [_t("risk_analyst", t, tool="detect_signals",
                                          signals=[s["signal"] for s in sigs])]}


FOLLOW_UPS = {
    # if a finding is a concern, also run these investigations
    "rising_debt": ["weak_cash_conversion"],
    "earnings_drop": ["margin_compression"],
    "negative_fcf": ["rising_debt"],
    "weak_cash_conversion": ["receivable_buildup"],
}


def investigate(state: State) -> State:
    t = time.perf_counter()
    pending = list(state.get("pending", []))
    done = list(state.get("investigated", []))
    sig = pending.pop(0)
    tool = TOOLS[sig["signal"]]
    finding = tool(state["analysis"])
    finding["trigger"] = sig["reason"]
    done.append(sig["signal"])
    queued = []
    if finding["severity"] == "concern":
        for nxt in FOLLOW_UPS.get(sig["signal"], []):
            if nxt not in done and all(p["signal"] != nxt for p in pending):
                pending.append({"signal": nxt, "reason": f"follow-up to {sig['signal']} concern"})
                queued.append(nxt)
    return {"pending": pending, "investigated": done, "findings": [finding],
            "trace": [_t("investigate", t, tool=tool.__name__, signal=sig["signal"], severity=finding["severity"],
                         queued_follow_ups=queued)]}


def route_after_risk(state: State) -> str:
    if state.get("pending") and len(state.get("investigated", [])) < MAX_INVESTIGATIONS:
        return "investigate"
    return "synthesiser"


def synthesiser(state: State) -> State:
    t = time.perf_counter()
    a = state["analysis"]
    findings = state.get("findings", [])
    thesis = build_thesis(a, findings)
    return {"thesis": thesis, "trace": [_t("synthesiser", t, conflicts=len(thesis["conflicts"]))]}


def narrator(state: State) -> State:
    t = time.perf_counter()
    if not state.get("use_llm"):
        return {"narrative": {"ok": False, "reason": "LLM narrative not requested"},
                "trace": [_t("narrator", t, skipped=True)]}
    facts = narrative_facts(state["analysis"], state["thesis"], state.get("findings", []))
    res = llm.narrate(facts, state.get("mode", "beginner"))
    return {"narrative": res, "trace": [_t("narrator", t, tool="ollama.generate", ok=res.get("ok"),
                                           reason=res.get("reason", ""))]}


def route_after_load(state: State) -> str:
    return "financial_analyst" if state["analysis"].get("ready") else END


def build_graph():
    g = StateGraph(State)
    for name, fn in (("load_data", load_data), ("financial_analyst", financial_analyst),
                     ("valuation_analyst", valuation_analyst), ("peer_analyst", peer_analyst),
                     ("risk_analyst", risk_analyst), ("investigate", investigate),
                     ("synthesiser", synthesiser), ("narrator", narrator)):
        g.add_node(name, fn)
    g.add_edge(START, "load_data")
    g.add_conditional_edges("load_data", route_after_load, ["financial_analyst", END])
    g.add_edge("financial_analyst", "valuation_analyst")
    g.add_edge("valuation_analyst", "peer_analyst")
    g.add_edge("peer_analyst", "risk_analyst")
    g.add_conditional_edges("risk_analyst", route_after_risk, ["investigate", "synthesiser"])
    g.add_conditional_edges("investigate", route_after_risk, ["investigate", "synthesiser"])
    g.add_edge("synthesiser", "narrator")
    g.add_edge("narrator", END)
    return g.compile()


_graph = None


def run_agent(symbol: str, mode: str = "beginner", use_llm: bool = False) -> State:
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph.invoke({"symbol": symbol, "mode": mode, "use_llm": use_llm},
                         config={"recursion_limit": 50})


# ------------------------------------------------------------------- synthesis


def build_thesis(a: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    o, sc, f = a["outlook"], a["scores"], a["factors"]
    concerns = [x for x in findings if x["severity"] == "concern"]
    conflicts = []
    q, v, g, r = (sc[k]["value"] for k in ("quality", "valuation", "growth", "risk"))
    if q is not None and v is not None and q >= 70 and v < 40:
        conflicts.append("High business quality, but the valuation is expensive: a good company is not "
                         "automatically a good investment at any price.")
    if q is not None and g is not None and q >= 70 and g < 40:
        conflicts.append("Strong returns on capital, but growth has been slow. Quality may be priced for "
                         "growth that is not showing up.")
    if v is not None and q is not None and v >= 65 and q < 40:
        conflicts.append("The share looks cheap, but business quality is weak; low valuations can persist "
                         "(a possible 'value trap').")
    if r is not None and r >= 50 and o["code"] <= 2:
        conflicts.append("Overall outlook is positive, but several risk signals are active.")

    monitor = []
    seen = set()
    for x in findings:
        for e in x["evidence"]:
            m = e.get("metric")
            if m in M.DEFS and m not in seen:
                seen.add(m)
                monitor.append({"metric": m, "label": M.DEFS[m].label, "why": x["title"]})
    for m in (["roe", "roa", "net_income_growth"] if a["profile"] in ("bank", "nbfc", "insurance")
              else ["revenue_growth", "operating_margin", "roce", "cash_conversion", "debt_to_equity"]):
        if m not in seen and a["headline"].get(m, {}).get("available"):
            seen.add(m)
            monitor.append({"metric": m, "label": M.DEFS[m].label, "why": "core indicator for this sector"})
    for extra in a.get("unavailable_sector_metrics", []):
        monitor.append({"metric": None, "label": extra, "why": "key sector metric not available from current "
                                                               "data source - check company disclosures"})

    fc = a["forecast"]["revenue"]
    future = []
    if fc.get("available"):
        s = fc["scenarios"]
        future.append(f"Revenue scenarios for the next {a['forecast']['horizon_years']} years: bear "
                      f"{s['bear']['growth']:.1%}, base {s['base']['growth']:.1%}, bull {s['bull']['growth']:.1%} "
                      f"a year ({fc['model']} model; backtest reliability {fc['reliability']}).")
    for x in findings:
        future.append(f"{x['title']}: {x['explanation']}")

    return {
        "outlook": o,
        "why_consider": [p["plain"] for p in f["positives"]] or ["No standout strengths were identified from the "
                                                                 "available data."],
        "what_makes_it_attractive": _attractive(a),
        "weaknesses": [c["plain"] for c in f["concerns"]] + [x["title"] for x in concerns],
        "future_drivers": future,
        "monitor": monitor[:10],
        "conflicts": conflicts,
        "should_i_consider": should_i_consider(a, conflicts),
    }


def _attractive(a: dict[str, Any]) -> str:
    q = a["scores"]["quality"]["value"]
    hl = a["scores"]["health"]["value"]
    parts = []
    if q is not None:
        parts.append("high-return business" if q >= 70 else "average-return business" if q >= 40
                     else "low-return business")
    if hl is not None:
        parts.append("with a strong balance sheet" if hl >= 65 else "with a moderate balance sheet" if hl >= 40
                     else "with a stretched balance sheet")
    return ("A " + " ".join(parts) + ".") if parts else "Insufficient data to judge business quality."


def should_i_consider(a: dict[str, Any], conflicts: list[str]) -> dict[str, Any]:
    o = a["outlook"]
    code, val = o["code"], o["valuation_verdict"]
    conf = a["confidence"]["level"]
    if o.get("capped"):
        plain = ("The available numbers look good, but there is not enough evidence to call this a strong long-term "
                 "investment yet. " + o["cap_reasons"][0] + " Check the company's annual reports before deciding.")
    elif code == 1 and val in ("attractive", "reasonable"):
        plain = ("The business shows strong long-term fundamentals and the price does not look stretched. "
                 "It may deserve a place on a long-term research shortlist. Check the risks and whether it fits "
                 "your goals before investing.")
    elif code in (1, 2) and val == "expensive":
        plain = ("The business looks strong, but the current price already expects a lot. A great company is not "
                 "always a great investment at any price. Patient investors may wait for a more reasonable valuation.")
    elif code == 2:
        plain = ("The overall picture is positive. Review the concerns listed below; they are the main things that "
                 "could change this view.")
    elif code == 3:
        plain = ("The evidence is mixed. Some numbers are good and some are not. Do more research on the concerns "
                 "below before considering it.")
    elif code == 4:
        plain = ("Important numbers are getting worse. Long-term investors may want to see a clear recovery before "
                 "considering it.")
    else:
        plain = ("There are significant financial concerns. Be cautious: the risks outweigh the positives in the "
                 "available data.")
    sc = a["scores"]
    detail = (f"Outlook '{o['label']}' ({o['rule']}). Scores: quality {sc['quality']['value']}, health "
              f"{sc['health']['value']}, growth {sc['growth']['value']}, valuation {sc['valuation']['value']} "
              f"({val}), risk {sc['risk']['value']}. Confidence {conf}.")
    return {"plain": plain, "detail": detail, "confidence": conf,
            "disclaimer": "KOI is a research and decision-support tool, not personalised financial advice."}


def narrative_facts(a: dict[str, Any], thesis: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact, pre-formatted facts for the LLM. Only these may appear in the narrative."""
    h = a["headline"]
    key = {}
    for k in ("revenue_growth", "operating_margin", "net_margin", "roe", "roce", "debt_to_equity", "cash_conversion"):
        m = h.get(k, {})
        if m.get("available"):
            key[m["label"]] = fmt(m["value"], m["unit"])
    cur = a["valuation"]["current"]
    return {
        "company": a["company"]["name"], "sector": a["company"].get("sector"),
        "outlook": a["outlook"]["label"], "valuation_verdict": a["outlook"]["valuation_verdict"],
        "confidence": a["confidence"]["level"],
        "scores_out_of_100": {k: a["scores"][k]["value"] for k in ("quality", "health", "growth", "valuation", "risk")},
        "latest_metrics": key,
        "revenue_cagr": fmt(a["cagr"]["revenue"].get("value"), "pct"),
        "profit_cagr": fmt(a["cagr"]["net_income"].get("value"), "pct"),
        "pe": None if not cur.get("pe", {}).get("value") else round(cur["pe"]["value"], 1),
        "peer_median_pe": None if not a["peers"]["medians"].get("pe") else round(a["peers"]["medians"]["pe"], 1),
        "strengths": thesis["why_consider"], "weaknesses": thesis["weaknesses"],
        "conflicts": thesis["conflicts"], "investigations": [f"{x['title']}: {x['explanation']}" for x in findings],
        "verdict": thesis["should_i_consider"]["plain"],
    }
