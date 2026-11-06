"""Deterministic financial metric calculations with full evidence trails.

Every computed value carries: formula, the exact input figures with their reporting periods,
and a status. Missing inputs produce ``available: False`` with a reason, never a zero.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Callable

from .data import FinData, consecutive_years

# ------------------------------------------------------------------ definitions


@dataclass(frozen=True)
class MetricDef:
    key: str
    label: str
    unit: str            # pct | x | days | INR | ratio
    formula: str
    better: str          # higher | lower | neutral
    category: str        # growth | profitability | health | cashflow | efficiency | valuation | bank
    plain: str           # beginner-level explanation of what the metric means
    level: str = "intermediate"   # minimum interface mode where it is shown


DEFS: dict[str, MetricDef] = {d.key: d for d in [
    MetricDef("revenue", "Revenue", "INR", "Total revenue as reported", "higher", "growth",
              "Total money the company earned from selling its products or services.", "beginner"),
    MetricDef("revenue_growth", "Revenue growth", "pct", "Revenue(t) / Revenue(t-1) - 1", "higher", "growth",
              "How much more (or less) the company sold compared with the previous year.", "beginner"),
    MetricDef("net_income", "Net profit", "INR", "Net income attributable to shareholders", "higher", "profitability",
              "What is left for shareholders after all costs, interest and taxes.", "beginner"),
    MetricDef("net_income_growth", "Profit growth", "pct", "Net profit(t) / Net profit(t-1) - 1", "higher", "growth",
              "How fast the company's profit is growing.", "beginner"),
    MetricDef("eps_growth", "EPS growth", "pct", "Diluted EPS(t) / Diluted EPS(t-1) - 1", "higher", "growth",
              "Growth in profit per share - what each share you own earns."),
    MetricDef("ebitda_margin", "EBITDA margin", "pct", "EBITDA / Revenue", "higher", "profitability",
              "Share of sales left as operating cash profit before interest, tax and depreciation."),
    MetricDef("operating_margin", "Operating margin", "pct", "Operating income (or EBIT) / Revenue", "higher",
              "profitability", "Share of each rupee of sales kept as profit from the core business.", "beginner"),
    MetricDef("net_margin", "Net profit margin", "pct", "Net profit / Revenue", "higher", "profitability",
              "Share of each rupee of sales that ends up as final profit."),
    MetricDef("roe", "Return on equity (ROE)", "pct", "Net profit / Average shareholders' equity", "higher",
              "profitability", "How much profit the company makes with shareholders' money.", "beginner"),
    MetricDef("roce", "Return on capital employed (ROCE)", "pct",
              "EBIT / Average (Total assets - Current liabilities)", "higher", "profitability",
              "How efficiently the business turns all the long-term money invested in it into profit.", "beginner"),
    MetricDef("roa", "Return on assets (ROA)", "pct", "Net profit / Average total assets", "higher", "profitability",
              "Profit generated for every rupee of assets the company holds."),
    MetricDef("roic", "Return on invested capital (ROIC)", "pct",
              "EBIT x (1 - effective tax rate) / Average invested capital", "higher", "profitability",
              "After-tax return on all capital (debt and equity) used in the business.", "advanced"),
    MetricDef("debt_to_equity", "Debt-to-equity", "x", "Total debt / Shareholders' equity", "lower", "health",
              "How much the company has borrowed compared with its own money.", "beginner"),
    MetricDef("current_ratio", "Current ratio", "x", "Current assets / Current liabilities", "higher", "health",
              "Whether short-term assets can cover bills due within a year."),
    MetricDef("interest_coverage", "Interest coverage", "x", "EBIT / Interest expense", "higher", "health",
              "How many times over operating profit can pay the interest bill."),
    MetricDef("total_debt", "Total borrowings", "INR", "Total debt as reported", "lower", "health",
              "Total money the company owes to lenders."),
    MetricDef("asset_growth", "Asset growth", "pct", "Total assets(t) / Total assets(t-1) - 1", "neutral", "health",
              "How fast the company's balance sheet is expanding.", "advanced"),
    MetricDef("equity_growth", "Equity growth", "pct", "Equity(t) / Equity(t-1) - 1", "higher", "health",
              "How fast shareholders' net worth in the company is growing.", "advanced"),
    MetricDef("equity_to_assets", "Equity to assets", "pct", "Shareholders' equity / Total assets", "higher", "bank",
              "Capital cushion: share of assets funded by shareholders rather than deposits or borrowings."),
    MetricDef("operating_cf", "Operating cash flow", "INR", "Cash flow from operations as reported", "higher",
              "cashflow", "Cash actually generated by running the business.", "beginner"),
    MetricDef("investing_cf", "Investing cash flow", "INR", "Cash flow from investing as reported", "neutral",
              "cashflow", "Cash spent on (or received from) assets and investments.", "advanced"),
    MetricDef("financing_cf", "Financing cash flow", "INR", "Cash flow from financing as reported", "neutral",
              "cashflow", "Cash from or paid to lenders and shareholders.", "advanced"),
    MetricDef("free_cash_flow", "Free cash flow", "INR", "Operating cash flow - Capital expenditure", "higher",
              "cashflow", "Cash left after investing in the business; can fund dividends or reduce debt.", "beginner"),
    MetricDef("cash_conversion", "Cash conversion", "x", "Operating cash flow / Net profit", "higher", "cashflow",
              "Whether reported profits are backed by real cash. Near or above 1.0x is healthy."),
    MetricDef("fcf_margin", "FCF margin", "pct", "Free cash flow / Revenue", "higher", "cashflow",
              "Share of sales that becomes free cash.", "advanced"),
    MetricDef("capex_intensity", "Capex intensity", "pct", "Capital expenditure / Revenue", "neutral", "cashflow",
              "How much of its sales the company reinvests in fixed assets.", "advanced"),
    MetricDef("accruals_ratio", "Accruals ratio", "pct", "(Net profit - Operating cash flow) / Average total assets",
              "lower", "cashflow", "High values mean profits are running ahead of cash - a quality warning.", "advanced"),
    MetricDef("asset_turnover", "Asset turnover", "x", "Revenue / Average total assets", "higher", "efficiency",
              "Sales generated per rupee of assets.", "advanced"),
    MetricDef("equity_multiplier", "Equity multiplier", "x", "Average total assets / Average equity", "neutral",
              "efficiency", "Leverage component of DuPont analysis.", "advanced"),
    MetricDef("receivable_days", "Receivable days", "days", "Receivables / Revenue x 365", "lower", "efficiency",
              "Average days customers take to pay.", "advanced"),
    MetricDef("inventory_days", "Inventory days", "days", "Inventory / Cost of revenue x 365", "lower", "efficiency",
              "Average days stock sits before it is sold.", "advanced"),
    MetricDef("payable_days", "Payable days", "days", "Payables / Cost of revenue x 365", "neutral", "efficiency",
              "Average days the company takes to pay suppliers.", "advanced"),
    MetricDef("cash_conversion_cycle", "Cash conversion cycle", "days",
              "Receivable days + Inventory days - Payable days", "lower", "efficiency",
              "Days of cash tied up in day-to-day operations.", "advanced"),
    MetricDef("net_interest_income", "Net interest income", "INR", "Interest earned - Interest paid", "higher",
              "bank", "A lender's core earnings: interest earned on loans minus interest paid on deposits."),
    MetricDef("nii_growth", "NII growth", "pct", "NII(t) / NII(t-1) - 1", "higher", "bank",
              "Growth of a lender's core interest earnings."),
]}


# ------------------------------------------------------------------ helpers


def _ref(fd: FinData, metric: str, period: str) -> dict[str, Any] | None:
    v = fd.a(metric, period)
    if v is None:
        return None
    prov = fd.provenance.get(metric, {})
    return {"metric": metric, "period": period, "value": v, "unit": prov.get("unit"),
            "source": prov.get("source"), "source_label": prov.get("source_label")}


def _avg(fd: FinData, metric: str, i: int) -> tuple[float | None, list[dict], str]:
    """Average of period i and i-1 if consecutive; else period-end value (noted)."""
    p = fd.annual_periods[i]
    cur = _ref(fd, metric, p)
    if cur is None:
        return None, [], ""
    if i > 0 and consecutive_years(fd.annual_periods[i - 1], p):
        prev = _ref(fd, metric, fd.annual_periods[i - 1])
        if prev is not None:
            return (cur["value"] + prev["value"]) / 2, [prev, cur], ""
    return cur["value"], [cur], "period-end value used (prior year unavailable)"


def _div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


Computed = tuple[float | None, list[dict], str]   # value, inputs, note


def _growth(metric: str) -> Callable[[FinData, int], Computed]:
    def f(fd: FinData, i: int) -> Computed:
        if i == 0 or not consecutive_years(fd.annual_periods[i - 1], fd.annual_periods[i]):
            return None, [], "needs the previous consecutive year"
        prev, cur = _ref(fd, metric, fd.annual_periods[i - 1]), _ref(fd, metric, fd.annual_periods[i])
        if prev is None or cur is None:
            return None, [x for x in (prev, cur) if x], f"{metric} missing"
        if prev["value"] <= 0:
            return None, [prev, cur], "growth undefined when the base year is zero or negative"
        return cur["value"] / prev["value"] - 1, [prev, cur], ""
    return f


def _ratio(num: str, den: str, scale: float = 1.0, den_avg: bool = False, abs_num: bool = False,
           pos_den: bool = True) -> Callable[[FinData, int], Computed]:
    def f(fd: FinData, i: int) -> Computed:
        p = fd.annual_periods[i]
        n = _ref(fd, num, p)
        if den_avg:
            d_val, d_inputs, note = _avg(fd, den, i)
        else:
            d = _ref(fd, den, p)
            d_val, d_inputs, note = (d["value"] if d else None), ([d] if d else []), ""
        inputs = ([n] if n else []) + d_inputs
        if n is None or d_val is None:
            return None, inputs, f"{num if n is None else den} unavailable for {p}"
        if pos_den and d_val <= 0:
            return None, inputs, f"{den} is zero or negative; ratio not meaningful"
        nv = abs(n["value"]) if abs_num else n["value"]
        return nv / d_val * scale, inputs, note
    return f


def _first(fd: FinData, p: str, *metrics: str) -> dict | None:
    for m in metrics:
        r = _ref(fd, m, p)
        if r is not None:
            return r
    return None


def _operating_margin(fd: FinData, i: int) -> Computed:
    p = fd.annual_periods[i]
    n = _first(fd, p, "operating_income", "ebit")
    d = _ref(fd, "revenue", p)
    if n is None or d is None or d["value"] <= 0:
        return None, [x for x in (n, d) if x], "operating income or revenue unavailable"
    return n["value"] / d["value"], [n, d], ""


def _roce(fd: FinData, i: int) -> Computed:
    p = fd.annual_periods[i]
    ebit = _first(fd, p, "ebit", "operating_income")
    if ebit is None:
        return None, [], "EBIT unavailable"
    vals, inputs = [], [ebit]
    idx = [i - 1, i] if i > 0 and consecutive_years(fd.annual_periods[i - 1], p) else [i]
    for j in idx:
        pj = fd.annual_periods[j]
        ta, cl = _ref(fd, "total_assets", pj), _ref(fd, "current_liabilities", pj)
        if ta is None or cl is None:
            continue
        vals.append(ta["value"] - cl["value"])
        inputs += [ta, cl]
    if not vals or sum(vals) / len(vals) <= 0:
        return None, inputs, "capital employed unavailable"
    note = "" if len(vals) == 2 else "period-end capital employed used"
    return ebit["value"] / (sum(vals) / len(vals)), inputs, note


def _interest_coverage(fd: FinData, i: int) -> Computed:
    p = fd.annual_periods[i]
    ebit = _first(fd, p, "ebit", "operating_income")
    ie = _ref(fd, "interest_expense", p)
    if ebit is None or ie is None:
        return None, [x for x in (ebit, ie) if x], "EBIT or interest expense unavailable"
    if abs(ie["value"]) < 1:
        return None, [ebit, ie], "no meaningful interest expense"
    return ebit["value"] / abs(ie["value"]), [ebit, ie], ""


def _fcf(fd: FinData, i: int) -> Computed:
    p = fd.annual_periods[i]
    ocf, capex = _ref(fd, "operating_cf", p), _ref(fd, "capex", p)
    if ocf is not None and capex is not None:
        return ocf["value"] - abs(capex["value"]), [ocf, capex], ""
    r = _ref(fd, "free_cash_flow", p)
    if r is not None:
        return r["value"], [r], "as reported by source"
    return None, [x for x in (ocf, capex) if x], "operating cash flow or capex unavailable"


def _fcf_margin(fd: FinData, i: int) -> Computed:
    v, inputs, note = _fcf(fd, i)
    rev = _ref(fd, "revenue", fd.annual_periods[i])
    if v is None or rev is None or rev["value"] <= 0:
        return None, inputs, "FCF or revenue unavailable"
    return v / rev["value"], inputs + [rev], note


def _cash_conversion(fd: FinData, i: int) -> Computed:
    p = fd.annual_periods[i]
    ocf, ni = _ref(fd, "operating_cf", p), _ref(fd, "net_income", p)
    if ocf is None or ni is None:
        return None, [x for x in (ocf, ni) if x], "operating cash flow or net profit unavailable"
    if ni["value"] <= 0:
        return None, [ocf, ni], "net profit is zero or negative; ratio not meaningful"
    return ocf["value"] / ni["value"], [ocf, ni], ""


def _accruals(fd: FinData, i: int) -> Computed:
    p = fd.annual_periods[i]
    ocf, ni = _ref(fd, "operating_cf", p), _ref(fd, "net_income", p)
    ta, ta_inputs, note = _avg(fd, "total_assets", i)
    if ocf is None or ni is None or not ta:
        return None, [x for x in (ocf, ni) if x] + ta_inputs, "inputs unavailable"
    return (ni["value"] - ocf["value"]) / ta, [ni, ocf] + ta_inputs, note


def _roic(fd: FinData, i: int) -> Computed:
    p = fd.annual_periods[i]
    ebit = _first(fd, p, "ebit", "operating_income")
    tax, pbt = _ref(fd, "tax_provision", p), _ref(fd, "pretax_income", p)
    ic, ic_inputs, note = _avg(fd, "invested_capital", i)
    if ebit is None or not ic or ic <= 0:
        return None, ([ebit] if ebit else []) + ic_inputs, "EBIT or invested capital unavailable"
    rate, inputs = 0.25, [ebit]
    if tax and pbt and pbt["value"] > 0:
        rate = min(max(tax["value"] / pbt["value"], 0.0), 0.5)
        inputs += [tax, pbt]
        rnote = ""
    else:
        rnote = "25% tax rate assumed"
    return ebit["value"] * (1 - rate) / ic, inputs + ic_inputs, "; ".join(x for x in (note, rnote) if x)


def _days(num: str, den: str, den_fallback: str | None = None) -> Callable[[FinData, int], Computed]:
    def f(fd: FinData, i: int) -> Computed:
        p = fd.annual_periods[i]
        n = _ref(fd, num, p)
        d = _ref(fd, den, p) or (_ref(fd, den_fallback, p) if den_fallback else None)
        if n is None or d is None or d["value"] <= 0:
            return None, [x for x in (n, d) if x], f"{num} or {den} unavailable"
        return n["value"] / d["value"] * 365, [n, d], ""
    return f


def _ccc(fd: FinData, i: int) -> Computed:
    parts = [COMPUTE["receivable_days"](fd, i), COMPUTE["inventory_days"](fd, i), COMPUTE["payable_days"](fd, i)]
    if any(p[0] is None for p in parts):
        return None, [], "one of receivable, inventory or payable days unavailable"
    return parts[0][0] + parts[1][0] - parts[2][0], [x for p in parts for x in p[1]], ""


def _equity_multiplier(fd: FinData, i: int) -> Computed:
    ta, ta_in, n1 = _avg(fd, "total_assets", i)
    eq, eq_in, n2 = _avg(fd, "total_equity", i)
    if not ta or not eq or eq <= 0:
        return None, ta_in + eq_in, "assets or equity unavailable"
    return ta / eq, ta_in + eq_in, n1 or n2


def _reported(metric: str) -> Callable[[FinData, int], Computed]:
    def f(fd: FinData, i: int) -> Computed:
        r = _ref(fd, metric, fd.annual_periods[i])
        return (r["value"], [r], "") if r else (None, [], f"{metric} not reported")
    return f


def _capex_intensity(fd: FinData, i: int) -> Computed:
    return _ratio("capex", "revenue", abs_num=True)(fd, i)


COMPUTE: dict[str, Callable[[FinData, int], Computed]] = {
    "revenue": _reported("revenue"),
    "revenue_growth": _growth("revenue"),
    "net_income": _reported("net_income"),
    "net_income_growth": _growth("net_income"),
    "eps_growth": _growth("eps_diluted"),
    "ebitda_margin": _ratio("ebitda", "revenue"),
    "operating_margin": _operating_margin,
    "net_margin": _ratio("net_income", "revenue"),
    "roe": _ratio("net_income", "total_equity", den_avg=True),
    "roce": _roce,
    "roa": _ratio("net_income", "total_assets", den_avg=True),
    "roic": _roic,
    "debt_to_equity": _ratio("total_debt", "total_equity"),
    "current_ratio": _ratio("current_assets", "current_liabilities"),
    "interest_coverage": _interest_coverage,
    "total_debt": _reported("total_debt"),
    "asset_growth": _growth("total_assets"),
    "equity_growth": _growth("total_equity"),
    "equity_to_assets": _ratio("total_equity", "total_assets"),
    "operating_cf": _reported("operating_cf"),
    "investing_cf": _reported("investing_cf"),
    "financing_cf": _reported("financing_cf"),
    "free_cash_flow": _fcf,
    "cash_conversion": _cash_conversion,
    "fcf_margin": _fcf_margin,
    "capex_intensity": _capex_intensity,
    "accruals_ratio": _accruals,
    "asset_turnover": _ratio("revenue", "total_assets", den_avg=True),
    "equity_multiplier": _equity_multiplier,
    "receivable_days": _days("receivables", "revenue"),
    "inventory_days": _days("inventory", "cost_of_revenue"),
    "payable_days": _days("payables", "cost_of_revenue"),
    "cash_conversion_cycle": _ccc,
    "net_interest_income": _reported("net_interest_income"),
    "nii_growth": _growth("net_interest_income"),
}

# Metrics that are not meaningful for a profile (e.g. EBITDA margin for a bank).
NOT_APPLICABLE: dict[str, set[str]] = {
    "bank": {"ebitda_margin", "operating_margin", "roce", "roic", "current_ratio", "interest_coverage",
             "debt_to_equity", "free_cash_flow", "fcf_margin", "cash_conversion", "capex_intensity",
             "receivable_days", "inventory_days", "payable_days", "cash_conversion_cycle", "accruals_ratio"},
    "nbfc": {"ebitda_margin", "roce", "roic", "current_ratio", "free_cash_flow", "fcf_margin", "cash_conversion",
             "capex_intensity", "receivable_days", "inventory_days", "payable_days", "cash_conversion_cycle",
             "accruals_ratio"},
    "insurance": {"ebitda_margin", "roce", "roic", "current_ratio", "interest_coverage", "debt_to_equity",
                  "receivable_days", "inventory_days", "payable_days", "cash_conversion_cycle", "capex_intensity"},
}
NOT_APPLICABLE_REASON = {
    "bank": "Not meaningful for banks: borrowing (deposits) is the raw material of the business.",
    "nbfc": "Not meaningful for lenders, whose cash flows are dominated by loan disbursements.",
    "insurance": "Not meaningful for insurers; insurance-specific metrics apply instead.",
}


# ------------------------------------------------------------------ public API


def compute_series(fd: FinData) -> dict[str, list[dict[str, Any]]]:
    """Per-period values for every metric, oldest first."""
    na = NOT_APPLICABLE.get(fd.profile, set())
    out: dict[str, list[dict[str, Any]]] = {}
    for key, fn in COMPUTE.items():
        if key in na:
            continue
        points = []
        for i, p in enumerate(fd.annual_periods):
            try:
                v, inputs, note = fn(fd, i)
            except (ZeroDivisionError, ValueError):
                v, inputs, note = None, [], "calculation error"
            if v is not None and (math.isnan(v) or math.isinf(v)):
                v, note = None, "not a finite number"
            points.append({"period": p, "value": v, "inputs": inputs, "note": note})
        out[key] = points
    return out


def latest(series: list[dict[str, Any]]) -> dict[str, Any] | None:
    for pt in reversed(series):
        if pt["value"] is not None:
            return pt
    return None


def values(series: list[dict[str, Any]]) -> list[float]:
    return [p["value"] for p in series if p["value"] is not None]


def cagr(fd: FinData, metric: str) -> dict[str, Any]:
    """CAGR across the longest span of available annual values for a reported metric."""
    pts = [(p, fd.a(metric, p)) for p in fd.annual_periods if fd.a(metric, p) is not None]
    if len(pts) < 2:
        return {"value": None, "note": "needs at least two annual periods", "inputs": []}
    (p0, v0), (p1, v1) = pts[0], pts[-1]
    years = round(_date_days(p0, p1) / 365.25, 2)
    inputs = [_ref(fd, metric, p0), _ref(fd, metric, p1)]
    if years < 1.9:
        # One year of change is a growth rate, not a compound trend.
        return {"value": None, "note": "needs at least two years between first and last value", "inputs": inputs,
                "years": years}
    if v0 <= 0 or v1 <= 0:
        return {"value": None, "note": "CAGR undefined for zero/negative endpoints", "inputs": inputs, "years": years}
    return {"value": (v1 / v0) ** (1 / years) - 1, "years": years, "from": p0, "to": p1, "inputs": inputs,
            "formula": f"({metric} {p1} / {metric} {p0})^(1/{years}) - 1",
            "label": f"{years:.1f}-year CAGR", "note": ""}


def _date_days(a: str, b: str) -> int:
    from .data import days_between
    return days_between(a, b)


def consistency(series: list[dict[str, Any]]) -> dict[str, Any]:
    vals = values(series)
    if len(vals) < 2:
        return {"positive_share": None, "stdev": None, "n": len(vals)}
    return {"positive_share": sum(1 for v in vals if v > 0) / len(vals), "stdev": statistics.pstdev(vals),
            "n": len(vals)}


def trend(series: list[dict[str, Any]], window: int = 3) -> dict[str, Any]:
    """Latest value versus the average of up to `window` earlier values."""
    vals = [p for p in series if p["value"] is not None]
    if len(vals) < 2:
        return {"direction": "unknown", "change": None}
    last = vals[-1]["value"]
    prior = [p["value"] for p in vals[-1 - window:-1]]
    base = sum(prior) / len(prior)
    change = last - base
    tol = max(abs(base) * 0.05, 1e-9)
    direction = "improving" if change > tol else "deteriorating" if change < -tol else "stable"
    return {"direction": direction, "change": change, "latest": last, "prior_avg": base,
            "from": vals[-1 - len(prior)]["period"], "to": vals[-1]["period"]}


def ttm(fd: FinData, metric: str) -> dict[str, Any] | None:
    """Trailing twelve months from four consecutive quarters, if available."""
    qs = [p for p in fd.quarterly_periods if fd.q(metric, p) is not None]
    if len(qs) < 4:
        return None
    last4 = qs[-4:]
    for a, b in zip(last4, last4[1:]):
        if not (80 <= _date_days(a, b) <= 100):
            return None
    return {"value": sum(fd.q(metric, p) for p in last4), "periods": last4,
            "inputs": [{"metric": metric, "period": p, "value": fd.q(metric, p), "period_type": "quarterly"}
                       for p in last4]}


def headline(fd: FinData, series: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """Latest value of each metric, with definition and evidence, in a UI-ready shape."""
    out: dict[str, dict[str, Any]] = {}
    na = NOT_APPLICABLE.get(fd.profile, set())
    for key, d in DEFS.items():
        base = {"key": key, "label": d.label, "unit": d.unit, "formula": d.formula, "better": d.better,
                "category": d.category, "plain": d.plain, "level": d.level}
        if key in na:
            out[key] = {**base, "available": False, "applicable": False,
                        "reason": NOT_APPLICABLE_REASON.get(fd.profile, "Not applicable")}
            continue
        s = series.get(key, [])
        pt = latest(s)
        if pt is None:
            reason = next((p["note"] for p in reversed(s) if p["note"]), "no data")
            out[key] = {**base, "available": False, "applicable": True, "reason": reason}
            continue
        out[key] = {**base, "available": True, "applicable": True, "value": pt["value"], "period": pt["period"],
                    "inputs": pt["inputs"], "note": pt["note"], "trend": trend(s)}
    return out
