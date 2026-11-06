"""Evidence gating, confidence caps and API smoke tests. SYNTHETIC fixtures only; no network, no LLM."""

import os
import tempfile

os.environ.setdefault("KOI_DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ["KOI_OLLAMA_URL"] = "http://127.0.0.1:9"  # nothing listens here: forces the no-LLM path

from fastapi.testclient import TestClient  # noqa: E402

from koi import db  # noqa: E402
from koi.agent import llm  # noqa: E402
from koi.analysis import metrics as M  # noqa: E402
from koi.analysis import scoring as S  # noqa: E402
from koi.api import app  # noqa: E402

from .test_core import P, fixture  # noqa: E402


def _scores(**vals):
    return {k: {"value": vals.get(k)} for k in ("quality", "health", "growth", "valuation", "risk", "fundamentals")}


def test_missing_score_never_counts_as_a_pass():
    # Excellent quality and growth, but no health and no risk score: must not reach a positive outlook.
    out = S.classify(_scores(quality=95, growth=90, fundamentals=92), "stable")
    assert out["code"] == 3 and "health" in out["rule"]


def test_full_scores_can_reach_strong():
    out = S.classify(_scores(quality=80, health=80, growth=60, risk=20, valuation=50, fundamentals=75), "stable")
    assert out["code"] == 1 and not out["capped"]


def test_evidence_gate_caps_lenders_and_short_history():
    good = _scores(quality=80, health=80, growth=60, risk=20, valuation=50, fundamentals=75)
    assert S.classify(good, "stable", S.evidence_gate("bank", 5))["capped"] is True
    assert S.classify(good, "stable", S.evidence_gate("it_services", 3))["code"] == 3
    assert S.evidence_gate("it_services", 4) == []


def test_confidence_cannot_be_high_next_to_a_warning():
    full = {k: {"coverage": 1.0} for k in ("quality", "health", "growth", "valuation", "risk")}
    assert S.confidence(full, 5, 4, 4, {"consolidated"})["level"] == "High"
    assert S.confidence(full, 4, 4, 4, {"consolidated"})["level"] == "Medium"
    assert S.confidence(full, 5, 4, 4, {"unspecified"})["level"] == "Medium"
    assert S.confidence(full, 3, 4, 4, {"consolidated"})["level"] == "Low"


def test_cagr_requires_two_years():
    fd = fixture()
    fd.annual_periods = P[-2:]
    assert M.cagr(fd, "revenue")["value"] is None
    assert M.cagr(fixture(), "revenue")["label"].endswith("year CAGR")


def test_llm_unavailable_degrades_cleanly():
    st = llm.status()
    assert st["available"] is False
    assert llm.narrate({"x": 1}, "beginner")["ok"] is False


# ------------------------------------------------------------------ API


def _seed(symbol: str = "SYNTH") -> None:
    fd = fixture()
    ts = db.now_iso()
    db.init_db()
    with db.tx() as conn:
        conn.execute("INSERT OR REPLACE INTO companies (symbol, name, profile, master_source, master_updated_at, "
                     "info_updated_at) VALUES (?,?,?,?,?,?)",
                     (symbol, "Synthetic Test Co", "manufacturing", "test_fixture", ts, ts))
        statements = {"revenue": "income", "net_income": "income", "ebit": "income", "ebitda": "income",
                      "interest_expense": "income", "operating_cf": "cashflow", "capex": "cashflow"}
        for metric, vals in fd.annual.items():
            for period, value in vals.items():
                db.upsert_fact(conn, {"symbol": symbol, "statement": statements.get(metric, "balance"),
                                      "metric": metric, "period_end": period, "period_type": "annual",
                                      "consolidation": "unspecified", "value": value, "unit": "INR",
                                      "source": "test_fixture", "retrieved_at": ts})
        conn.execute("INSERT OR REPLACE INTO market_snapshot (symbol, price, market_cap, shares_outstanding, beta, "
                     "currency, as_of, source) VALUES (?,?,?,?,?,?,?,?)",
                     (symbol, 100.0, 2e11, 2e9, 1.0, "INR", ts, "test_fixture"))


client = TestClient(app)  # lifespan not entered: no worker thread, no network


def test_analysis_report_dcf_financials_endpoints():
    _seed()
    a = client.get("/api/companies/SYNTH/analysis").json()
    assert a["ready"] is True
    assert a["outlook"]["plain_label"] and a["summary"]["headline"]
    assert a["confidence"]["level"] != "High"  # 4 years + unspecified consolidation
    # Second call is served from cache and is identical.
    assert client.get("/api/companies/SYNTH/analysis").json()["outlook"] == a["outlook"]

    for mode in ("beginner", "intermediate", "advanced"):
        r = client.get(f"/api/companies/SYNTH/report?mode={mode}&llm_narrative=true").json()
        assert r["ready"] and len(r["sections"]) == 15
        assert r["narrative"]["ok"] is False  # no Ollama: deterministic report still complete
        assert ("trace" in r) == (mode == "advanced")

    d = client.post("/api/companies/SYNTH/dcf", json={"terminal_growth": 0.04}).json()
    assert d["available"] and d["assumptions"]["terminal_growth"] == 0.04

    f = client.get("/api/companies/SYNTH/financials?period=annual").json()
    assert f["periods"] == P and "income" in f["statements"]


def test_input_validation():
    assert client.get("/api/companies/bad%20sym!/analysis").status_code == 422
    assert client.get("/api/companies/SYNTH/report?mode=expert").status_code == 422
    assert client.post("/api/companies/SYNTH/dcf", json={"beta": 50}).status_code == 422
