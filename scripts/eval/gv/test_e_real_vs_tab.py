"""Test E/F: real performances (Wikimedia Commons, YouTube) vs the classtab tablature of the same piece.
Both TAB modes are scored: "ses" (heard position) and "edisyon" (edition suggestion), see classtab.compare.
Run from the repo root: python -m scripts.eval.gv.test_e_real_vs_tab docs/results/gv/pairs_commons2.tsv <out_csv>
(pairs.tsv: audio_path <TAB> tab_txt_path, repo-relative)
"""
import argparse
import csv
from pathlib import Path

from gtab.data.features import cqt_from_file
from gtab.pipeline import analyze
from scripts.eval.gv import classtab
from scripts.eval.gv.candidate import add_args, load_candidate


def main(pairs_file: Path, out: Path, ckpt: str | None = None, cal: str | None = None) -> None:
    m = load_candidate(ckpt, cal)
    pairs = [l.split("\t") for l in pairs_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = None
        for audio, tab_path in pairs:
            tab = classtab.events(Path(tab_path))
            cqt = cqt_from_file(audio)
            for mode in ("ses", "edisyon"):
                an = analyze(cqt, m, mode)
                row = {"audio": Path(audio).name, "tab": Path(tab_path).stem, "mode": mode,
                       **classtab.compare(tab, an["notes"], an["string"])}
                w = w or csv.DictWriter(f, fieldnames=list(row))
                if f.tell() == 0:
                    w.writeheader()
                w.writerow(row)
                f.flush()
                print(row, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", type=Path)
    ap.add_argument("out", type=Path)
    add_args(ap)
    a = ap.parse_args()
    main(a.pairs, a.out, a.ckpt, a.cal)
