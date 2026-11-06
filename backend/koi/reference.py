"""Curated reference data: sector groups, analysis profiles and peer lists.

This is classification data, NOT financial data. It seeds sector discovery and peer
identification. Every symbol is validated against the live data source at ingestion time;
symbols that no longer resolve (renames, delistings) are reported as unavailable, not hidden.
Companies outside these groups get sector/industry from the data source and peers by industry match.
"""

from __future__ import annotations

# profile -> how the analysis engine treats the company (see analysis/sector_rules.py)
SECTOR_GROUPS: list[dict] = [
    {"key": "it_services", "name": "IT Services", "profile": "it_services",
     "description": "Software services, consulting and outsourcing.",
     "symbols": ["TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM", "PERSISTENT", "COFORGE", "MPHASIS"]},
    {"key": "private_banks", "name": "Private Banks", "profile": "bank",
     "description": "Private-sector scheduled commercial banks.",
     "symbols": ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "INDUSINDBK", "IDFCFIRSTB", "FEDERALBNK"]},
    {"key": "psu_banks", "name": "Public Sector Banks", "profile": "bank",
     "description": "Government-owned scheduled commercial banks.",
     "symbols": ["SBIN", "BANKBARODA", "PNB", "CANBK", "UNIONBANK"]},
    {"key": "nbfc", "name": "NBFCs & Financial Services", "profile": "nbfc",
     "description": "Non-bank lenders and financial services holding companies.",
     "symbols": ["BAJFINANCE", "BAJAJFINSV", "SHRIRAMFIN", "CHOLAFIN", "MUTHOOTFIN", "M&MFIN"]},
    {"key": "insurance", "name": "Insurance", "profile": "insurance",
     "description": "Life and general insurers.",
     "symbols": ["LICI", "SBILIFE", "HDFCLIFE", "ICICIPRULI", "ICICIGI"]},
    {"key": "fmcg", "name": "FMCG", "profile": "fmcg",
     "description": "Fast-moving consumer goods.",
     "symbols": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "TATACONSUM", "DABUR", "GODREJCP", "MARICO", "COLPAL"]},
    {"key": "automobiles", "name": "Automobiles", "profile": "manufacturing",
     "description": "Passenger vehicles, two-wheelers and commercial vehicles.",
     "symbols": ["MARUTI", "M&M", "BAJAJ-AUTO", "EICHERMOT", "TVSMOTOR", "HEROMOTOCO", "ASHOKLEY"]},
    {"key": "pharma", "name": "Pharmaceuticals", "profile": "pharma",
     "description": "Branded generics, generics exports and APIs.",
     "symbols": ["SUNPHARMA", "DIVISLAB", "CIPLA", "DRREDDY", "TORNTPHARM", "LUPIN", "ZYDUSLIFE", "AUROPHARMA"]},
    {"key": "cement", "name": "Cement", "profile": "manufacturing",
     "description": "Cement and building materials.",
     "symbols": ["ULTRACEMCO", "SHREECEM", "AMBUJACEM", "ACC", "DALBHARAT", "JKCEMENT"]},
    {"key": "metals", "name": "Metals & Mining", "profile": "manufacturing",
     "description": "Steel, aluminium, zinc and mining.",
     "symbols": ["JSWSTEEL", "TATASTEEL", "HINDALCO", "VEDL", "JINDALSTEL", "SAIL", "NMDC"]},
    {"key": "oil_gas", "name": "Oil, Gas & Energy", "profile": "manufacturing",
     "description": "Refining, exploration and gas distribution.",
     "symbols": ["RELIANCE", "ONGC", "IOC", "BPCL", "HINDPETRO", "GAIL"]},
    {"key": "power", "name": "Power & Utilities", "profile": "utility",
     "description": "Power generation, transmission and distribution.",
     "symbols": ["NTPC", "POWERGRID", "TATAPOWER", "ADANIPOWER", "JSWENERGY", "NHPC"]},
    {"key": "telecom", "name": "Telecom", "profile": "telecom",
     "description": "Telecom services and infrastructure.",
     "symbols": ["BHARTIARTL", "INDUSTOWER", "IDEA"]},
    {"key": "paints", "name": "Paints & Chemicals", "profile": "manufacturing",
     "description": "Decorative paints and speciality chemicals.",
     "symbols": ["ASIANPAINT", "PIDILITIND", "BERGEPAINT", "KANSAINER", "SRF"]},
    {"key": "capital_goods", "name": "Capital Goods & Engineering", "profile": "manufacturing",
     "description": "Engineering, construction and electrical equipment.",
     "symbols": ["LT", "SIEMENS", "ABB", "BHEL", "CUMMINSIND", "BEL", "HAL"]},
    {"key": "consumer_durables", "name": "Consumer Durables & Retail", "profile": "manufacturing",
     "description": "Jewellery, appliances, electricals and retail.",
     "symbols": ["TITAN", "TRENT", "DMART", "HAVELLS", "VOLTAS", "DIXON", "CROMPTON"]},
]

