"""GET /api/claims?symbol=&name=&month=&url= -> guidance extracted from ONE transcript.
A transcript never changes, so the response is cached at the CDN for 30 days: each document is read by a model once, for everyone."""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import re
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))   # repo root, so `finn` imports on Vercel
from finn.web import send
from finn import research, llm

ALLOWED = re.compile(r"^https://([a-z0-9-]+\.)*(bseindia\.com|nseindia\.com|nseindia\.in|[a-z0-9-]+\.(com|in|co\.in|net))/", re.I)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        sym, url, month = q.get("symbol", "").upper(), q.get("url", ""), q.get("month", "")
        if not re.fullmatch(r"[A-Z0-9&-]{1,20}", sym) or not ALLOWED.match(url) or not re.fullmatch(r"[A-Z][a-z]{2} 20\d\d", month):
            return send(self, 400, {"error": "bad parameters"})
        try:
            out = research.extract_claims(sym, q.get("name", sym)[:80], month, url)
        except llm.LLMError as e:
            return send(self, 503, {"error": f"model unavailable: {str(e)[:120]}"})
        except Exception as e:
            return send(self, 502, {"error": f"could not read transcript ({type(e).__name__}: {str(e)[:80]})"})
        send(self, 200, out, "public, s-maxage=2592000")
