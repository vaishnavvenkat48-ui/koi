"""Valuation: current multiples, historical multiples and a transparent DCF."""

from __future__ import annotations

from typing import Any

from ..config import settings
from . import metrics as M
from .data import FinData, price_on_or_before

FINANCIAL_PROFILES = {"bank", "nbfc", "insurance"}


def _earnings_basis(fd: FinData, metric: str) -> dict[str, Any] | None:
    t = M.ttm(fd, metric)
    if t:
        return {"value": t["value"], "basis": f"TTM ({t['periods'][0]} to {t['periods'][-1]})", "inputs": t["inputs"]}
    p = fd.annual_periods[-1] if fd.annual_periods else None
    v = fd.a(metric, p)
    if v is None:
        # latest annual period that has the metric
        for pp in reversed(fd.annual_periods):
            if fd.a(metric, pp) is not None:
                p, v = pp, fd.a(metric, pp)
                break
    if v is None:
        return None
    return {"value": v, "basis": f"FY ending {p}", "inputs": [{"metric": metric, "period": p, "value": v}]}


def _latest_balance(fd: FinData, metric: str) -> dict[str, Any] | None:
    for p in reversed(fd.quarterly_periods):
        v = fd.q(metric, p)
        if v is not None:
            return {"value": v, "period": p, "period_type": "quarterly"}
    for p in reversed(fd.annual_periods):
        v = fd.a(metric, p)
        if v is not None:
            return {"value": v, "period": p, "period_type": "annual"}
    return None


def current_multiples(fd: FinData) -> dict[str, Any]:
    snap = fd.snapshot or {}
    mcap, price = snap.get("market_cap"), snap.get("price")
    out: dict[str, Any] = {"market_cap": mcap, "price": price, "as_of": snap.get("as_of"), "source": snap.get("source")}

    def item(key: str, label: str, value: float | None, formula: str, inputs: list, reason: str = "") -> None:
        out[key] = {"key": key, "label": label, "value": value, "available": value is not None,
                    "formula": formula, "inputs": inputs, "reason": reason if value is None else ""}

    if not mcap:
        for k, lbl in (("pe", "P/E"), ("pb", "P/B"), ("ev_ebitda", "EV/EBITDA"), ("earnings_yield", "Earnings yield"),
                       ("ps", "Price/Sales")):
            item(k, lbl, None, "", [], "market capitalisation unavailable")
        return out
    mc_in = {"metric": "market_cap", "value": mcap, "as_of": snap.get("as_of"), "source": snap.get("source")}

    ni = _earnings_basis(fd, "net_income")
    if ni and ni["value"] > 0:
        item("pe", "P/E", mcap / ni["value"], f"Market cap / Net profit ({ni['basis']})", [mc_in] + ni["inputs"])
        item("earnings_yield", "Earnings yield", ni["value"] / mcap, f"Net profit ({ni['basis']}) / Market cap",
             [mc_in] + ni["inputs"])
    else:
        reason = "net profit unavailable" if not ni else "P/E not meaningful: net profit is zero or negative"
        item("pe", "P/E", None, "", [], reason)
        item("earnings_yield", "Earnings yield", None, "", [], reason)

    eq = _latest_balance(fd, "total_equity")
    if eq and eq["value"] > 0:
        item("pb", "P/B", mcap / eq["value"], f"Market cap / Shareholders' equity ({eq['period']})",
             [mc_in, {"metric": "total_equity", **eq}])
    else:
        item("pb", "P/B", None, "", [], "equity unavailable or negative")

    rev = _earnings_basis(fd, "revenue")
    if rev and rev["value"] > 0:
        item("ps", "Price/Sales", mcap / rev["value"], f"Market cap / Revenue ({rev['basis']})", [mc_in] + rev["inputs"])
    else:
        item("ps", "Price/Sales", None, "", [], "revenue unavailable")

    if fd.profile in FINANCIAL_PROFILES:
        item("ev_ebitda", "EV/EBITDA", None, "", [], "Not meaningful for financial companies")
    else:
        debt = _latest_balance(fd, "total_debt")
        cash = _latest_balance(fd, "cash_and_st_investments") or _latest_balance(fd, "cash")
        ebitda = _earnings_basis(fd, "ebitda")
        if ebitda and ebitda["value"] > 0:
            ev = mcap + (debt["value"] if debt else 0) - (cash["value"] if cash else 0)
            note = [] if debt and cash else ["debt or cash missing; treated as not reported"]
            item("ev_ebitda", "EV/EBITDA", ev / ebitda["value"],
                 f"(Market cap + Debt - Cash) / EBITDA ({ebitda['basis']})",
                 [mc_in, {"metric": "total_debt", **(debt or {"value": None})},
                  {"metric": "cash", **(cash or {"value": None})}] + ebitda["inputs"], "; ".join(note))
            out["enterprise_value"] = ev
        else:
            item("ev_ebitda", "EV/EBITDA", None, "", [], "EBITDA unavailable or negative")
    return out


