"""
Guitar Pro 7/8 writer (.gp = zip with Content/score.gpif). README23 4.2.

The layout was learned from files Guitar Pro 8.1.5 saved for us (black box, README23): tables MasterBars -> Bars ->
Voices -> Beats -> Notes (+ Rhythms) linked by id lists; String 0 = lowest string (same as gtab); Fret counts from
the capo (MIDI = tuning + capo + fret); the nylon guitar track fields come from a reference file the user saved.
Unlike MusicXML, .gp lets us set the instrument (Guitar Pro opens MusicXML tracks as piano) and embed the recording
with one sync point per bar, so the TAB follows the player's own timing.
"""

import hashlib
import json
import uuid
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Optional

import numpy as np

from gtab.core.instrument import STANDARD_6

GP_FRAME_RATE = 44100           # sync FrameOffset is counted at 44.1 kHz whatever the file rate (README23, test C)
STEPS = ("C", "C", "D", "D", "E", "F", "F", "G", "G", "A", "A", "B")
SHARP = (0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0)
NOTE_VALUE = {"whole": "Whole", "half": "Half", "quarter": "Quarter", "eighth": "Eighth", "16th": "16th",
              "32nd": "32nd", "64th": "64th", "128th": "128th"}
LEFT_FINGER = {1: "I", 2: "M", 3: "A", 4: "C"}       # Guitar Pro letters; finger 0 (open string) is not written
TEMPO_UNIT_QUARTER = 2                               # "80 2" = quarter = 80 in Guitar Pro tempo automations
NYLON = dict(set_name="Nylon Guitar", set_type="nylonGuitar", sound="Nylon Spinosa", program=24,
             path="Stringed/Acoustic Guitars/Nylon Guitar", patch="Concerto-Nylon")


def _sub(el: ET.Element, tag: str, text: object = None, **attr: str) -> ET.Element:
    e = ET.SubElement(el, tag, attr)
    if text is not None:
        e.text = str(text)
    return e


def bar_times(beats: np.ndarray, first_beat: float, beats_per_bar: int, n_bars: int) -> np.ndarray:
    """Start time (s) of bars 0..n_bars (n_bars + 1 values, the last = end of the last bar) from the beat grid.
    Beat indices outside the detected beats are extrapolated with the median beat period."""
    beats = np.asarray(beats, float)
    idx = first_beat + beats_per_bar * np.arange(n_bars + 1)
    period = float(np.median(np.diff(beats))) if len(beats) > 1 else 0.5
    k = np.arange(len(beats))
    out = np.interp(idx, k, beats)
    out = np.where(idx < 0, beats[0] + idx * period, out)
    return np.where(idx > k[-1], beats[-1] + (idx - k[-1]) * period, out)


