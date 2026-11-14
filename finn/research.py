"""Pull side: the Promise Ledger.

Two model steps, both grounded only in the company's own documents:
  1. extract (per transcript, cached forever): what did management commit to, with a verbatim quote and page.
  2. judge (once per company): set each commitment against the numbers reported afterwards.
Between them, plain code checks every quote against the page it cites, and the judge may only
point at an extracted claim by index — it never gets to write a quote itself."""
import re
from . import llm, pdftext

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fy_label(period: str) -> str:
    """'Sep 2026' -> 'Q2 FY27' (Indian fiscal year, April to March)."""
    m = re.match(r"([A-Z][a-z]{2}) (20\d\d)", period or "")
    if not m or m.group(1) not in MON:
        return period
    mon, yr = MON.index(m.group(1)) + 1, int(m.group(2))
    fy = yr + 1 if mon >= 4 else yr
    q = {6: 1, 9: 2, 12: 3, 3: 4}.get(mon)
    return f"Q{q} FY{fy % 100:02d}" if q else f"FY{fy % 100:02d}"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9%.]+", " ", (s or "").lower()).strip()


def verify_quote(quote: str, pages: list[str], page: int | None):
    """Is the quote really in the transcript? Returns (verified, page_found).
    Exact match after normalising case/punctuation, else >=80% of its 6-word runs on one page."""
    q = _norm(quote)
    if len(q) < 12:
        return False, page
    norm = [_norm(p) for p in pages]
    order = sorted(range(len(norm)), key=lambda i: abs(i + 1 - (page or 1)))
    for i in order:
        if q in norm[i]:
            return True, i + 1
    words = q.split()
    grams = [" ".join(words[j:j + 6]) for j in range(max(1, len(words) - 5))]
    for i in order:
        hit = sum(g in norm[i] for g in grams)
        if hit / len(grams) >= 0.8:
            return True, i + 1
    return False, page


CLAIMS = """You are reading the transcript of an earnings conference call of {name} ({sym}), filed around {month}.
Work ONLY from the transcript below. Do not use anything you know about the company from elsewhere.

Extract what MANAGEMENT (not analysts) explicitly committed to or guided for the future on headline items:
revenue/volume growth, margins, profit, capex, capacity or store additions, debt, order inflow, credit cost.
Keep only statements with a number, a range, or a clear direction with a time frame. Skip vague optimism.

Return JSON:
{{"quarter": "the quarter this call discusses, like 'Q2 FY27'",
 "guidance": [{{"topic": "<= 6 words, e.g. 'FY27 revenue growth'", "metric": "revenue_growth|margin|profit|capex|capacity|volume|debt|other",
   "period": "the period the promise is about, e.g. 'FY27', 'Q3 FY27', 'next 2-3 years'",
   "said": "one plain sentence with the numbers, e.g. 'FY27 revenue growth of 3-5% in constant currency'",
   "low": number or null, "high": number or null, "unit": "% | Rs Cr | bps | stores | other",
   "change": "new | reiterated | raised | cut | unclear",
   "quote": "EXACT words copied from the transcript, 12-35 words, one continuous span", "page": page number from the [pN] marker, "speaker": "name"}}],
 "reported": [{{"topic": "", "value": "what was reported for this quarter, with number", "quote": "exact words, 10-30 words", "page": 0}}],
 "business": "2 sentences: what the company sells and its main segments, only as described in this call"}}
At most 8 guidance items (the most important, numeric first) and at most 6 reported items.

Transcript:
{text}"""


