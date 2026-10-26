"""Guitar Pro writer (README23 4.2): read back with our own .gpif reader; sync formula checked on Guitar Pro's numbers."""
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

from gtab.core.instrument import parse_tuning
from gtab.render.gpfile import audio_padding, bar_times, fallback_position, sync_points, write_gp
from gtab.render.score import build_measures
from scripts.eval.gp.gpif import load, notes, track_info


class TestGpWriter(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def write(self, pitch, string, fret, q, finger=None, **kw):
        meas, _ = build_measures(np.array(q, float), 0.0, 4, 1.0)
        out = self.tmp / "t.gp"
        info = write_gp(out, meas, np.array(pitch), np.array(string), np.array(fret), (4, 4), 1.0, bpm=80,
                        finger=None if finger is None else np.array(finger), **kw)
        return out, info

    def test_read_back_string_fret_midi_rhythm(self):
        # G3 open (string 3), then a C major dyad on beat 2, then E4 open lasting to the bar end
        out, info = self.write([55, 48, 52, 64], [3, 1, 2, 5], [0, 3, 2, 0], [0, 1, 1, 2])
        got = [(n["midi"], int(n["string"]), int(n["fret"]), n["dur"]) for n in notes(load(out)) if n["midi"] is not None]
        self.assertEqual(got, [(55, 3, 0, "Quarter"), (48, 1, 3, "Quarter"), (52, 2, 2, "Quarter"), (64, 5, 0, "Half")])
        self.assertEqual(info["notes"], 4)
        self.assertIn("set=nylonGuitar program=24 tuning=40 45 50 55 59 64", track_info(load(out))[0])

    def test_tie_across_barline_and_finger_letters(self):
        # a note from beat 3 lasting 4 beats crosses the bar line -> two tied halves; finger 2 = "M"
        out, _ = self.write([57, 60], [3, 4], [2, 1], [2, 6], finger=[2, 1])
        root = load(out)
        ties = [(n.find("Tie").get("origin"), n.find("Tie").get("destination"))
                for n in root.find("Notes") if n.find("Tie") is not None]
        self.assertEqual(ties, [("true", "false"), ("false", "true")])
        self.assertEqual([n.findtext("LeftFingering") for n in root.find("Notes")], ["M", "M", "I"])

    def test_drop_d_capo_frets_count_from_capo(self):
        # Drop D + capo 2: low string open (fret 0 from the capo) sounds D2 + 2 = E2 (40)
        out, _ = self.write([40], [0], [0], [0], instrument=parse_tuning("DADGBE"), capo=2)
        root = load(out)
        self.assertEqual(root.findtext(".//Property[@name='CapoFret']/Fret"), "2")
        self.assertEqual(root.findtext(".//Property[@name='Tuning']/Pitches"), "38 45 50 55 59 64")
        self.assertEqual(notes(root)[0]["midi"], 40)

    def test_unplaced_note_gets_lowest_fret(self):
        self.assertEqual(fallback_position(64, (40, 45, 50, 55, 59, 64), 0), (5, 0))
        self.assertEqual(fallback_position(64, (40, 45, 50, 55, 59, 64), 2), (4, 3))   # E4 below the capo on e
        out, info = self.write([64], [-1], [-1], [0])
        self.assertEqual(info["unplaced"], 1)
        self.assertEqual((notes(load(out))[0]["string"], notes(load(out))[0]["fret"]), ("5", "0"))


class TestSync(unittest.TestCase):

    def test_matches_guitar_pro_test_c(self):
        # Guitar Pro wrote bar 2 at 282000 and bar 4 at 547000 frames with tempi 75.06384 / 79.878975 (README23 C);
        # its sync points were 2 bars of 4/4 apart, so one span here = 8 quarters
        t = np.array([0, 282000, 547000]) / 44100
        s = sync_points(t, 8, 80)
        self.assertEqual([p["frame"] for p in s], [0, 282000])
        np.testing.assert_allclose([p["tempo"] for p in s], [75.06384, 79.878975], atol=1e-3)

    def test_one_point_per_bar_and_padding(self):
        t = np.array([-0.5, 1.5, 3.5])
        pad = audio_padding(t)
        self.assertEqual(pad, 22050)
        s = sync_points(t, 4, 120, pad)
        self.assertEqual([(p["bar"], p["frame"]) for p in s], [(0, 0), (1, 88200)])

    def test_bar_times_extrapolate_before_first_beat(self):
        beats = np.array([0.0, 0.5, 1.0, 1.5])
        np.testing.assert_allclose(bar_times(beats, -1, 2, 2), [-0.5, 0.5, 1.5])


class TestZip(unittest.TestCase):

    def test_audio_embedded_with_sync(self):
        tmp = Path(tempfile.mkdtemp())
        wav = tmp / "a.wav"
        wav.write_bytes(b"RIFF0000WAVE")                     # content is only copied, never decoded by the writer
        meas, _ = build_measures(np.array([0.0]), 0.0, 4, 1.0)
        info = write_gp(tmp / "a.gp", meas, np.array([64]), np.array([5]), np.array([0]), (4, 4), 1.0, bpm=80,
                        audio=wav, times=np.array([0.0, 2.0]))
        names = zipfile.ZipFile(tmp / "a.gp").namelist()
        self.assertEqual(names[:3], ["VERSION", "meta.json", "Content/score.gpif"])
        self.assertTrue(names[3].startswith("Content/Assets/") and names[3].endswith(".wav"))
        self.assertEqual((info["sync"], info["audio"]), (1, True))


if __name__ == "__main__":
    unittest.main()