# Names used only until the official company master is downloaded.
SEED_NAMES: dict[str, str] = {
    "TCS": "Tata Consultancy Services", "INFY": "Infosys", "HCLTECH": "HCL Technologies", "WIPRO": "Wipro",
    "TECHM": "Tech Mahindra", "LTIM": "LTIMindtree", "PERSISTENT": "Persistent Systems", "COFORGE": "Coforge",
    "MPHASIS": "Mphasis", "HDFCBANK": "HDFC Bank", "ICICIBANK": "ICICI Bank", "KOTAKBANK": "Kotak Mahindra Bank",
    "AXISBANK": "Axis Bank", "INDUSINDBK": "IndusInd Bank", "IDFCFIRSTB": "IDFC First Bank",
    "FEDERALBNK": "Federal Bank", "SBIN": "State Bank of India", "BANKBARODA": "Bank of Baroda",
    "PNB": "Punjab National Bank", "CANBK": "Canara Bank", "UNIONBANK": "Union Bank of India",
    "BAJFINANCE": "Bajaj Finance", "BAJAJFINSV": "Bajaj Finserv", "SHRIRAMFIN": "Shriram Finance",
    "CHOLAFIN": "Cholamandalam Investment and Finance", "MUTHOOTFIN": "Muthoot Finance",
    "M&MFIN": "Mahindra & Mahindra Financial Services", "LICI": "Life Insurance Corporation of India",
    "SBILIFE": "SBI Life Insurance", "HDFCLIFE": "HDFC Life Insurance", "ICICIPRULI": "ICICI Prudential Life Insurance",
    "ICICIGI": "ICICI Lombard General Insurance", "HINDUNILVR": "Hindustan Unilever", "ITC": "ITC",
    "NESTLEIND": "Nestle India", "BRITANNIA": "Britannia Industries", "TATACONSUM": "Tata Consumer Products",
    "DABUR": "Dabur India", "GODREJCP": "Godrej Consumer Products", "MARICO": "Marico",
    "COLPAL": "Colgate-Palmolive (India)", "MARUTI": "Maruti Suzuki India", "M&M": "Mahindra & Mahindra",
    "BAJAJ-AUTO": "Bajaj Auto", "EICHERMOT": "Eicher Motors", "TVSMOTOR": "TVS Motor Company",
    "HEROMOTOCO": "Hero MotoCorp", "ASHOKLEY": "Ashok Leyland", "SUNPHARMA": "Sun Pharmaceutical Industries",
    "DIVISLAB": "Divi's Laboratories", "CIPLA": "Cipla", "DRREDDY": "Dr. Reddy's Laboratories",
    "TORNTPHARM": "Torrent Pharmaceuticals", "LUPIN": "Lupin", "ZYDUSLIFE": "Zydus Lifesciences",
    "AUROPHARMA": "Aurobindo Pharma", "ULTRACEMCO": "UltraTech Cement", "SHREECEM": "Shree Cement",
    "AMBUJACEM": "Ambuja Cements", "ACC": "ACC", "DALBHARAT": "Dalmia Bharat", "JKCEMENT": "JK Cement",
    "JSWSTEEL": "JSW Steel", "TATASTEEL": "Tata Steel", "HINDALCO": "Hindalco Industries", "VEDL": "Vedanta",
    "JINDALSTEL": "Jindal Steel & Power", "SAIL": "Steel Authority of India", "NMDC": "NMDC",
    "RELIANCE": "Reliance Industries", "ONGC": "Oil & Natural Gas Corporation", "IOC": "Indian Oil Corporation",
    "BPCL": "Bharat Petroleum Corporation", "HINDPETRO": "Hindustan Petroleum Corporation", "GAIL": "GAIL (India)",
    "NTPC": "NTPC", "POWERGRID": "Power Grid Corporation of India", "TATAPOWER": "Tata Power",
    "ADANIPOWER": "Adani Power", "JSWENERGY": "JSW Energy", "NHPC": "NHPC", "BHARTIARTL": "Bharti Airtel",
    "INDUSTOWER": "Indus Towers", "IDEA": "Vodafone Idea", "ASIANPAINT": "Asian Paints",
    "PIDILITIND": "Pidilite Industries", "BERGEPAINT": "Berger Paints India", "KANSAINER": "Kansai Nerolac Paints",
    "SRF": "SRF", "LT": "Larsen & Toubro", "SIEMENS": "Siemens", "ABB": "ABB India", "BHEL": "Bharat Heavy Electricals",
    "CUMMINSIND": "Cummins India", "BEL": "Bharat Electronics", "HAL": "Hindustan Aeronautics", "TITAN": "Titan Company",
    "TRENT": "Trent", "DMART": "Avenue Supermarts", "HAVELLS": "Havells India", "VOLTAS": "Voltas",
    "DIXON": "Dixon Technologies (India)", "CROMPTON": "Crompton Greaves Consumer Electricals",
}

