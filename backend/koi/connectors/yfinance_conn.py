"""Yahoo Finance connector (via yfinance) for NSE-listed companies.

Coverage limits (as observed): ~4 annual income/cash-flow periods, ~5 balance-sheet periods,
~5 quarterly periods, daily prices. The source does not state consolidation basis.
"""

from __future__ import annotations

import math
import warnings as _warnings
from datetime import date
from typing import Any

import pandas as pd

from .base import (
    CompanyProfile, FactRecord, FundamentalsBundle, MarketSnapshot, RateLimiter, SourceUnavailable,
)

# KOI metric -> ordered list of source labels (first present label wins).
METRIC_MAP: dict[str, dict[str, list[str]]] = {
    "income": {
        "revenue": ["Total Revenue", "Operating Revenue"],
        "cost_of_revenue": ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
        "gross_profit": ["Gross Profit"],
        "operating_income": ["Operating Income"],
        "ebitda": ["EBITDA", "Normalized EBITDA"],
        "ebit": ["EBIT"],
        "depreciation": ["Reconciled Depreciation", "Depreciation And Amortization In Income Statement"],
        "interest_expense": ["Interest Expense", "Interest Expense Non Operating"],
        "interest_income": ["Interest Income"],
        "net_interest_income": ["Net Interest Income"],
        "pretax_income": ["Pretax Income"],
        "tax_provision": ["Tax Provision"],
        "net_income": ["Net Income Common Stockholders", "Net Income",
                       "Net Income From Continuing Operation Net Minority Interest"],
        "eps_basic": ["Basic EPS"],
        "eps_diluted": ["Diluted EPS"],
        "diluted_shares": ["Diluted Average Shares"],
        "unusual_items": ["Total Unusual Items"],
    },
    "balance": {
        "total_assets": ["Total Assets"],
        "total_liabilities": ["Total Liabilities Net Minority Interest"],
        "total_equity": ["Stockholders Equity", "Common Stock Equity"],
        "minority_interest": ["Minority Interest"],
        "total_debt": ["Total Debt"],
        "current_assets": ["Current Assets"],
        "current_liabilities": ["Current Liabilities"],
        "cash": ["Cash And Cash Equivalents", "Cash Financial"],
        "cash_and_st_investments": ["Cash Cash Equivalents And Short Term Investments"],
        "inventory": ["Inventory"],
        "receivables": ["Accounts Receivable"],
        "payables": ["Accounts Payable", "Payables"],
        "net_ppe": ["Net PPE"],
        "goodwill_intangibles": ["Goodwill And Other Intangible Assets"],
        "invested_capital": ["Invested Capital"],
        "shares_outstanding": ["Ordinary Shares Number", "Share Issued"],
    },
    "cashflow": {
        "operating_cf": ["Operating Cash Flow"],
        "investing_cf": ["Investing Cash Flow"],
        "financing_cf": ["Financing Cash Flow"],
        "capex": ["Capital Expenditure"],
        "free_cash_flow": ["Free Cash Flow"],
        "dividends_paid": ["Cash Dividends Paid"],
        "change_in_working_capital": ["Change In Working Capital"],
    },
}

SHARE_METRICS = {"diluted_shares", "shares_outstanding"}
PER_SHARE_METRICS = {"eps_basic", "eps_diluted"}

_limiter = RateLimiter()


def yf_symbol(nse_symbol: str) -> str:
    return f"{nse_symbol}.NS"


