"""GET /api/company?symbol=KPITTECH -> standardised financials + links to primary documents. No model call."""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import re
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))   # repo root, so `finn` imports on Vercel
from finn.web import send
from finn.sources import screener


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        sym = (parse_qs(urlparse(self.path).query).get("symbol") or [""])[0].upper().strip()
        if not re.fullmatch(r"[A-Z0-9&-]{1,20}", sym):
            return send(self, 400, {"error": "symbol must be an NSE ticker"})
        try:
            data = screener.get(sym)
        except screener.NotFound:
            return send(self, 404, {"error": f"no company found for {sym}"})
        except Exception as e:
            return send(self, 502, {"error": f"source unavailable ({type(e).__name__})"})
        # Fundamentals change once a quarter: let the CDN hold them for six hours.
        send(self, 200, data, "public, s-maxage=21600, stale-while-revalidate=86400")
