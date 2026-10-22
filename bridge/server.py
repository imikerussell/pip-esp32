"""Pip's brain. FastAPI bridge between the ESP-Mosaico body and Claude + Fish Audio (+ YouTube stats).

Contract (AGENTS.md):
  POST /react?event=<name>   header X-Pet-Key: $BRIDGE_SHARED_SECRET   body: optional JPEG camera frame
  200 -> body = raw PCM s16le mono AUDIO_SAMPLE_RATE, streamed; headers X-Face, X-Line, X-Mood-Rgb
  204 -> nothing to say (face-only change via X-Face)

Events from the device: boot, poke, hold, stats (double tap), pickup, shake, flip, putdown, look (camera), idle.
Per event Claude (BRAIN_MODEL) writes {face, direction, line, speak, saw, present}; Fish drama-3 renders
"[direction] line". Looks only speak when Mike's mood changes or something new happens. Nobody seen for
SLEEP_AFTER_S -> Pip falls asleep (silent sleepy face) and wakes with a line when Mike reappears.
SHOWTIME=1 in .env: touch/motion reactions come from a pre-generated, pre-rendered pool (instant), looks use
BRAIN_FAST_MODEL. Audio cache: bridge/cache/<hash of model, voice, text, rate>.pcm. Turns: bridge/turns.jsonl.

Run (from the project root):  bridge/.venv/bin/python bridge/server.py      live B-roll log: bridge/live_log.py
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import random
import re
import sys
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import anthropic
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CACHE = HERE / "cache"
LOOKS = HERE / "looks"
TURNS = HERE / "turns.jsonl"
FISH_URL = "https://api.fish.audio/v1/tts"
YT = "https://www.googleapis.com/youtube/v3"

EXPRESSIONS = ["idle", "happy", "surprised", "dizzy", "sad", "love", "sleepy", "talking"]
FACES = EXPRESSIONS[:-1]           # talking is the mouth animation, not a choice
MOOD_RGB = {"idle": "F08A4E", "happy": "FFC24A", "surprised": "FFE066", "dizzy": "B39DFF",
            "sad": "7FB2FF", "love": "FF6F91", "sleepy": "8F8FB3", "talking": "F08A4E"}
POOLED = ("poke", "hold", "pickup", "shake", "flip", "putdown")
SLEEP_AFTER_S = 120

EVENTS = {
    "boot": "Pip was just switched on and is waking up for the first time today.",
    "poke": "Mike tapped Pip's face with his finger.",
    "hold": "Mike is pressing and holding his finger on Pip's face, like a gentle pat.",
    "stats": "Mike double-tapped Pip to ask how the YouTube channel is doing.",
    "pickup": "Mike just picked Pip up off the desk. Pip is suddenly in the air.",
    "shake": "Mike is shaking Pip around. Pip is very dizzy.",
    "flip": "Mike turned Pip upside down. Pip is hanging upside down and panicking.",
    "putdown": "Mike gently put Pip back down on the desk. Pip is relieved to be safe.",
    "look": "Pip glanced at Mike through its camera.",
    "wake": "Pip was asleep because nobody was around, and just saw Mike come back.",
    "idle": "Nothing has happened for a while; it is quiet on the desk.",
    "test": "A test from the developer.",
}


def read_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in (ROOT / ".env").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = read_env()
for key in ("FISH_API_KEY", "ANTHROPIC_API_KEY", "FISH_VOICE_ID", "BRIDGE_SHARED_SECRET"):
    if not ENV.get(key):
        sys.exit(f"{key} is empty in .env")

FISH_MODEL = ENV.get("FISH_DRAMA_MODEL", "drama-3")
VOICE = ENV["FISH_VOICE_ID"]
RATE = int(ENV.get("AUDIO_SAMPLE_RATE", "16000") or 16000)
BRAIN_MODEL = ENV.get("BRAIN_MODEL", "claude-sonnet-5")
BRAIN_FAST_MODEL = ENV.get("BRAIN_FAST_MODEL", "")
PET_NAME = ENV.get("PET_NAME", "Pip")
SECRET = ENV["BRIDGE_SHARED_SECRET"]
HOST = "0.0.0.0"
PORT = int(ENV.get("BRIDGE_PORT", "8787") or 8787)
SHOWTIME = ENV.get("SHOWTIME", "0").lower() in ("1", "true", "yes", "on")
COOLDOWN_S = float(ENV.get("SPEAK_COOLDOWN_SECONDS", "6") or 6)
YT_KEY = ENV.get("YOUTUBE_API_KEY", "")
YT_CHANNEL = ENV.get("YOUTUBE_CHANNEL_ID", "")
YT_POLL_S = max(60, int(ENV.get("YOUTUBE_POLL_SECONDS", "120") or 120))
POOL_SIZE = 2

CACHE.mkdir(exist_ok=True)
LOOKS.mkdir(exist_ok=True)
claude = anthropic.AsyncAnthropic(api_key=ENV["ANTHROPIC_API_KEY"], timeout=25.0, max_retries=1)
fish = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0),
                         headers={"Authorization": f"Bearer {ENV['FISH_API_KEY']}"})


class Memory:
    """Short memory so Pip can refer back ("you poked me AGAIN") and never repeats itself."""

    def __init__(self) -> None:
        self.lines: deque[str] = deque(maxlen=30)
        self.events: deque[tuple[float, str]] = deque(maxlen=12)
        self.last_saw = ""
        self.last_present = time.time()
        self.asleep = False
        self.last_spoke = 0.0
        self.stats: dict | None = None
        self.stats_said: dict | None = None

    def note_event(self, event: str) -> None:
        self.events.append((time.time(), event))

    def summary(self) -> str:
        now = time.time()
        recent = [f"{e} ({int(now - t)}s ago)" for t, e in self.events if e != "look"][-8:]
        pokes = sum(1 for t, e in self.events if e == "poke" and now - t < 180)
        parts = [f"Recent happenings, oldest first: {', '.join(recent) or 'none'}."]
        if pokes >= 2:
            parts.append(f"Mike has poked Pip {pokes} times in the last 3 minutes.")
        if self.last_saw:
            parts.append(f"Last time Pip looked, it saw: {self.last_saw}")
        return " ".join(parts)


MEM = Memory()
busy = asyncio.Lock()
pool: dict[str, deque[dict]] = {e: deque() for e in POOLED}
pool_lock = asyncio.Lock()

SYSTEM = f"""You are {PET_NAME}, a tiny fluffy peach bear-cub puffball who lives on a little square screen on \
Mike's desk. Mike makes YouTube videos (the Creator Magic channel). You are cute, cosy, dramatic, kind and a \
little cheeky, like a beloved cartoon side-kick. You react out loud to what just happened to you.

