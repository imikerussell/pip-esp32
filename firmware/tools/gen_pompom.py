#!/usr/bin/env python3
"""Generate Pom-pom's vector parts (ui/*.svg) from one place.

Pom-pom = the fluffy peach puffball bear cub from design/faces/firefly/F1_pompom.png.
All geometry lives in a 400x400 "pom" canvas; the scene places the parts inside the
`pom` container. Eyes are separate images so they can morph (blink). Morph pairs must
share identical structure: same number of paths, same commands, same fills, same order.
Run:  python3 tools/gen_pompom.py   (from the project root)
"""
import math
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "ui"

# Colours sampled by eye from the concept sheet.
OUTLINE = "#7A3418"
FUR = "#F08A4E"
FUR_LIGHT = "#F7A46C"
EAR_IN = "#F9A98E"
INK = "#2A140D"
BLUSH = "#FF7F86"
WHITE = "#FFFFFF"

K = 0.5523  # cubic bezier circle constant


def ellipse_path(cx, cy, rx, ry):
    """Closed ellipse as M + 4 cubics. Same command structure for any rx/ry (morph-safe)."""
    kx, ky = rx * K, ry * K
    return (f"M {cx:.2f} {cy - ry:.2f} "
            f"C {cx + kx:.2f} {cy - ry:.2f} {cx + rx:.2f} {cy - ky:.2f} {cx + rx:.2f} {cy:.2f} "
            f"C {cx + rx:.2f} {cy + ky:.2f} {cx + kx:.2f} {cy + ry:.2f} {cx:.2f} {cy + ry:.2f} "
            f"C {cx - kx:.2f} {cy + ry:.2f} {cx - rx:.2f} {cy + ky:.2f} {cx - rx:.2f} {cy:.2f} "
            f"C {cx - rx:.2f} {cy - ky:.2f} {cx - kx:.2f} {cy - ry:.2f} {cx:.2f} {cy - ry:.2f} Z")


def lens_path(cx, top_y, bottom_y, mid_y, rx):
    """A closed eyelid: same M + 4 cubics as ellipse_path, squashed into a soft curved band."""
    kx = rx * K
    return (f"M {cx:.2f} {top_y:.2f} "
            f"C {cx + kx:.2f} {top_y:.2f} {cx + rx:.2f} {mid_y - 1:.2f} {cx + rx:.2f} {mid_y:.2f} "
            f"C {cx + rx:.2f} {mid_y + 1:.2f} {cx + kx:.2f} {bottom_y:.2f} {cx:.2f} {bottom_y:.2f} "
            f"C {cx - kx:.2f} {bottom_y:.2f} {cx - rx:.2f} {mid_y + 1:.2f} {cx - rx:.2f} {mid_y:.2f} "
            f"C {cx - rx:.2f} {mid_y - 1:.2f} {cx - kx:.2f} {top_y:.2f} {cx:.2f} {top_y:.2f} Z")


def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">\n{body}</svg>\n')


def fluff_ring(cx, cy, rx, ry, n, r, fill):
    """Scalloped edge: a ring of circles around an ellipse."""
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}"/>')
    return out


def body_svg():
    cx, cy = 200, 214
    p = []
    # Ears (behind the body): outline, fur, pink inner.
    for ex in (86, 314):
        p.append(f'<circle cx="{ex}" cy="88" r="52" fill="{OUTLINE}"/>')
        p.append(f'<circle cx="{ex}" cy="88" r="45" fill="{FUR}"/>')
        p.append(f'<circle cx="{ex}" cy="90" r="25" fill="{EAR_IN}"/>')
    # Fluffy outline, then fur, then a lighter inner fluff for depth.
    p.append(f'<ellipse cx="{cx}" cy="{cy}" rx="158" ry="146" fill="{OUTLINE}"/>')
    p += fluff_ring(cx, cy, 152, 140, 20, 31, OUTLINE)
    p.append(f'<ellipse cx="{cx}" cy="{cy}" rx="152" ry="140" fill="{FUR}"/>')
    p += fluff_ring(cx, cy, 152, 140, 20, 25, FUR)
    p += fluff_ring(cx, cy + 6, 116, 104, 16, 22, FUR_LIGHT)
    p.append(f'<ellipse cx="{cx}" cy="{cy + 6}" rx="116" ry="104" fill="{FUR_LIGHT}"/>')
    # Blush.
    for bx in (104, 296):
        p.append(f'<ellipse cx="{bx}" cy="252" rx="24" ry="13" fill="{BLUSH}" fill-opacity="0.55"/>')
    # Nose: a soft rounded triangle.
    p.append(f'<path d="M 188 236 Q 200 230 212 236 Q 214 240 206 247 Q 200 252 194 247 '
             f'Q 186 240 188 236 Z" fill="{INK}"/>')
    return svg(400, 400, "".join(f"  {x}\n" for x in p))


