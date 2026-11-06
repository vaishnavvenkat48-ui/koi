"""Sector-aware scoring rules.

Each score is a weighted average of component scores. A component maps a metric linearly from
`bad` (score 0) to `good` (score 100), clipped to 0..100. `bad` may be above `good` for
"lower is better" metrics. Thresholds differ by analysis profile because a 25% operating margin
means different things for an IT company and a steel maker, and leverage means something
different for a bank.

Signals named here are produced in scoring.py (see `derived()`); all are deterministic.
"""

from __future__ import annotations

# (signal, label, bad, good, weight)
Rule = tuple[str, str, float, float, float]

DEFAULT: dict[str, list[Rule]] = {
    "quality": [
        ("roce", "Return on capital employed", 0.08, 0.25, 3),
        ("roe", "Return on equity", 0.08, 0.22, 3),
        ("operating_margin", "Operating margin", 0.05, 0.22, 2),
        ("margin_stability", "Margin stability (std. dev. of operating margin)", 0.06, 0.01, 1),
    ],
    "health": [
        ("debt_to_equity", "Debt-to-equity", 2.0, 0.2, 3),
        ("interest_coverage", "Interest coverage", 1.5, 10.0, 3),
        ("current_ratio", "Current ratio", 0.8, 2.0, 1),
        ("cash_conversion_avg", "Cash conversion (3-yr avg)", 0.5, 1.0, 2),
    ],
    "growth": [
        ("revenue_cagr", "Revenue CAGR", 0.0, 0.15, 3),
        ("net_income_cagr", "Profit CAGR", 0.0, 0.18, 3),
        ("eps_cagr", "EPS CAGR", 0.0, 0.15, 2),
        ("growth_consistency", "Share of years with revenue growth", 0.25, 1.0, 1),
    ],
    "valuation": [
        ("pe_vs_peers", "P/E relative to peer median", 1.6, 0.7, 3),
        ("pe_vs_history", "P/E relative to own history", 1.5, 0.7, 2),
        ("earnings_yield", "Earnings yield", 0.02, 0.08, 2),
        ("ev_ebitda", "EV/EBITDA", 30.0, 8.0, 1),
        ("dcf_margin_of_safety", "DCF value vs price", -0.5, 0.3, 1),
    ],
    # Risk components are "safety" scores; risk = 100 - weighted safety.
    "risk": [
        ("leverage_change", "Change in debt-to-equity", 0.5, -0.1, 2),
        ("margin_change", "Change in operating margin vs prior avg", -0.04, 0.01, 2),
        ("negative_fcf_share", "Share of years with negative FCF", 0.6, 0.0, 2),
        ("earnings_volatility", "Profit growth volatility", 0.4, 0.05, 1),
        ("accruals_avg", "Accruals ratio (3-yr avg)", 0.08, -0.02, 1),
        ("interest_coverage", "Interest coverage", 1.5, 6.0, 2),
        ("data_years", "Years of data available", 2, 5, 1),
    ],
}


def _override(base: dict[str, list[Rule]], changes: dict[str, dict[str, tuple[float, float]]],
              drop: dict[str, set[str]] | None = None, add: dict[str, list[Rule]] | None = None) -> dict[str, list[Rule]]:
    out: dict[str, list[Rule]] = {}
    for score, rules in base.items():
        new = []
        for sig, label, bad, good, w in rules:
            if drop and sig in drop.get(score, set()):
                continue
            if sig in changes.get(score, {}):
                bad, good = changes[score][sig]
            new.append((sig, label, bad, good, w))
        out[score] = new + (add or {}).get(score, [])
    return out


