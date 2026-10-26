"""Second stage, string accuracy: automatic string labels for YouTube "notes on each string" lessons (real guitars).

Lessons of this kind play a string from its open note upwards (or back down) one fret at a time. In the notes found
by the product model (heard pitch only) we look for chromatic runs: consecutive notes, every step exactly one
semitone, at most MAX_GAP_S apart, at least MIN_RUN notes, whose lowest note is an open-string pitch and which span at
most 12 semitones; when the title names the string, runs of natural notes (steps of 1 or 2 semitones,
>= 5 notes, within open .. 12th fret of that string) count too (a missing open note, a repeated note or one intruding ghost are tolerated). Such a run is labelled as that string (fret = pitch - open pitch). If the video title names one
string ("low E string", "6th string", ...) only runs on that string are kept.
Label noise: chromatic-scale lessons often play the scale in FIRST POSITION across strings (E F F# G G# on the low E,
then the open A ...), which gives the same pitch run as a single-string scan. So only the unambiguous part of a run is
labelled: notes below the next string's open pitch (the run started on this string's open note, nothing else can
play them there). Higher notes are labelled only when the title says the lesson stays on one string
(SINGLE_STRING). Labels are judged by cross-validation on our own recordings, whose strings are known exactly.
The model's notes per video are cached (data/raw/gv/yt_notes/) so label rules can be changed without re-running it.
Output: data/raw/gv/yt_labels/<id>.npz (notes (N, 3) s, string (N,), fret (N,): only labelled notes) + a summary.
Run from the repo root: python -m scripts.eval.gv.yt_string_labels
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from gtab.core.instrument import STANDARD_6
from gtab.data.features import cqt_from_file
from gtab.pipeline import analyze, load_models
from gtab.utils import get_device
from scripts.eval.gv.paths import RAW

AUDIO, OUT, NOTES = RAW / "yt_strings", RAW / "yt_labels", RAW / "yt_notes"
MIN_RUN, MAX_GAP_S, MAX_SPAN = 8, 4.0, 12
MIN_NAMED, NAMED_GAP_S = 5, 8.0       # title names the string: natural-note runs (steps of 1 or 2 semitones)
OPEN = {p: s for s, p in enumerate(STANDARD_6.tuning)}          # open pitch -> string (0 = low E)
SINGLE_STRING = re.compile(r"single[- ]string|one[- ]string|on (?:the )?(?:low |high )?[a-g] string|each string|"
                           r"every string|notes on (?:the )?|\bstring \d|\d(?:st|nd|rd|th) string", re.I)
NEXT_OPEN = {s: STANDARD_6.tuning[s + 1] for s in range(5)} | {5: 128}      # high e: nothing above it
TITLE_STRING = [(re.compile(p, re.I), s) for p, s in (
    (r"low\s*e\b|6th\s*string|sixth\s*string", 0), (r"\ba\s*string|5th\s*string", 1), (r"\bd\s*string|4th\s*string", 2),
    (r"\bg\s*string|3rd\s*string", 3), (r"\bb\s*string|2nd\s*string", 4), (r"high\s*e\b|1st\s*string|string\s*1\b", 5))]


MULTI = re.compile(r"\bstrings\b|\b[a-g]\s*(?:&|and|y|e)\s*[a-g]\b|\d(?:st|nd|rd|th)\s*(?:&|and|-)\s*\d", re.I)


def title_string(title: str) -> int | None:
    # one named string only: "E & B string", "D and G String", "E and A strings" cover two strings -> unknown
    if MULTI.search(title):
        return None
    hits = {s for rx, s in TITLE_STRING if rx.search(title)}
    return hits.pop() if len(hits) == 1 else None


def runs(notes: np.ndarray, steps: tuple[int, ...] = (1,), gap: float = MAX_GAP_S,
         min_len: int = MIN_RUN) -> list[list[int]]:
    # chromatic runs in onset order; a repeated pitch or ONE intruding note (ghost) between two run notes is skipped,
    # so a single model slip does not split a string scan in two
    o = [int(i) for i in np.argsort(notes[:, 0], kind="stable")]
    out, used = [], set()
    for start in o:
        if start in used:
            continue
        cur, step, k = [start], 0, o.index(start) + 1
        while k < len(o):
            nxt = None
            for j in o[k:k + 3]:                      # the next note, or the one after a skipped intruder
                d = int(notes[j, 2] - notes[cur[-1], 2])
                if notes[j, 0] - notes[cur[-1], 0] > gap:
                    break
                if abs(d) in steps and (step == 0 or np.sign(d) == step):
                    nxt, step = j, int(np.sign(d))
                    break
                if d != 0 and j != o[k]:              # two foreign notes in a row: the run ends
                    break
            if nxt is None:
                break
            cur.append(nxt); k = o.index(nxt) + 1
        if len(cur) >= min_len:
            out.append(cur); used.update(cur)
    return out


def label(notes: np.ndarray, only: int | None, single: bool = False) -> tuple[list[int], list[int]]:
    idx, strings = [], []
    if only is not None:                              # the title names the string: lessons play natural notes on it
        lo_s = STANDARD_6.tuning[only]
        for r in runs(notes, (1, 2), NAMED_GAP_S, MIN_NAMED):
            p = notes[r, 2].astype(int)
            if p.min() >= lo_s and p.max() <= lo_s + MAX_SPAN:
                idx += r; strings += [only] * len(r)
        return idx, strings
    for r in runs(notes):
        p = notes[r, 2].astype(int)
        lo, ends = int(p.min()), (int(p[0]), int(p[-1]))
        # the run must start (or end) at its lowest note, which is the open string or one fret above it (open missed)
        open_p = lo if lo in OPEN else lo - 1 if lo - 1 in OPEN else None
        if open_p is None or lo not in ends or p.max() - open_p > MAX_SPAN:
            continue
        s = OPEN[open_p]
        if only is not None and s != only:
            continue
        keep = [i for i in r if single or notes[i, 2] < NEXT_OPEN[s]]
        idx += keep; strings += [s] * len(keep)
    return idx, strings


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")   # video titles carry emoji; the Windows console code page has none
    m = load_models(get_device())
    meta = {v["id"]: v for v in json.loads((RAW / "yt_selected_all.json").read_text(encoding="utf-8"))}
    OUT.mkdir(parents=True, exist_ok=True)
    NOTES.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.npz"):                  # labels are rebuilt from scratch with the current rules
        old.unlink()
    total, per_string = 0, Counter()
    for wav in sorted(AUDIO.glob("*.wav")):
        vid = wav.stem
        cache = NOTES / f"{vid}.npz"
        if cache.exists():
            notes = np.load(cache)["notes"]
        else:
            notes = analyze(cqt_from_file(str(wav)), m, "ses")["notes"]
            np.savez(cache, notes=notes)
        if not len(notes):
            continue
        title = meta.get(vid, {}).get("t", "")
        only, single = title_string(title), bool(SINGLE_STRING.search(title))
        idx, strings = label(notes, only, single)
        if idx:
            n = notes[idx]
            s = np.array(strings)
            np.savez(OUT / f"{vid}.npz", notes=n, string=s,
                     fret=n[:, 2].astype(int) - np.array(STANDARD_6.tuning)[s])
            per_string.update(strings)
        total += len(idx)
        with open(RAW / "progress_ytlabel.txt", "a", encoding="utf-8") as f:
            f.write(f"{vid}\n")
        print(f"{vid}  notes {len(notes):5d}  labelled {len(idx):4d}  title string {only} single {single:d}  "
              f"{meta.get(vid, {}).get('t', '')[:60]}", flush=True)
    print(f"labelled notes {total}; per string (0 = low E): {dict(sorted(per_string.items()))}")


if __name__ == "__main__":
    main()
