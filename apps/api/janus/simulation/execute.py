"""Running one job in a child process with a hard timeout (simulation-service design §5, DP-S6).

The worker never runs model code in its own process: each job is a child (`python -m
janus.simulation.execute` for the compartmental model, `Rscript httk_job.R` for httk) in its own
process group, killed with the group when it passes `JOB_TIMEOUT_S`. Arguments are built here
from the validated canonical input and the allow-list: the request's own text never reaches a
command line (ids are re-checked against the allow-list and replaced by the allow-list's values,
numbers are formatted from integers). No shell is involved.

Every result is a distribution over a predefined virtual population (owner decision 2026-11-09).
"""

from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from janus.simulation import compartmental
from janus.simulation.allowlist import AllowList, allowlist
from janus.simulation.calibration import half_life_interval, httk_model_error
from janus.simulation.queue import JOB_TIMEOUT_S
from janus.simulation.schemas import CompartmentalIn, HttkPopulationIn, parse

R_SCRIPT = Path(__file__).with_name("httk_job.R")
POP_SEED = 20261109
HTTK_LABEL = "httk PBPK model (pbtk, package defaults) with HTTK-Pop virtual individuals"
_ENV_KEEP = {"PATH", "HOME", "TMPDIR", "R_LIBS_USER", "LANG"}


class JobTimeoutError(Exception):
    pass


class ModelError(Exception):
    """The model process failed or wrote something unexpected (details are not kept)."""


def _run(argv: list[str], stdin: str, timeout: float) -> str:
    env = {k: v for k, v in os.environ.items() if k in _ENV_KEEP}
    env.setdefault("TMPDIR", "/tmp")
    with subprocess.Popen(  # noqa: S603 - fixed argv, no shell
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
        start_new_session=True,
    ) as proc:
        try:
            out, _ = proc.communicate(stdin, timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            raise JobTimeoutError from None
        if proc.returncode != 0:
            raise ModelError("model process failed")
        return out


def _floats(parts: list[str], n: int) -> list[float]:
    if len(parts) != n:
        raise ModelError("unexpected model output")
    try:
        vals = [float(p) for p in parts]
    except ValueError:
        raise ModelError("unexpected model output") from None
    if not all(math.isfinite(v) for v in vals):
        raise ModelError("unexpected model output")
    return vals


def parse_httk(out: str) -> dict[str, Any]:
    """Strict reader of httk_job.R output: `V,<R>,<httk>` and one `Q,<p5>,<p50>,<p95>` per age
    range."""
    versions: dict[str, str] = {}
    quant: list[list[float]] = []
    half_life: float | None = None
    for line in out.splitlines():
        if not line:
            continue
        tag, _, rest = line.partition(",")
        if tag == "V":
            r, _, h = rest.rpartition(",")
            versions = {"r": r[:80], "httk": h[:20]}
        elif tag == "Q":
            q = _floats(rest.split(","), 3)
            if not (0 <= q[0] <= q[1] <= q[2]):
                raise ModelError("unexpected model output")
            quant.append(q)
        elif tag == "H":
            half_life = _floats([rest], 1)[0]
            if half_life <= 0:
                raise ModelError("unexpected model output")
        else:
            raise ModelError("unexpected model output")
    return {"versions": versions, "quantiles": quant, "half_life_h": half_life}


def run_httk_population(req: HttkPopulationIn, allow: AllowList, timeout: float) -> dict[str, Any]:
    """Both predefined HTTK-Pop age ranges; the older-to-younger ratio of medians is the result
    (time-machine design §7.4: httk failed validation, so absolute values are not a level)."""
    chem = allow.httk[req.compound].chem
    young = allow.httk_populations["adult"]
    old = allow.httk_populations["adult_65plus"]
    argv = [
        "Rscript",
        str(R_SCRIPT),
        chem,
        str(req.samples),
        str(POP_SEED),
        str(young.age_low),
        str(young.age_high),
        str(old.age_low),
        str(old.age_high),
    ]
    out = parse_httk(_run(argv, "", timeout))
    q = out["quantiles"]
    t_half = out["half_life_h"]
    if len(q) != 2 or q[0][1] <= 0 or t_half is None:
        raise ModelError("unexpected model output")
    return {
        "model": "httk",
        "label": HTTK_LABEL,
        "samples": req.samples,
        "seed": POP_SEED,
        "daily_dose_mg_per_kg": 1,
        "older_to_younger_median_ratio": q[1][1] / q[0][1],
        "groups": [
            {
                "population": young.id,
                "age_years": [young.age_low, young.age_high],
                "css_band_mg_l": q[0],
            },
            {
                "population": old.id,
                "age_years": [old.age_low, old.age_high],
                "css_band_mg_l": q[1],
            },
        ],
        # The only calibrated interval: half-life (owner decision 2026-11-09).
        "half_life_h": t_half,
        "half_life_interval_h": list(half_life_interval(t_half)),
        "model_error": httk_model_error(),
        "tool_versions": out["versions"],
    }


def run_compartmental(req: CompartmentalIn, allow: AllowList) -> dict[str, Any]:
    c = allow.compartmental[req.compound]
    lim = allow.limits
    hours = compartmental.horizon(
        req.doses, req.interval_h, lim.horizon_after_last_dose_h, lim.horizon_max_h
    )
    p = compartmental.params_for(c, c.populations[req.population])
    out = compartmental.explore(
        p, req.dose_mg, hours, req.samples, interval_h=req.interval_h, doses=req.doses
    )
    out["population"] = req.population
    return out


MAX_RESULT_BYTES = 200_000  # below the table's 256 KiB check


def run(canon: dict[str, Any], timeout: float = JOB_TIMEOUT_S) -> dict[str, Any]:
    """Validate again (defence in depth), run in a child process, check the size."""
    out = _run_any(canon, timeout)
    if len(json.dumps(out)) > MAX_RESULT_BYTES:
        raise ModelError("result too large")
    return out


def _run_any(canon: dict[str, Any], timeout: float) -> dict[str, Any]:
    allow = allowlist()
    req = parse(canon, allow)
    if isinstance(req, HttkPopulationIn):
        return run_httk_population(req, allow, timeout)
    text = _run([sys.executable, "-m", "janus.simulation.execute"], json.dumps(canon), timeout)
    try:
        out: Any = json.loads(text)
    except ValueError:
        raise ModelError("unexpected model output") from None
    if not isinstance(out, dict):
        raise ModelError("unexpected model output")
    return cast(dict[str, Any], out)


def main() -> None:
    """Child entry point of the compartmental model: canonical JSON in, result JSON out."""
    allow = allowlist()
    req = parse(json.loads(sys.stdin.read(4096)), allow)
    if not isinstance(req, CompartmentalIn):
        raise SystemExit(2)
    sys.stdout.write(json.dumps(run_compartmental(req, allow)))


if __name__ == "__main__":
    main()
