"""Second stage, string accuracy: is the played string learnable from the acoustic model's own features? (no product
change, the acoustic model is frozen)

Per note: the model's shared BiLSTM features averaged over an ATTACK window (onset .. +4 frames, ~90 ms: the pluck)
and a BODY window (+4 .. +16 frames: timbre and decay), plus the model's own string probability for each string at
that pitch. A "string expert" = one linear layer whose 6 outputs are masked to the strings that can play the pitch.
Training data: YouTube "notes on each string" lessons auto-labelled by yt_string_labels (real guitars, labels from
chromatic / named-string runs). Evaluation:
  1. YouTube, 5-fold cross-validation GROUPED BY VIDEO (a video is never in train and test at once)
  2. train on all YouTube notes, test on our own recordings (T01 frets 0-12 on every string, T02 same note on 3
     strings, E01 frets 0-5 on every string), whose strings are known exactly and never used for training
Compared with the product's choice on the same notes (the model's own string probabilities, = the "ses" mode for a
single note). Reported for all notes with >= 2 possible strings and for fret >= 5 (the hard ones).
Run from the repo root: python -m scripts.eval.gv.string_probe
"""
import glob
from pathlib import Path

import numpy as np
import torch

from gtab.config import FRAME_RATE
from gtab.core.instrument import STANDARD_6
from gtab.data.features import cqt_from_file
from gtab.data.torch_dataset import _normalize
from gtab.models.inference import _chunked
from gtab.pipeline import analyze, load_models
from gtab.utils import get_device
from scripts.eval.gv.own_recordings import T02_BLOCKS, expected_for, pos
from scripts.eval.gv.paths import RAW, RESULTS
from scripts.eval.gv.yt_string_labels import label as chromatic_label

TUNING = np.array(STANDARD_6.tuning)
ATTACK, BODY = 4, 16
PROGRESS = RAW / "progress_probe.txt"
CACHE = RAW / "probe_features.npz"           # features of the YouTube and own notes (rebuilt when missing)


def frame_features(cqt: np.ndarray, m: dict) -> tuple[np.ndarray, np.ndarray]:
    def fn(x):
        tab, _, _, _, z = m["model"].forward_full(x, return_features=True)
        return z, torch.softmax(tab, -1)
    z, tab = _chunked(fn, _normalize(cqt), m["device"])
    return z, tab


