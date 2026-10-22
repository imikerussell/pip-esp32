# Drama3 face concepts

Ten face concepts for the 480x480 round-cornered AMOLED tile. Five hand-built in SVG by Zeus (`zeus/`), five generated with Adobe Firefly (`firefly/`). `CONTACT_SHEET.png` shows all ten side by side in the happy state.

All Zeus designs share one expression grammar, so the firmware state machine is identical whichever character wins:

| State | Trigger | Eyes | Mouth | Extras |
|---|---|---|---|---|
| idle | nothing happening | dots with a highlight (Mimi: closed, sleepy) | small smile | none |
| happy | general good vibes | closed upward arcs | open D smile + tongue | yellow sparkles, body bounces up 10 px |
| surprised | poked | big round eyes, two highlights | small O | yellow burst lines, body stretches tall |
| dizzy | shaken / picked up | spirals (opposite spin per eye) | wavy line | orbit ring + stars, body tilts 9 degrees |
| sad | camera sees Mike sad | smaller watery eyes + worried brows | frown | blue tear, body squashes down |
| love | camera sees Mike smiling | pink hearts | open smile | floating hearts, bigger blush |

Shared accent colours: sparkle yellow `#FFD23F`, heart pink `#FF4F8B`, tear blue `#6CC7FF`. Every cell is on `#000000`, and all key content sits inside the 18 px safe margin (dashed line on the sheets; not drawn in the per-state PNGs).

Files per concept: `NN_name.svg` (2x3 sheet, source of truth), `NN_name.png` (rendered sheet), `NN_name_<state>.png` (480x480 frames, states `idle happy surprised dizzy sad love`). Generator: `zfaces.py` builds everything; every shape is a circle, ellipse, rounded rect, quadratic arc or polyline, so it ports to LVGL or a hand-rolled canvas without a vector library.

## Zeus concepts

### 01 Mochi
- **Personality:** a soft, squishy rice-cake who wobbles at everything and forgives instantly.
- **Palette:** body `#FFEEF3`, under-shade `#F6CFDC`, ink `#3B2235`, blush `#FF8FB0`, tongue `#FF5C8A`, floor shadow `#2A1A22`.
- **Why it works on a tiny screen:** one big pale dome on black has the highest contrast of the set, so it reads from across a room. The face is just two dots and an arc, and squash/stretch on a single shape is the cheapest "drama" there is to animate.

### 02 Bolt
- **Personality:** an eager little helper bot that tries very hard and short-circuits when you shake it.
- **Palette:** head `#DCE3EE`, edge `#9AA7BC`, visor `#0E1424`, eye glow `#3DF5FF`, ear bolts `#FF6B6B`, antenna bulb changes per mood (yellow `#FFD23F`, pink `#FF4F8B`, blue `#6CC7FF`, purple `#B07CFF`, white).
- **Why it works on a tiny screen:** the face lives on a dark visor, so the cyan eyes glow on AMOLED and look great on camera. The antenna bulb is a free second mood channel the viewer reads at a glance.

### 03 Pip
- **Personality:** a retro pixel pet, half slime and half kitten, straight out of a 1997 keychain.
- **Palette:** body `#7CF06B`, outline `#2E9E4F`, highlight `#D4FFC4`, ink `#10241A`, blush `#FF8FB0`, tongue `#FF7FA8`.
- **Why it works on a tiny screen:** it is literally the original tamagotchi language, an 18x18 grid of 22 px blocks. Each expression is a few tiny sprites stamped onto one body, so it needs almost no memory and is pin-sharp at any scale. It is the strongest "tamagotchi" nod for the video.

### 04 Boo
- **Personality:** a shy little ghost who floats over when you are sad and hides when you poke it.
- **Palette:** body `#EEE8FF`, side shade `#CFC4F5`, ink `#231A3D`, blush `#FF9EC4`, floor shadow `#1C1830`.
- **Why it works on a tiny screen:** a ghost on a black screen looks like it is floating in the dark. The wavy hem gives you an idle animation for free (a slow bob plus a scallop wiggle), and the silhouette is instantly recognisable.

### 05 Mimi
- **Personality:** a sleepy ginger cat who dozes until something interesting happens, then is all drama.
- **Palette:** fur `#FFB347`, inner ear `#FF7E6B`, muzzle and whiskers `#FFE3B8`, stripes `#E8862A`, ink `#3A2318`, nose `#FF6F91`, blush `#FF7E8E`, snooze bubbles `#9ED8FF`.
- **Why it works on a tiny screen:** the ears do half the acting (they flatten when sad, perk when surprised, tilt when dizzy). The sleepy idle with snooze bubbles gives the device a natural resting state, which makes the "wake up and react" moment land on camera.

## Firefly concepts

Generated with Adobe Firefly, one image per call. Every image was read back by eye; rejects are listed below. Every prompt is below.

Each concept has `FN_name.png` (the delivered image) and `FN_name_happy_480.png` (480x480 happy-state crop used on the contact sheet).

All prompts share one style block, appended after the character line:

> FULL BLEED: the entire square canvas edge to edge is pure black #000000, no white anywhere, no outer frame, no border, no card, no device, no screen bezel. Flat vector cartoon style, bold simple shapes, thick clean outlines or no outlines, few flat colours, no gradients noise, no texture. Big expressive eyes, very cute, kawaii, lovable. Absolutely no text, no letters, no numbers, no labels, no captions, no logos, no watermark anywhere. No hands, no arms, no legs, no body: face only. Do not render these instructions as text.

