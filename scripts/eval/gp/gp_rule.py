"""
Guitar Pro string rule vs our modes (README23). Guitar Pro 8.1.5 was probed as a black box: pitch-only MusicXML in,
saved .gp out. Its choices are reproduced exactly (87/87 probe notes) by a Viterbi over onset-group shapes:
static cost = a * sum(frets), transition = b * |hand shift| (hand = mean fretted fret, open strings = 0),
a = 1, b = 0.5; shapes use distinct strings and a fretted span <= 4.

Same tables as eval_edition (real notes, labelled notes) plus end-to-end on gaps_test (deep2 notes, +-50 ms match).

Run:
    python -m scripts.eval.gp.gp_rule > docs/results/gp/gp_rule.log
"""

import argparse
import itertools

import numpy as np
import torch

from gtab.data.gaps_score import match_notes
from gtab.evaluation.pitch_eval import load_selection
from gtab.models.edition_net import EditionNet, predict as seq_predict
from gtab.models.inference import load_model
from gtab.models.stack import active
from gtab.paths import ckpt_path
from gtab.utils import get_device
from scripts.eval.eval_edition import INSTR, ONSET_TOL, gaps_tracks, greedy, gs_tracks, naive, pooled

GP_A, GP_B = 1.0, 0.5          # fitted on the Guitar Pro probe (README23); b in [0.5, 0.9] keeps 87/87
MAX_SPAN = 4

Shape = tuple[tuple[int, int], ...]


def shapes(pitches: list[int]) -> list[Shape]:
    """Playable (string, fret) assignments of one onset group: distinct strings, fretted span <= MAX_SPAN."""
    opts = [INSTR.pitch_to_positions(int(p)) for p in pitches]
    out = []
    for combo in itertools.product(*opts):
        fr = [f for _, f in combo if f > 0]
        if len({s for s, _ in combo}) == len(combo) and (not fr or max(fr) - min(fr) <= MAX_SPAN):
            out.append(combo)
    return out


def hand(shape: Shape) -> float:
    fr = [f for _, f in shape if f > 0]
    return sum(fr) / len(fr) if fr else 0.0


def viterbi(cands: list[list[Shape]], a: float, b: float) -> list[int]:
    """Best shape index per (non-empty) group; cost = a * sum(frets) + b * |hand shift|."""
    hands = [[hand(c) for c in cs] for cs in cands]
    cost = np.array([a * sum(f for _, f in c) for c in cands[0]])
    back = []
    for k in range(1, len(cands)):
        static = np.array([a * sum(f for _, f in c) for c in cands[k]])
        trans = b * np.abs(np.array(hands[k])[:, None] - np.array(hands[k - 1])[None, :])
        tot = cost[None, :] + trans
        back.append(tot.argmin(1))
        cost = tot.min(1) + static
    path = [int(cost.argmin())]
    for bp in reversed(back):
        path.append(int(bp[path[-1]]))
    return path[::-1]


def gp_like(notes: np.ndarray, chord: np.ndarray, a: float = GP_A, b: float = GP_B) -> list:
    """Notes ordered as order_notes gives them (chords pitch-ascending) -> [(string, fret) | None] per note."""
    starts = [i for i in range(len(notes)) if i == 0 or not chord[i]] + [len(notes)]
    groups = [list(range(s, e)) for s, e in zip(starts[:-1], starts[1:])]
    cands = [shapes([notes[i, 2] for i in g]) for g in groups]
    keep = [k for k, c in enumerate(cands) if c]          # unplayable groups (out of range / too many notes) skipped
    out: list = [None] * len(notes)
    if not keep:
        return out
    for k, j in zip(keep, viterbi([cands[k] for k in keep], a, b)):
        for i, sf in zip(groups[k], cands[k][j]):
            out[i] = sf
    return out


def edition_fn(net: EditionNet, device: torch.device):
    def run(t: dict, key: str = "notes", chord: str = "chord") -> list:
        s, f, _ = seq_predict(net, t[key], t[chord], device)
        return [(int(x), int(y)) if x >= 0 else None for x, y in zip(s, f)]
    return run


