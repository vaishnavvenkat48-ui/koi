"""Transparent scenario forecasting with backtesting against simple baselines.

Models (all fitted only on past values):
  naive  - next value equals the last value (baseline)
  drift  - last value compounded at the historical CAGR of the fitting window
  trend  - log-linear least-squares trend
Backtest: rolling-origin one-step-ahead forecasts; mean absolute percentage error (MAPE) per model.
The base case uses the model with the lowest backtest error; ties go to the simpler model.
Bear and bull cases shift the base growth by one standard deviation of historical log growth.
"""

from __future__ import annotations

import math
import statistics
from typing import Any

from . import metrics as M
from .data import FinData

HORIZON = 3
MIN_SIGMA = 0.03


def _log_growths(vals: list[float]) -> list[float]:
    return [math.log(b / a) for a, b in zip(vals, vals[1:]) if a > 0 and b > 0]


def _model_growth(name: str, vals: list[float]) -> float | None:
    """Annual growth rate implied by a model fitted to vals."""
    if name == "naive":
        return 0.0
    if any(v <= 0 for v in vals) or len(vals) < 2:
        return None
    if name == "drift":
        return (vals[-1] / vals[0]) ** (1 / (len(vals) - 1)) - 1
    if name == "trend":
        n = len(vals)
        xs = list(range(n))
        ys = [math.log(v) for v in vals]
        mx, my = sum(xs) / n, sum(ys) / n
        den = sum((x - mx) ** 2 for x in xs)
        if den == 0:
            return None
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
        return math.exp(slope) - 1
    return None


MODELS = ["naive", "drift", "trend"]


def backtest(vals: list[float]) -> dict[str, Any]:
    results: dict[str, list[float]] = {m: [] for m in MODELS}
    tests = []
    for k in range(2, len(vals)):
        train, actual = vals[:k], vals[k]
        row = {"origin_index": k - 1, "actual": actual}
        for m in MODELS:
            g = _model_growth(m, train)
            if g is None or actual == 0:
                continue
            pred = train[-1] * (1 + g)
            results[m].append(abs(pred - actual) / abs(actual))
            row[m] = pred
        tests.append(row)
    mape = {m: (sum(e) / len(e) if e else None) for m, e in results.items()}
    return {"mape": mape, "tests": tests, "n_tests": len(tests)}


def forecast_metric(periods: list[str], vals: list[float], label: str) -> dict[str, Any]:
    if len(vals) < 3 or any(v <= 0 for v in vals):
        return {"label": label, "available": False,
                "reason": "needs at least three positive annual values" if len(vals) < 3 else
                          "history contains zero or negative values; growth models not meaningful",
                "history": [{"period": p, "value": v} for p, v in zip(periods, vals)]}
    bt = backtest(vals)
    # Round errors so float noise cannot break ties in favour of a more complex model.
    ranked = sorted((round(e, 6), MODELS.index(m), m) for m, e in bt["mape"].items() if e is not None)
    best = ranked[0][2] if ranked else "drift"
    g_base = _model_growth(best, vals) or 0.0
    lg = _log_growths(vals)
    sigma = max(statistics.pstdev(lg) if len(lg) >= 2 else MIN_SIGMA, MIN_SIGMA)
    scenarios: dict[str, Any] = {}
    last = vals[-1]
    for name, g in (("bear", g_base - sigma), ("base", g_base), ("bull", g_base + sigma)):
        g = min(max(g, -0.30), 0.40)
        scenarios[name] = {"growth": g, "path": [last * (1 + g) ** h for h in range(1, HORIZON + 1)]}
    band = [{"h": h, "low": last * (1 + g_base) ** h * math.exp(-sigma * math.sqrt(h)),
             "high": last * (1 + g_base) ** h * math.exp(sigma * math.sqrt(h))} for h in range(1, HORIZON + 1)]
    naive_err = bt["mape"].get("naive")
    best_err = bt["mape"].get(best)
    return {
        "label": label, "available": True, "history": [{"period": p, "value": v} for p, v in zip(periods, vals)],
        "model": best, "backtest": bt, "beats_naive": (best_err is not None and naive_err is not None
                                                       and best_err < naive_err),
        "sigma": sigma, "scenarios": scenarios, "band_68pct": band,
        "assumptions": {
            "base": f"{best} model selected by lowest one-step backtest error ({bt['n_tests']} test(s))",
            "bear_bull": "base growth -/+ one standard deviation of historical annual log growth "
                         f"({sigma:.1%}); clamped to -30%..+40%",
        },
        "reliability": "illustrative" if bt["n_tests"] < 3 else "low" if bt["n_tests"] < 5 else "moderate",
        "reliability_note": (f"Only {bt['n_tests']} backtest point(s): treat model selection as illustrative, "
                             "not as evidence that the model forecasts well.") if bt["n_tests"] < 3 else "",
    }


