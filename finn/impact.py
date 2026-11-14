"""Event study: how much did the stock actually move on days a given type of filing landed?

For each filing we find the first trading session whose close (15:30 IST) comes after the
announcement, and take that day's return minus the Nifty's. Aggregated by category this
gives an evidence-based sense of which filing types have historically coincided with moves
in *this* portfolio — a prior for triage, not a causal claim (results days carry many filings)."""
import bisect, datetime as dt, statistics as st

CLOSE = dt.time(15, 30)


def returns(series: dict) -> dict:
    c = series["c"]
    return {series["d"][i]: (c[i] / c[i - 1] - 1) * 100 for i in range(1, len(c)) if c[i - 1]}


def reaction_day(days: list[str], when: dt.datetime) -> str | None:
    d = when.date() if when.time() <= CLOSE else when.date() + dt.timedelta(days=1)
    i = bisect.bisect_left(days, d.isoformat())
    return days[i] if i < len(days) else None


def abnormal(prices: dict, symbol: str, when: dt.datetime):
    """(reaction_date, stock %, abnormal % vs Nifty, volume multiple vs prior 20d) or None."""
    s = prices.get(symbol)
    if not s:
        return None
    day = reaction_day(s["d"], when)
    if not day:
        return None
    i = s["d"].index(day)
    if i < 1:
        return None
    r = (s["c"][i] / s["c"][i - 1] - 1) * 100
    nr = returns(prices["NIFTY"]).get(day, 0.0) if "NIFTY" in prices else 0.0
    prev = [v for v in s["v"][max(0, i - 20):i] if v]
    vm = s["v"][i] / (sum(prev) / len(prev)) if prev and s["v"][i] else None
    return day, round(r, 2), round(r - nr, 2), round(vm, 2) if vm else None


def study(events: list[dict], prices: dict) -> dict:
    """events: [{symbol, category, tier, ar, day}] -> stats per category, plus the no-news baseline."""
    nifty = returns(prices["NIFTY"])
    seen, by = set(), {}
    event_days = set()
    for e in events:
        if e.get("ar") is None:
            continue
        if e["tier"] <= 2:
            event_days.add((e["symbol"], e["day"]))
        k = (e["symbol"], e["day"], e["category"])
        if k in seen:
            continue
        seen.add(k)
        by.setdefault(e["category"], []).append(abs(e["ar"]))
    base = []
    for sym, s in prices.items():
        if sym == "NIFTY":
            continue
        for day, r in returns(s).items():
            if (sym, day) not in event_days and day in nifty:
                base.append(abs(r - nifty[day]))
    b = st.median(base) if base else None
    out = {"baseline": {"median_abs": round(b, 2) if b else None, "n": len(base)}, "categories": {}}
    for cat, xs in by.items():
        med = st.median(xs)
        out["categories"][cat] = {
            "n": len(xs), "median_abs": round(med, 2),
            "share_gt2": round(sum(x > 2 for x in xs) / len(xs), 2),
            "lift": round(med / b, 2) if b else None,
        }
    return out
