"""Pip voice audition: a small local site to pick a Fish Audio voice.

Run:   bridge/.venv/bin/python bridge/audition.py        (from the project root)
Open:  http://127.0.0.1:8790

What it does
- Searches the Fish Audio voice library (GET /model) and shows cards with the library preview clip.
- For any voice and any line, renders three takes through POST /v1/tts:
    1. standard TTS  (FISH_STANDARD_MODEL, bare line)
    2. drama-3       (bare line, no direction)
    3. drama-3       ("[direction] line")
  and plays them in the browser as 16 kHz WAV (what the device speaker will get) or 44.1 kHz.
- Caches audio in bridge/cache/ by hash of (model, voice, text, rate), logs every call to
  bridge/audition.jsonl, and shows the exact request (key redacted) so it can go on screen.
- "Pick for Pip" writes FISH_VOICE_ID into .env.

Secrets stay in .env on the Mac. The page talks only to this server on localhost.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
CACHE = Path(__file__).resolve().parent / "cache"
LOG = Path(__file__).resolve().parent / "audition.jsonl"
PAGE = Path(__file__).resolve().parent / "audition.html"
FISH = "https://api.fish.audio"
PORT = 8790


def read_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if not ENV_PATH.exists():
        return env
    for raw in ENV_PATH.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def write_env_value(key: str, value: str) -> None:
    """Replace KEY=... in .env in place (keeps comments and order); append if missing."""
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    done = False
    for i, line in enumerate(lines):
        if re.match(rf"^\s*{re.escape(key)}\s*=", line):
            lines[i] = f"{key}={value}"
            done = True
    if not done:
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n")
    try:
        os.chmod(ENV_PATH, 0o600)
    except OSError:
        pass


ENV = read_env()
API_KEY = ENV.get("FISH_API_KEY", "")
if not API_KEY:
    sys.exit("FISH_API_KEY is empty in .env")
DRAMA = ENV.get("FISH_DRAMA_MODEL", "drama-3")
STANDARD = ENV.get("FISH_STANDARD_MODEL", "s2.1-pro-free")
ALLOWED_MODELS = {DRAMA, STANDARD, "drama-3", "s2.1-pro-free", "s2.1-pro", "s2-pro"}
CACHE.mkdir(exist_ok=True)

app = FastAPI(title="Pip voice audition")
client = httpx.AsyncClient(base_url=FISH, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=60)


def slim(m: dict) -> dict:
    samples = m.get("samples") or []
    return {
        "id": m.get("_id"),
        "title": m.get("title") or "(untitled)",
        "description": (m.get("description") or "")[:160],
        "tags": (m.get("tags") or [])[:8],
        "languages": m.get("languages") or [],
        "task_count": m.get("task_count") or 0,
        "like_count": m.get("like_count") or 0,
        "author": (m.get("author") or {}).get("nickname") or "",
        "preview": samples[0].get("audio") if samples else None,
        "preview_text": (samples[0].get("text") or "")[:120] if samples else "",
        "cover": f"https://public-platform.r2.fish.audio/{m['cover_image']}" if m.get("cover_image") else None,
    }


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return PAGE.read_text()


@app.get("/api/config")
async def config() -> dict:
    env = read_env()
    return {
        "drama_model": DRAMA,
        "standard_model": STANDARD,
        "voice_id": env.get("FISH_VOICE_ID", ""),
        "pet_name": env.get("PET_NAME", "Pip"),
        "sample_rate": int(env.get("AUDIO_SAMPLE_RATE", "16000") or 16000),
    }


@app.get("/api/voices")
async def voices(q: str = "", sort: str = "task_count", page: int = 1, tag: str = "", licensed: bool = False, n: int = 12) -> dict:
    params: dict = {"language": "en", "page_size": max(1, min(n, 24)), "page_number": max(1, page), "sort_by": sort}
    if q.strip():
        params["title"] = q.strip()
    if tag.strip():
        params["tag"] = tag.strip()
    if licensed:
        params["licensed"] = "true"
    r = await client.get("/model", params=params)
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text[:300])
    d = r.json()
    return {"total": d.get("total"), "has_more": d.get("has_more"), "items": [slim(m) for m in d.get("items", [])]}


@app.get("/api/voice/{voice_id}")
async def voice(voice_id: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{32}", voice_id):
        raise HTTPException(400, "voice id should be 32 hex characters")
    r = await client.get(f"/model/{voice_id}")
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text[:300])
    return slim(r.json())


def cache_key(model: str, voice_id: str, text: str, rate: int) -> str:
    return hashlib.sha256(f"{model}\x00{voice_id}\x00{text}\x00{rate}".encode()).hexdigest()[:24]


@app.post("/api/tts")
async def tts(req: Request) -> Response:
    body = await req.json()
    model = str(body.get("model") or DRAMA)
    voice_id = str(body.get("voice_id") or "")
    text = str(body.get("text") or "").strip()
    rate = int(body.get("sample_rate") or 16000)
    if model not in ALLOWED_MODELS:
        raise HTTPException(400, f"unknown model {model}")
    if not re.fullmatch(r"[0-9a-f]{32}", voice_id):
        raise HTTPException(400, "voice id should be 32 hex characters")
    if not text:
        raise HTTPException(400, "empty text")
    if rate not in (8000, 16000, 24000, 32000, 44100):
        raise HTTPException(400, "bad sample rate")

    payload = {"text": text, "reference_id": voice_id, "format": "wav", "sample_rate": rate, "latency": "balanced"}
    # The request we made, with the key redacted, for showing on screen.
    shown = (
        "curl -X POST https://api.fish.audio/v1/tts \\\n"
        "  -H 'Authorization: Bearer $FISH_API_KEY' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        f"  -H 'model: {model}' \\\n"
        f"  -d '{json.dumps(payload, ensure_ascii=False)}'"
    )
    key = cache_key(model, voice_id, text, rate)
    path = CACHE / f"{key}.wav"
    cached = path.exists() and path.stat().st_size > 44
    t0 = time.perf_counter()
    status = 200
    err = ""
    if not cached:
        # Always send the model header explicitly: a missing/misspelt header silently falls back to s2.1-pro.
        r = await client.post("/v1/tts", json=payload, headers={"model": model})
        status = r.status_code
        if status != 200:
            err = r.text[:400]
        else:
            path.write_bytes(r.content)
    ms = int((time.perf_counter() - t0) * 1000)
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": model,
        "voice_id": voice_id,
        "text": text,
        "sample_rate": rate,
        "cached": cached,
        "latency_ms": ms,
        "status": status,
        "bytes": path.stat().st_size if path.exists() else 0,
        "error": err,
    }
    with LOG.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[tts] model={model} voice={voice_id} rate={rate} cached={cached} {ms} ms status={status} {err}", flush=True)
    if status != 200:
        return JSONResponse({"error": err or f"Fish returned {status}", "status": status, "request": shown}, status_code=502)
    headers = {
        "X-Model": model,
        "X-Latency-Ms": str(ms),
        "X-Cache": "hit" if cached else "miss",
        "X-Request": json.dumps(shown),
        "Cache-Control": "no-store",
    }
    return FileResponse(path, media_type="audio/wav", headers=headers)


@app.post("/api/pick")
async def pick(req: Request) -> dict:
    body = await req.json()
    voice_id = str(body.get("voice_id") or "")
    if not re.fullmatch(r"[0-9a-f]{32}", voice_id):
        raise HTTPException(400, "voice id should be 32 hex characters")
    write_env_value("FISH_VOICE_ID", voice_id)
    title = str(body.get("title") or "")
    with LOG.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "picked": voice_id, "title": title}) + "\n")
    print(f"[pick] FISH_VOICE_ID={voice_id} ({title}) written to .env", flush=True)
    return {"ok": True, "voice_id": voice_id}


if __name__ == "__main__":
    import uvicorn

    print(f"Pip voice audition  ->  http://127.0.0.1:{PORT}   (drama={DRAMA}, standard={STANDARD})", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
