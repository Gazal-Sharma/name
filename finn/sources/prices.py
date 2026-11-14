"""End-of-day price and volume from Yahoo Finance (pipeline only; not used at request time)."""


def eod(symbols: list[str], days: int = 400, benchmark: str = "^NSEI") -> dict:
    import yfinance as yf
    tickers = [f"{s}.NS" for s in symbols] + [benchmark]
    df = yf.download(tickers, period=f"{days}d", interval="1d", group_by="ticker",
                     auto_adjust=False, progress=False, threads=True)
    out = {}
    for sym, t in zip(symbols + ["NIFTY"], tickers):
        try:
            sub = df[t].dropna(subset=["Close"])
        except KeyError:
            continue
        if sub.empty:
            continue
        out[sym] = {
            "d": [i.strftime("%Y-%m-%d") for i in sub.index],
            "c": [round(float(x), 2) for x in sub["Close"]],
            "v": [int(x) if x == x else 0 for x in sub["Volume"]],
        }
    return out