def extract_claims(sym: str, name: str, month: str, url: str) -> dict:
    data = pdftext.fetch(url, max_mb=25, timeout=45)
    pages = pdftext.pages(data, max_pages=80)
    text = pdftext.tagged(pages, 160_000)
    if len(text) < 2000:
        raise ValueError("transcript has no extractable text (scanned PDF)")
    j = llm.ask("extract", CLAIMS.format(name=name, sym=sym, month=month, text=text), max_out=5000, min_gap=6.0, timeout=120)
    out = {"month": month, "url": url, "pages": len(pages), "quarter": j.get("quarter"), "business": j.get("business"),
           "guidance": [], "reported": []}
    for g in (j.get("guidance") or [])[:8]:
        if not g.get("said") or not g.get("quote"):
            continue
        ok, pg = verify_quote(g["quote"], pages, g.get("page"))
        out["guidance"].append({**{k: g.get(k) for k in ("topic", "metric", "period", "said", "low", "high", "unit", "change", "quote", "speaker")},
                                "page": pg, "quote_verified": ok})
    for r in (j.get("reported") or [])[:6]:
        if r.get("value"):
            ok, pg = verify_quote(r.get("quote") or "", pages, r.get("page"))
            out["reported"].append({"topic": r.get("topic"), "value": r["value"], "page": pg, "quote_verified": ok})
    return out


def numbers_table(co: dict) -> str:
    """Reported numbers the judge may cite, with growth precomputed so the model does no arithmetic."""
    q, lines = co["quarters"], []
    rows = q["rows"]
    rev = rows.get("Sales") or rows.get("Revenue")
    op, opm, pbt, pat = rows.get("Operating Profit"), rows.get("OPM %"), rows.get("Profit before tax"), rows.get("Net Profit")
    def g(a, i, k):
        return f"{(a[i] / a[i - k] - 1) * 100:+.1f}%" if a and i >= k and a[i] is not None and a[i - k] else "n/a"
    lines.append("QUARTERLY (Rs crore) | revenue | rev YoY | rev QoQ | EBITDA | EBITDA margin | PBT | PAT | PAT YoY")
    for i in range(max(0, len(q["periods"]) - 9), len(q["periods"])):
        p = q["periods"][i]
        lines.append(f"{p} ({fy_label(p)}) | {rev[i]} | {g(rev, i, 4)} | {g(rev, i, 1)} | {op[i] if op else 'n/a'} | "
                     f"{f'{op[i] / rev[i] * 100:.1f}%' if op and op[i] is not None and rev[i] else 'n/a'} | {pbt[i] if pbt else 'n/a'} | {pat[i] if pat else 'n/a'} | {g(pat, i, 4)}")
    a = co["annual"]; ar = a["rows"]
    arev = ar.get("Sales") or ar.get("Revenue")
    lines.append("ANNUAL (Rs crore) | revenue | growth | EBITDA margin | PAT | PAT growth")
    for i in range(max(0, len(a["periods"]) - 4), len(a["periods"])):
        p = a["periods"][i]
        lab = "TTM (last four quarters)" if p == "TTM" else f"{p} ({fy_label(p)[-4:]})"
        m = ar.get("OPM %")
        ttm = p == "TTM"
        lines.append(f"{lab} | {arev[i]} | {'n/a' if ttm else g(arev, i, 1)} | {str(m[i]) + '%' if m and m[i] is not None else 'n/a'} | "
                     f"{ar['Net Profit'][i]} | {'n/a' if ttm else g(ar['Net Profit'], i, 1)}")
    lines.append("Note: 'EBITDA margin' is operating profit before depreciation and other income, over revenue. It is not the same "
                 "as a company's own 'operating margin' or 'EBIT margin'; test those from what later calls reported.")
    c = (co.get("cashflow") or {}).get("rows", {})
    if c.get("Cash from Operating Activity"):
        lines.append("CASH FLOW, last 3 years: operating " + str(c["Cash from Operating Activity"][-3:]) + ", free " + str((c.get("Free Cash Flow") or [])[-3:]))
    b = (co.get("balance") or {}).get("rows", {})
    debt = b.get("Borrowings") or b.get("Borrowing")
    if debt:
        lines.append("BORROWINGS, last 3 balance sheets: " + str(debt[-3:]))
    return "\n".join(lines)


