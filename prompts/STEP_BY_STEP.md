# Build Pip, step by step

Open a terminal in the repo folder and start Claude Code there. Paste one prompt at a time.
Each step ends with something you can SEE or HEAR, which is your on-camera beat. Wait for it to work
before the next one.

Before step 0: fill in `.env` (Fish key, Anthropic key, YouTube key, Wi-Fi), plug the Mosaico into the
Studio by USB-C, camera module in the LEFT slot.

---

## Step 0: Get your bearings (off camera)

```
Read AGENTS.md, the Fish Audio API docs (https://docs.fish.audio) and your ESP-Mosaico workspace docs. Check .env has every value
filled in (tell me which are empty, never print the secret values). Run the ESP-Mosaico doctor and
tell me if the toolchain is ready and whether the device is plugged in. Don't build anything yet.
```

---

## Step 1: First words (the before/after)

```
Build the smallest possible Python script in bridge/say.py that sends one line to the Fish Audio API
and plays the result with afplay. Make it say this line twice:
first with our standard TTS model and no direction:
  "Oh. You're back. I missed you."
then with drama-3 and the direction
  "[gasps, then bursts into happy tears, trying to stay composed] Oh. You're back. I missed you."
Use FISH_VOICE_ID from .env. Show me the API request you made.
```
**Camera beat:** flat voice, then the Drama 3 one. Your face. That's the hook of the build.

---

## Step 2: Give it a face

```
Create the firmware project drama_pet with mosaico.py, starting from the working drama3_probe project
(read its code first), and symlink it to ./firmware. Draw the face from
design/faces/<PICKED CONCEPT> on the 480x480 screen using GSP: black background, the idle expression,
with a gentle blink every few seconds and a slow breathing bob. Build it, show it in the simulator and
send me a screenshot. Then recover the device into Vibe Mode if needed, install it with system-update
and take a screenshot from the real device.
```
**Camera beat:** the face blinks at you for the first time.

---

## Step 3: All the feelings

```
Add every expression in our contract (idle, happy, surprised, dizzy, sad, love, sleepy, talking) and a
smooth-enough transition between them. Talking = the mouth animates while audio plays. Add a debug mode
where tapping the screen cycles through the expressions. Screenshot each one from the simulator into
design/faces/built/ and show me a grid.
```

---

## Step 4: The brain

```
Build the bridge in bridge/ as a FastAPI server on BRIDGE_HOST:BRIDGE_PORT that follows the contract in
AGENTS.md: POST /react?event=..., optional JPEG body, X-Pet-Key auth, streamed PCM back. For each event Claude (BRAIN_MODEL)
writes Pip's reply as JSON {face, direction, line}, in Pip's personality: tiny, cute, dramatic, kind,
3 to 14 words. Then Fish drama-3 renders "[direction] line" as 16-bit mono PCM at AUDIO_SAMPLE_RATE.
Cache audio, log every turn to bridge/turns.jsonl. Give me a little test command that fakes a "poke"
and plays the audio on the Mac, so we can hear it before the device is involved.
```

---

## Step 5: Poke it

```
On the device: connect to Wi-Fi from secrets.h (generate it from .env), and when I tap the face, send a
"poke" event to the bridge, switch to the face it returns and stream the PCM through the
speaker with the talking mouth. Add a tiny buzz on the vibration motor when poked. If the bridge is
unreachable, show a sleepy face and don't crash. Install it and tell me when to poke.
```
**Camera beat:** first poke. It reacts out loud. Do it three times; it never says the same thing twice.

---

## Step 6: Pick me up

```
Use the IMU. Detect: picked up, shaken, turned upside down, and put back down. Send each as an event to
the bridge (with a cooldown so it doesn't spam). Shaken = dizzy face. Upside down = it panics.
Put down gently = relieved. Make sure the brain knows which one happened so the drama fits.
```
**Camera beat:** pick it up, shake it, flip it.

---

## Step 7: It can see me (the big one)

```
Turn on the camera. Every CAMERA_LOOK_SECONDS while idle, and immediately after any poke, grab a frame,
send it with a "look" event to /react. In the bridge, Claude looks at my face and energy (expression, posture, what
I'm doing, never judging appearance) and has Pip respond with a matching performance: if I look tired it
gets gentle and cosy, if I'm grinning it gets excited, if I frown it gets dramatically worried. Only speak
when my mood CHANGES or something new happens, otherwise stay quiet and just change face. Log what it saw.
```
**Camera beat:** act tired, then grin, then frown at the laptop. It follows you. This is the trailer payoff.

---

## Step 8: It knows the channel

```
Have the bridge poll the YouTube Data API for the channel's views and subscribers every YOUTUBE_POLL_SECONDS.
When I say nothing for a while, or when I double-tap, Pip comments on the numbers with drama: a new
subscriber is a celebration, a quiet hour is a tragedy. Add a "stats" face if it helps. Never invent numbers:
only say figures the API returned.
```

---

## Step 9: Make it lovable

```
Polish pass. Pip should feel alive: idle animations (looks around, yawns, falls asleep if nobody's there
for 2 minutes, wakes up when I appear on camera), a short memory of the last few things that happened so
it can refer back ("you poked me AGAIN"), no repeated lines, and a cosy personality. Keep every line short.
Show me 10 sample turns from turns.jsonl with latency, and fix anything slower than you'd want on camera.
```

---

## Step 10: Showtime mode (for the trailer)

```
Add a SHOWTIME flag in .env. When on, use the faster model where it helps, pre-warm the audio cache for
the common reactions, and print a big live log on the Mac (what it saw, what it said, latency) that looks
good on screen as B-roll. Then let's film.
```
