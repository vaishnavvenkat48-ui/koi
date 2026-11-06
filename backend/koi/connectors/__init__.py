"""Data source connectors.

Registered sources are described in DATA_SOURCES. Terms notes reflect what KOI's authors could
check; they are not legal advice. Re-check each provider's current terms before relying on it.
"""

DATA_SOURCES = [
    {
        "key": "nse_equity_master",
        "name": "NSE securities available for trading (EQUITY_L.csv)",
        "url": "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
        "coverage": "Company master: NSE symbol, company name, series, listing date, ISIN.",
        "terms_note": "Public archive file on nseindia.com. NSE's website terms restrict automated and commercial "
                      "use; KOI downloads it at most once per refresh window for local personal research.",
    },
    {
        "key": "yfinance",
        "name": "Yahoo Finance via the open-source yfinance library",
        "url": "https://github.com/ranaroussi/yfinance",
        "coverage": "About 4 annual and 5 quarterly periods of income statement, balance sheet and cash flow; "
                    "daily prices; market cap, beta, sector/industry; insider and institutional holding %. "
                    "Consolidation basis is not stated by the source, so it is recorded as 'unspecified'.",
        "terms_note": "Unofficial; not affiliated with Yahoo. Yahoo's terms permit personal, non-commercial use only. "
                      "Free of charge, but not verified as licensed for redistribution. Rate-limited by KOI.",
    },
    {
        "key": "nse_xbrl",
        "name": "NSE corporate filings - financial results (XBRL)",
        "url": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results",
        "coverage": "Planned: official quarterly and annual results filed under SEBI LODR (standalone and "
                    "consolidated), longer history. Not yet implemented.",
        "terms_note": "Official filings are public, but nseindia.com endpoints require browser session cookies and "
                      "its terms restrict automated access. To be reviewed before implementation.",
    },
]
