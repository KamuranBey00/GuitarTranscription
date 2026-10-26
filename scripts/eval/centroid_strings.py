"""
"Hand centre" string choice (user idea, 26 Oct 2026): a note that can be played in several places is pulled towards the
centre of the fretting hand, estimated from nearby ANCHOR notes whose position is certain (only one playable place, or
the acoustic model is >= p_anchor sure). Earlier context priors (Katman 3.6 / 3.6b, README22 step 4) used the previous
note only; this variant uses confident neighbours in a time window.

Score of candidate c of a non-anchor note:  log P_audio(c) - lam * |fret(c) - centre|   (lam = 0 -> product choice).
Open strings: "neutral" = distance 0 (reachable from any hand position) | "fret0" = treated as fret 0.

Rule fixed BEFORE measuring (README22 step 4 style):
- settings are chosen on GuitarSet val (PLAYED string, hexaphonic labels; steel guitar);
- our own recordings (PLAYED string on a classical guitar) are TEST ONLY and never steer a choice;
- GAPS (WRITTEN edition) is reported only to show the pull towards the written tab;
- a product candidate needs >= +0.02 on GuitarSet val and no loss on our own recordings.

Run:
    python -m scripts.eval.centroid_strings > docs/results/gv/centroid_strings.log
"""

import argparse
import glob
import itertools
from pathlib import Path

import numpy as np

from gtab.config import FRAME_RATE
from gtab.data.features import cqt_from_file
from gtab.data.torch_dataset import _normalize
from gtab.decoding.viterbi import energy_rise, segment
from gtab.evaluation.pitch_eval import load_selection
from gtab.models.inference import load_model, predict_heads
from gtab.models.stack import active
from gtab.paths import ckpt_path
from gtab.utils import get_device
from scripts.eval.eval_edition import INSTR, emissions, gaps_tracks, greedy, gs_tracks, pooled
from scripts.eval.gv import classtab
from scripts.eval.gv.own_recordings import WAV, expected_for, tab_array

LAMS = (0.0, 0.1, 0.25, 0.5, 1.0, 2.0)
SIGMAS = (1.0, 3.0)                 # seconds: width of the time window around a note
OPEN_MODES = ("neutral", "fret0")
P_ANCHOR = 0.9


def anchors(em: list[dict]) -> list:
    """(string, fret) of notes whose place is certain, else None."""
    out = []
    for e in em:
        if not e:
            out.append(None); continue
        best = max(e, key=e.get)
        out.append(best if len(e) == 1 or np.exp(e[best]) >= P_ANCHOR else None)
    return out


def centre_pick(notes: np.ndarray, em: list[dict], lam: float, sigma: float, open_mode: str) -> list:
    """Product (greedy) choice for anchors / lam 0; hand-centre pull for the uncertain notes."""
    picks = greedy(em)
    if lam == 0 or not len(notes):
        return picks
    anc = anchors(em)
    t = notes[:, 0]
    idx = np.array([j for j, a in enumerate(anc) if a is not None and a[1] > 0])   # open strings say nothing of the hand
    if not len(idx):
        return picks
    hand = np.array([anc[j][1] for j in idx], float)
    for i, e in enumerate(em):
        if anc[i] is not None or len(e) < 2:
            continue
        w = np.exp(-0.5 * ((t[idx] - t[i]) / sigma) ** 2)
        if w.sum() < 1e-3:                                    # no confident neighbour nearby: keep the audio choice
            continue
        centre = float(w @ hand / w.sum())
        dist = lambda c: 0.0 if (c[1] == 0 and open_mode == "neutral") else abs(c[1] - centre)
        picks[i] = max(e, key=lambda c: e[c] - lam * dist(c))
    return picks


def settings() -> list[tuple]:
    return [(0.0, SIGMAS[0], OPEN_MODES[0])] + [s for s in itertools.product(LAMS[1:], SIGMAS, OPEN_MODES)]