Each turn you get one event (and sometimes a photo from your camera). Reply with:
- face: one of {", ".join(FACES)} (the face you pull; your mouth animates by itself while you talk).
- direction: a short stage direction for a voice actor: emotion, energy, pace, breaths, sounds. \
Example: gasping, scandalised, then dissolving into giggles. No quotes, no brackets.
- line: what you say, 3 to 14 words. Spoken English, playful, specific.
- speak: true to say the line out loud, false to stay quiet and only change your face.
- saw: one short sentence on what the photo shows about Mike's expression, energy, posture and what he is \
doing, or "nobody" if no person is visible, or "no photo".
- present: true if a person is visible in the photo (or there is no photo).

Rules:
- Be kind. Tease gently, never insult. Never comment on anyone's body, looks, clothes or appearance. Read only \
expression and energy: "you look tired", "that's a big grin", "you're frowning at the screen".
- Never repeat or closely paraphrase any of your recent lines. Vary openings, jokes and sounds.
- Fit the physical event: dizzy when shaken, panicking when upside down, relieved when put down, giggly or \
indignant when poked, melting when held. Refer back to recent happenings when it is funny ("AGAIN?!").
- Match Mike's mood when you can see him: tired -> gentle and cosy, grinning -> excited, frowning -> \
dramatically worried for him.
- YouTube numbers: only ever say figures given to you in this message. Never invent or round up numbers.
- You may wrap one or two words in one of these tags: <whisper>..</whisper>, <emphasis>..</emphasis>, \
<soft>..</soft>, <fast>..</fast>, <slow>..</slow>, <stress>..</stress>, <forceful>..</forceful>. No other tags, \
no emoji. Sounds like a giggle or gasp belong in the direction, not the line.
- Keep it short. You are a small creature, not a narrator."""

SCHEMA = {
    "type": "object",
    "properties": {
        "face": {"type": "string", "enum": FACES},
        "direction": {"type": "string"},
        "line": {"type": "string"},
        "speak": {"type": "boolean"},
        "saw": {"type": "string"},
        "present": {"type": "boolean"},
    },
    "required": ["face", "direction", "line", "speak", "saw", "present"],
    "additionalProperties": False,
}
ALLOWED_TAGS = ("whisper", "emphasis", "soft", "fast", "slow", "stress", "forceful")


def clean_line(line: str) -> str:
    def keep(m: re.Match) -> str:
        return m.group(0) if m.group(1).lower() in ALLOWED_TAGS else ""
    line = re.sub(r"</?([a-zA-Z]+)>", keep, line)
    return re.sub(r"\s+", " ", line).strip()


def subtitle(line: str) -> str:
    text = re.sub(r"</?[a-zA-Z]+>", "", line)
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("—", "-"),
                 ("…", "...")):
        text = text.replace(a, b)
    return text.encode("ascii", "ignore").decode()[:120]


def fmt(n: int) -> str:
    return f"{n:,}"


def stats_text() -> str:
    s = MEM.stats
    if not s:
        return "YouTube numbers are not available right now; do not mention any numbers."
    out = [f"Live YouTube numbers for Creator Magic (from the API just now): {fmt(s['subs'])} subscribers "
           f"(YouTube rounds this), {fmt(s['views'])} total views, {fmt(s['videos'])} videos."]
    if s.get("latest_title"):
        out.append(f"Latest video \"{s['latest_title']}\" has {fmt(s['latest_views'])} views.")
    prev = MEM.stats_said
    if prev:
        dv, dl = s["views"] - prev["views"], s.get("latest_views", 0) - prev.get("latest_views", 0)
        mins = max(1, int((s["ts"] - prev["ts"]) / 60))
        out.append(f"Since Pip last mentioned the numbers ({mins} min ago): {dv:+,} total views, "
                   f"{dl:+,} on the latest video, {s['subs'] - prev['subs']:+,} subscribers.")
    out.append("New subscribers or a jump in views = celebration; a flat quiet spell = a tiny tragedy.")
    return " ".join(out)


async def youtube_poller() -> None:
    if not (YT_KEY and YT_CHANNEL):
        print("[yt] no YOUTUBE_API_KEY / YOUTUBE_CHANNEL_ID; stats disabled", flush=True)
        return
    async with httpx.AsyncClient(timeout=10) as yt:
        while True:
            try:
                r = (await yt.get(f"{YT}/channels", params={"part": "statistics,contentDetails", "id": YT_CHANNEL,
                                                            "key": YT_KEY})).json()
                item = r["items"][0]
                st = item["statistics"]
                stats = {"ts": time.time(), "subs": int(st["subscriberCount"]), "views": int(st["viewCount"]),
                         "videos": int(st["videoCount"])}
                uploads = item["contentDetails"]["relatedPlaylists"]["uploads"]
                pl = (await yt.get(f"{YT}/playlistItems", params={"part": "contentDetails", "maxResults": 1,
                                                                  "playlistId": uploads, "key": YT_KEY})).json()
                vid = pl["items"][0]["contentDetails"]["videoId"]
                v = (await yt.get(f"{YT}/videos", params={"part": "statistics,snippet", "id": vid,
                                                          "key": YT_KEY})).json()["items"][0]
                stats.update(latest_title=v["snippet"]["title"][:80], latest_views=int(v["statistics"]["viewCount"]))
                MEM.stats = stats
                print(f"[yt] {fmt(stats['subs'])} subs, {fmt(stats['views'])} views, latest "
                      f"{fmt(stats['latest_views'])} views", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[yt] poll failed: {type(e).__name__}: {e}", flush=True)
            await asyncio.sleep(YT_POLL_S)


async def think(event: str, jpeg: bytes | None, model_pref: str | None = None, generic: bool = False) -> tuple[dict, str, float]:
    what = EVENTS.get(event, f"Event: {event}.")
    content: list[dict] = []
    if jpeg:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                     "data": base64.standard_b64encode(jpeg).decode()}})
    extra = []
    if event == "look":
        extra.append("Only set speak=true if Mike's mood or energy clearly changed since last time, or something "
                     "new is happening (he started doing something, someone new appeared). Otherwise speak=false "
                     "and just pick a face that mirrors his mood.")
    else:
        extra.append("This event always deserves a spoken reaction: speak=true.")
    if event in ("stats", "idle"):
        extra.append(stats_text())
    if not jpeg:
        extra.append("There is no photo this time: saw='no photo', present=true.")
    history = "\n".join(f"- {l}" for l in MEM.lines) or "(none yet)"
    memory = "This line will be used later at a random moment, so keep it generic to the event." if generic \
        else MEM.summary()
    content.append({"type": "text", "text": (f"Event: {event}. {what}\n{memory}\n" + "\n".join(extra) +
                                             f"\nYour recent lines (never repeat these):\n{history}")})
    t0 = time.perf_counter()
    models = [m for m in ((model_pref or BRAIN_MODEL), BRAIN_FAST_MODEL, BRAIN_MODEL) if m]
    last_err: Exception | None = None
    for model in dict.fromkeys(models):
        try:
            cfg: dict = {"format": {"type": "json_schema", "schema": SCHEMA}}
            if "haiku-4-5" not in model:
                cfg["effort"] = "low"
            resp = await claude.messages.create(model=model, max_tokens=2000, system=SYSTEM,
                                                messages=[{"role": "user", "content": content}], output_config=cfg)
            if resp.stop_reason == "refusal":
                raise RuntimeError("refusal")
            data = json.loads(next(b.text for b in resp.content if b.type == "text"))
            return data, model, time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"[brain] {model} failed: {type(e).__name__}: {e}", flush=True)
    raise RuntimeError(f"brain unavailable: {last_err}")


def shape(reply: dict) -> tuple[str, str, str, str]:
    face = reply.get("face") if reply.get("face") in FACES else "idle"
    direction = re.sub(r"[\[\]]", "", str(reply.get("direction", ""))).strip()[:160]
    line = clean_line(str(reply.get("line", "")))[:200]
    return face, direction, line, (f"[{direction}] {line}" if direction else line)


def cache_path(text: str) -> Path:
    key = hashlib.sha256(f"{FISH_MODEL}\x00{VOICE}\x00{text}\x00{RATE}".encode()).hexdigest()[:24]
    return CACHE / f"{key}.pcm"


async def fish_stream(text: str, stats: dict) -> AsyncIterator[bytes]:
    """Stream PCM from the cache or Fish, always in whole 16-bit samples."""
    path = cache_path(text)
    t0 = time.perf_counter()
    if path.exists() and path.stat().st_size > 0:
        stats.update(cached=True, fish_ttfb_ms=0)
        data = path.read_bytes()
        stats["bytes"] = len(data)
        for i in range(0, len(data), 4096):
            yield data[i:i + 4096]
        return
    stats["cached"] = False
    body = {"text": text, "reference_id": VOICE, "format": "pcm", "sample_rate": RATE, "latency": "balanced"}
    buf, carry = bytearray(), b""
    print(f"[fish] POST /v1/tts model={FISH_MODEL} voice={VOICE} rate={RATE}", flush=True)
    async with fish.stream("POST", FISH_URL, json=body, headers={"model": FISH_MODEL}) as r:
        if r.status_code != 200:
            stats["fish_error"] = f"{r.status_code} {(await r.aread())[:300]!r}"
            print(f"[fish] error {stats['fish_error']}", flush=True)
            return
        async for chunk in r.aiter_bytes():
            stats.setdefault("fish_ttfb_ms", int((time.perf_counter() - t0) * 1000))
            chunk = carry + chunk
            even = len(chunk) & ~1
            carry = chunk[even:]
            if even:
                buf += chunk[:even]
                yield chunk[:even]
    stats["bytes"] = len(buf)
    if buf:
        path.write_bytes(bytes(buf))


async def prerender(text: str) -> None:
    async for _ in fish_stream(text, {}):
        pass


async def refill_pool() -> None:
    """SHOWTIME: keep POOL_SIZE ready-to-play reactions per touch/motion event (Claude + Fish done ahead)."""
    async with pool_lock:
        for event in POOLED:
            while len(pool[event]) < POOL_SIZE:
                try:
                    reply, model, _ = await think(event, None, generic=True)
                    face, direction, line, text = shape(reply)
                    await prerender(text)
                    MEM.lines.append(line)
                    pool[event].append({"face": face, "direction": direction, "line": line, "text": text,
                                        "model": model})
                    print(f"[pool] {event}: {line}", flush=True)
                except Exception as e:  # noqa: BLE001
                    print(f"[pool] {event} failed: {e}", flush=True)
                    break


def log_turn(rec: dict) -> None:
    with TURNS.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def silent(face: str, rec: dict) -> Response:
    rec.update(face=face, speak=False)
    log_turn(rec)
    return Response(status_code=204, headers={"X-Face": face, "X-Mood-Rgb": MOOD_RGB.get(face, "F08A4E")})


@asynccontextmanager
async def lifespan(_app: FastAPI):
    tasks = [asyncio.create_task(youtube_poller())]
    if SHOWTIME:
        tasks.append(asyncio.create_task(refill_pool()))
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(title="Pip bridge", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "pet": PET_NAME, "brain": BRAIN_MODEL, "voice_model": FISH_MODEL, "voice": VOICE,
            "showtime": SHOWTIME, "asleep": MEM.asleep, "pool": {e: len(q) for e, q in pool.items()},
            "stats": MEM.stats}


@app.post("/react")
async def react(request: Request, event: str = "poke") -> Response:
    if request.headers.get("x-pet-key") != SECRET:
        raise HTTPException(401, "bad pet key")
    event = re.sub(r"[^a-z_]", "", event.lower())[:16] or "poke"
    body = await request.body()
    jpeg = body if body[:2] == b"\xff\xd8" else None
    now = time.time()
    t0 = time.perf_counter()
    rec: dict = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, "showtime": SHOWTIME,
                 "jpeg_bytes": len(jpeg) if jpeg else 0, "client": request.client.host if request.client else ""}
    if jpeg:
        (LOOKS / "last.jpg").write_bytes(jpeg)
    if busy.locked():
        rec["skipped"] = "busy"
        log_turn(rec)
        return Response(status_code=204)
    if event != "look":
        MEM.note_event(event)
    if event == "idle" and MEM.asleep:
        return silent("sleepy", rec)

    async with busy:
        reply = None
        if SHOWTIME and event in POOLED and pool[event] and not jpeg_needed(event):
            reply = pool[event].popleft()
            rec.update(brain_model=f"pool/{reply['model']}", brain_ms=0, saw="(pooled)")
            asyncio.create_task(refill_pool())
            face, direction, line, text = reply["face"], reply["direction"], reply["line"], reply["text"]
            speak = True
        else:
            woke = False
            if MEM.asleep and event != "look":
                MEM.asleep, woke = False, True
            model_pref = BRAIN_FAST_MODEL if (SHOWTIME and event == "look" and BRAIN_FAST_MODEL) else None
            try:
                data, model, brain_s = await think(event, jpeg, model_pref)
            except Exception as e:  # noqa: BLE001
                rec["error"] = str(e)
                log_turn(rec)
                return JSONResponse({"error": "brain unavailable"}, status_code=503, headers={"X-Face": "sleepy"})
            face, direction, line, text = shape(data)
            speak = bool(data.get("speak")) or event != "look"
            saw = str(data.get("saw", ""))[:200]
            rec.update(brain_model=model, brain_ms=int(brain_s * 1000), saw=saw, present=data.get("present"))
            if event == "look":
                if data.get("present") is False:
                    if now - MEM.last_present > SLEEP_AFTER_S:
                        if not MEM.asleep:
                            print("[pip] nobody around for a while: falling asleep", flush=True)
                        MEM.asleep = True
                        return silent("sleepy", rec)
                    return silent("idle" if face == "sleepy" else face, rec)
                MEM.last_present = now
                if MEM.asleep:          # Mike came back: wake up with a line
                    MEM.asleep, woke = False, True
                    data, model, brain_s = await think("wake", jpeg, model_pref)
                    face, direction, line, text = shape(data)
                    speak = True
                    rec.update(event="look/wake", brain_ms=rec["brain_ms"] + int(brain_s * 1000))
                elif speak and now - MEM.last_spoke < COOLDOWN_S:
                    speak = False
                MEM.last_saw = saw or MEM.last_saw
            else:
                MEM.last_present = now
            if woke:
                rec["woke"] = True
            if event in ("stats", "idle") and MEM.stats:
                MEM.stats_said = dict(MEM.stats)
        if not speak:
            rec.update(direction=direction, line=line)
            return silent(face, rec)
        MEM.lines.append(line)
        MEM.last_spoke = time.time()
        rec.update(face=face, speak=True, direction=direction, line=line, tts_model=FISH_MODEL, voice=VOICE,
                   text=text)
        print(f"[turn] {rec['event']} -> {face} | [{direction}] {line} | brain {rec.get('brain_ms')} ms "
              f"({rec.get('brain_model')})", flush=True)

    stats: dict = {}

    async def body_iter() -> AsyncIterator[bytes]:
        try:
            async for chunk in fish_stream(text, stats):
                yield chunk
        finally:
            rec.update(stats)
            rec["total_ms"] = int((time.perf_counter() - t0) * 1000)
            log_turn(rec)

    return StreamingResponse(body_iter(), media_type="audio/pcm", headers={
        "X-Face": face, "X-Line": subtitle(line), "X-Mood-Rgb": MOOD_RGB.get(face, "F08A4E"),
        "X-Sample-Rate": str(RATE), "Cache-Control": "no-store"})


def jpeg_needed(event: str) -> bool:
    return False   # pooled touch/motion reactions don't depend on the camera


if __name__ == "__main__":
    import uvicorn

    print(f"{PET_NAME} bridge on http://{ENV.get('BRIDGE_HOST', HOST)}:{PORT}  brain={BRAIN_MODEL} "
          f"fast={BRAIN_FAST_MODEL or '-'}  voice={FISH_MODEL}/{VOICE}  SHOWTIME={'ON' if SHOWTIME else 'off'}",
          flush=True)
    random.seed()
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
