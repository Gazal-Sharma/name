"""Stage 2: turn raw data into the app snapshot (web/data/*.json).

Order matters for cost: rules classify everything for free, the impact study is pure
arithmetic, and only recent filings that rules flagged as "can't tell" reach the cheap model."""
import datetime as dt, json, os, pathlib, re, sys, hashlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from finn import config, impact, llm, pdftext
from finn.classify import classify, CATEGORY_LABEL

RAW, OUT = pathlib.Path("data/raw"), pathlib.Path("public/data")
(OUT / "company").mkdir(parents=True, exist_ok=True)
LLM_DAYS, LLM_CAP = 60, int(os.environ.get("FINN_LLM_CAP", "220"))
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
now = dt.datetime.now(IST).replace(tzinfo=None)
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

prices = json.loads((RAW / "prices.json").read_text())
sector = dict(config.PORTFOLIO)
funda = {p.stem: json.loads(p.read_text()) for p in (RAW / "screener").glob("*.json")}


def pct(a, b):
    return round((a / b - 1) * 100, 1) if a is not None and b not in (None, 0) and b > 0 else None


def results_block(f: dict, period: str | None):
    """Headline numbers for one quarter with QoQ and YoY, straight from the standardised table."""
    q = f.get("quarters")
    if not q:
        return None
    ps = q["periods"]
    i = ps.index(period) if period in ps else None
    if i is None:
        return None
    rows = q["rows"]
    lender = f.get("is_lender")
    spec = [("Revenue", "Revenue" if "Revenue" in rows else "Sales"),
            ("EBITDA", None if lender else "Operating Profit"),
            ("PBT", "Profit before tax"), ("PAT", "Net Profit")]
    out = []
    for label, key in spec:
        if key is None or key not in rows:
            continue
        v = rows[key]
        out.append({"k": label, "v": v[i], "qoq": pct(v[i], v[i - 1]) if i >= 1 else None,
                    "yoy": pct(v[i], v[i - 4]) if i >= 4 else None,
                    "prev": v[i - 1] if i >= 1 else None, "ya": v[i - 4] if i >= 4 else None})
    m = rows.get("OPM %")
    margin = None
    if m and not lender and m[i] is not None:
        margin = {"v": m[i], "prev": m[i - 1] if i >= 1 else None, "ya": m[i - 4] if i >= 4 else None}
    pdf = (q.get("pdf") or {}).get(period)
    return {"period": period, "rows": out, "margin": margin, "lender": bool(lender), "basis": f.get("basis"),
            "trend": {"periods": ps[-8:], "rev": rows[spec[0][1]][-8:], "pat": rows.get("Net Profit", [])[-8:]},
            "source": ("https://www.screener.in" + pdf) if pdf and pdf.startswith("/") else pdf}


def period_from_text(text: str):
    """'period ended September 30, 2026' / '30th September 2026' / 'Jun 30, 2026' -> 'Sep 2026'."""
    t = text or ""
    m = (re.search(r"ended\s+(?:on\s+)?([A-Z][a-z]{2})[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+(20\d\d)", t)
         or re.search(r"ended\s+(?:on\s+)?\d{1,2}(?:st|nd|rd|th)?\s+([A-Z][a-z]{2})[a-z]*\.?,?\s+(20\d\d)", t))
    return f"{m.group(1)} {m.group(2)}" if m and m.group(1) in MONTHS else None


def infer_period(when):
    """Fallback when the text has no date: results are filed 2-8 weeks after the quarter closes."""
    y, m = when.year, when.month
    q_end = [(3, y), (6, y), (9, y), (12, y - 1)] if m <= 2 else [(3, y), (6, y), (9, y), (12, y)]
    past = [(mm, yy) for mm, yy in q_end if (yy, mm) < (y, m)]
    mm, yy = max(past, key=lambda x: (x[1], x[0])) if past else (12, y - 1)
    return f"{[k for k, v in MONTHS.items() if v == mm][0]} {yy}"


# ---------------------------------------------------------------- 1. classify everything
items = []
for sym in sector:
    p = RAW / "filings" / f"{sym}.json"
    if not p.exists():
        continue
    for r in json.loads(p.read_text()):
        when = dt.datetime.strptime(r["an_dt"], "%d-%b-%Y %H:%M:%S")
        c = classify(r["desc"], r["attchmntText"])
        ab = impact.abnormal(prices, sym, when)
        items.append({
            "id": str(r.get("seq_id") or hashlib.md5((sym + r["an_dt"] + (r["attchmntFile"] or "")).encode()).hexdigest()[:10]),
            "sym": sym, "t": when.isoformat(timespec="minutes"), "desc": r["desc"], "cat": c["category"], "kind": c["kind"],
            "tier": c["tier"], "text": c["text"][:400], "url": r["attchmntFile"], "size": r.get("fileSize"),
            "nse_summary": r.get("voiceSummary"), "ask": c["ask_llm"], "src": "rule",
            "day": ab[0] if ab else None, "r": ab[1] if ab else None, "ar": ab[2] if ab else None, "vm": ab[3] if ab else None,
            "_when": when,
        })