def historical_multiples(fd: FinData) -> dict[str, Any]:
    """P/E and P/B at each fiscal year end.

    Uses split-adjusted closing price x current shares outstanding as historical market cap,
    because the source's price history is split-adjusted. Buybacks/issuance introduce small errors.
    """
    shares = (fd.snapshot or {}).get("shares_outstanding")
    points = []
    if not shares:
        return {"points": [], "note": "shares outstanding unavailable"}
    for p in fd.annual_periods:
        px = price_on_or_before(fd.symbol, p)
        if px is None:
            continue
        mcap = px[1] * shares
        ni, eq = fd.a("net_income", p), fd.a("total_equity", p)
        # A large change in share count (merger, split, bonus, big issuance) makes this
        # approximation unreliable for that year, so the point is shown but excluded from medians.
        then_shares = fd.a("shares_outstanding", p)
        excluded = bool(then_shares and abs(then_shares / shares - 1) > 0.15)
        points.append({
            "period": p, "price_date": px[0], "price": px[1], "market_cap": mcap,
            "pe": mcap / ni if ni and ni > 0 else None,
            "pb": mcap / eq if eq and eq > 0 else None,
            "excluded": excluded,
            "note": "share count changed >15% vs today (merger, split, bonus or issuance); excluded from median"
            if excluded else "",
        })
    pes = sorted(x["pe"] for x in points if x["pe"] and not x["excluded"])
    pbs = sorted(x["pb"] for x in points if x["pb"] and not x["excluded"])
    return {
        "points": points,
        "median_pe": _median(pes), "median_pb": _median(pbs),
        "method": "Split-adjusted close on or before fiscal year end x current shares outstanding, divided by "
                  "that year's net profit (P/E) or equity (P/B).",
    }


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def dcf(fd: FinData, growth: float | None, *, risk_free: float | None = None, erp: float | None = None,
        terminal_growth: float | None = None, beta: float | None = None, years_high: int = 5,
        years_fade: int = 5) -> dict[str, Any]:
    """Two-stage free-cash-flow-to-firm DCF. Every assumption is returned with the result."""
    if fd.profile in FINANCIAL_PROFILES:
        return {"available": False, "reason": "DCF on free cash flow is not meaningful for banks, NBFCs and insurers."}
    snap = fd.snapshot or {}
    shares = snap.get("shares_outstanding")
    series = M.compute_series(fd)
    fcfs = [p for p in series.get("free_cash_flow", []) if p["value"] is not None][-3:]
    if not fcfs or not shares:
        return {"available": False, "reason": "free cash flow history or share count unavailable"}
    base_fcf = sum(p["value"] for p in fcfs) / len(fcfs)
    if base_fcf <= 0:
        return {"available": False, "reason": "average free cash flow over the last years is not positive; "
                                              "a cash-flow DCF would not be meaningful"}
    rf = settings.dcf_risk_free if risk_free is None else risk_free
    prem = settings.dcf_equity_risk_premium if erp is None else erp
    tg = settings.dcf_terminal_growth if terminal_growth is None else terminal_growth
    raw_beta = snap.get("beta") if beta is None else beta
    b = min(max(raw_beta if raw_beta else 1.0, 0.6), 1.6)
    ke = rf + b * prem
    debt = _latest_balance(fd, "total_debt")
    cash = _latest_balance(fd, "cash_and_st_investments") or _latest_balance(fd, "cash")
    d = debt["value"] if debt else 0.0
    c = cash["value"] if cash else 0.0
    mcap = snap.get("market_cap") or 0
    # Cost of debt from one fiscal year: that year's interest over that year's debt (same period).
    kd, kd_note = rf + 0.02, "risk-free + 2% (interest or debt not reported for the same year)"
    for p in reversed(fd.annual_periods):
        ie_p, debt_p = fd.a("interest_expense", p), fd.a("total_debt", p)
        if ie_p and debt_p and debt_p > 0:
            raw_kd = abs(ie_p) / debt_p
            kd = min(max(raw_kd, 0.06), 0.14)
            kd_note = f"interest / debt for FY ending {p} = {raw_kd:.1%}" + (
                " (clamped to 6-14%)" if kd != raw_kd else "")
            break
    tax = settings.dcf_tax_rate
    weight_e = mcap / (mcap + d) if mcap + d > 0 else 1.0
    wacc = weight_e * ke + (1 - weight_e) * kd * (1 - tax)
    g1 = 0.08 if growth is None else min(max(growth, -0.05), 0.25)
    if wacc <= tg + 0.01:
        return {"available": False, "reason": "discount rate is too close to terminal growth for a stable DCF"}

    flows, fcf, pv = [], base_fcf, 0.0
    total_years = years_high + years_fade
    for t in range(1, total_years + 1):
        g = g1 if t <= years_high else g1 + (tg - g1) * (t - years_high) / years_fade
        fcf *= 1 + g
        disc = (1 + wacc) ** t
        pv += fcf / disc
        flows.append({"year": t, "growth": g, "fcf": fcf, "pv": fcf / disc})
    tv = fcf * (1 + tg) / (wacc - tg)
    pv_tv = tv / (1 + wacc) ** total_years
    ev = pv + pv_tv
    equity = ev - d + c
    per_share = equity / shares
    price = snap.get("price")

    def value_at(w: float, g_term: float) -> float | None:
        if w <= g_term + 0.005:
            return None
        f, p_sum = base_fcf, 0.0
        for t in range(1, total_years + 1):
            g = g1 if t <= years_high else g1 + (g_term - g1) * (t - years_high) / years_fade
            f *= 1 + g
            p_sum += f / (1 + w) ** t
        tvv = f * (1 + g_term) / (w - g_term) / (1 + w) ** total_years
        return (p_sum + tvv - d + c) / shares

    sensitivity = [{"wacc": w, "terminal_growth": gt, "value_per_share": value_at(w, gt)}
                   for w in (wacc - 0.01, wacc, wacc + 0.01) for gt in (tg - 0.01, tg, tg + 0.01)]
    return {
        "available": True,
        "value_per_share": per_share,
        "price": price,
        "margin_of_safety": (per_share / price - 1) if price else None,
        "enterprise_value": ev, "equity_value": equity, "pv_terminal_share": pv_tv / ev if ev else None,
        "flows": flows, "terminal_value": tv, "sensitivity": sensitivity,
        "assumptions": {
            "base_fcf": base_fcf, "base_fcf_periods": [p["period"] for p in fcfs],
            "base_fcf_method": f"average free cash flow over the last {len(fcfs)} year(s)",
            "growth_stage1": g1, "growth_source": "base-case revenue scenario (clamped to -5%..25%)"
            if growth is not None else "default 8% (no forecast available)",
            "years_high_growth": years_high, "years_fade": years_fade, "terminal_growth": tg,
            "risk_free": rf, "equity_risk_premium": prem, "beta_raw": raw_beta, "beta_used": b,
            "beta_note": "source beta is clamped to 0.6-1.6; Yahoo betas for Indian stocks are measured "
                         "against a non-Indian benchmark and are often unrealistic",
            "cost_of_equity": ke, "cost_of_debt_pre_tax": kd, "cost_of_debt_note": kd_note,
            "tax_rate": tax, "wacc": wacc,
            "net_debt_basis": f"debt and cash from the latest reported balance sheet "
                              f"({debt['period'] if debt else 'n/a'})",
            "debt": d, "cash": c, "shares": shares,
        },
        "caveat": "A DCF is highly sensitive to its assumptions. Treat the result as one reference point, "
                  "not a fair-value guarantee.",
    }
