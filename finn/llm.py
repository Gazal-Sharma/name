"""Gemini access with task-based routing, a content-addressed cache and a usage ledger.

Routing (free tier, measured on 15 Nov 2026 — see data/raw/model_check.json):
  triage  -> flash-lite : one short filing in, small JSON out. Bulk, cheap.
  extract -> flash      : a whole transcript (~25k tokens) in, guidance claims out.
  reason  -> strongest free model : only for the final promised-vs-delivered verdicts.
Every call is cached by sha256(model-tier + prompt), so a document is read once, ever."""
import hashlib, json, os, pathlib, re, time
import requests

ROUTES = {
    "triage": ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"],
    "extract": ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"],
    "reason": ["gemini-4-hydrogen", "gemini-3.6-flash", "gemini-3.5-flash"],
}
_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
CACHE_DIR = pathlib.Path(os.environ.get("FINN_LLM_CACHE", "data/cache/llm"))
USAGE = []            # in-memory ledger for this process; the pipeline persists it
_dead = {}            # model -> time it last hit a quota wall
_last_call = [0.0]


class LLMError(Exception):
    pass


def available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def _parse_json(txt: str):
    txt = txt.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```\w*\n?|```$", "", txt).strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", txt, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def ask(task: str, prompt: str, *, cache: bool = True, max_out: int = 4096, temperature: float = 0.1,
        min_gap: float = 0.0, timeout: int = 90):
    """Return parsed JSON for `prompt`, routed by `task`. Raises LLMError if every model fails."""
    key = hashlib.sha256((task + "\x00" + prompt).encode()).hexdigest()[:24]
    path = CACHE_DIR / task / f"{key}.json"
    if cache and path.exists():
        USAGE.append({"task": task, "cached": True})
        return json.loads(path.read_text())
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise LLMError("no GEMINI_API_KEY")
    last = None
    for model in ROUTES[task]:
        if time.time() - _dead.get(model, 0) < 120:
            continue
        for attempt in range(2):
            wait = min_gap - (time.time() - _last_call[0])
            if wait > 0:
                time.sleep(wait)
            _last_call[0] = time.time()
            try:
                r = requests.post(_URL.format(m=model), headers={"x-goog-api-key": api_key}, timeout=timeout, json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": temperature,
                                         "maxOutputTokens": max_out}})
            except requests.RequestException as e:
                last = f"{model}: {e!r}"[:200]
                continue
            if r.status_code == 200:
                j = r.json()
                try:
                    txt = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
                    data = _parse_json(txt)
                except Exception as e:
                    last = f"{model}: bad JSON {e!r}"[:200]
                    continue
                u = j.get("usageMetadata", {})
                USAGE.append({"task": task, "model": model, "in": u.get("promptTokenCount", 0),
                              "out": u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0), "cached": False})
                if cache:
                    try:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps(data, ensure_ascii=False))
                    except OSError:
                        pass
                return data
            last = f"{model}: HTTP {r.status_code} {r.text[:160]}"
            if r.status_code == 429:
                m = re.search(r"retry in ([\d.]+)s", r.text)
                delay = float(m.group(1)) if m else 20
                if attempt == 0 and delay <= 40:
                    time.sleep(delay + 1)
                    continue
                _dead[model] = time.time()
                break
            if r.status_code in (500, 503):
                time.sleep(3)
                continue
            break   # 4xx other than 429: try the next model
    raise LLMError(last or "all models unavailable")


def usage_summary() -> dict:
    out = {}
    for u in USAGE:
        k = u["task"]
        o = out.setdefault(k, {"calls": 0, "cache_hits": 0, "tokens_in": 0, "tokens_out": 0, "models": {}})
        if u.get("cached"):
            o["cache_hits"] += 1
        else:
            o["calls"] += 1; o["tokens_in"] += u["in"]; o["tokens_out"] += u["out"]
            o["models"][u["model"]] = o["models"].get(u["model"], 0) + 1
    return out