def eye_svg(closed):
    # 100x100 canvas, three paths: pupil, big sparkle, small sparkle.
    if not closed:
        d = [ellipse_path(50, 50, 34, 37), ellipse_path(62, 35, 11, 11), ellipse_path(38, 63, 5, 5)]
    else:
        # Lid: a gentle downward smile-curve band; sparkles collapse to zero size inside it.
        d = [lens_path(50, 54, 62, 56, 34), ellipse_path(50, 58, 0.01, 0.01), ellipse_path(50, 58, 0.01, 0.01)]
    fills = [INK, WHITE, WHITE]
    return svg(100, 100, "".join(f'  <path d="{dd}" fill="{f}"/>\n' for dd, f in zip(d, fills)))


PINK = "#FF6F91"
TONGUE = "#FF9AA8"
TEAR = "#7FD0FF"
ZZZ = "#CDBBFF"


def stroke(d, color=INK, w=6):
    return (f'<path d="{d}" stroke="{color}" stroke-width="{w}" stroke-linecap="round" '
            f'stroke-linejoin="round" fill="none"/>')


def fill(d, color):
    return f'<path d="{d}" fill="{color}"/>'


# ---- eyes (100x100 canvas, shown at 84x84) ----
def eye_happy():
    return svg(100, 100, "  " + stroke("M 16 62 Q 50 20 84 62", INK, 11) + "\n")


def eye_surprised():
    return svg(100, 100, f'  <circle cx="50" cy="50" r="38" fill="{WHITE}" stroke="{INK}" stroke-width="6"/>\n'
                         f'  <circle cx="50" cy="52" r="13" fill="{INK}"/>\n'
                         f'  <circle cx="55" cy="47" r="4" fill="{WHITE}"/>\n')


def eye_dizzy():
    pts = []
    turns, r0, r1, n = 2.6, 3.0, 36.0, 90
    for i in range(n + 1):
        t = i / n
        a = 2 * math.pi * turns * t
        r = r0 + (r1 - r0) * t
        pts.append((50 + r * math.cos(a), 50 + r * math.sin(a)))
    d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    return svg(100, 100, "  " + stroke(d, INK, 6) + "\n")


def eye_love():
    heart = "M 50 80 C 22 62 14 46 19 34 C 24 22 42 20 50 34 C 58 20 76 22 81 34 C 86 46 78 62 50 80 Z"
    return svg(100, 100, f'  <circle cx="50" cy="50" r="40" fill="{WHITE}" stroke="{INK}" stroke-width="5"/>\n'
                         f'  {fill(heart, PINK)}\n'
                         f'  <ellipse cx="36" cy="38" rx="6" ry="4" fill="{WHITE}" fill-opacity="0.85"/>\n')


# ---- brows (260x40 canvas at pom 70,128; left brow centred x=60, right x=200) ----
def brows(kind):
    if kind == "normal":
        a, b = "M 42 22 Q 60 12 78 22", "M 182 22 Q 200 12 218 22"
    elif kind == "sad":
        a, b = "M 42 24 Q 62 20 78 8", "M 182 8 Q 198 20 218 24"
    else:  # up (surprised / dizzy)
        a, b = "M 42 16 Q 60 2 78 16", "M 182 16 Q 200 2 218 16"
    return svg(260, 40, "  " + stroke(a, OUTLINE, 5) + "\n  " + stroke(b, OUTLINE, 5) + "\n")