PROFILES: dict[str, dict[str, list[Rule]]] = {
    "default": DEFAULT,
    "manufacturing": DEFAULT,
    "pharma": _override(DEFAULT, {"quality": {"roce": (0.08, 0.25), "operating_margin": (0.08, 0.25)}}),
    "it_services": _override(DEFAULT, {
        "quality": {"roce": (0.15, 0.45), "roe": (0.12, 0.35), "operating_margin": (0.10, 0.25)},
        "health": {"debt_to_equity": (0.6, 0.05)},
        "growth": {"revenue_cagr": (0.0, 0.14), "net_income_cagr": (0.0, 0.15)},
    }),
    "fmcg": _override(DEFAULT, {
        "quality": {"roce": (0.15, 0.60), "roe": (0.12, 0.40), "operating_margin": (0.08, 0.22)},
        "growth": {"revenue_cagr": (0.0, 0.12), "net_income_cagr": (0.0, 0.14)},
        "valuation": {"pe_vs_history": (1.4, 0.8)},
    }),
    "utility": _override(DEFAULT, {
        "quality": {"roce": (0.05, 0.14), "roe": (0.07, 0.16), "operating_margin": (0.10, 0.35)},
        "health": {"debt_to_equity": (3.0, 0.8), "interest_coverage": (1.3, 5.0), "current_ratio": (0.6, 1.5)},
        "growth": {"revenue_cagr": (0.0, 0.10), "net_income_cagr": (0.0, 0.12)},
        "risk": {"interest_coverage": (1.2, 4.0)},
    }),
    "telecom": _override(DEFAULT, {
        "quality": {"roce": (0.03, 0.15), "roe": (0.0, 0.18), "operating_margin": (0.05, 0.30)},
        "health": {"debt_to_equity": (4.0, 1.0), "interest_coverage": (1.0, 5.0), "current_ratio": (0.3, 1.0)},
        "risk": {"interest_coverage": (1.0, 4.0)},
    }),
    # Lenders: leverage and margins work differently. Asset quality (GNPA/NNPA), capital adequacy and
    # NIM are the right metrics but are not provided by the current data source; they are reported
    # as unavailable rather than substituted.
    "bank": _override(
        DEFAULT,
        {"quality": {"roe": (0.08, 0.18)}, "growth": {"revenue_cagr": (0.0, 0.18), "net_income_cagr": (0.0, 0.20)},
         "valuation": {"pe_vs_history": (1.5, 0.7)}},
        drop={"quality": {"roce", "operating_margin", "margin_stability"},
              "health": {"debt_to_equity", "interest_coverage", "current_ratio", "cash_conversion_avg"},
              "valuation": {"ev_ebitda", "dcf_margin_of_safety"},
              "risk": {"leverage_change", "margin_change", "negative_fcf_share", "accruals_avg", "interest_coverage"}},
        add={"quality": [("roa", "Return on assets", 0.005, 0.018, 3)],
             "health": [("equity_to_assets", "Equity to assets", 0.06, 0.12, 3)],
             "valuation": [("pb_vs_peers", "P/B relative to peer median", 1.6, 0.7, 3),
                           ("pb", "Price to book", 4.0, 1.0, 1)],
             "risk": [("roa_change", "Change in return on assets", -0.004, 0.001, 2),
                      ("equity_to_assets", "Equity to assets", 0.06, 0.11, 2)]},
    ),
    "nbfc": _override(
        DEFAULT,
        {"quality": {"roe": (0.10, 0.20)}, "health": {"debt_to_equity": (8.0, 3.0)},
         "growth": {"revenue_cagr": (0.0, 0.20), "net_income_cagr": (0.0, 0.22)}},
        drop={"quality": {"roce", "margin_stability"}, "health": {"current_ratio", "cash_conversion_avg"},
              "valuation": {"ev_ebitda", "dcf_margin_of_safety"},
              "risk": {"negative_fcf_share", "accruals_avg"}},
        add={"quality": [("roa", "Return on assets", 0.01, 0.035, 3)],
             "health": [("equity_to_assets", "Equity to assets", 0.10, 0.25, 2)],
             "valuation": [("pb_vs_peers", "P/B relative to peer median", 1.6, 0.7, 2)]},
    ),
    "insurance": _override(
        DEFAULT,
        {"quality": {"roe": (0.08, 0.18)}, "growth": {"revenue_cagr": (0.0, 0.15), "net_income_cagr": (0.0, 0.15)}},
        drop={"quality": {"roce", "operating_margin", "margin_stability"},
              "health": {"debt_to_equity", "interest_coverage", "current_ratio", "cash_conversion_avg"},
              "valuation": {"ev_ebitda", "dcf_margin_of_safety"},
              "risk": {"leverage_change", "margin_change", "negative_fcf_share", "accruals_avg", "interest_coverage"}},
        add={"quality": [("roa", "Return on assets", 0.003, 0.02, 1)],
             "valuation": [("pb_vs_peers", "P/B relative to peer median", 1.6, 0.7, 2)]},
    ),
}

UNAVAILABLE_SECTOR_METRICS: dict[str, list[str]] = {
    "bank": ["Gross / net NPA (asset quality)", "Capital adequacy ratio (CRAR)", "Net interest margin (NIM)",
             "CASA ratio", "Provision coverage ratio"],
    "nbfc": ["Gross / net stage-3 assets", "Capital adequacy ratio", "Assets under management growth",
             "Net interest margin", "Cost of funds"],
    "insurance": ["Value of new business (VNB) and margin", "Solvency ratio", "Persistency ratios",
                  "Combined ratio (general insurers)", "Embedded value"],
}


def rules_for(profile: str) -> dict[str, list[Rule]]:
    return PROFILES.get(profile, DEFAULT)