JUDGE = """You are a buy-side analyst checking a management team's word against its record for {name} ({sym}).
You have (A) guidance management gave on its last earnings calls, oldest call first, each item tagged [c<call>.g<n>],
(B) what management said it reported on each call, and (C) the reported financials.
Use ONLY this material. No outside knowledge, no news, no broker views.

Indian fiscal years run April to March: FY27 ends March 2027; Q1 = Jun quarter, Q2 = Sep, Q3 = Dec, Q4 = Mar.
Company-wide table numbers are consolidated and in Rs crore. If a promise is in a unit the table cannot test
(constant-currency growth, a segment, a non-financial KPI), judge it from what later calls reported, and say so.

For each DISTINCT promise (merge repeats across calls; if guidance was raised or cut, say so in "delivered"):
- verdict "kept": the period has ended or enough of it has passed and results are in line or better
- "missed": results fell short
- "partly": mixed, or met only after the guidance was cut
- "open": cannot be judged yet. Say what would settle it and where the run-rate stands.
Prefer promises that can be checked. Give 5 to 8 entries, most important first.

Return JSON:
{{"entries": [{{"ref": "c1.g2 (the EARLIEST call where this promise was made)", "topic": "<= 6 words",
   "delivered": "<= 28 words: the specific reported number(s) that answer the promise, with the period",
   "evidence": "<= 24 words: where that number comes from (quarterly table, annual table, or which later call)",
   "verdict": "kept|missed|partly|open"}}],
 "summary": "<= 40 words: is this management's guidance reliable? Be specific and direct.",
 "business": "<= 45 words: what the company does and its segments, from the calls only",
 "bull": ["3 points, each <= 22 words, each tied to a number or statement above"],
 "bear": ["3 points, each <= 22 words, each tied to a number or statement above"]}}

(A) and (B): CALLS
{calls}

(C) REPORTED FINANCIALS
{table}"""


def build_ledger(co: dict, calls: list[dict]) -> dict:
    calls = sorted(calls, key=lambda c: (int(c["month"][-4:]), MON.index(c["month"][:3])))
    refs, blocks = {}, []
    for ci, c in enumerate(calls, 1):
        b = [f"--- Call c{ci}: {c['month']}, discussing {c.get('quarter') or 'the latest quarter'}"]
        for gi, g in enumerate(c["guidance"], 1):
            refs[f"c{ci}.g{gi}"] = (c, g)
            b.append(f"[c{ci}.g{gi}] ({g.get('change') or 'new'}; about {g.get('period')}) {g['said']}")
        for r in c["reported"]:
            b.append(f"  reported: {r.get('topic')}: {r['value']}")
        blocks.append("\n".join(b))
    if not refs:
        return {"symbol": co["symbol"], "calls": [{"month": c["month"], "url": c["url"]} for c in calls], "entries": [],
                "summary": "Management gave no explicit numeric guidance in the calls read.", "score": {}}
    j = llm.ask("reason", JUDGE.format(name=co["name"], sym=co["symbol"], calls="\n".join(blocks), table=numbers_table(co)),
                max_out=6000, min_gap=6.0, timeout=150)
    entries, score = [], {"kept": 0, "missed": 0, "partly": 0, "open": 0}
    for e in j.get("entries") or []:
        m = re.search(r"c\d+\.g\d+", str(e.get("ref", "")))
        if not m or m.group(0) not in refs or e.get("verdict") not in score:
            continue      # a verdict that cannot be traced to an extracted, quoted claim is dropped
        c, g = refs[m.group(0)]
        score[e["verdict"]] += 1
        entries.append({"topic": e.get("topic") or g.get("topic"), "said": g["said"], "said_when": f"{c['month']} call",
                        "quote": g["quote"], "page": g["page"], "url": c["url"], "quote_verified": g["quote_verified"],
                        "speaker": g.get("speaker"), "delivered": e.get("delivered"), "evidence": e.get("evidence"),
                        "verdict": e["verdict"]})
    return {"symbol": co["symbol"], "calls": [{"month": c["month"], "url": c["url"], "quarter": c.get("quarter")} for c in calls],
            "entries": entries, "score": score, "summary": j.get("summary"), "business": j.get("business"),
            "bull": (j.get("bull") or [])[:3], "bear": (j.get("bear") or [])[:3]}