POPULAR = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC", "BHARTIARTL",
           "LT", "SBIN", "BAJFINANCE", "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO"]

MARKET_INDICES = [
    {"key": "NIFTY50", "name": "NIFTY 50", "yf_symbol": "^NSEI"},
    {"key": "SENSEX", "name": "S&P BSE SENSEX", "yf_symbol": "^BSESN"},
    {"key": "NIFTYBANK", "name": "NIFTY Bank", "yf_symbol": "^NSEBANK"},
    {"key": "NIFTYIT", "name": "NIFTY IT", "yf_symbol": "^CNXIT"},
]

# Map data-source sector/industry text to an analysis profile for companies outside curated groups.
INDUSTRY_PROFILE_HINTS: list[tuple[str, str]] = [
    ("banks", "bank"), ("bank", "bank"),
    ("credit services", "nbfc"), ("financial", "nbfc"), ("capital markets", "nbfc"), ("mortgage", "nbfc"),
    ("insurance", "insurance"),
    ("information technology", "it_services"), ("software", "it_services"),
    ("drug", "pharma"), ("pharma", "pharma"), ("biotech", "pharma"),
    ("utilities", "utility"), ("telecom", "telecom"),
    ("household", "fmcg"), ("packaged foods", "fmcg"), ("tobacco", "fmcg"), ("beverages", "fmcg"),
    ("personal products", "fmcg"), ("confectioners", "fmcg"),
]


def profile_for_industry(sector: str | None, industry: str | None) -> str:
    text = f"{industry or ''} {sector or ''}".lower()
    for hint, profile in INDUSTRY_PROFILE_HINTS:
        if hint in text:
            return profile
    return "manufacturing" if text.strip() else "default"


def group_for_symbol(symbol: str) -> dict | None:
    for g in SECTOR_GROUPS:
        if symbol in g["symbols"]:
            return g
    return None