def forecast(fd: FinData, series: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    def hist(metric: str) -> tuple[list[str], list[float]]:
        pts = [(p, fd.a(metric, p)) for p in fd.annual_periods if fd.a(metric, p) is not None]
        return [p for p, _ in pts], [v for _, v in pts]

    rev_p, rev_v = hist("revenue")
    ni_p, ni_v = hist("net_income")
    revenue = forecast_metric(rev_p, rev_v, "Revenue")
    earnings_direct = forecast_metric(ni_p, ni_v, "Net profit (direct model)")

    # Earnings scenarios = revenue scenario x margin scenario (bear: lowest historical margin, etc.).
    margins = M.values(series.get("net_margin", []))
    earnings: dict[str, Any] = {"available": False, "reason": "revenue forecast or margin history unavailable"}
    if revenue.get("available") and margins:
        m = {"bear": min(margins), "base": sum(margins[-3:]) / len(margins[-3:]), "bull": max(margins)}
        earnings = {"available": True, "margins": m, "scenarios": {
            k: {"margin": m[k], "path": [r * m[k] for r in revenue["scenarios"][k]["path"]]} for k in m},
            "assumptions": {"bear": "lowest historical net margin", "base": "average net margin of last 3 years",
                            "bull": "highest historical net margin"}}

    conv = M.values(series.get("cash_conversion", []))
    cash_flow: dict[str, Any] = {"available": False, "reason": "cash conversion history unavailable"}
    if earnings.get("available") and conv:
        avg_conv = sum(conv[-3:]) / len(conv[-3:])
        cash_flow = {"available": True, "conversion": avg_conv,
                     "scenarios": {k: {"path": [e * avg_conv for e in v["path"]]} for k, v in earnings["scenarios"].items()},
                     "assumptions": {"all": f"operating cash flow = earnings x 3-year average cash conversion ({avg_conv:.2f}x)"}}

    leverage: dict[str, Any] = {"available": False, "reason": "debt, equity or payout history unavailable"}
    p_last = fd.annual_periods[-1] if fd.annual_periods else None
    debt, equity = fd.a("total_debt", p_last), fd.a("total_equity", p_last)
    if earnings.get("available") and debt is not None and equity and equity > 0:
        payouts = []
        for p in fd.annual_periods:
            ni, div = fd.a("net_income", p), fd.a("dividends_paid", p)
            if ni and ni > 0 and div is not None:
                payouts.append(min(abs(div) / ni, 1.5))
        payout = sum(payouts[-3:]) / len(payouts[-3:]) if payouts else 0.3
        sc = {}
        for k, v in earnings["scenarios"].items():
            eq, path = equity, []
            for e in v["path"]:
                eq += e * (1 - payout)
                path.append(debt / eq if eq > 0 else None)
            sc[k] = {"path": path}
        leverage = {"available": True, "scenarios": sc, "start": debt / equity,
                    "assumptions": {"debt": "held flat at latest reported level",
                                    "equity": f"grows by retained earnings (payout ratio {payout:.0%}"
                                              f"{'' if payouts else ' assumed'})"}}
    return {
        "horizon_years": HORIZON,
        "revenue": revenue, "earnings_direct": earnings_direct, "earnings": earnings,
        "cash_flow": cash_flow, "leverage": leverage,
        "disclaimer": "Scenarios extrapolate a short history with simple models. They are not predictions; "
                      "past growth does not guarantee future growth.",
    }