def real_notes_table(data: dict, methods: dict) -> None:
    print("\n1) TEL UYUMU (gercek notalar; partisyonda etiketli notalar)")
    print(f"  {'yontem':<44}" + "".join(f"{k:>15}" for k in data))
    print("  " + "-" * (44 + 15 * len(data)))
    for name, fn in methods.items():
        print(f"  {name:<44}" + "".join(f"{pooled(v, fn):>15.3f}" for v in data.values()))


def agreement_table(data: dict, methods: dict, ref: str) -> None:
    """How often each method places a note exactly where the Guitar Pro rule does (all notes, labelled or not)."""
    print(f"\n2) GUITAR PRO KURALIYLA AYNI YER (tum notalar; referans: {ref})")
    print(f"  {'yontem':<44}" + "".join(f"{k:>15}" for k in data))
    print("  " + "-" * (44 + 15 * len(data)))
    for name, fn in methods.items():
        if name == ref:
            continue
        row = []
        for tracks in data.values():
            same = tot = 0
            for t in tracks:
                for p, q in zip(fn(t), methods[ref](t)):
                    if p is not None and q is not None:
                        same += tuple(p[:2]) == tuple(q); tot += 1
            row.append(same / max(tot, 1))
        print(f"  {name:<44}" + "".join(f"{x:>15.3f}" for x in row))


def end_to_end(tracks: list, methods: dict) -> None:
    n_lab = n_found = 0
    hit = dict.fromkeys(methods, 0)
    for t in tracks:
        gold_notes = [(on, int(p)) for on, _, p in t["notes"]]
        mi, _ = match_notes(gold_notes, [dict(pitch=int(p)) for _, _, p in t["det"]], t["det"][:, 0], ONSET_TOL)
        preds = {m: fn(t) for m, fn in methods.items()}
        for i, (g, lab) in enumerate(zip(t["gold"], t["lab"])):
            if not lab:
                continue
            j = mi[i]; n_lab += 1; n_found += j >= 0
            for m, p in preds.items():
                hit[m] += j >= 0 and p[j] is not None and tuple(p[j][:2]) == tuple(g)
    print(f"\n3) UCTAN UCA (gaps_test; deep2 notalari; etiketli {n_lab}, bulunan {n_found})")
    print(f"  {'yontem':<44}{'tel: bulunanlarda':>19}{'tum etiketlilerde':>19}")
    print("  " + "-" * 82)
    for m, h in hit.items():
        print(f"  {m:<44}{h / max(n_found, 1):>19.3f}{h / max(n_lab, 1):>19.3f}")


def main(ckpt: str, seq: str, load_cal: str) -> None:
    device = get_device()
    model, _, _ = load_model("crnn", device, ckpt)
    net = EditionNet().to(device)
    net.load_state_dict(torch.load(ckpt_path(seq), map_location=device)["model"])
    _, thr, ot, rules = load_selection(load_cal)["gaps_val"]
    data = {"gaps_val": gaps_tracks("gaps_val", model, device),
            "gaps_test": gaps_tracks("gaps_test", model, device, dec=(thr, ot, rules)),
            "GuitarSet val": gs_tracks(model, device)}
    print(f"Guitar Pro kurali a={GP_A} b={GP_B} span<={MAX_SPAN} | edisyon: {seq} | ses: {ckpt}")
    ed = edition_fn(net, device)
    methods = {"naif (en dusuk perde)": lambda t: naive(t["notes"]),
               "GUITAR PRO kurali (taklit)": lambda t: gp_like(t["notes"], t["chord"]),
               "EDISYON dizi modeli  [edisyon onerisi]": ed,
               "ses / greedy         [duyulan konum]": lambda t: greedy(t["em"])}
    real_notes_table(data, methods)
    agreement_table(data, methods, "GUITAR PRO kurali (taklit)")
    end_to_end(data["gaps_test"], {
        "naif (en dusuk perde)": lambda t: naive(t["det"]),
        "GUITAR PRO kurali (taklit)": lambda t: gp_like(t["det"], t["det_chord"]),
        "EDISYON dizi modeli  [edisyon onerisi]": lambda t: ed(t, "det", "det_chord"),
        "ses / greedy         [duyulan konum]": lambda t: greedy(t["det_em"])})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", default="edition_seq.pt")
    ap.add_argument("--ckpt", default=active()["acoustic"])
    ap.add_argument("--load-cal", default=ckpt_path(active()["cal"]))
    a = ap.parse_args()
    main(a.ckpt, a.seq, a.load_cal)
