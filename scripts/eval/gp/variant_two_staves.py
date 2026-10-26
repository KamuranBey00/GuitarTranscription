"""Variant A2 (README23): rewrite our two-part MusicXML (P1 notation, P2 TAB) as ONE part with two staves + a guitar instrument-sound.

Hypothesis under test: Guitar Pro maps a part to a track, so two parts became two piano tracks; one part with
<staves>2</staves> should give a single guitar track that shows notation and TAB together.

Input is the OLD two-part layout (P1 notation, P2 TAB) that musicxml.py wrote before README23 4.1;
the writer now produces the A2 layout itself, so this only reproduces the historical probe.

Run:
    python -m scripts.eval.gp.variant_two_staves in.musicxml out.musicxml
"""
import copy
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SOUND = "pluck.guitar.nylon-string"


def sub(el: ET.Element, tag: str, text: object = None, **attr: str) -> ET.Element:
    e = ET.SubElement(el, tag, attr)
    if text is not None:
        e.text = str(text)
    return e


def staffed(note: ET.Element, staff: int) -> ET.Element:
    """Copy a note and add <staff> where the MusicXML schema wants it (after type / dot / time-modification)."""
    n = copy.deepcopy(note)
    v = n.find("voice")
    if v is not None:
        v.text = "1" if staff == 1 else "5"
    pos = list(n).index(n.find("type")) + 1 if n.find("type") is not None else len(n)
    for tag in ("dot", "time-modification"):   # <staff> comes after these in the schema
        pos = max(pos, *[list(n).index(e) + 1 for e in n.findall(tag)], pos)
    s = ET.Element("staff")
    s.text = str(staff)
    n.insert(pos, s)
    return n


def merged_attributes(a1: ET.Element, a2: ET.Element) -> ET.Element:
    a = ET.Element("attributes")
    for tag in ("divisions", "key", "time"):
        a.append(copy.deepcopy(a1.find(tag)))
    sub(a, "staves", 2)
    for num, src in ((1, a1), (2, a2)):
        c = copy.deepcopy(src.find("clef"))
        c.set("number", str(num))
        a.append(c)
    sd = copy.deepcopy(a2.find("staff-details"))
    sd.set("number", "2")
    a.append(sd)
    return a


def merge_measure(m1: ET.Element, m2: ET.Element) -> ET.Element:
    m = ET.Element("measure", number=m1.get("number"))
    if m1.find("attributes") is not None:
        m.append(merged_attributes(m1.find("attributes"), m2.find("attributes")))
    for d in m1.findall("direction"):
        m.append(copy.deepcopy(d))
    total = 0
    for n in m1.findall("note"):
        m.append(staffed(n, 1))
        if n.find("chord") is None:
            total += int(n.findtext("duration"))
    sub(sub(m, "backup"), "duration", total)   # rewind to the bar start before writing the TAB staff
    for n in m2.findall("note"):
        m.append(staffed(n, 2))
    return m


def main(src: Path, dst: Path) -> None:
    root = ET.parse(src).getroot()
    p1, p2 = root.find("part[@id='P1']"), root.find("part[@id='P2']")
    pl = root.find("part-list")
    sp2 = pl.find("score-part[@id='P2']")
    pl.remove(sp2)
    sp1 = pl.find("score-part[@id='P1']")
    sp1.find("part-name").text = "Classical Guitar"
    si = sp1.find("score-instrument")
    sub(si, "instrument-sound", SOUND)
    new = ET.Element("part", id="P1")
    for m1, m2 in zip(p1.findall("measure"), p2.findall("measure")):
        new.append(merge_measure(m1, m2))
    root.remove(p1)
    root.remove(p2)
    root.append(new)
    ET.indent(root)
    dst.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n",
                   encoding="utf-8")
    print(f"{dst}: {len(new)} measures, one part, 2 staves")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
