"""Portfolio and demo configuration. The engine itself takes any NSE symbol;
this file only decides what gets precomputed for the demo."""

PORTFOLIO = [
    # symbol, sector
    ("INFY", "IT"), ("HCLTECH", "IT"), ("PERSISTENT", "IT"),
    ("HDFCBANK", "Financials"), ("ICICIBANK", "Financials"), ("BAJFINANCE", "Financials"), ("CDSL", "Financials"),
    ("TITAN", "Consumer"), ("TRENT", "Consumer"), ("ETERNAL", "Consumer"),
    ("LT", "Industrials"), ("POLYCAB", "Industrials"), ("DIXON", "Industrials"),
    ("RELIANCE", "Energy"), ("BHARTIARTL", "Telecom"), ("SUNPHARMA", "Pharma"),
    ("MARUTI", "Auto"), ("INDIGO", "Aviation"),
]
# Research demo set: precomputed so the demo is instant. Anything else runs live.
RESEARCH_DEMO = ["INFY", "POLYCAB", "DIXON", "KPITTECH", "ASIANPAINT", "TATAPOWER", "DMART"]

BENCHMARK = "^NSEI"
PRICE_HISTORY_DAYS = 400      # calendar days of EOD history kept
FILING_HISTORY_DAYS = 365     # filings kept for the impact study
FEED_DAYS = 120               # filings shipped to the app

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