def own_tracks(m: dict) -> list[dict]:
    """Our recordings: notes found by the product decoding + per-note audio log-probs (test only)."""
    _, thr, ot, rules = m["sel"]
    out = []
    for wav in sorted(glob.glob(str(WAV / "*.wav"))):
        groups = expected_for(Path(wav).stem)
        if groups is None:
            continue
        cqt = cqt_from_file(wav)
        probs, ons, offs, pons = predict_heads(m["model"], _normalize(cqt), m["device"], with_pitch_onset=True)
        segs = segment(probs, ons, thr, ot, INSTR, rise=energy_rise(cqt, INSTR), offsets=offs,
                       pitch_onsets=pons if rules.get("onset_source") == "pitch" else None, **rules)
        notes = np.array([(a / FRAME_RATE, b / FRAME_RATE, p) for a, b, p in segs], float).reshape(-1, 3)
        out.append(dict(name=Path(wav).stem, group=Path(wav).stem[:3], tab=tab_array(groups), notes=notes,
                        em=emissions(probs, notes)))
    return out


def own_scores(tracks: list[dict], setting: tuple) -> dict[str, float]:
    """Played-string agreement on matched notes (classtab LCS, as own_recordings), mean over files per group."""
    per = {}
    for t in tracks:
        picks = centre_pick(t["notes"], t["em"], *setting)
        string = np.array([-1 if p is None else p[0] for p in picks])
        r = classtab.compare(t["tab"], t["notes"], string)
        key = "T01" if t["group"] == "T01" else "T02" if t["group"] == "T02" else "E"
        per.setdefault(key, []).append(r["string_agree"])
    out = {k: float(np.nanmean(v)) for k, v in per.items()}
    out["ALL"] = float(np.nanmean([x for v in per.values() for x in v]))
    return out


def table(data: dict, own: list[dict]) -> list[tuple]:
    rows = []
    for st in settings():
        fn = lambda t, st=st: centre_pick(t["notes"], t["em"], *st)
        rows.append((st, {k: pooled(v, fn) for k, v in data.items()}, own_scores(own, st)))
    return rows


def report(rows: list[tuple]) -> None:
    print(f"{'lam':>5} {'sigma':>5} {'open':>8} | {'GS val (played)':>15} | {'gaps_val (written)':>18} "
          f"{'gaps_test (written)':>19} | own played: {'T01':>6} {'T02':>6} {'E':>6} {'ALL':>6}")
    for (lam, sig, op), d, o in rows:
        print(f"{lam:5.2f} {sig:5.1f} {op:>8} | {d['GuitarSet val']:15.3f} | {d['gaps_val']:18.3f} "
              f"{d['gaps_test']:19.3f} | {'':11} {o.get('T01', np.nan):6.3f} {o.get('T02', np.nan):6.3f} "
              f"{o.get('E', np.nan):6.3f} {o['ALL']:6.3f}")
    base = rows[0]
    best = max(rows[1:], key=lambda r: r[1]["GuitarSet val"])          # chosen on GuitarSet val only
    print(f"\nproduct (lam 0): GS {base[1]['GuitarSet val']:.3f} | own ALL {base[2]['ALL']:.3f}")
    print(f"chosen on GuitarSet val: lam {best[0][0]} sigma {best[0][1]} open {best[0][2]} -> GS "
          f"{best[1]['GuitarSet val']:.3f} ({best[1]['GuitarSet val'] - base[1]['GuitarSet val']:+.3f}) | own ALL "
          f"{best[2]['ALL']:.3f} ({best[2]['ALL'] - base[2]['ALL']:+.3f})  [rule: >= +0.02 GS and no own loss]")


def main(ckpt: str, load_cal: str) -> None:
    device = get_device()
    model, _, _ = load_model("crnn", device, ckpt)
    data = {"GuitarSet val": gs_tracks(model, device), "gaps_val": gaps_tracks("gaps_val", model, device),
            "gaps_test": gaps_tracks("gaps_test", model, device)}
    m = dict(model=model, device=device, sel=load_selection(load_cal)["gaps_val"])
    own = own_tracks(m)
    print(f"model {ckpt} | anchors: one place or P >= {P_ANCHOR} | own recordings {len(own)} files (test only)\n"
          "string = audio greedy per note (no chord constraint, same for every row)\n")
    report(table(data, own))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=active()["acoustic"])
    ap.add_argument("--load-cal", default=ckpt_path(active()["cal"]))
    a = ap.parse_args()
    main(a.ckpt, a.load_cal)
