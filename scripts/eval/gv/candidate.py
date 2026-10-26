"""Load the product stack with a candidate acoustic model and its decoding (README22 second stage).

gtab.pipeline.load_models refuses an acoustic model whose beat net was trained on another one (stack check), which is
right for the product; for measuring a candidate's NOTES and STRINGS the rest of the stack (beat net, rhythm net,
edition net) can stay as it is. Rhythm results with a candidate are therefore not final until its beat net is retrained.
"""
from gtab.evaluation.pitch_eval import load_selection
from gtab.models.inference import load_model
from gtab.paths import ckpt_path
from gtab.pipeline import load_models
from gtab.utils import get_device


def load_candidate(ckpt: str | None = None, cal: str | None = None) -> dict:
    m = load_models(get_device())
    if ckpt:
        m["model"] = load_model("crnn", m["device"], ckpt)[0]
        m["sel"] = load_selection(ckpt_path(cal))["gaps_val"]
    return m


def add_args(ap) -> None:
    ap.add_argument("--ckpt", help="candidate acoustic model (default: active stack)")
    ap.add_argument("--cal", help="its calibration file; the product's tabcrnn_deep2.cal.json = current decoding")
