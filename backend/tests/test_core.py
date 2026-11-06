"""Unit tests for deterministic analysis. Uses SYNTHETIC test fixtures (not real company data)."""

import os
import tempfile

os.environ["KOI_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

import pytest  # noqa: E402

from koi import db  # noqa: E402
from koi.agent import llm  # noqa: E402
from koi.analysis import forecast as F  # noqa: E402
from koi.analysis import metrics as M  # noqa: E402
from koi.analysis import scoring as S  # noqa: E402
from koi.analysis.data import FinData  # noqa: E402

P = ["2022-03-31", "2023-03-31", "2024-03-31", "2025-03-31"]


def fixture(profile: str = "manufacturing") -> FinData:
    fd = FinData(symbol="TESTCO", company={"symbol": "TESTCO", "name": "Synthetic Test Co"}, profile=profile)
    data = {
        "revenue": [100, 110, 121, 133.1],
        "net_income": [10, 11, 12, 14],
        "ebit": [15, 16.5, 18, 20],
        "ebitda": [20, 22, 24, 26],
        "total_equity": [50, 58, 66, 75],
        "total_assets": [120, 130, 140, 150],
        "current_liabilities": [20, 22, 24, 26],
        "total_debt": [10, 10, 12, 30],
        "operating_cf": [12, 12, 13, 15],
        "capex": [-4, -4, -5, -6],
        "interest_expense": [1, 1, 1.2, 2.5],
    }
    for m, vals in data.items():
        fd.annual[m] = dict(zip(P, [v * 1e9 for v in vals]))
        fd.provenance[m] = {"unit": "INR", "source": "test_fixture"}
    fd.annual_periods = P
    fd.consolidation = {"unspecified"}
    return fd


def test_growth_and_cagr():
    fd = fixture()
    s = M.compute_series(fd)
    assert s["revenue_growth"][0]["value"] is None  # first year has no prior
    assert s["revenue_growth"][1]["value"] == pytest.approx(0.10)
    c = M.cagr(fd, "revenue")
    assert c["value"] == pytest.approx(0.10, abs=0.002)


def test_ratios_use_average_balances_and_trace_inputs():
    fd = fixture()
    s = M.compute_series(fd)
    roe = s["roe"][1]
    assert roe["value"] == pytest.approx(11 / ((50 + 58) / 2))
    assert {i["metric"] for i in roe["inputs"]} == {"net_income", "total_equity"}
    fcf = s["free_cash_flow"][3]["value"]
    assert fcf == pytest.approx(9e9)


def test_missing_data_is_unavailable_not_zero():
    fd = fixture()
    del fd.annual["interest_expense"]
    h = M.headline(fd, M.compute_series(fd))
    assert h["interest_coverage"]["available"] is False
    assert "value" not in h["interest_coverage"]


def test_bank_profile_excludes_non_applicable_metrics():
    fd = fixture("bank")
    h = M.headline(fd, M.compute_series(fd))
    assert h["debt_to_equity"]["applicable"] is False
    assert h["roe"]["available"] is True


def test_scoring_and_classification_are_deterministic():
    fd = fixture()
    s = M.compute_series(fd)
    ctx = {"fd": fd, "headline": M.headline(fd, s), "series": s, "valuation": {}, "historical": {},
           "peer_medians": {}, "dcf": None}
    a, b = S.score_all(ctx), S.score_all(ctx)
    assert a["scores"]["quality"]["value"] == b["scores"]["quality"]["value"]
    assert a["scores"]["valuation"]["value"] is None  # no valuation data -> unavailable, not guessed
    out = S.classify(a["scores"], "stable")
    assert out["code"] in S.OUTLOOKS and out["valuation_verdict"] == "unavailable"


def test_forecast_backtest_prefers_accurate_model():
    vals = [100.0, 110.0, 121.0, 133.1, 146.41]
    bt = F.backtest(vals)
    assert bt["mape"]["drift"] < bt["mape"]["naive"]
    res = F.forecast_metric(P + ["2026-03-31"], vals, "Revenue")
    assert res["available"] and res["scenarios"]["bear"]["growth"] < res["scenarios"]["bull"]["growth"]


def test_forecast_refuses_negative_history():
    assert F.forecast_metric(P[:3], [10.0, -5.0, 8.0], "x")["available"] is False


def test_llm_number_validation_rejects_invented_figures():
    facts = {"roe": "24.5%", "pe": 18.2, "periods": ["2025"]}
    assert llm.validate_numbers("ROE is 24.5% and P/E 18.2 in 2025.", facts) == []
    assert llm.validate_numbers("Revenue will reach 9,999 crore.", facts) == ["9,999"]


def test_restatement_creates_revision():
    base = {"symbol": "TESTCO", "statement": "income", "metric": "revenue", "period_end": "2025-03-31",
            "period_type": "annual", "consolidation": "unspecified", "value": 100.0, "unit": "INR",
            "source": "test_fixture", "retrieved_at": db.now_iso()}
    with db.tx() as conn:
        assert db.upsert_fact(conn, base) == "inserted"
        assert db.upsert_fact(conn, base) == "unchanged"
        assert db.upsert_fact(conn, {**base, "value": 105.0}) == "revised"
    row = db.query_one("SELECT value, revision FROM financial_facts WHERE symbol='TESTCO'")
    assert row == {"value": 105.0, "revision": 1}
    assert db.query_one("SELECT old_value FROM financial_fact_revisions")["old_value"] == 100.0
