"""Shared plumbing for the serverless endpoints."""
import json, os
os.environ.setdefault("FINN_LLM_CACHE", "/tmp/finn-llm")


def send(h, status: int, body: dict, cache: str | None = None):
    data = json.dumps(body, ensure_ascii=False).encode()
    h.send_response(status)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Cache-Control", cache if cache and status == 200 else "no-store")
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    h.wfile.write(data)
