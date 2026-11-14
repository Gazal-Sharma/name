"""Stage 1: fetch raw data (no LLM). Prices, filings, screener fundamentals."""
import json, pathlib, sys, time, datetime as dt, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from finn import config
from finn.sources import screener, prices
from finn.sources.nse import NSE

RAW = pathlib.Path("data/raw"); (RAW / "filings").mkdir(parents=True, exist_ok=True); (RAW / "screener").mkdir(exist_ok=True)
status = {"ran_at": dt.datetime.utcnow().isoformat() + "Z", "errors": []}
port = [s for s, _ in config.PORTFOLIO]
allsyms = port + [s for s in config.RESEARCH_DEMO if s not in port]

try:
    p = prices.eod(port, config.PRICE_HISTORY_DAYS, config.BENCHMARK)
    (RAW / "prices.json").write_text(json.dumps(p, separators=(",", ":")))
    status["prices"] = {k: [len(v["d"]), v["d"][-1]] for k, v in p.items()}
except Exception as e:
    status["errors"].append(f"prices: {e!r}")

nse = NSE(); descs = collections.Counter()
for s in port:
    try:
        rows = nse.announcements(s, config.FILING_HISTORY_DAYS)
        (RAW / "filings" / f"{s}.json").write_text(json.dumps(rows, indent=0))
        status.setdefault("filings", {})[s] = len(rows)
        descs.update(r["desc"] for r in rows)
    except Exception as e:
        status["errors"].append(f"filings {s}: {e!r}")
    time.sleep(0.6)
status["desc_counts"] = dict(descs.most_common())

for s in allsyms:
    try:
        d = screener.get(s)
        (RAW / "screener" / f"{s}.json").write_text(json.dumps(d, separators=(",", ":")))
        status.setdefault("screener", {})[s] = [d["name"], d["quarters"]["periods"][-1], len(d["documents"]["concalls"])]
    except Exception as e:
        status["errors"].append(f"screener {s}: {e!r}")
    time.sleep(1.2)

(RAW / "status.json").write_text(json.dumps(status, indent=1))
print(json.dumps(status, indent=1)[:3000])
