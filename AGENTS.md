# drama3-esp32: agent rules

You are building **Pip**, an AI-age tamagotchi.
Pip lives on an **ESP-Mosaico** tile (ESP32-S31). It has a cute cartoon face on its screen, it watches
Mike through its camera, reads his mood, and talks to him in a **Fish Audio Drama 3** voice whose
performance matches what it sees. Poke it and it reacts. Pick it up or shake it and it reacts. It knows
the channel's live YouTube stats. It must be **cute and lovable** above everything else.

Prefer the version that works reliably and looks great over the clever one. Small steps, each one visibly working before the next.

## Architecture (do not change without asking)

```
 ESP-Mosaico (body)                          Computer (brain)    bridge/  Python, FastAPI
 ------------------                          -------------------------------------------
 face UI (GSP SVG morphs, 480x480)           POST /react?event=<name>   (ONE call per reaction)
 touch  -> poke | hold                         header X-Pet-Key, body = JPEG camera frame (optional)
 IMU    -> shake | pickup | flip | putdown          |
 camera -> look (every N s)                  Claude (vision: reads Mike's mood) writes
 timer  -> idle | stats                        {face, direction, line}
                                             Fish Audio API, model drama-3, "[direction] line"
 speaker <- raw PCM                <------   200: body = raw PCM 16-bit mono 16 kHz (streamed)
 face    <- X-Face header                         headers X-Face, X-Line, X-Mood-Rgb
                                             204: nothing to say (face-only change via X-Face)
                                             YouTube Data API -> views/subs for stats lines
```

- One request per reaction: the device POSTs the event (with a fresh camera JPEG when it has one) and
  plays the PCM as it streams back. This shape is already built in `firmware/`.
- **Secrets never go on the device** except Wi-Fi and the bridge address/secret. All API keys stay in
  `.env` on your computer and are read by the bridge only.
- The device sends header `X-Pet-Key: $BRIDGE_SHARED_SECRET`; the bridge rejects anything else.
- The bridge picks an **expression name** from a fixed set (below). The device never decides what to
  say; it only plays faces and sound.
- Expression set (shared contract, keep in sync on both sides):
  `idle, happy, surprised, dizzy, sad, love, sleepy, talking`.

## The character

**F1 Pom-pom**: the fluffy peach puffball bear cub, `design/faces/firefly/F1_pompom.png` (6-state sheet:
idle, happy, surprised, dizzy, sad, love). It is a raster concept: rebuild it on the device as simple
vector shapes (round fluffy body with a scalloped edge, two round ears, big eyes, small mouth, blush) using
GSP SVG morphs, matching the colours of the sheet. Keep it cute above all.

## Folder map

| Path | What |
|---|---|
| `.env` | All keys and settings. Read it, never print secret values, never commit it. |
| `bridge/` | The brain server (Python 3.11+, FastAPI, uvicorn, httpx, anthropic). Use a venv in `bridge/.venv`. |
| `firmware/` | The ESP-Mosaico app. Build it as `projects/drama_pet` inside your ESP-Mosaico workspace. |
| Fish Audio docs | https://docs.fish.audio : if the `model` header is missing or misspelt Fish falls back to s2.1-pro, so log the model on every call. |
| ESP-Mosaico docs | Espressif's ESP-Mosaico guide and the BSP/GSP docs in your ESP-Mosaico workspace. |
| `design/faces/` | Face concepts and the final expression sheet; the firmware draws the chosen character. |
| `prompts/STEP_BY_STEP.md` | The build, one prompt per step. |

## Firmware rules (ESP-Mosaico)

- The firmware project lives inside your ESP-Mosaico workspace as `projects/drama_pet`.
  **Before any firmware work, read the workspace's own `AGENTS.md` files and follow them.** They win over this file for firmware.
- Load the ESP-IDF environment and run `mosaico.py` from the workspace root.
- Test UI in the simulator before the device.
- Device writes go **only** through `python mosaico.py` (`iris system-update` for new UI/resources,
  `iris app-update` for code only). Never `idf.py flash` or `esptool`.
- Use `python mosaico.py iris screenshot` to SEE the screen and `iris logs` to read logs. Check your own work.
- GSP callbacks run on the render task: never block or do networking in them. Networking, camera and audio
  run in their own tasks; the UI polls results from a timer.
- C only. Do not invent APIs: check headers in `submodule/esp-mosaico-bsp/components/` and the ESP-Mosaico docs.
- Camera module goes in the **LEFT** slot only. Never hot-remove a module. The kit camera (SC101IOT) outputs
  YUV only: scale with PPA to 480x480 then use the chip's hardware JPEG encoder.
  If frames come out corrupt, disable USB Serial/JTAG in `sdkconfig.defaults` (GPIO33 clash).
- Audio: ES8311 at 16 kHz mono 16-bit for both speaker and mic (shared I2S port).
- Face: use GSP SVG `morph_to` animations (blink, mouth flap, squash/stretch). Full-frame raster
  animation will not fit the 1 MB `ui_apps` partition.
- Run tethered on a solid 5 V supply: the battery is 65 mAh.
- Wi-Fi is 2.4 GHz. Generate `main/secrets.h` (git-ignored) from `.env` with a script; do not hand-copy secrets.

## Voice rules (Fish Audio Drama 3)

- Every spoken line = `[stage direction] line`. The direction is free text describing the performance
  (e.g. `[gasping, scandalised, then giggling]`). Use the paired tags from the Fish Audio docs on single
  words where it adds comedy (`<whisper>`, `<emphasis>`, ...). Only use tags the docs list.
- Lines are SHORT: 3 to 14 words. Pip is a small creature, not a narrator.
- Pip is kind. It can tease Mike but never insults him or comments on his body or appearance negatively.
  Mood reads are about expression and energy ("you look tired", "that's a big grin"), never looks.
- Cache audio by hash of (model, voice, text) in `bridge/cache/` so repeats are instant.
- Log every turn (event, what Claude saw, line, direction, latency) to `bridge/turns.jsonl`.

## How to work

- Small steps. After each step: run it, show the human the result (sim screenshot, device screenshot, a WAV
  played with `afplay`), and stop for their go before the next step.
- If something fails twice the same way, stop and explain; don't thrash.
- Keep a short log of what changed in `BUILD_LOG.md` (newest at top).
