"""Variant A3 (README23): ONE part, ONE staff; each P1 note gets the string/fret of its P2 twin (+ tuning in staff-details).

Hypothesis: Guitar Pro keeps one note list per guitar track and draws notation + TAB from it, so a single staff that
carries <technical><string>/<fret> avoids doubled notes. (Result: no doubling in either variant, but Guitar Pro then
shows circled string numbers instead of a TAB staff.)

Input is the OLD two-part layout (P1 notation, P2 TAB) that musicxml.py wrote before README23 4.1;
the writer now produces the A2 layout itself, so this only reproduces the historical probe.

Run:
    python -m scripts.eval.gp.variant_one_staff in.musicxml out.musicxml
"""
import copy
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SOUND = "pluck.guitar.nylon-string"


def key(n: ET.Element) -> tuple:
    p = n.find("pitch")
    return None if p is None else (p.findtext("step"), p.findtext("alter"), p.findtext("octave"))


def add_tab(n1: ET.Element, n2: ET.Element) -> None:
    """Replace P1 fingering-only technical with P2's string/fret (keep the fingering if present)."""
    tech2 = n2.find("notations/technical")
    if tech2 is None:
        return
    nt = n1.find("notations")
    if nt is None:
        nt = ET.SubElement(n1, "notations")
    tech = nt.find("technical")
    if tech is None:
        tech = ET.SubElement(nt, "technical")
    for tag in ("string", "fret"):
        e = ET.SubElement(tech, tag)
        e.text = tech2.findtext(tag)


def main(src: Path, dst: Path) -> None:
    root = ET.parse(src).getroot()
    p1, p2 = root.find("part[@id='P1']"), root.find("part[@id='P2']")
    pl = root.find("part-list")
    pl.remove(pl.find("score-part[@id='P2']"))
    sp1 = pl.find("score-part[@id='P1']")
    sp1.find("part-name").text = "Classical Guitar"
    ET.SubElement(sp1.find("score-instrument"), "instrument-sound").text = SOUND
    miss = 0
    for m1, m2 in zip(p1.findall("measure"), p2.findall("measure")):
        a1, a2 = m1.find("attributes"), m2.find("attributes")
        if a1 is not None and a2 is not None:   # tuning must live on the notation staff now
            sd = copy.deepcopy(a2.find("staff-details"))
            a1.append(sd)
        n1s = [n for n in m1.findall("note") if n.find("rest") is None]
        n2s = [n for n in m2.findall("note") if n.find("rest") is None]
        for n1, n2 in zip(n1s, n2s):
            if key(n1) != key(n2):
                miss += 1
                continue
            add_tab(n1, n2)
    root.remove(p2)
    ET.indent(root)
    dst.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n",
                   encoding="utf-8")
    print(f"{dst}: pitch mismatches between P1/P2 twins = {miss}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
