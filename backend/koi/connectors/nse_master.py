"""NSE company master (EQUITY_L.csv): symbol, name, series, listing date, ISIN."""

from __future__ import annotations

import csv
import io

import httpx

from .base import RateLimiter, SourceUnavailable

URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
HEADERS = {
    # NSE rejects requests without a browser-like user agent.
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/130.0 Safari/537.36",
    "Accept": "text/csv,*/*",
}
_limiter = RateLimiter(3.0)


def fetch_equity_master() -> list[dict[str, str]]:
    with _limiter:
        try:
            r = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise SourceUnavailable(f"NSE equity master download failed: {e}") from e
    reader = csv.DictReader(io.StringIO(r.text))
    rows: list[dict[str, str]] = []
    for raw in reader:
        row = {k.strip(): (v or "").strip() for k, v in raw.items() if k}
        sym = row.get("SYMBOL")
        if not sym:
            continue
        rows.append({
            "symbol": sym,
            "name": row.get("NAME OF COMPANY", sym),
            "series": row.get("SERIES", ""),
            "listing_date": row.get("DATE OF LISTING", ""),
            "isin": row.get("ISIN NUMBER", ""),
        })
    if len(rows) < 100:
        raise SourceUnavailable(f"NSE equity master looked truncated ({len(rows)} rows)")
    return rows
