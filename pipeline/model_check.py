"""Which Gemini models answer on this key's free tier? Decides the routing table."""
import json, os, pathlib, time, requests
key = os.environ.get("GEMINI_API_KEY", "")
cands = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite",
         "gemini-3.1-flash-lite", "gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash",
         "gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-pro-latest", "gemini-3.1-pro-preview",
         "gemini-4-hydrogen", "gemini-4-carbon", "gemini-4-argon", "gemma-4-31b-it"]
out = {}
for m in cands:
    t = time.time()
    try:
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                          headers={"x-goog-api-key": key}, timeout=60,
                          json={"contents": [{"parts": [{"text": 'Return JSON {"ok": true}'}]}],
                                "generationConfig": {"responseMimeType": "application/json"}})
        j = r.json()
        out[m] = {"status": r.status_code, "secs": round(time.time() - t, 1),
                  "usage": j.get("usageMetadata"), "err": (j.get("error") or {}).get("message", "")[:160]}
    except Exception as e:
        out[m] = {"error": repr(e)[:160]}
    time.sleep(1)
pathlib.Path("data/raw").mkdir(parents=True, exist_ok=True)
pathlib.Path("data/raw/model_check.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
