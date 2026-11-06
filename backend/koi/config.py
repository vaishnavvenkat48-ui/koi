"""Runtime configuration, read from environment variables (see ../.env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR.parent / ".env")
load_dotenv(BACKEND_DIR / ".env")


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path(os.getenv("KOI_DB_PATH", str(BACKEND_DIR / "data" / "koi.db")))
    # Ollama is optional. Deterministic analysis works without it.
    ollama_url: str = os.getenv("KOI_OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("KOI_OLLAMA_MODEL", "llama3.1:8b")
    ollama_timeout_s: float = _float("KOI_OLLAMA_TIMEOUT_S", 90.0)
    # Freshness windows (hours) before data is considered stale.
    fundamentals_ttl_h: float = _float("KOI_FUNDAMENTALS_TTL_H", 24 * 7)
    price_ttl_h: float = _float("KOI_PRICE_TTL_H", 6)
    company_master_ttl_h: float = _float("KOI_COMPANY_MASTER_TTL_H", 24 * 7)
    # Minimum seconds between requests to any single external source.
    source_min_interval_s: float = _float("KOI_SOURCE_MIN_INTERVAL_S", 1.5)
    cors_origins: tuple[str, ...] = tuple(
        o.strip() for o in os.getenv("KOI_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()
    )
    # DCF defaults (all user-overridable per request). These are assumptions, not data.
    dcf_risk_free: float = _float("KOI_DCF_RISK_FREE", 0.07)
    dcf_equity_risk_premium: float = _float("KOI_DCF_ERP", 0.06)
    dcf_terminal_growth: float = _float("KOI_DCF_TERMINAL_GROWTH", 0.05)
    dcf_tax_rate: float = _float("KOI_DCF_TAX_RATE", 0.25)


settings = Settings()
