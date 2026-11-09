"""Measured model error shown with every simulation result (simulation-service design §5.1; owner
decision 2026-11-09). Pure after loading `data/simulation/calibration.json` (numbers and provenance
only).

- httk half-life: measured against Obach 2008 (geometric bias, within-2-fold share, GMFE, n), and
  a split-conformal 80 % interval: the prediction divided and multiplied by the square root of
  the calibrated interval width (the interval is symmetric in log10).
- httk concentrations and the compartmental concentration bands get no calibrated interval.
"""

from __future__ import annotations

import json
import math
from functools import cache
from pathlib import Path
from typing import Any

from janus.paths import repo_root


def load(root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root() / "data"
    return json.loads((base / "simulation" / "calibration.json").read_text(encoding="utf-8"))


@cache
def calibration() -> dict[str, Any]:
    return load()


def half_life_interval(t_h: float, cal: dict[str, Any] | None = None) -> tuple[float, float]:
    """The calibrated 80 % interval of an httk half-life (hours)."""
    if not (math.isfinite(t_h) and t_h > 0):
        raise ValueError("half-life must be positive")
    width = float((cal or calibration())["httk_half_life"]["conformal"]["interval_width_fold"])
    f = math.sqrt(width)
    return t_h / f, t_h * f


def httk_model_error(cal: dict[str, Any] | None = None) -> dict[str, Any]:
    """The measured error block every httk result carries."""
    c = (cal or calibration())["httk_half_life"]
    return {
        "calibration_version": (cal or calibration())["version"],
        "half_life": {
            "dataset": c["dataset"],
            "retrieved": c["retrieved"],
            "n_drugs": c["n_drugs"],
            "geometric_bias_fold": c["geometric_bias_fold"],
            "bias_direction": c["bias_direction"],
            "gmfe": c["gmfe"],
            "within_2_fold": c["within_2_fold"],
            "interval_nominal_coverage": c["conformal"]["nominal_coverage"],
            "interval_held_out_coverage": c["conformal"]["held_out_coverage"],
        },
        "concentrations_validated": False,
    }