def note_features(z: np.ndarray, tab: np.ndarray, notes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # -> features (N, 2D + 6), model string probabilities (N, 6) (0 where the string cannot play the pitch)
    T, feats, probs = len(z), [], []
    for on, _, p in notes:
        a = min(int(round(on * FRAME_RATE)), T - 1)
        att, body = z[a:min(T, a + ATTACK)].mean(0), z[min(T - 1, a + ATTACK):min(T, a + BODY)].mean(0)
        pr = np.zeros(6)
        for s in range(6):
            f = int(p) - TUNING[s]
            if 0 <= f < tab.shape[2] - 1:
                pr[s] = tab[a:min(T, a + BODY), s, f + 1].mean()
        feats.append(np.concatenate([att, body, pr])); probs.append(pr)
    return np.array(feats, np.float32), np.array(probs)


def candidates(pitch: np.ndarray) -> np.ndarray:
    f = pitch[:, None].astype(int) - TUNING[None]
    return (f >= 0) & (f <= 19)


def youtube_set(m: dict) -> tuple[np.ndarray, ...]:
    X, P, y, pitch, fret, group = [], [], [], [], [], []
    for k, f in enumerate(sorted(glob.glob(str(RAW / "yt_labels" / "*.npz")))):
        d = np.load(f)
        z, tab = frame_features(cqt_from_file(str(RAW / "yt_strings" / f"{Path(f).stem}.wav")), m)
        x, pr = note_features(z, tab, d["notes"])
        X.append(x); P.append(pr); y.append(d["string"]); pitch.append(d["notes"][:, 2]); fret.append(d["fret"])
        group += [k] * len(x)
        with open(PROGRESS, "a", encoding="utf-8") as g:
            g.write(f"yt {Path(f).stem}\n")
    return (np.concatenate(X), np.concatenate(P), np.concatenate(y).astype(int), np.concatenate(pitch),
            np.concatenate(fret), np.array(group))


def own_labels(stem: str, notes: np.ndarray) -> tuple[list[int], list[int]]:
    # -> (note indices, true strings) from the timing of a 60 BPM exercise
    on = notes[:, 0]
    if stem.startswith("T02"):
        spots = T02_BLOCKS[int(stem.strip()[-1])]
        target = pos(*spots[0])[0]                         # the block plays one pitch on three strings
        first = on[notes[:, 2] == target]
        if not len(first):
            return [], []
        beat = {0: 0, 1: 0, 3: 1, 4: 1, 6: 2, 7: 2}        # play play rest, play play rest, play play rest
        idx, s = [], []
        for i in np.flatnonzero(notes[:, 2] == target):
            k = (on[i] - first.min()) / 1.0
            if abs(k - round(k)) < 0.3 and int(round(k)) in beat:
                idx.append(int(i)); s.append(pos(*spots[beat[int(round(k))]])[1])
        return idx, s
    if stem.startswith("T01"):
        truth = [g[0] for g in expected_for("T01")]
        t0, ioi = on.min(), np.median(np.diff(np.sort(on)))
        idx, s = [], []
        for i in range(len(notes)):
            k0 = (on[i] - t0) / ioi
            ks = [k for k in range(int(k0) - 2, int(k0) + 3) if 0 <= k < len(truth) and truth[k][0] == int(notes[i, 2])]
            if ks:
                k = min(ks, key=lambda k: abs(k - k0)); idx.append(i); s.append(truth[k][1])
        return idx, s
    return chromatic_label(notes, None, True)              # E01: frets 0-5 from the open note on every string


def own_set(m: dict) -> tuple[np.ndarray, ...]:
    X, P, y, pitch, src = [], [], [], [], []
    for wav in sorted(glob.glob(str(RAW / "own_wav" / "*.wav"))):
        stem = Path(wav).stem
        if stem[:3] not in ("T01", "T02", "E01"):
            continue
        cqt = cqt_from_file(wav)
        notes = analyze(cqt, m, "ses")["notes"]
        idx, s = own_labels(stem, notes)
        if not idx:
            continue
        z, tab = frame_features(cqt, m)
        x, pr = note_features(z, tab, notes[idx])
        X.append(x); P.append(pr); y.append(np.array(s)); pitch.append(notes[idx, 2]); src += [stem[:3]] * len(idx)
    return np.concatenate(X), np.concatenate(P), np.concatenate(y).astype(int), np.concatenate(pitch), np.array(src)


def fit(X: np.ndarray, y: np.ndarray, mask: np.ndarray, wd: float = 1e-3, epochs: int = 300):
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Xt, mt, yt = (torch.tensor((X - mu) / sd), torch.tensor(mask), torch.tensor(y, dtype=torch.long))
    lin = torch.nn.Linear(X.shape[1], 6)
    opt = torch.optim.Adam(lin.parameters(), lr=1e-2, weight_decay=wd)
    for _ in range(epochs):
        logits = lin(Xt).masked_fill(~mt, -1e9)
        loss = torch.nn.functional.cross_entropy(logits, yt)
        opt.zero_grad(); loss.backward(); opt.step()
    def predict(Xn: np.ndarray, mn: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            return lin(torch.tensor((Xn - mu) / sd)).masked_fill(~torch.tensor(mn), -1e9).argmax(1).numpy()
    return predict


def acc(pred: np.ndarray, y: np.ndarray, sel: np.ndarray) -> str:
    return f"{(pred[sel] == y[sel]).mean():.3f} (n {int(sel.sum())})" if sel.any() else "-"


def report(name: str, pred: np.ndarray, base: np.ndarray, y: np.ndarray, multi: np.ndarray, hard: np.ndarray) -> str:
    return (f"{name:28s} expert {acc(pred, y, multi)} | product {acc(base, y, multi)}   ||   fret>=5: expert "
            f"{acc(pred, y, multi & hard)} | product {acc(base, y, multi & hard)}")


def main() -> None:
    m = load_models(get_device())
    if CACHE.exists():
        c = np.load(CACHE)
        X, P, y, pitch, fret, group = (c[k] for k in ("X", "P", "y", "pitch", "fret", "group"))
        Xo, Po, yo, po, src = (c[k] for k in ("Xo", "Po", "yo", "po", "src"))
    else:
        PROGRESS.unlink(missing_ok=True)
        X, P, y, pitch, fret, group = youtube_set(m)
        Xo, Po, yo, po, src = own_set(m)
        np.savez(CACHE, X=X, P=P, y=y, pitch=pitch, fret=fret, group=group, Xo=Xo, Po=Po, yo=yo, po=po, src=src)
    mask = candidates(pitch)
    multi, hard = mask.sum(1) >= 2, fret >= 5
    base = np.where(mask, P, -1).argmax(1)
    lines = [f"YouTube: {len(y)} labelled notes from {len(set(group))} videos; per string {np.bincount(y, minlength=6).tolist()}"]
    folds = np.arange(len(set(group))) % 5
    pred = np.zeros_like(y)
    for k in range(5):
        te = folds[group] == k
        pred[te] = fit(X[~te], y[~te], mask[~te])(X[te], mask[te])
    lines.append(report("YouTube 5-fold CV by video", pred, base, y, multi, hard))
    mo = candidates(po)
    model = fit(X, y, mask)
    pred_o, base_o = model(Xo, mo), np.where(mo, Po, -1).argmax(1)
    fo = po.astype(int) - TUNING[yo]
    for s in ("T01", "T02", "E01", "ALL"):
        sel = (src == s) if s != "ALL" else np.ones(len(yo), bool)
        lines.append(report(f"own {s} (train: all YouTube)", np.where(sel, pred_o, -9), np.where(sel, base_o, -9),
                            np.where(sel, yo, -8), sel & (mo.sum(1) >= 2), fo >= 5))
    out = "\n".join(lines)
    print(out)
    (RESULTS / "string_probe.log").write_text(out + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
