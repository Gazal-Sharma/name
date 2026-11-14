"""POST /api/ask -> plain-English help from the cheapest model.
  {mode: "explain", question, context?}  a beginner's question, optionally about one card on screen
  {mode: "brief", facts}                 turn the digest's facts into a short written brief
The model is given the facts; it is told not to add numbers or give investment advice."""
from http.server import BaseHTTPRequestHandler
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))   # repo root, so `finn` imports on Vercel
from finn.web import send
from finn import llm

EXPLAIN = """You are the help desk inside FINN, an app that shows an investor the stock-exchange filings of Indian companies they hold.
The person asking is a complete beginner. Answer in plain English, 2 to 5 short sentences, no jargon unless you explain it,
no bullet points, no markdown. Use an everyday comparison when it helps. If context from the screen is given, explain that
specific item: what happened and why an investor might care, using only the numbers in the context.
Never recommend buying or selling. If the question is not about investing, companies, markets or this app, say you can only help with those.
{context}
Question: {question}
Return JSON: {{"answer": "..."}}"""

BRIEF = """Write a spoken morning brief for an investor from the facts below. 70 to 110 words, flowing natural sentences as a
radio business presenter would say them, no lists, no headings, no symbols. Start with how many filings there were and how many matter.
Then pick out what stands out across companies (strongest and weakest results, any notable non-results item), comparing them
rather than reciting each one. Say numbers the way people speak ("revenue rose 47 percent", "profit fell by almost half").
Write "crore" in words. Use ONLY the facts given; do not add numbers, causes or opinions that are not there.
Facts:
{facts}
Return JSON: {{"answer": "..."}}"""


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            n = int(self.headers.get("content-length") or 0)
            if n > 20_000:
                return send(self, 413, {"error": "too long"})
            b = json.loads(self.rfile.read(n))
            mode = b.get("mode")
            if mode == "brief":
                prompt = BRIEF.format(facts=json.dumps(b["facts"], ensure_ascii=False)[:8000])
            else:
                q = str(b["question"]).strip()[:500]
                assert q
                ctx = b.get("context")
                prompt = EXPLAIN.format(question=q, context=f"Context from the screen: {json.dumps(ctx, ensure_ascii=False)[:3000]}" if ctx else "")
        except Exception:
            return send(self, 400, {"error": "bad request"})
        try:
            j = llm.ask("triage", prompt, cache=False, max_out=500, temperature=0.3, timeout=40)
            send(self, 200, {"answer": str(j.get("answer", "")).strip()})
        except Exception as e:
            send(self, 503, {"error": f"model unavailable ({str(e)[:80]})"})
