"""The recorded API answers the web app decodes in its tests and shows in demo mode
(`apps/web/src/modelkit/modelkit.recorded.json`). Regenerate with
`uv run python -m tests.modelkit_record` from `apps/api`; a test checks the file matches."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from janus.main import create_app
from janus.modelkit.store import ModelkitHolder
from tests.modelkit_helpers import seed_dicts, write_run

RECORDED = (
    Path(__file__).resolve().parents[2] / "web" / "src" / "modelkit" / "modelkit.recorded.json"
)
RECORDED_ON = "2026-11-11"


def recorded() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        write_run(Path(tmp), seed_dicts())
        app = create_app(configure_logs=False)
        app.state.modelkit = ModelkitHolder(Path(tmp))
        with TestClient(app) as cl:
            drugs = cl.get("/modelkit/drugs").json()
            keys = [d["key"] for d in drugs["drugs"]]
            return {
                "recorded": RECORDED_ON,
                "drugs": drugs,
                "validation": cl.get("/modelkit/validation").json(),
                "drug": {k: cl.get(f"/modelkit/drugs/{k}").json() for k in keys},
                "evidence": {k: cl.get(f"/modelkit/drugs/{k}/evidence").json() for k in keys},
            }


if __name__ == "__main__":
    RECORDED.write_text(json.dumps(recorded(), ensure_ascii=False, indent=2) + "\n", "utf-8")
