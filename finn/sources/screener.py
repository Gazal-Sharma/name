"""screener.in: standardised financial tables + links to primary documents.
One HTTP request per company. No LLM involved anywhere in this file."""
import re
import requests
from bs4 import BeautifulSoup
from ..config import UA

BASE = "https://www.screener.in/company/{sym}/{view}"


class NotFound(Exception):
    pass


def fetch_html(symbol: str, consolidated: bool = True, timeout: int = 25) -> str:
    url = BASE.format(sym=symbol.upper(), view="consolidated/" if consolidated else "")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    if r.status_code == 404:
        raise NotFound(symbol)
    r.raise_for_status()
    return r.text


def _num(s: str):
    s = (s or "").replace(",", "").replace("%", "").replace("₹", "").replace("Cr.", "").strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _table(soup, sec_id):
    t = soup.select_one(f"#{sec_id} table")
    if not t:
        return None
    periods = [th.get_text(strip=True) for th in t.select("thead th")][1:]
    rows, links = {}, {}
    for tr in t.select("tbody tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        label = tds[0].get_text(" ", strip=True).replace("+", "").strip()
        if label == "Raw PDF":
            links = {p: (td.find("a")["href"] if td.find("a") else None) for p, td in zip(periods, tds[1:])}
            continue
        rows[label] = [_num(td.get_text(strip=True)) for td in tds[1:]]
    return {"periods": periods, "rows": rows, **({"pdf": links} if links else {})}


def parse(html: str, symbol: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    if not h1:
        raise NotFound(symbol)
    out = {"symbol": symbol.upper(), "name": h1.get_text(strip=True)}

    top = {}
    for li in soup.select("#top-ratios li"):
        name = li.select_one(".name")
        if not name:
            continue
        nums = [_num(n.get_text()) for n in li.select(".number")]
        top[name.get_text(strip=True)] = nums[0] if len(nums) == 1 else nums
    out["top"] = top

    about = soup.select_one(".company-profile .about")
    out["about"] = re.sub(r"\s*\[\d+\]", "", about.get_text(" ", strip=True)) if about else None

    for a in soup.select(".company-links a[href]"):
        m = re.search(r"bseindia\.com/.*/(\d{6})/", a["href"])
        if m:
            out["bse_code"] = m.group(1)
    m = re.search(r"bseindia\.com/stock-share-price/[^\"]*/(\d{6})/", html)
    if m and "bse_code" not in out:
        out["bse_code"] = m.group(1)

    sub = soup.select_one("#quarters .sub")
    out["basis"] = "consolidated" if sub and "Consolidated" in sub.get_text() else "standalone"

    out["quarters"] = _table(soup, "quarters")
    out["annual"] = _table(soup, "profit-loss")
    out["balance"] = _table(soup, "balance-sheet")
    out["cashflow"] = _table(soup, "cash-flow")
    out["ratios"] = _table(soup, "ratios")
    q = out["quarters"]
    out["is_lender"] = bool(q and "Financing Profit" in q["rows"])

    docs = {"annual_reports": [], "concalls": [], "credit_ratings": []}
    d = soup.find(id="documents")
    if d:
        for a in d.select(".annual-reports li a[href]"):
            txt = " ".join(a.get_text(" ").split())
            y = re.search(r"(20\d\d)", txt)
            docs["annual_reports"].append({"year": int(y.group(1)) if y else None, "url": a["href"], "label": txt[:60]})
        for li in d.select(".concalls li"):
            txt = " ".join(li.get_text(" ").split())
            m = re.match(r"([A-Z][a-z]{2}) (20\d\d)", txt)
            item = {"month": f"{m.group(1)} {m.group(2)}" if m else txt[:8]}
            for a in li.find_all("a", href=True):
                k = a.get_text(strip=True).lower()
                if k in ("transcript", "ppt", "rec"):
                    item[k] = a["href"]
            docs["concalls"].append(item)
        for a in d.select(".credit-ratings li a[href]"):
            docs["credit_ratings"].append({"label": " ".join(a.get_text(" ").split())[:80], "url": a["href"]})
    out["documents"] = docs
    return out


def get(symbol: str) -> dict:
    """Consolidated view first; fall back to standalone when a company has no subsidiaries."""
    html = fetch_html(symbol, True)
    data = parse(html, symbol)
    if not data["quarters"] or not any(v is not None for v in data["quarters"]["rows"].get(
            "Sales", data["quarters"]["rows"].get("Revenue", []))):
        data = parse(fetch_html(symbol, False), symbol)
    return data
