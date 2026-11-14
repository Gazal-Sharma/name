"""NSE corporate announcements. The API needs browser-like headers and a cookie
from a normal page visit first; one session is reused across symbols."""
import datetime as dt
import time
import requests
from ..config import UA

_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
_API = "https://www.nseindia.com/api/corporate-announcements"
_H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
      "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"}
KEEP = ("symbol", "sm_name", "desc", "an_dt", "attchmntFile", "attchmntText", "voiceSummary", "seq_id", "fileSize")


class NSE:
    def __init__(self):
        self.s = None

    def _session(self, fresh=False):
        if self.s is None or fresh:
            self.s = requests.Session()
            self.s.get(_PAGE, headers=_H, timeout=20)
        return self.s

    def announcements(self, symbol: str, days: int = 30, to: dt.date | None = None) -> list[dict]:
        """Filings for one symbol, newest first. Long ranges are fetched in 90-day chunks."""
        to = to or dt.date.today()
        out, seen = [], set()
        end = to
        start_all = to - dt.timedelta(days=days)
        while end > start_all:
            start = max(start_all, end - dt.timedelta(days=90))
            rows = self._get(symbol, start, end)
            for r in rows:
                key = r.get("seq_id") or (r.get("an_dt"), r.get("attchmntFile"))
                if key in seen:
                    continue
                seen.add(key)
                out.append({k: r.get(k) for k in KEEP})
            end = start - dt.timedelta(days=1)
        return out

    def _get(self, symbol, start, end):
        params = {"index": "equities", "symbol": symbol,
                  "from_date": start.strftime("%d-%m-%Y"), "to_date": end.strftime("%d-%m-%Y")}
        last = None
        for attempt in range(3):
            try:
                r = self._session(fresh=attempt > 0).get(_API, params=params, headers={**_H, "Referer": _PAGE}, timeout=30)
                if r.status_code == 200:
                    j = r.json()
                    return j if isinstance(j, list) else []
                last = f"HTTP {r.status_code}"
            except Exception as e:  # network / JSON errors: retry with a fresh cookie
                last = repr(e)[:120]
            time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"NSE announcements failed for {symbol}: {last}")