# ---- mouths (120x60 canvas at pom 140,236; centre x=60) ----
def mouth(kind):
    if kind == "idle":
        return svg(120, 60, "  " + stroke("M 26 17 Q 28 37 44 35 Q 58 33 60 21 Q 62 33 76 35 Q 92 37 94 17") + "\n")
    if kind == "happy":
        return svg(120, 60, "  " + fill("M 30 14 Q 60 20 90 14 Q 88 50 60 52 Q 32 50 30 14 Z", INK) + "\n  "
                   + fill(ellipse_path(60, 42, 14, 6), TONGUE) + "\n")
    if kind == "surprised":
        return svg(120, 60, "  " + fill(ellipse_path(60, 30, 11, 15), INK) + "\n  "
                   + fill(ellipse_path(60, 38, 6, 4), TONGUE) + "\n")
    if kind == "dizzy":
        return svg(120, 60, "  " + stroke("M 24 30 Q 31 21 38 30 Q 45 39 52 30 Q 59 21 66 30 Q 73 39 80 30 Q 87 21 96 29", INK, 5) + "\n")
    if kind == "sad":
        return svg(120, 60, "  " + stroke("M 40 40 Q 60 20 80 40") + "\n")
    if kind == "love":
        return svg(120, 60, "  " + fill("M 40 18 Q 60 23 80 18 Q 78 44 60 45 Q 42 44 40 18 Z", INK) + "\n  "
                   + fill(ellipse_path(60, 38, 9, 4), TONGUE) + "\n")
    if kind == "sleepy":
        return svg(120, 60, "  " + fill(ellipse_path(60, 30, 8, 6), INK) + "\n")
    # Talking morph pair: same structure (dark mouth + tongue, both M + 4 cubics).
    if kind == "talk_closed":
        return svg(120, 60, "  " + fill(ellipse_path(60, 28, 18, 3), INK) + "\n  "
                   + fill(ellipse_path(60, 29, 0.01, 0.01), TONGUE) + "\n")
    if kind == "talk_open":
        return svg(120, 60, "  " + fill(ellipse_path(60, 30, 21, 17), INK) + "\n  "
                   + fill(ellipse_path(60, 39, 12, 6), TONGUE) + "\n")
    raise ValueError(kind)


# ---- extras ----
def tear():
    d = "M 15 2 C 15 2 28 20 28 29 C 28 37 22 42 15 42 C 8 42 2 37 2 29 C 2 20 15 2 15 2 Z"
    return svg(30, 44, f"  {fill(d, TEAR)}\n  <ellipse cx=\"10\" cy=\"29\" rx=\"3\" ry=\"5\" fill=\"{WHITE}\" fill-opacity=\"0.8\"/>\n")


def zzz():
    def z(x, y, s):
        return stroke(f"M {x} {y} L {x + s} {y} L {x} {y + s} L {x + s} {y + s}", ZZZ, max(3, s // 6))
    return svg(80, 80, "  " + z(6, 50, 20) + "\n  " + z(34, 26, 16) + "\n  " + z(58, 6, 13) + "\n")


def love_blush():
    return svg(260, 40, f'  <ellipse cx="34" cy="20" rx="27" ry="14" fill="{PINK}" fill-opacity="0.75"/>\n'
                        f'  <ellipse cx="226" cy="20" rx="27" ry="14" fill="{PINK}" fill-opacity="0.75"/>\n')


if __name__ == "__main__":
    for old in UI.glob("*.svg"):
        old.unlink()
    files = {
        "pom_body.svg": body_svg(),
        "eye_open.svg": eye_svg(False), "eye_closed.svg": eye_svg(True),
        "eye_happy.svg": eye_happy(), "eye_surprised.svg": eye_surprised(),
        "eye_dizzy.svg": eye_dizzy(), "eye_love.svg": eye_love(),
        "brows_normal.svg": brows("normal"), "brows_sad.svg": brows("sad"), "brows_up.svg": brows("up"),
        "tear.svg": tear(), "zzz.svg": zzz(), "love_blush.svg": love_blush(),
    }
    for k in ("idle", "happy", "surprised", "dizzy", "sad", "love", "sleepy", "talk_closed", "talk_open"):
        files[f"mouth_{k}.svg"] = mouth(k)
    for name, text in files.items():
        (UI / name).write_text(text)
    print("wrote", len(files), "svgs")