def _pitch(props: ET.Element, name: str, midi: int, octave_shift: int = 0) -> None:
    p = _sub(_sub(props, "Property", name=name), "Pitch")
    _sub(p, "Step", STEPS[midi % 12])
    _sub(p, "Accidental", "#" if SHARP[midi % 12] else None)
    _sub(p, "Octave", midi // 12 + octave_shift)       # Guitar Pro octave = midi // 12 (C4 = 60 -> 5)


def _staff_props(staff: ET.Element, instrument, capo: int) -> None:
    props = _sub(staff, "Properties")
    _sub(_sub(props, "Property", name="CapoFret"), "Fret", capo)
    _sub(_sub(props, "Property", name="FretCount"), "Number", instrument.num_frets)
    _sub(_sub(props, "Property", name="PartialCapoFret"), "Fret", 0)
    _sub(_sub(props, "Property", name="PartialCapoStringFlags"), "Bitset", "0" * len(instrument.tuning))
    tun = _sub(props, "Property", name="Tuning")
    _sub(tun, "Pitches", " ".join(str(p) for p in instrument.tuning))   # low -> high, open strings (no capo)
    _sub(tun, "Instrument", "Guitar")
    _sub(tun, "Label")
    _sub(tun, "LabelVisible", "false")


# RSE settings of the reference nylon track Guitar Pro saved for us (README23 4.2): without the icon, channel strip,
# pickups and effect chain Guitar Pro shows the track and its sound as "?" (unknown)
NYLON_EFFECTS = (("E30_EqGEq", "0.5 0.5 0.5 0.5 0.5 0.5 0.5 0.685714"), ("M07_DynamicClassicDynamic", "0.5 0.5 0.94"),
                 ("M04_StudioReverbRoomAmbience", "1 0.42 0.4 0.5 0.2"))


def _instrument_set(t: ET.Element) -> None:
    iset = _sub(t, "InstrumentSet")
    _sub(iset, "Name", NYLON["set_name"]); _sub(iset, "Type", NYLON["set_type"]); _sub(iset, "LineCount", 5)
    el = _sub(_sub(iset, "Elements"), "Element")
    _sub(el, "Name", "Pitched"); _sub(el, "Type", "pitched"); _sub(el, "SoundbankName")
    art = _sub(_sub(el, "Articulations"), "Articulation")
    for tag, val in (("Name", None), ("StaffLine", 0), ("Noteheads", "noteheadBlack noteheadHalf noteheadWhole"),
                     ("TechniquePlacement", "outside"), ("TechniqueSymbol", None), ("InputMidiNumbers", None),
                     ("OutputRSESound", None), ("OutputMidiNumber", 0)):
        _sub(art, tag, val)


def _sound(t: ET.Element) -> None:
    snd = _sub(_sub(t, "Sounds"), "Sound")
    _sub(snd, "Name", NYLON["sound"]); _sub(snd, "Label", NYLON["sound"])
    _sub(snd, "Path", NYLON["path"]); _sub(snd, "Role", "Factory")
    midi = _sub(snd, "MIDI")
    _sub(midi, "LSB", 0); _sub(midi, "MSB", 0); _sub(midi, "Program", NYLON["program"])
    rse = _sub(snd, "RSE")
    _sub(rse, "SoundbankPatch", NYLON["patch"]); _sub(rse, "ElementsSettings")
    pick = _sub(rse, "Pickups")
    _sub(pick, "OverloudPosition", 0); _sub(pick, "Volumes", "1 1"); _sub(pick, "Tones", "1 1")
    chain = _sub(rse, "EffectChain")
    for eid, params in NYLON_EFFECTS:
        _sub(_sub(chain, "Effect", id=eid), "Parameters", params)


def _track(root: ET.Element, instrument, capo: int) -> None:
    t = _sub(_sub(root, "Tracks"), "Track", id="0")
    for tag, val in (("Name", NYLON["set_name"]), ("ShortName", "n.guit."), ("Color", "237 116 116"),
                     ("SystemsDefautLayout", 3), ("PalmMute", 0.3), ("AutoAccentuation", 0.2),
                     ("PlayingStyle", "StringedFinger"), ("UseOneChannelPerString", None), ("IconId", 23)):
        _sub(t, tag, val)
    _instrument_set(t)
    tr = _sub(t, "Transpose")
    _sub(tr, "Chromatic", 0); _sub(tr, "Octave", -1)   # guitar is written an octave above sounding pitch
    _sub(_sub(_sub(t, "RSE"), "ChannelStrip", version="E56"), "Parameters",
         "0.5 0.5 0.5 0.5 0.5 0.5 0.5 0.5 0.5 0 0.5 0.5 0.75 0.5 0.5 0.5")
    _sub(t, "ForcedSound", -1)
    _sound(t)
    mc = _sub(t, "MidiConnection")
    for tag, val in (("Port", 0), ("PrimaryChannel", 0), ("SecondaryChannel", 1), ("ForeOneChannelPerString", "false")):
        _sub(mc, tag, val)
    _sub(t, "PlaybackState", "Default"); _sub(t, "AudioEngineState", "RSE")
    _staff_props(_sub(_sub(t, "Staves"), "Staff"), instrument, capo)
    a = _sub(_sub(t, "Automations"), "Automation")
    for tag, val in (("Type", "Sound"), ("Linear", "false"), ("Bar", 0), ("Position", 0), ("Visible", "true"),
                     ("Value", f"{NYLON['path']};{NYLON['sound']};Factory")):
        _sub(a, tag, val)


def _automation(parent: ET.Element, kind: str, bar: int, value: object = None) -> ET.Element:
    a = _sub(parent, "Automation")
    for tag, val in (("Type", kind), ("Linear", "false"), ("Bar", bar), ("Position", 0), ("Visible", "true")):
        _sub(a, tag, val)
    return _sub(a, "Value", value)


def sync_points(times: np.ndarray, quarters_per_bar: float, score_tempo: float, pad: int = 0) -> list[dict]:
    """One sync point per bar start (times = n_bars + 1 values, the last is the end of the last bar):
    FrameOffset at 44.1 kHz (+ pad frames), ModifiedTempo = quarters / bar duration * 60, i.e. the tempo that carries
    this bar onto the next bar's start."""
    times = np.asarray(times, float)
    dt = np.diff(times)
    tempo = np.where(dt > 0, quarters_per_bar / np.maximum(dt, 1e-9) * 60.0, score_tempo)
    return [dict(bar=k, frame=int(round(t * GP_FRAME_RATE)) + pad, tempo=float(q), original=float(score_tempo))
            for k, (t, q) in enumerate(zip(times[:-1], tempo))]


def audio_padding(times: np.ndarray) -> int:
    """Frames of silence Guitar Pro must put before the recording when bar 0 starts before the audio (t0 < 0)."""
    return max(0, int(round(-float(times[0]) * GP_FRAME_RATE))) if len(times) else 0


def _master_track(root: ET.Element, score_tempo: float, syncs: list[dict]) -> None:
    mt = _sub(root, "MasterTrack")
    _sub(mt, "Tracks", 0)
    autos = _sub(mt, "Automations")
    _automation(autos, "Tempo", 0, f"{score_tempo:g} {TEMPO_UNIT_QUARTER}")
    for s in syncs:
        v = _automation(autos, "SyncPoint", s["bar"])
        _sub(v, "BarIndex", s["bar"]); _sub(v, "BarOccurrence", 0)
        _sub(v, "ModifiedTempo", f"{s['tempo']:.6g}"); _sub(v, "OriginalTempo", f"{s['original']:g}")
        _sub(v, "FrameOffset", s["frame"])


def _rhythm_id(rhythms: ET.Element, cache: dict, piece) -> int:
    key = (piece.type, piece.dots, piece.triplet)
    if key not in cache:
        r = _sub(rhythms, "Rhythm", id=str(len(cache)))
        _sub(r, "NoteValue", NOTE_VALUE[piece.type])
        if piece.dots:
            _sub(r, "AugmentationDot", count=str(piece.dots))
        if piece.triplet:
            _sub(r, "PrimaryTuplet", num="3", den="2")
        cache[key] = len(cache)
    return cache[key]


def _note(notes: ET.Element, nid: int, piece, midi: int, string: int, fret: int, finger: int) -> None:
    n = _sub(notes, "Note", id=str(nid))
    if piece.tie_start or piece.tie_stop:
        _sub(n, "Tie", origin=str(piece.tie_start).lower(), destination=str(piece.tie_stop).lower())
    if finger in LEFT_FINGER:
        _sub(n, "LeftFingering", LEFT_FINGER[finger])
    _sub(n, "InstrumentArticulation", 0)
    props = _sub(n, "Properties")
    _pitch(props, "ConcertPitch", midi)
    _sub(_sub(props, "Property", name="Fret"), "Fret", fret)
    _sub(_sub(props, "Property", name="Midi"), "Number", midi)
    _sub(_sub(props, "Property", name="String"), "String", string)
    _pitch(props, "TransposedPitch", midi, octave_shift=1)


def fallback_position(midi: int, tuning: tuple, capo: int) -> Optional[tuple[int, int]]:
    """A note the model left without a string still needs one on a Guitar Pro guitar track: lowest fret wins."""
    cands = [(s, midi - o - capo) for s, o in enumerate(tuning) if 0 <= midi - o - capo <= 24]
    return min(cands, key=lambda c: c[1]) if cands else None


class _Tables:
    """Builds the id-linked tables (Bars, Voices, Beats, Notes, Rhythms) bar by bar."""

    def __init__(self, root: ET.Element):
        self.mbars, self.bars, self.voices, self.beats, self.notes, self.rhythms = (
            _sub(root, t) for t in ("MasterBars", "Bars", "Voices", "Beats", "Notes", "Rhythms"))
        self.rcache: dict = {}
        self.n_beats = self.n_notes = 0
        self.unplaced = 0

    def beat(self, piece, notes: list[tuple[int, int, int, int]]) -> int:
        """notes: (midi, string, fret, finger) of one chord / note; [] = rest."""
        b = _sub(self.beats, "Beat", id=str(self.n_beats))
        _sub(b, "Dynamic", "MF")                 # Guitar Pro's default; without it alphaTab shows a forte mark
        _sub(b, "Rhythm", ref=str(_rhythm_id(self.rhythms, self.rcache, piece)))
        ids = []
        for midi, s, f, g in notes:
            _note(self.notes, self.n_notes, piece, midi, s, f, g)
            ids.append(str(self.n_notes)); self.n_notes += 1
        if ids:
            _sub(b, "Notes", " ".join(ids))
        self.n_beats += 1
        return self.n_beats - 1

    def bar(self, k: int, sig: tuple[int, int], beat_ids: list[int]) -> None:
        mb = _sub(self.mbars, "MasterBar")
        key = _sub(mb, "Key")
        _sub(key, "AccidentalCount", 0); _sub(key, "Mode", "Major"); _sub(key, "TransposeAs", "Sharps")
        _sub(mb, "Time", f"{sig[0]}/{sig[1]}")
        _sub(mb, "Bars", k)
        bar = _sub(self.bars, "Bar", id=str(k))
        _sub(bar, "Clef", "G2")              # no Ottavia: the track's Transpose Octave -1 already writes it 8va
        _sub(bar, "Voices", f"{k} -1 -1 -1")
        _sub(_sub(self.voices, "Voice", id=str(k)), "Beats", " ".join(map(str, beat_ids)))


def _fill(tables: _Tables, measures, pitch, string, fret, finger, sig, instrument, capo: int) -> None:
    for k, pieces in enumerate(measures):
        beat_ids = []
        for pc in pieces:
            chord = []
            for i in sorted(pc.notes, key=lambda i: pitch[i]):
                pos = ((int(string[i]), int(fret[i])) if string[i] >= 0
                       else fallback_position(int(pitch[i]), instrument.tuning, capo))
                if pos is None:
                    continue
                tables.unplaced += string[i] < 0
                g = int(finger[i]) if finger is not None else -1
                chord.append((int(pitch[i]), pos[0], pos[1], g))
            beat_ids.append(tables.beat(pc, chord))
        tables.bar(k, sig, beat_ids)


def _header(root: ET.Element, title: str) -> None:
    _sub(root, "GPVersion", "8.1.5")
    _sub(root, "GPRevision", "13008", required="12024", recommended="13000")
    _sub(_sub(root, "Encoding"), "EncodingDescription", "GP8")
    score = _sub(root, "Score")
    for tag in ("Title", "SubTitle", "Artist", "Album", "Words", "Music", "WordsAndMusic", "Copyright", "Tabber",
                "Instructions", "Notices"):
        _sub(score, tag, title if tag == "Title" else "")


def _asset_id(audio: Path) -> str:
    """Guitar Pro names an embedded file by a UUID derived from its content; any stable unique id works the same."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, hashlib.sha1(audio.read_bytes()).hexdigest()))


def _backing_track(root: ET.Element, padding: int) -> None:
    bt = _sub(root, "BackingTrack")
    for tag, val in (("IconId", 21), ("Color", "0 0 0"), ("Name", "Audio Track"), ("ShortName", "a.track"),
                     ("PlaybackState", "Default"), ("Enabled", "true"), ("Source", "Local"), ("AssetId", 0),
                     ("YouTubeVideoUrl", None), ("Filter", 6), ("FramesPerPixel", 1000), ("FramePadding", padding),
                     ("Semitones", 0), ("Cents", 0)):
        _sub(bt, tag, val)


def _assets(root: ET.Element, audio: Path, member: str, asset_id: str) -> None:
    a = _sub(_sub(root, "Assets"), "Asset", id="0")
    _sub(a, "OriginalFilePath", audio.resolve().as_posix())
    _sub(a, "OriginalFileSha1", asset_id)
    _sub(a, "EmbeddedFilePath", member)


def write_gp(path, measures, pitch, string, fret, sig, beat_q, bpm=None, finger=None, title="Transkripsiyon",
             instrument=STANDARD_6, capo=0, audio=None, times=None) -> dict:
    """
    Same inputs as write_musicxml (string 0 = lowest, -1 = unplaced; fret from the capo) plus optional audio (the
    recording, embedded) and times = bar_times(...) (n_bars + 1 seconds) for one sync point per bar.
    Bar 0 may start before the recording (t0 < 0): FramePadding puts silence before it and every FrameOffset moves
    by the same frames (Guitar Pro clamps a negative FrameOffset instead, README23 4.2).
    -> dict(notes, unplaced (got a fallback string), sync (number of sync points), audio (bool)).
    """
    audio = Path(audio) if audio else None
    score_tempo = float(bpm * beat_q) if bpm else 120.0          # Guitar Pro tempo is in quarter notes
    root = ET.Element("GPIF")
    _header(root, title)
    use_sync = audio is not None and times is not None
    pad = audio_padding(times) if use_sync else 0
    syncs = sync_points(times, sig[0] * 4 / sig[1], score_tempo, pad) if use_sync else []
    _master_track(root, score_tempo, syncs)
    if audio:
        _backing_track(root, pad)
    _track(root, instrument, capo)
    tables = _Tables(root)
    _fill(tables, measures, pitch, string, fret, finger, sig, instrument, capo)
    member = None
    if audio:
        asset_id = _asset_id(audio)
        member = f"Content/Assets/{asset_id}{audio.suffix.lower()}"
        _assets(root, audio, member, asset_id)
    _write_zip(Path(path), root, audio, member)
    return dict(notes=tables.n_notes, unplaced=tables.unplaced, sync=len(syncs), audio=bool(audio), padding=pad)


def _write_zip(path: Path, root: ET.Element, audio: Optional[Path], member: Optional[str]) -> None:
    ET.indent(root)
    gpif = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("VERSION", "7.0")
        z.writestr("meta.json", json.dumps({"hasAudio": bool(audio), "version": "1.0.0"}, indent=4) + "\n")
        z.writestr("Content/score.gpif", gpif)
        if audio:
            z.write(audio, member)
