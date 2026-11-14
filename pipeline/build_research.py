"""Stage 3: precompute the Promise Ledger for the demo set, so those open instantly.
Any other ticker runs the same code live through /api."""
import datetime as dt, json, os, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from finn import config, llm, research

RAW, OUT = pathlib.Path("data/raw/screener"), pathlib.Path("public/data/research")
OUT.mkdir(parents=True, exist_ok=True)
CLAIMS = pathlib.Path("data/claims"); CLAIMS.mkdir(parents=True, exist_ok=True)
N_CALLS = 5
want = os.environ.get("FINN_RESEARCH", ",".join(config.RESEARCH_DEMO)).split(",")
if not llm.available():
    print("no GEMINI_API_KEY: skipping research"); sys.exit(0)

for sym in [s for s in want if s]:
    p = RAW / f"{sym}.json"
    if not p.exists():
        print(sym, "no fundamentals"); continue
    co = json.loads(p.read_text())
    listed = [c for c in co["documents"]["concalls"] if c.get("transcript")][:N_CALLS]
    stamp = "|".join(c["transcript"] for c in listed) + "|" + co["quarters"]["periods"][-1]
    outp = OUT / f"{sym}.json"
    if outp.exists() and json.loads(outp.read_text()).get("stamp") == stamp:
        print(sym, "up to date"); continue
    calls = []
    for c in listed:
        try:
            calls.append(research.extract_claims(sym, co["name"], c["month"], c["transcript"]))
            print(sym, c["month"], "guidance:", len(calls[-1]["guidance"]), "verified:", sum(g["quote_verified"] for g in calls[-1]["guidance"]), flush=True)
        except Exception as e:
            print(sym, c["month"], "FAILED", repr(e)[:200], flush=True)
    if not calls:
        continue
    (CLAIMS / f"{sym}.json").write_text(json.dumps(calls, indent=1, ensure_ascii=False))
    try:
        led = research.build_ledger(co, calls)
        led.update(stamp=stamp, generated=dt.datetime.utcnow().isoformat(timespec="minutes") + "Z")
        outp.write_text(json.dumps(led, ensure_ascii=False, separators=(",", ":")))
        print(sym, "ledger:", led["score"], flush=True)
    except Exception as e:
        print(sym, "LEDGER FAILED", repr(e)[:300], flush=True)

up = pathlib.Path("data/llm_usage.json")
hist = json.loads(up.read_text()) if up.exists() else []
hist.append({"at": dt.datetime.utcnow().isoformat(timespec="minutes") + "Z", "stage": "research", "usage": llm.usage_summary()})
up.write_text(json.dumps(hist[-60:], indent=1))
