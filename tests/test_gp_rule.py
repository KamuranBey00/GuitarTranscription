"""The Guitar-Pro-like rule must keep reproducing Guitar Pro's own string choices on probe B (README23)."""
import unittest
from itertools import groupby
from pathlib import Path

import numpy as np

from scripts.eval.gp.gp_rule import gp_like
from scripts.eval.gp.gpif import load, notes

PROBE = Path(__file__).resolve().parents[1] / "docs" / "results" / "gp" / "probe" / "B_pitch_only.gp"


def probe_notes() -> tuple[np.ndarray, np.ndarray, list[tuple[int, int]]]:
    rows, chord, gold = [], [], []
    played = [n for n in notes(load(PROBE)) if n["midi"] is not None]
    for _, grp in groupby(played, key=lambda n: (n["bar"], n["beat"])):
        for j, n in enumerate(sorted(grp, key=lambda n: n["midi"])):
            rows.append((0.0, 0.0, n["midi"])); chord.append(j > 0)
            gold.append((int(n["string"]), int(n["fret"])))
    return np.array(rows, float), np.array(chord), gold


class TestGpRule(unittest.TestCase):
    def test_guitar_pro_ile_ayni(self):
        arr, chord, gold = probe_notes()
        self.assertEqual(len(gold), 87)
        self.assertEqual([tuple(p) for p in gp_like(arr, chord)], gold)

    def test_komsu_baglami_e4_u_bos_telden_kaldirir(self):
        # C5 E4 C5 E4 E4: the E4 between two C5 (8th fret) -> 2nd string 5th fret; the later run -> open string
        arr = np.array([(0, 0, p) for p in (72, 64, 72, 64, 64)], float)
        pred = gp_like(arr, np.zeros(5, bool))
        self.assertEqual((pred[1], pred[3]), ((4, 5), (5, 0)))


if __name__ == "__main__":
    unittest.main()
