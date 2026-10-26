"""
Probe B (README23): a pitch-only MusicXML (no string/fret) so Guitar Pro must choose the strings itself.

Run:
    python -m scripts.eval.gp.make_probe [out.musicxml]
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

STEPS = ("C", "C", "D", "D", "E", "F", "F", "G", "G", "A", "A", "B")
ALTER = (0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0)
N = {"E2": 40, "F2": 41, "A2": 45, "B2": 47, "C3": 48, "D3": 50, "E3": 52, "F3": 53, "G3": 55, "G#3": 56,
     "A3": 57, "B3": 59, "C4": 60, "D4": 62, "E4": 64, "F#4": 66, "F4": 65, "A4": 69, "B4": 71, "C5": 72, "D5": 74, "E5": 76}
R = None  # rest

# Each section is a list of (event, quarter-length); an event is a pitch name, a tuple of names (chord) or a rest.
SECTIONS: list[tuple[str, list[tuple[object, float]]]] = [
    ("isolated notes (rest between)", [(p, 1.0) if p else (R, 1.0) for p in
                                       ["E4", None, "B3", None, "G3", None, "D4", None, "A3", None, "C4", None]]),
    ("chromatic E2..E5", [(m, 1.0) for m in range(40, 77)] + [(R, 3.0)]),
    ("high melody", [(p, 1.0) for p in ["A4", "B4", "C5", "D5", "E5", "D5", "C5", "B4"]]),
    ("jump: C5 then E4", [("C5", 1.0), ("E4", 1.0), ("C5", 1.0), ("E4", 1.0)]),
    ("repeated E4", [("E4", 0.5)] * 8),
    ("chords", [(("C3", "E3", "G3", "C4", "E4"), 4.0), (("E2", "B2", "E3", "G#3", "B3", "E4"), 4.0),
                (("F2", "C3", "F3", "A3", "C4", "F4"), 4.0), (("D3", "A3", "D4", "F#4"), 4.0),
                (("A3", "E4", "A4"), 4.0)]),
]


def sub(el: ET.Element, tag: str, text: object = None, **attr: str) -> ET.Element:
    e = ET.SubElement(el, tag, attr)
    if text is not None:
        e.text = str(text)
    return e


def add_note(m: ET.Element, midi: int | None, q: float, chord: bool) -> None:
    n = sub(m, "note")
    if chord:
        sub(n, "chord")
    if midi is None:
        sub(n, "rest")
    else:
        p = sub(n, "pitch")
        sub(p, "step", STEPS[midi % 12])
        if ALTER[midi % 12]:
            sub(p, "alter", ALTER[midi % 12])
        sub(p, "octave", midi // 12 - 1)
    sub(n, "duration", int(q * 2))
    sub(n, "voice", 1)
    sub(n, "type", {0.5: "eighth", 1.0: "quarter", 2.0: "half", 3.0: "half", 4.0: "whole"}[q])
    if q == 3.0:
        sub(n, "dot")


def events() -> list[tuple[str, object, float]]:
    return [(name, ev, q) for name, evs in SECTIONS for ev, q in evs]


def build() -> ET.Element:
    root = ET.Element("score-partwise", version="4.0")
    sub(sub(root, "work"), "work-title", "GP string probe")
    sp = sub(sub(root, "part-list"), "score-part", id="P1")
    sub(sp, "part-name", "Guitar")
    sub(sub(sp, "score-instrument", id="P1-I1"), "instrument-name", "Acoustic Guitar (nylon)")
    sub(sub(sp, "midi-instrument", id="P1-I1"), "midi-program", 25)
    part = sub(root, "part", id="P1")
    m, used, num, last = None, 4.0, 0, None
    for name, ev, q in events():
        if used + q > 4.0 + 1e-9 or used >= 4.0:
            num += 1
            m, used = sub(part, "measure", number=str(num)), 0.0
            if num == 1:
                a = sub(m, "attributes")
                sub(a, "divisions", 2)
                sub(sub(a, "key"), "fifths", 0)
                t = sub(a, "time"); sub(t, "beats", 4); sub(t, "beat-type", 4)
                c = sub(a, "clef"); sub(c, "sign", "G"); sub(c, "line", 2); sub(c, "clef-octave-change", -1)
        if name != last:   # section label so each test is easy to find in Guitar Pro
            sub(sub(sub(m, "direction", placement="above"), "direction-type"), "words", name)
            last = name
        pitches = [ev] if not isinstance(ev, tuple) else list(ev)
        for j, p in enumerate(pitches):
            midi = None if p is None else (p if isinstance(p, int) else N[p])
            add_note(m, midi, q, chord=j > 0)
        used += q
    if used < 4.0:   # pad the last bar so Guitar Pro does not flag an incomplete measure
        add_note(m, None, 4.0 - used if 4.0 - used in (1.0, 2.0, 3.0) else 1.0, chord=False)
    return root


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/results/gp/probe/B_pitch_only.musicxml")
    root = build()
    ET.indent(root)
    out.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n",
                   encoding="utf-8")
    print(f"{out} | {len(root.find('part'))} measures")
