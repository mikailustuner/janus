"""The public read-only API document (open-data design §6, Req 7).

`python -m janus.open.openapi` writes `docs/openapi-public.json`: the app's own OpenAPI schema cut
to the public GET routes (no body, no personal data in or out), with examples. `--check` fails
when the committed document differs (CI), so the document cannot drift from the code.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from typing import Any, Final

from janus.main import create_app
from janus.paths import repo_root
from janus.settings import Settings

REPO: Final = repo_root()
OUT: Final = REPO / "docs" / "openapi-public.json"

PUBLIC: Final = (
    "/health",
    "/privacy/storage",
    "/memory/snapshot",
    "/seance/catalogue",
    "/light/overview",
    "/light/validation",
    "/light/export",
    "/timemachine/catalogue",
    "/timemachine/substance/{substance_id}",
    "/timemachine/cascade/{cascade_id}",
    "/open/outcomes",
    "/open/outcomes.csv",
    "/open/data-quality",
    "/open/data-quality.csv",
    "/open/data-quality.md",
    "/open/faers-onset",
    "/open/faers-onset.csv",
    "/open/faers-onset/{position}",
)

ERR = "#/components/schemas/PublicError"

EXAMPLES: Final[Mapping[str, Mapping[str, Any]]] = {
    "/open/outcomes": {
        "200": {
            "empty": {
                "summary": "No released cell yet (the honest empty state)",
                "value": {
                    "dataset": "janus-open-outcomes",
                    "version": "open-outcomes-1+1f3c0a9b2d4e",
                    "snapshot_date": "2026-11-09",
                    "license": "CC BY 4.0",
                    "license_url": "https://creativecommons.org/licenses/by/4.0/",
                    "attribution": (
                        "Janus open outcome dataset (released cells of donated reports and "
                        "doctor-confirmed outcomes), CC BY 4.0."
                    ),
                    "dictionary_url": (
                        "https://github.com/mikailustuner/janus/blob/main/docs/open-data.md"
                    ),
                    "release_rule": {
                        "k": 20,
                        "epsilon": "1",
                        "noise": "discrete Laplace, scale 1/epsilon, deterministic per cell "
                        "version",
                        "sibling_rule": True,
                        "hidden_cells_listed": False,
                    },
                    "layers": ["contributions", "outcomes"],
                    "cells": [],
                    "notices": [
                        "counts_are_reports_not_people",
                        "not_verified",
                        "not_incidence",
                        "noise_added",
                    ],
                },
            },
            "one_cell": {
                "summary": "A released cell (illustrative values, not real data)",
                "value": {
                    "cells": [
                        {
                            "layer": "contributions",
                            "ingredients": ["Q411347"],
                            "event": "peripheral_oedema",
                            "direction": "adverse",
                            "region": "EU",
                            "value": 23,
                        }
                    ]
                },
            },
        },
        "503": {"unavailable": {"value": {"error": "open_data_unavailable"}}},
    },
    "/timemachine/catalogue": {
        "503": {"not_installed": {"value": {"error": "time_machine_not_installed"}}},
    },
    "/timemachine/substance/{substance_id}": {
        "404": {"unknown": {"value": {"error": "unknown_substance"}}},
        "422": {"invalid": {"value": {"error": "invalid_request", "fields": ["substance_id"]}}},
    },
    "/timemachine/cascade/{cascade_id}": {
        "404": {"unknown": {"value": {"error": "unknown_cascade"}}},
    },
    "/open/data-quality": {
        "503": {"unavailable": {"value": {"error": "data_quality_unavailable"}}},
    },
    "/open/faers-onset": {
        "503": {"unavailable": {"value": {"error": "onset_table_unavailable"}}},
    },
    "/open/faers-onset/{position}": {
        "404": {"unknown": {"value": {"error": "unknown_position"}}},
        "422": {"invalid": {"value": {"error": "invalid_request", "fields": ["position"]}}},
    },
    "/seance/catalogue": {"503": {"unavailable": {"value": {"error": "seance_unavailable"}}}},
    "/light/overview": {"503": {"unavailable": {"value": {"error": "light_unavailable"}}}},
    "/memory/snapshot": {"503": {"unavailable": {"value": {"error": "memory_unavailable"}}}},
}


def _refs(node: Any, out: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            out.add(ref.rsplit("/", 1)[1])
        for v in node.values():  # pyright: ignore[reportUnknownVariableType]
            _refs(v, out)
    elif isinstance(node, list):
        for v in node:  # pyright: ignore[reportUnknownVariableType]
            _refs(v, out)


def document() -> dict[str, Any]:
    app = create_app(Settings.from_env({}), database=None, configure_logs=False)
    full = app.openapi()
    paths: dict[str, Any] = {}
    for path in PUBLIC:
        op = dict(full["paths"][path]["get"])
        responses: dict[str, Any] = dict(op.get("responses", {}))
        responses.pop("422", None)  # FastAPI's validation error: no public route takes a body
        for status, examples in EXAMPLES.get(path, {}).items():
            entry = dict(responses.get(status, {"description": "Error"}))
            content = dict(entry.get("content", {}))
            media = dict(content.get("application/json", {}))
            if status != "200":
                media["schema"] = {"$ref": ERR}
            media["examples"] = examples
            content["application/json"] = media
            entry["content"] = content
            responses[status] = entry
        op["responses"] = responses
        paths[path] = {"get": op}
    used: set[str] = set()
    _refs(paths, used)
    schemas = full.get("components", {}).get("schemas", {})
    # Close over nested references.
    while True:
        more: set[str] = set()
        for name in used:
            _refs(schemas.get(name, {}), more)
        if more <= used:
            break
        used |= more
    picked = {n: schemas[n] for n in sorted(used) if n in schemas}
    picked["PublicError"] = {
        "type": "object",
        "required": ["error"],
        "properties": {
            "error": {"type": "string", "description": "A fixed code; never a sentence."},
            "fields": {"type": "array", "items": {"type": "string"}},
        },
    }
    return {
        "openapi": full["openapi"],
        "info": {
            "title": "Janus public read-only API",
            "version": "1.0.0",
            "description": (
                "The GET routes of the Janus API that take no body and return no personal data: "
                "service status, the FAERS snapshot, the séance catalogue, the light-face "
                "overview, validation and export, the time machine, the open outcome dataset, the "
                "weekly data-quality report and the FAERS onset table of the PIPC rows. "
                "Medical routes are `no-store`; nothing but an access line (route, status, "
                "latency) is logged. Research prototype, not a medical device; not medical "
                "advice. Documentation: docs/open-api.md."
            ),
            "license": {"name": "Apache-2.0", "identifier": "Apache-2.0"},
        },
        "servers": [{"url": "/api", "description": "Same-origin API of a Janus deployment"}],
        "paths": paths,
        "components": {"schemas": picked},
    }


def text() -> str:
    return json.dumps(document(), ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m janus.open.openapi")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    want = text()
    if args.check:
        ok = OUT.is_file() and OUT.read_text(encoding="utf-8") == want
        if not ok:
            print(f"stale: {OUT.relative_to(REPO)}", file=sys.stderr)
        return 0 if ok else 1
    OUT.write_text(want, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