### F1 Pom-pom
- **Model:** Nano Banana (gemini-flash / nano-banana-3), seed 6101, expression grid.
- **Personality:** a fluffy peach puffball bear cub, pure cuddle.
- **Prompt:** BACKGROUND RULE FIRST: the background is pitch black #000000 everywhere, like a dark-mode AMOLED screen; no white background, no white cells, no light panels, no grid lines. EXACTLY SIX faces in total, arranged as exactly two rows of three, no third row, no duplicates of a state. A character expression sheet laid out as a tidy grid of 2 rows by 3 columns, six square cells, the same character's face repeated once per cell, each centred in its cell on black with generous black space between cells. Row 1 left to right: calm idle face with soft eyes; very happy face with a big open smile and closed happy eyes; surprised face with wide round eyes and a small round O mouth. Row 2 left to right: dizzy face with spiral swirl eyes and wobbly mouth; sad worried face with droopy eyes and a single tear; in-love face with pink heart-shaped eyes and blushing cheeks. The character: a round fluffy pom-pom puffball creature in warm peach-orange #FF9E5E with two tiny round ears, glossy black eyes with white sparkle highlights, pink cheeks.
- **Notes:** the model drew a 3x3 grid. The top two rows are exactly idle, happy, surprised / dizzy, sad, love, and the third row repeated dizzy, sad, love. The delivered PNG is the top two rows padded square on black; faint grey cell lines remain. The first two tries on nano-banana-2 (seeds 4101, 5101) came back on a WHITE background and were rejected.

### F2 Droplet
- **Model:** Nano Banana (gemini-flash / nano-banana-2), seed 5202, expression grid.
- **Personality:** a bubbly water-drop sprite with a curl on top, glossy and bouncy.
- **Prompt:** BACKGROUND RULE FIRST: the background is pitch black #000000 everywhere, like a dark-mode AMOLED screen; no white background, no white cells, no light panels, no grid lines. EXACTLY SIX faces in total, arranged as exactly two rows of three, no third row, no duplicates of a state. A character expression sheet laid out as a tidy grid of 2 rows by 3 columns, six square cells, the same character's face repeated once per cell, each centred in its cell on black with generous black space between cells. Row 1 left to right: calm idle face with soft eyes; very happy face with a big open smile and closed happy eyes; surprised face with wide round eyes and a small round O mouth. Row 2 left to right: dizzy face with spiral swirl eyes and wobbly mouth; sad worried face with droopy eyes and a single tear; in-love face with pink heart-shaped eyes and blushing cheeks. The character: a cute water-droplet jelly creature in bright aqua #3FD9E8, teardrop shape with a pointed top curl, shiny highlight, big black oval eyes with white sparkles.
- **Notes:** the same 3x3 habit. Rows 1-2 are the six states in order, so the delivered PNG is those two rows padded square. Seed 4202 came back on white and was rejected.

### F3 Axolotl
- **Model:** Nano Banana (gemini-flash / nano-banana-2), seed 5303, expression grid.
- **Personality:** a baby axolotl with frilly magenta gills, gentle and goofy.
- **Prompt:** BACKGROUND RULE FIRST: the background is pitch black #000000 everywhere, like a dark-mode AMOLED screen; no white background, no white cells, no light panels, no grid lines. EXACTLY SIX faces in total, arranged as exactly two rows of three, no third row, no duplicates of a state. A character expression sheet laid out as a tidy grid of 2 rows by 3 columns, six square cells, the same character's face repeated once per cell, each centred in its cell on black with generous black space between cells. Row 1 left to right: calm idle face with soft eyes; very happy face with a big open smile and closed happy eyes; surprised face with wide round eyes and a small round O mouth. Row 2 left to right: dizzy face with spiral swirl eyes and wobbly mouth; sad worried face with droopy eyes and a single tear; in-love face with pink heart-shaped eyes and blushing cheeks. The character: a baby axolotl face in soft pink #FF8FC8 with three frilly gills on each side of the head in magenta, wide simple smile, small black bead eyes with white sparkles.
- **Notes:** six faces on black, but laid out as 2 columns x 3 rows in the order idle, happy / dizzy, surprised / sad, love. Delivered as generated. Seed 4303 was a 3x3 sheet in white boxes and was rejected.

### F4 Cloud
- **Model:** Firefly Image 5 (native), seed 4404, single hero face.
- **Personality:** a puffy lavender cloud with star-sparkle eyes, dreamy and sweet.
- **Prompt:** A single character face, centred, filling about 70 percent of the square canvas, happy expression with a big smile, for a tiny square AMOLED screen. The character: a puffy cloud creature in soft lavender #B9A6FF with rosy cheeks and big shiny black eyes with white sparkles.
- **Notes:** first try, clean. It has a thin white rim on the upper left of the outline (a sticker edge). That's a deliberate style feature, not a frame.

### F5 Onigiri
- **Model:** Firefly Image 5 (native), seed 6505, single hero face.
- **Personality:** a happy rice-ball buddy in a nori wrap, snack-sized joy.
- **Prompt:** A single character face alone, centred, nothing else in the image, empty pure black around it,, filling about 70 percent of the square canvas, happy expression with a big smile, for a tiny square AMOLED screen. The character: a triangular rice-ball onigiri buddy, white rice with a dark green seaweed band at the bottom, big shiny black eyes, rosy cheeks, tiny smile.
- **Notes:** Firefly Image 4 failed twice: seed 4505 added corner flowers and mismatched eyes, and seed 5505 ignored the style entirely and made a photoreal onigiri on a cream backdrop. Image 5 got it right on the first try.

### Firefly lessons
- Nano Banana treats "expression sheet" as a white-paper sticker sheet. The black background only stuck once the background rule came first in the prompt, and even then it drew 3x3 instead of 2x3 on 3 of 4 tries.
- For a single face on black, native Firefly Image 5 obeyed the brief and Image 4 did not.