def _clean(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _frame_to_facts(df: pd.DataFrame | None, statement: str, period_type: str, currency: str | None) -> list[FactRecord]:
    if df is None or df.empty:
        return []
    out: list[FactRecord] = []
    for col in df.columns:
        period_end = pd.Timestamp(col).date().isoformat()
        for metric, labels in METRIC_MAP[statement].items():
            for label in labels:
                if label in df.index:
                    v = _clean(df.at[label, col])
                    if v is None:
                        continue  # missing stays missing; try next label
                    unit = "shares" if metric in SHARE_METRICS else (
                        f"{currency or 'INR'}/share" if metric in PER_SHARE_METRICS else (currency or "INR"))
                    out.append(FactRecord(statement, metric, label, period_end, period_type, v, unit, currency))
                    break
    return out


class YFinanceConnector:
    key = "yfinance"

    def __init__(self) -> None:
        import yfinance  # imported lazily so the API can start without network

        # yfinance uses pandas APIs deprecated in newer pandas; the warnings are noise for KOI users.
        _warnings.filterwarnings("ignore", module=r"yfinance\..*")
        self._yf = yfinance

    def fetch(self, symbol: str, price_period: str = "10y") -> FundamentalsBundle:
        warnings: list[str] = []
        with _limiter:
            t = self._yf.Ticker(yf_symbol(symbol))
            try:
                info = t.info or {}
            except Exception as e:  # yfinance raises a variety of errors for unknown symbols / throttling
                raise SourceUnavailable(f"yfinance info failed for {symbol}: {e}") from e
        if not info or (info.get("quoteType") is None and info.get("longName") is None and info.get("shortName") is None):
            raise SourceUnavailable(f"yfinance has no record for {yf_symbol(symbol)}")

        currency = info.get("financialCurrency") or info.get("currency")
        profile = CompanyProfile(
            name=info.get("longName") or info.get("shortName"),
            sector=info.get("sector"), industry=info.get("industry"), website=info.get("website"),
            description=info.get("longBusinessSummary"), currency=currency,
        )
        snapshot = MarketSnapshot(
            price=_clean(info.get("currentPrice") or info.get("regularMarketPrice")),
            market_cap=_clean(info.get("marketCap")),
            shares_outstanding=_clean(info.get("sharesOutstanding")),
            beta=_clean(info.get("beta")),
            currency=info.get("currency"),
            held_insiders_pct=_pct(info.get("heldPercentInsiders")),
            held_institutions_pct=_pct(info.get("heldPercentInstitutions")),
        )

        facts: list[FactRecord] = []
        frames = [
            ("income_stmt", "income", "annual"), ("balance_sheet", "balance", "annual"), ("cashflow", "cashflow", "annual"),
            ("quarterly_income_stmt", "income", "quarterly"), ("quarterly_balance_sheet", "balance", "quarterly"),
            ("quarterly_cashflow", "cashflow", "quarterly"),
        ]
        for attr, statement, ptype in frames:
            with _limiter:
                try:
                    df = getattr(t, attr)
                except Exception as e:
                    warnings.append(f"{attr} unavailable: {e}")
                    continue
            facts.extend(_frame_to_facts(df, statement, ptype, currency))
        if not any(f.period_type == "annual" for f in facts):
            warnings.append("No annual financial statements returned by yfinance.")
        if currency and currency != "INR":
            # Some Indian companies (e.g. Infosys) report to Yahoo in USD while the share trades in INR.
            # Mixing the two would make every valuation ratio wrong by the exchange rate.
            facts = self._convert_to_inr(facts, currency, warnings)
            profile.currency = "INR"

        prices: list[dict[str, Any]] = []
        with _limiter:
            try:
                hist = t.history(period=price_period, interval="1d", auto_adjust=False)
            except Exception as e:
                hist = None
                warnings.append(f"price history unavailable: {e}")
        if hist is not None and not hist.empty:
            for ts, row in hist.iterrows():
                close = _clean(row.get("Close"))
                if close is None:
                    continue
                prices.append({
                    "date": pd.Timestamp(ts).date().isoformat(), "open": _clean(row.get("Open")),
                    "high": _clean(row.get("High")), "low": _clean(row.get("Low")), "close": close,
                    "volume": _clean(row.get("Volume")),
                })
        return FundamentalsBundle(profile=profile, snapshot=snapshot, facts=facts, prices=prices, warnings=warnings)

    def _convert_to_inr(self, facts: list[FactRecord], currency: str, warnings: list[str]) -> list[FactRecord]:
        """Convert money facts to INR at the exchange rate on (or just before) each period end."""
        with _limiter:
            try:
                fx = self._yf.Ticker(f"{currency}INR=X").history(period="10y", interval="1d")["Close"].dropna()
            except Exception:
                fx = None
        if fx is None or fx.empty:
            warnings.append(f"Figures are reported in {currency} and no {currency}/INR rate was available; "
                            "money figures were dropped rather than mixed with INR prices.")
            return [f for f in facts if f.unit == "shares"]
        rates = sorted((pd.Timestamp(ts).date().isoformat(), float(v)) for ts, v in fx.items())
        out: list[FactRecord] = []
        for f in facts:
            if f.unit == "shares":
                out.append(f)
                continue
            rate = None
            for day, v in reversed(rates):
                if day <= f.period_end:
                    rate = (day, v)
                    break
            if rate is None or (date.fromisoformat(f.period_end) - date.fromisoformat(rate[0])).days > 10:
                continue  # no rate near this period end: leave the value missing, never guess
            f.value *= rate[1]
            f.unit = "INR/share" if f.unit.endswith("/share") else "INR"
            f.source_label = f"{f.source_label} ({currency}→INR at {rate[1]:.2f} on {rate[0]})"
            f.currency = "INR"
            out.append(f)
        warnings.append(f"Figures were reported in {currency}; converted to INR at each period-end exchange rate.")
        return out

    def fetch_index(self, yf_sym: str) -> dict[str, Any] | None:
        with _limiter:
            try:
                hist = self._yf.Ticker(yf_sym).history(period="1y", interval="1d")
            except Exception:
                return None
        if hist is None or hist.empty:
            return None
        closes = [(pd.Timestamp(ts).date().isoformat(), float(c)) for ts, c in hist["Close"].dropna().items()]
        return {"series": closes, "as_of": closes[-1][0] if closes else date.today().isoformat()}


def _pct(v: Any) -> float | None:
    f = _clean(v)
    return None if f is None else round(f * 100, 2)
