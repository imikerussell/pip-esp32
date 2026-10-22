"""Fake a device event against the bridge and play Pip's reply on the Mac.

    bridge/.venv/bin/python bridge/fake_event.py poke        (also: hold, pickup, shake, flip, putdown, boot)
    bridge/.venv/bin/python bridge/fake_event.py poke --no-play

Prints the face, line and timings, saves the reply as bridge/last_reply.wav and plays it with afplay.
"""
from __future__ import annotations

import subprocess
import sys
import time
import wave
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from server import ENV, PORT, RATE, SECRET  # noqa: E402  (reads .env the same way)


def main() -> int:
    event = next((a for a in sys.argv[1:] if not a.startswith("-")), "poke")
    play = "--no-play" not in sys.argv
    host = ENV.get("BRIDGE_HOST", "127.0.0.1")
    url = f"http://{host}:{PORT}/react?event={event}"
    t0 = time.perf_counter()
    first = None
    pcm = bytearray()
    with httpx.stream("POST", url, headers={"X-Pet-Key": SECRET}, timeout=60) as r:
        hdr_ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code != 200:
            print(f"{event}: HTTP {r.status_code} face={r.headers.get('x-face')} {r.read()[:200]!r}")
            return 1
        for chunk in r.iter_bytes():
            if first is None:
                first = int((time.perf_counter() - t0) * 1000)
            pcm += chunk
        face, line = r.headers.get("x-face"), r.headers.get("x-line")
    total = int((time.perf_counter() - t0) * 1000)
    secs = len(pcm) / 2 / RATE
    print(f"event   {event}\nface    {face}\nline    {line}\n"
          f"timing  headers {hdr_ms} ms, first audio {first} ms, done {total} ms, {secs:.1f} s of audio")
    out = HERE / "last_reply.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(pcm))
    if play and pcm:
        subprocess.run(["afplay", str(out)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
