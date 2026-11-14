"""POST /api/ledger {symbol, company, calls} -> promised vs delivered. The one call that uses the strongest model."""
from http.server import BaseHTTPRequestHandler
import json
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))   # repo root, so `finn` imports on Vercel
from finn.web import send
from finn import research, llm


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            n = int(self.headers.get("content-length") or 0)
            if n > 600_000:
                return send(self, 413, {"error": "payload too large"})
            body = json.loads(self.rfile.read(n))
            co, calls = body["company"], body["calls"]
            assert co.get("quarters") and isinstance(calls, list) and calls
        except Exception:
            return send(self, 400, {"error": "expected {company, calls}"})
        try:
            send(self, 200, research.build_ledger(co, calls[:6]))
        except llm.LLMError as e:
            send(self, 503, {"error": f"model unavailable: {str(e)[:120]}"})
        except Exception as e:
            send(self, 500, {"error": f"{type(e).__name__}: {str(e)[:120]}"})
