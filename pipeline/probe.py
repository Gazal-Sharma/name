"""Probe: check which data sources are reachable from CI and save real samples.
Writes everything to probe_out/ so parsers are built against real shapes."""
import json, os, sys, time, traceback, datetime as dt, pathlib, re
import requests

OUT = pathlib.Path("probe_out"); OUT.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
report = {"ran_at": dt.datetime.utcnow().isoformat() + "Z"}

def step(name):
    def deco(fn):
        t = time.time()
        try:
            report[name] = {"ok": True, **(fn() or {})}
        except Exception as e:
            report[name] = {"ok": False, "error": repr(e)[:500], "trace": traceback.format_exc()[-800:]}
        report[name]["secs"] = round(time.time() - t, 1)
        print(name, json.dumps(report[name])[:600], flush=True)
    return deco

@step("yahoo")
def _():
    import yfinance as yf
    tickers = ["INFY.NS", "CDSL.NS", "ETERNAL.NS", "DIXON.NS"]
    df = yf.download(tickers, period="1mo", interval="1d", group_by="ticker", auto_adjust=False, progress=False)
    res = {}
    for t in tickers:
        try:
            sub = df[t].dropna(how="all")
            res[t] = {"rows": len(sub), "last": str(sub.index[-1].date()), "close": float(sub["Close"].iloc[-1]), "vol": float(sub["Volume"].iloc[-1])}
        except Exception as e:
            res[t] = {"error": repr(e)[:200]}
    return {"tickers": res}

@step("yahoo_raw")
def _():
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/INFY.NS?range=1mo&interval=1d", headers={"User-Agent": UA}, timeout=20)
    return {"status": r.status_code, "len": len(r.text)}

def screener(sym, cons=True):
    url = f"https://www.screener.in/company/{sym}/" + ("consolidated/" if cons else "")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    return r

@step("screener")
def _():
    res = {}
    for sym in ["INFY", "HDFCBANK", "DIXON"]:
        r = screener(sym)
        (OUT / f"screener_{sym}.html").write_text(r.text, encoding="utf-8")
        res[sym] = {"status": r.status_code, "len": len(r.text), "has_quarters": 'id="quarters"' in r.text, "has_documents": 'id="documents"' in r.text}
        time.sleep(1.5)
    return res

doc_links = {}
@step("screener_docs")
def _():
    from bs4 import BeautifulSoup
    html = (OUT / "screener_INFY.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    sec = soup.find(id="documents")
    links = []
    for a in sec.find_all("a", href=True):
        links.append({"text": " ".join(a.get_text(" ").split())[:120], "href": a["href"]})
    doc_links["all"] = links
    (OUT / "screener_INFY_doclinks.json").write_text(json.dumps(links, indent=1))
    return {"n_links": len(links), "sample": links[:6]}

@step("transcript_pdf")
def _():
    import fitz
    cands = [l for l in doc_links.get("all", []) if "transcript" in l["text"].lower()]
    out = []
    for l in cands[:2]:
        h = {"User-Agent": UA, "Referer": "https://www.bseindia.com/"}
        r = requests.get(l["href"], headers=h, timeout=60)
        info = {"href": l["href"], "status": r.status_code, "bytes": len(r.content), "ctype": r.headers.get("content-type")}
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            doc = fitz.open(stream=r.content, filetype="pdf")
            text = "\n".join(f"[[page {i+1}]]\n" + p.get_text() for i, p in enumerate(doc))
            info.update(pages=len(doc), chars=len(text))
            (OUT / f"transcript_sample_{len(out)}.txt").write_text(text, encoding="utf-8")
        out.append(info)
    return {"docs": out, "n_transcripts_listed": len(cands)}

@step("annual_report_pdf")
def _():
    cands = [l for l in doc_links.get("all", []) if "financial year" in l["text"].lower()]
    if not cands: return {"note": "no AR links matched", }
    l = cands[0]
    r = requests.get(l["href"], headers={"User-Agent": UA, "Referer": "https://www.bseindia.com/"}, timeout=120, stream=True)
    n = 0
    for chunk in r.iter_content(1 << 20):
        n += len(chunk)
        if n > 80 << 20: break
    return {"href": l["href"], "text": l["text"], "status": r.status_code, "bytes": n, "ctype": r.headers.get("content-type"), "n_listed": len(cands)}

@step("bse_announcements")
def _():
    today = dt.date.today(); frm = today - dt.timedelta(days=30)
    h = {"User-Agent": UA, "Referer": "https://www.bseindia.com/", "Origin": "https://www.bseindia.com", "Accept": "application/json, text/plain, */*"}
    res = {}
    for code in ["500209", "540699"]:
        url = ("https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?pageno=1&strCat=-1"
               f"&strPrevDate={frm:%Y%m%d}&strScrip={code}&strSearch=P&strToDate={today:%Y%m%d}&strType=C&subcategory=-1")
        r = requests.get(url, headers=h, timeout=30)
        res[code] = {"status": r.status_code, "len": len(r.text)}
        try:
            j = r.json()
            (OUT / f"bse_ann_{code}.json").write_text(json.dumps(j, indent=1)[:400000])
            res[code]["rows"] = len(j.get("Table", [])); res[code]["total"] = j.get("Table1")
        except Exception as e:
            res[code]["body"] = r.text[:300]
        time.sleep(1)
    return res

@step("nse_announcements")
def _():
    s = requests.Session()
    h = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
    r0 = s.get("https://www.nseindia.com/", headers=h, timeout=20)
    r1 = s.get("https://www.nseindia.com/companies-listing/corporate-filings-announcements", headers=h, timeout=20)
    today = dt.date.today(); frm = today - dt.timedelta(days=30)
    url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol=CDSL&from_date={frm:%d-%m-%Y}&to_date={today:%d-%m-%Y}"
    r = s.get(url, headers={**h, "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements"}, timeout=30)
    res = {"home": r0.status_code, "page": r1.status_code, "api": r.status_code, "len": len(r.text)}
    try:
        j = r.json(); (OUT / "nse_ann_CDSL.json").write_text(json.dumps(j, indent=1)[:400000]); res["rows"] = len(j)
    except Exception:
        res["body"] = r.text[:300]
    return res

@step("gemini_models")
def _():
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key: return {"note": "no key in env"}
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", headers={"x-goog-api-key": key}, timeout=30)
    if r.status_code != 200: return {"status": r.status_code, "body": r.text[:300]}
    names = [m["name"] for m in r.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
    return {"status": 200, "models": names}

@step("gemini_call")
def _():
    key = os.environ.get("GEMINI_API_KEY", "")
    models = report.get("gemini_models", {}).get("models", [])
    flash = [m for m in models if "flash" in m and "lite" not in m and "image" not in m and "tts" not in m and "live" not in m and "preview" not in m]
    res = {}
    for m in (sorted(flash)[-2:] if flash else []):
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/{m}:generateContent", headers={"x-goog-api-key": key},
                          json={"contents": [{"parts": [{"text": "Reply with the single word: ok"}]}]}, timeout=60)
        res[m] = {"status": r.status_code, "body": r.text[:200] if r.status_code != 200 else r.json()["candidates"][0]["content"]["parts"][0].get("text", "")[:50]}
    return res

(OUT / "report.json").write_text(json.dumps(report, indent=1))
