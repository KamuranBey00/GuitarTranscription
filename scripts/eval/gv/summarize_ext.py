"""README22 second stage: one table of the external checks for several candidates (docs/results/gv/ext/).
Test B: note F1 and string accuracy per source (sample sets NOT used in training + the real GAPS recording);
Test E/F: Commons + YouTube vs classtab (tab notes found, string agreement), both modes; own recordings: the ALL lines.
Run from the repo root: python -m scripts.eval.gv.summarize_ext deep2 g1e13 g1s2e15 s1be8
"""
import argparse
import csv
import re
from pathlib import Path

import numpy as np

from scripts.eval.gv.paths import RESULTS

EXT = RESULTS / "ext"
UNSEEN = ("mg_soft_nylon", "rjs_lofi_nylon", "mdm_classical", "custom_classical_sf2")


def rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_b(m: str) -> dict[str, float]:
    r = rows(EXT / f"test_b_{m}.csv")
    mean = lambda src, k: float(np.nanmean([float(x[k]) for x in r if x["source"] in src]))
    return {"B real F": mean(("real_recording",), "F"), "B unseen F": mean(UNSEEN, "F"),
            "B unseen str": mean(UNSEEN, "string_acc")}


def test_ef(m: str) -> dict[str, float]:
    r = rows(EXT / f"test_e_{m}.csv") + rows(EXT / f"test_f_{m}.csv")
    get = lambda mode, k: float(np.nanmean([float(x[k]) for x in r if x["mode"] == mode]))
    return {"EF found": get("ses", "tab_found"), "EF str ses": get("ses", "string_agree"),
            "EF str ed": get("edisyon", "string_agree")}


def own(m: str) -> dict[str, float]:
    text = (EXT / f"own_{m}.log").read_text(encoding="utf-8")
    out = {}
    for mode, tag in (("ses", "ses"), ("edisyon", "ed")):
        a = re.search(rf"ALL {mode}\s+found ([\d.]+)\s+matched ([\d.]+)\s+string ([\d.]+)", text)
        out["own found"], out[f"own str {tag}"] = float(a.group(1)), float(a.group(3))
        t02 = re.search(rf"T02 {mode}\s+found ([\d.]+)\s+string ([\d.]+)", text)
        out[f"T02 str {tag}"] = float(t02.group(2))
    return out


def main(models: list[str]) -> None:
    table = {m: {**test_b(m), **test_ef(m), **own(m)} for m in models}
    cols = list(next(iter(table.values())))
    print(f"{'model':10s} " + " ".join(f"{c:>12s}" for c in cols))
    for m, v in table.items():
        print(f"{m:10s} " + " ".join(f"{v[c]:12.3f}" for c in cols))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    main(ap.parse_args().models)