items.sort(key=lambda x: x["_when"], reverse=True)
print(f"classified {len(items)} filings")

# ---------------------------------------------------------------- 2. impact study (rule categories, full year)
study = impact.study([{"symbol": i["sym"], "category": i["cat"], "tier": i["tier"], "ar": i["ar"], "day": i["day"]} for i in items], prices)

# ---------------------------------------------------------------- 3. cheap-model triage of the ambiguous recent ones
CATS = [c for c in CATEGORY_LABEL]
TRIAGE = """You triage one stock-exchange filing for a professional investor who holds this stock.
Use ONLY the filing content below. Do not use outside knowledge about the company.

Company: {name} ({sym}). Market cap ~Rs {mcap:,.0f} Cr. Trailing 12-month revenue ~Rs {rev:,.0f} Cr.
Exchange label: {desc}
Exchange text: {text}
Filing excerpt:
---
{pdf}
---
Return JSON:
{{"category": one of {cats},
 "materiality": 1 | 2 | 3,
 "headline": "<= 90 chars, the concrete fact: who/what/how much. No company name, no 'has informed'.",
 "why": "<= 120 chars: why an investor should or shouldn't care, with the number relative to company size when there is one",
 "amount_cr": number or null,
 "people": [{{"name": "", "role": "", "change": "appointed|resigned|retired|re-appointed|ceased|other", "effective": "", "background": "<= 50 words on career before this role, only from the filing; empty string if the filing has none"}}]}}
Materiality: 1 = could move the stock or change the investment view (large deal or order vs company size, CEO/CFO/MD/Chair change, rating change, big penalty, fund raise).
2 = worth one line (mid-size order, senior hire, new plant, moderate legal order).
3 = routine, marketing or housekeeping (awards, product PR, small tax demand under 0.1% of revenue, subsidiary paperwork, ESOP, schedules).
"people" only for appointments/resignations; otherwise []. Use category "unclassified" for routine paperwork."""

cut = now - dt.timedelta(days=LLM_DAYS)
todo = [i for i in items if i["ask"] and i["_when"] >= cut]
done = fail = 0
if llm.available():
    for it in todo[:LLM_CAP]:
        f = funda.get(it["sym"], {})
        excerpt = ""
        if it["url"] and it["url"].lower().endswith(".pdf"):
            try:
                excerpt = pdftext.tagged(pdftext.pages(pdftext.fetch(it["url"], max_mb=15, timeout=30), max_pages=4), 5000)
            except Exception as e:
                excerpt = f"(attachment unavailable: {type(e).__name__})"
        ann = (f.get("annual") or {}).get("rows", {})
        rev = (ann.get("Sales") or ann.get("Revenue") or [0])[-1] or 0
        prompt = TRIAGE.format(name=f.get("name", it["sym"]), sym=it["sym"], mcap=(f.get("top") or {}).get("Market Cap") or 0,
                               rev=rev, desc=it["desc"], text=it["text"] or it["desc"], pdf=excerpt or "(none)", cats=CATS)
        try:
            j = llm.ask("triage", prompt, max_out=700, min_gap=4.0)
            if isinstance(j, list):
                j = j[0]
            if j.get("category") in CATEGORY_LABEL:
                it["cat"] = j["category"]
            if j.get("materiality") in (1, 2, 3):
                it["tier"] = j["materiality"]
            it["title"] = (j.get("headline") or "").strip()[:110] or None
            it["why"] = (j.get("why") or "").strip()[:150] or None
            if j.get("amount_cr"):
                it["amount_cr"] = j["amount_cr"]
            ppl = [p for p in (j.get("people") or []) if p.get("name")]
            if ppl:
                it["people"] = ppl[:4]
            it["src"] = "model"
            done += 1
        except Exception as e:
            fail += 1
            it["llm_error"] = str(e)[:120]
            if fail >= 8 and done == 0:
                print("model unavailable, stopping triage:", e)
                break
print(f"triage: {done} enriched, {fail} failed, {max(0, len(todo) - LLM_CAP)} over cap")

# ---------------------------------------------------------------- 4. results numbers + clustering
feed_cut = now - dt.timedelta(days=config.FEED_DAYS)
feed = [i for i in items if i["_when"] >= feed_cut]
for it in feed:
    if it["kind"] == "results_filing":
        per = period_from_text(it["text"]) or infer_period(it["_when"])
        it["results"] = results_block(funda.get(it["sym"], {}), per) or {"period": per, "rows": []}
        it["title"] = f"{per or 'Quarterly'} results"

