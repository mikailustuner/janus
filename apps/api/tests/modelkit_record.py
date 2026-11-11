# ruff: noqa: S607
"""The recorded API answers the web app decodes in its tests and shows in demo mode
(`apps/web/src/modelkit/modelkit.recorded.json`): the real release, made by running the
`modelkit_evidence` pipeline job on the committed seeds (M0 and M1 files) in a temporary data
directory and asking this API for it. Regenerate with `uv run python -m tests.modelkit_record`
from `apps/api` (it starts the pipelines project with uv). Research use only."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from janus.main import create_app
from janus.modelkit.store import ModelkitHolder
from tests.modelkit_helpers import seed_dicts, write_run

WEB = Path(__file__).resolve().parents[2] / "web" / "src" / "modelkit"
RECORDED = WEB / "modelkit.recorded.json"  # the release: list, system report, featured drugs
RECORDED_M0 = WEB / "modelkit.m0.recorded.json"  # the six M0 drugs: every kind of drug page
# drug pages kept in the release file besides every drug with a parameter set (size limit 1 MB)
FEATURED = ("candesartan", "sunitinib", "telmisartan", "tramadol", "ertugliflozin")
RECORDED_ON = "2026-11-11"


def _answers(data_dir: Path, only: tuple[str, ...] | None) -> dict[str, Any]:
    app = create_app(configure_logs=False)
    app.state.modelkit = ModelkitHolder(data_dir)
    with TestClient(app) as cl:
        drugs = cl.get("/modelkit/drugs").json()
        keys = [
            d["key"] for d in drugs["drugs"] if only is None or d["has_set"] or d["key"] in only
        ]
        return {
            "recorded": RECORDED_ON,
            "drugs": drugs,
            "validation": cl.get("/modelkit/validation").json(),
            "drug": {k: cl.get(f"/modelkit/drugs/{k}").json() for k in keys},
            "evidence": {k: cl.get(f"/modelkit/drugs/{k}/evidence").json() for k in keys},
        }


def recorded_m0() -> dict[str, Any]:
    """The six drugs of milestone M0 from the committed M0 seed alone (golden outcomes)."""
    with tempfile.TemporaryDirectory() as tmp:
        write_run(Path(tmp), seed_dicts())
        return _answers(Path(tmp), None)


def recorded() -> dict[str, Any]:
    pipelines = Path(__file__).resolve().parents[3] / "pipelines"
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(  # noqa: S603 - fixed argument list, no shell
            [
                "uv",
                "run",
                "--project",
                str(pipelines),
                "janus-pipelines",
                "run",
                "modelkit_evidence",
            ],
            check=True,
            env={**os.environ, "JANUS_DATA_DIR": tmp},
            capture_output=True,
            timeout=300,
        )
        return _answers(Path(tmp), FEATURED)


if __name__ == "__main__":
    for path, data in ((RECORDED, recorded()), (RECORDED_M0, recorded_m0())):
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        assert len(text.encode()) < 1_000_000, f"{path.name} is over 1 MB"
        path.write_text(text, "utf-8")
