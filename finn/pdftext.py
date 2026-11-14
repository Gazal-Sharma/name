"""Download a PDF and return page-tagged text. PyMuPDF when available (CI), pypdf otherwise (serverless)."""
import io
import requests
from .config import UA


def fetch(url: str, max_mb: int = 40, timeout: int = 60) -> bytes:
    h = {"User-Agent": UA, "Accept": "application/pdf,*/*"}
    if "bseindia.com" in url:
        h["Referer"] = "https://www.bseindia.com/"
    if "nseindia" in url:
        h["Referer"] = "https://www.nseindia.com/"
    r = requests.get(url, headers=h, timeout=timeout, stream=True)
    r.raise_for_status()
    buf = io.BytesIO()
    for chunk in r.iter_content(1 << 18):
        buf.write(chunk)
        if buf.tell() > max_mb << 20:
            raise ValueError(f"PDF larger than {max_mb} MB")
    data = buf.getvalue()
    if not data.startswith(b"%PDF"):
        raise ValueError("not a PDF")
    return data


def pages(data: bytes, max_pages: int | None = None) -> list[str]:
    try:
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        n = len(doc) if max_pages is None else min(len(doc), max_pages)
        return [doc[i].get_text() for i in range(n)]
    except ImportError:
        from pypdf import PdfReader
        rd = PdfReader(io.BytesIO(data))
        n = len(rd.pages) if max_pages is None else min(len(rd.pages), max_pages)
        return [(rd.pages[i].extract_text() or "") for i in range(n)]


def tagged(pgs: list[str], limit_chars: int | None = None) -> str:
    out, total = [], 0
    for i, p in enumerate(pgs, 1):
        p = p.strip()
        if not p:
            continue
        s = f"[p{i}]\n{p}\n"
        if limit_chars and total + len(s) > limit_chars:
            out.append(s[: max(0, limit_chars - total)])
            break
        out.append(s); total += len(s)
    return "\n".join(out)