anchors, absorbed, seen_res = [], set(), {}
for it in sorted((i for i in feed if i["kind"] == "results_filing"), key=lambda x: x["_when"]):
    k = (it["sym"], it["results"]["period"])
    if k in seen_res:      # standalone + consolidated filed separately: keep one card
        seen_res[k].setdefault("related", []).append({"t": it["t"], "kind": "results_filing", "desc": it["desc"], "url": it["url"], "text": it["text"][:120]})
        absorbed.add(it["id"])
    else:
        seen_res[k] = it
        anchors.append(it)
for it in feed:
    if it["kind"] == "results_filing" or not (it["cat"] in ("results", "earnings_call") or it["kind"] == "newspaper"):
        continue
    best = None
    for a in anchors:
        if a["sym"] != it["sym"]:
            continue
        gap = (it["_when"] - a["_when"]).total_seconds() / 86400
        if -1.5 <= gap <= 8 and (best is None or abs(gap) < best[0]):
            best = (abs(gap), a)
    if best:
        a = best[1]
        a.setdefault("related", []).append({"t": it["t"], "kind": it["kind"], "desc": it["desc"], "url": it["url"], "text": it["text"][:120]})
        if it["kind"] == "transcript":
            a["has_transcript"] = True
        absorbed.add(it["id"])
feed = [i for i in feed if i["id"] not in absorbed]

# collapse same-day routine duplicates (e.g. four investor-meeting schedules filed in one evening)
merged, index = [], {}
for it in feed:
    k = (it["sym"], it["cat"], it["kind"], it["t"][:10]) if it["tier"] == 3 else None
    if k and k in index:
        head = index[k]
        head.setdefault("related", []).append({"t": it["t"], "kind": it["kind"], "desc": it["desc"], "url": it["url"], "text": it["text"][:120]})
        continue
    if k:
        index[k] = it
    merged.append(it)
feed = merged

for it in feed:
    for k in ("_when", "ask"):
        it.pop(k, None)
    if not it.get("title"):
        base = it["text"] if it["text"] and len(it["text"]) > 12 and it["text"].lower() != it["desc"].lower() else it["desc"]
        it["title"] = re.sub(r"\s+", " ", base)[:110]
    if not it.get("nse_summary"):
        it.pop("nse_summary", None)
    for k in [k for k, v in it.items() if v is None]:
        it.pop(k)

# ---------------------------------------------------------------- 5. write
companies = []
for sym, sec in config.PORTFOLIO:
    f, s = funda.get(sym, {}), prices.get(sym)
    top = f.get("top") or {}
    c = {"sym": sym, "name": f.get("name", sym), "sector": sec, "mcap": top.get("Market Cap"), "pe": top.get("Stock P/E")}
    if s:
        c.update(price=s["c"][-1], chg1=pct(s["c"][-1], s["c"][-2]), chg5=pct(s["c"][-1], s["c"][-6]), chg21=pct(s["c"][-1], s["c"][-22]))
    companies.append(c)

keep = 260
(OUT / "prices.json").write_text(json.dumps({k: {x: v[x][-keep:] for x in ("d", "c", "v")} for k, v in prices.items()}, separators=(",", ":")))
(OUT / "filings.json").write_text(json.dumps(feed, separators=(",", ":"), ensure_ascii=False))
for sym, f in funda.items():
    (OUT / "company" / f"{sym}.json").write_text(json.dumps(f, separators=(",", ":"), ensure_ascii=False))

usage_path = pathlib.Path("data/llm_usage.json")
hist = json.loads(usage_path.read_text()) if usage_path.exists() else []
hist.append({"at": now.isoformat(timespec="minutes"), "stage": "snapshot", "usage": llm.usage_summary()})
usage_path.write_text(json.dumps(hist[-60:], indent=1))

tiers = {t: sum(1 for i in feed if i["tier"] == t) for t in (1, 2, 3)}
meta = {"generated": now.isoformat(timespec="minutes"), "price_date": prices["NIFTY"]["d"][-1], "companies": companies,
        "impact": study, "labels": CATEGORY_LABEL, "feed_days": config.FEED_DAYS, "llm_days": LLM_DAYS,
        "counts": {"filings_year": len(items), "feed": len(feed), "tiers": tiers,
                   "rule_decided": sum(1 for i in feed if i["src"] == "rule"), "model_decided": sum(1 for i in feed if i["src"] == "model")},
        "research_ready": sorted(p.stem for p in (OUT / "research").glob("*.json")) if (OUT / "research").exists() else [],
        "demo": config.RESEARCH_DEMO}
(OUT / "meta.json").write_text(json.dumps(meta, separators=(",", ":"), ensure_ascii=False))
print(json.dumps({"feed": len(feed), "tiers": tiers, "impact": study}, indent=1)[:2500])
