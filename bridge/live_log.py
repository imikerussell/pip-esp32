"""Big live log for B-roll: tails bridge/turns.jsonl and shows what Pip saw, said and how fast.

    bridge/.venv/bin/python bridge/live_log.py          (Ctrl-C to quit; make the terminal big)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

TURNS = Path(__file__).resolve().parent / "turns.jsonl"
FACE_ICON = {"idle": "( o . o )", "happy": "( ^ w ^ )", "surprised": "( O o O )", "dizzy": "( @ ~ @ )",
             "sad": "( ; n ; )", "love": "( <3 . <3 )", "sleepy": "( - . - ) zZ", "talking": "( o O o )"}
FACE_COLOUR = {"idle": "#F08A4E", "happy": "#FFC24A", "surprised": "#FFE066", "dizzy": "#B39DFF",
               "sad": "#7FB2FF", "love": "#FF6F91", "sleepy": "#8F8FB3"}


def render(rec: dict, console: Console) -> None:
    face = rec.get("face") or "idle"
    colour = FACE_COLOUR.get(face, "#F08A4E")
    head = Text()
    head.append(f" {rec.get('event', '?').upper()} ", style=f"bold black on {colour}")
    head.append(f"  {FACE_ICON.get(face, face)}  ", style=f"bold {colour}")
    head.append(rec.get("ts", "")[11:], style="dim")
    body = Table.grid(padding=(0, 2))
    body.add_column(style="bold #9AA0A6", justify="right")
    body.add_column()
    if rec.get("saw") and rec["saw"] not in ("no photo", "(pooled)"):
        body.add_row("SAW", Text(rec["saw"], style="italic #CFE3FF"))
    if rec.get("speak") and rec.get("line"):
        body.add_row("DIRECTION", Text(f"[{rec.get('direction', '')}]", style="#FFB199"))
        body.add_row("SAID", Text(rec["line"], style="bold white"))
    else:
        body.add_row("SAID", Text("(stays quiet, changes face)", style="dim"))
    lat = []
    if rec.get("brain_ms") is not None:
        lat.append(f"brain {rec['brain_ms']} ms")
    if rec.get("fish_ttfb_ms") is not None:
        lat.append(f"voice {rec['fish_ttfb_ms']} ms" + (" (cached)" if rec.get("cached") else ""))
    if rec.get("total_ms"):
        lat.append(f"total {rec['total_ms']} ms")
    if lat:
        body.add_row("LATENCY", Text("  ·  ".join(lat), style="#5FD08A"))
    model = f"{rec.get('brain_model', '')} → Fish {rec.get('tts_model', '')}".strip(" →")
    console.print(Panel(body, title=head, title_align="left", subtitle=Text(model, style="dim"),
                        subtitle_align="right", border_style=colour, padding=(1, 2)))


def main() -> None:
    console = Console()
    console.print(Panel(Text("PIP · live brain", style="bold #F56138", justify="center"),
                        subtitle="Claude sees · Fish Audio Drama 3 speaks", border_style="#F56138"))
    TURNS.touch()
    with TURNS.open() as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("skipped"):
                continue
            render(rec, console)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
