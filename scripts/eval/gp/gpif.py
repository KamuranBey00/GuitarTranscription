"""
Decode a Guitar Pro 7/8 file (.gp = zip, Content/score.gpif) into a flat note list (README23).
String 0 = lowest string (same as gtab), fret 0 = open.

Run:
    python -m scripts.eval.gp.gpif docs/results/gp/probe/B_pitch_only.gp [track]
"""
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


def ids(text: str | None) -> list[int]:
    return [int(x) for x in (text or "").split() if int(x) >= 0]


def prop(el: ET.Element, name: str, child: str) -> str | None:
    p = el.find(f"Properties/Property[@name='{name}']/{child}")
    return None if p is None else p.text


def load(gp: Path) -> ET.Element:
    with zipfile.ZipFile(gp) as z:
        return ET.fromstring(z.read("Content/score.gpif"))


def notes(root: ET.Element, track: int = 0) -> list[dict]:
    by = {t: {e.get("id"): e for e in root.find(f"{t}s")} for t in ("Bar", "Voice", "Beat", "Note", "Rhythm")}
    out = []
    for k, mb in enumerate(root.find("MasterBars")):
        bar = by["Bar"][str(ids(mb.find("Bars").text)[track])]
        for v in ids(bar.find("Voices").text)[:1]:
            # Guitar Pro reuses one <Beat> id for identical consecutive beats, so the slot index is the identity
            for slot, b in enumerate(ids(by["Voice"][str(v)].find("Beats").text)):
                b = (b, slot)
                beat = by["Beat"][str(b[0])]
                rh = by["Rhythm"][beat.find("Rhythm").get("ref")].find("NoteValue").text
                text = beat.findtext("FreeText")
                for n in ids(beat.findtext("Notes")):
                    nt = by["Note"][str(n)]
                    out.append({"bar": k + 1, "beat": b, "midi": int(prop(nt, "Midi", "Number") or -1),
                                "string": prop(nt, "String", "String"), "fret": prop(nt, "Fret", "Fret"),
                                "dur": rh, "text": text})
                if not beat.findtext("Notes"):
                    out.append({"bar": k + 1, "beat": b, "midi": None, "dur": rh, "text": text})
    return out


def track_info(root: ET.Element) -> list[str]:
    rows = []
    for t in root.find("Tracks"):
        tun = t.find(".//Property[@name='Tuning']/Pitches")
        rows.append(f"track {t.get('id')} {t.findtext('Name')!r} set={t.findtext('InstrumentSet/Type')} "
                    f"program={t.findtext('Sounds/Sound/MIDI/Program')} tuning={None if tun is None else tun.text}")
    return rows


if __name__ == "__main__":
    root = load(Path(sys.argv[1]))
    print("\n".join(track_info(root)))
    for n in notes(root, int(sys.argv[2]) if len(sys.argv) > 2 else 0):
        if n["midi"] is not None:
            print(f"bar {n['bar']:3d} midi {n['midi']:3d} string {n['string']} fret {n['fret']} {n['dur']}"
                  f"{'  # ' + n['text'] if n['text'] else ''}")
