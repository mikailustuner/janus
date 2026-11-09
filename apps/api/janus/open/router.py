"""`/open/outcomes` (open-data design §4): the released outcome dataset as JSON and CSV; and
`/open/cascade-package/pipc` (mcp-server design §2.1): the PIPC rows of the open cascade package.

Read-only and stateless. Medical routes (nothing logged but the access line). 503
`open_data_unavailable` when there is no database or no noise key: the dataset is never served
without the release rule. Today's answer is the snapshot: the noise is deterministic per cell
version, so the same stored data give the same file.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
from pathlib import Path
from typing import Any, Literal

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from janus.db.pool import Database
from janus.http_policy.routes import medical_router
from janus.memory.disclosure import keyed_noise_source
from janus.memory.messages import DISCLAIMER
from janus.open import outcomes as o
from janus.open import package as pkg
from janus.settings import Settings

router = medical_router()


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReleaseRuleOut(_Out):
    k: int
    epsilon: str
    noise: Literal["discrete Laplace, scale 1/epsilon, deterministic per cell version"]
    sibling_rule: Literal[True]
    hidden_cells_listed: Literal[False]


class OpenCellOut(_Out):
    layer: Literal["contributions", "outcomes"]
    ingredients: list[str]
    event: str
    direction: Literal["adverse", "benefit"]
    region: Literal["TR", "EU", "US"]
    value: int


class OpenOutcomesOut(_Out):
    dataset: Literal["janus-open-outcomes"]
    version: str
    snapshot_date: dt.date
    license: Literal["CC BY 4.0"]
    license_url: str
    attribution: str
    dictionary_url: str
    release_rule: ReleaseRuleOut
    layers: list[Literal["contributions", "outcomes"]]
    # Layers not published because a stored row's consent does not name open publication.
    withheld_layers: list[Literal["contributions", "outcomes"]]
    cells: list[OpenCellOut]
    notices: list[
        Literal["counts_are_reports_not_people", "not_verified", "not_incidence", "noise_added"]
    ]


DICTIONARY_URL = "https://github.com/mikailustuner/janus/blob/main/docs/open-data.md"
NOTICES: list[
    Literal["counts_are_reports_not_people", "not_verified", "not_incidence", "noise_added"]
] = ["counts_are_reports_not_people", "not_verified", "not_incidence", "noise_added"]


def _today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


async def _build(
    request: Request,
) -> tuple[list[o.OpenCell], list[str], str, dt.date] | JSONResponse:
    settings: Settings = request.app.state.settings
    db = getattr(request.app.state, "database", None)
    if not isinstance(db, Database) or settings.noise_key is None:
        return JSONResponse({"error": "open_data_unavailable"}, status_code=503)
    sources = request.app.state.user_layer_sources
    noise = keyed_noise_source(settings.noise_key)

    def call() -> tuple[list[o.OpenCell], list[str]]:
        with db.read_only_tx() as conn:
            return o.release(
                conn, sources, k=settings.k, epsilon=settings.epsilon, noise_source=noise
            )

    cells, withheld = await run_in_threadpool(call)
    return cells, withheld, o.version(cells, settings.k, settings.epsilon), _today()


@router.get("/open/outcomes", response_model=OpenOutcomesOut)
async def open_outcomes(request: Request) -> Any:
    """Released cells of donated reports and doctor-confirmed outcomes (k = 20, noise, sibling
    rule). An empty `cells` list means that no cell is released yet."""
    built = await _build(request)
    if isinstance(built, JSONResponse):
        return built
    cells, withheld, version, snapshot = built
    settings: Settings = request.app.state.settings
    out = OpenOutcomesOut(
        dataset="janus-open-outcomes",
        version=version,
        snapshot_date=snapshot,
        license="CC BY 4.0",
        license_url=o.LICENSE_URL,
        attribution=o.ATTRIBUTION,
        dictionary_url=DICTIONARY_URL,
        release_rule=ReleaseRuleOut(
            k=settings.k,
            epsilon=str(settings.epsilon),
            noise="discrete Laplace, scale 1/epsilon, deterministic per cell version",
            sibling_rule=True,
            hidden_cells_listed=False,
        ),
        layers=["contributions", "outcomes"],
        withheld_layers=[w for w in ("contributions", "outcomes") if w in withheld],
        cells=[OpenCellOut.model_validate(o.cell_row(c)) for c in cells],
        notices=NOTICES,
    )
    return JSONResponse(out.model_dump(mode="json"))


@router.get(
    "/open/outcomes.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "The same cells as CSV."}},
)
async def open_outcomes_csv(request: Request) -> Any:
    """The released cells as CSV (header only when nothing is released yet)."""
    built = await _build(request)
    if isinstance(built, JSONResponse):
        return built
    cells, _, version, snapshot = built
    return Response(
        o.to_csv(cells, version, snapshot),
        media_type="text/csv; charset=utf-8",
        headers={
            "content-disposition": (
                f'attachment; filename="janus-open-outcomes-{snapshot.isoformat()}.csv"'
            ),
            "x-janus-dataset-version": version,
        },
    )


# --- The open cascade package, PIPC rows (mcp-server design §2.1, DP6) ----------------------------

# Read at request time; replaced in tests.
PACKAGE_DIR: Path = pkg.OUT


class LicenseOut(_Out):
    name: str
    path: str
    title: str


class PipcRowOut(_Out):
    position: int
    system: str
    kind: str
    drug_a: str
    adverse_event: str
    drug_b: str
    locator: str
    index_class: str | None
    marker_class: str | None
    unmatchable_role: str | None
    unmatchable_reason: str | None
    supporting: list[str]
    note: str | None


class CascadePackageOut(_Out):
    package: Literal["janus-cascade-package"]
    version: str
    created: str
    citation: str
    citation_url: str
    # The PIPC columns keep CC BY 4.0; the Janus mapping columns are Apache-2.0.
    licenses: dict[Literal["pipc", "pipc_rules"], list[LicenseOut]]
    rows: list[PipcRowOut]
    disclaimer: str = DISCLAIMER


def _csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def read_pipc_package(folder: Path) -> CascadePackageOut:
    """The PIPC table joined by position with the Janus mapping. Raises OSError, KeyError or
    ValueError when the package is missing or malformed."""
    meta = json.loads((folder / "datapackage.json").read_text(encoding="utf-8"))
    pipc = _csv_rows((folder / "pipc.csv").read_text(encoding="utf-8"))
    rules = {r["position"]: r for r in _csv_rows((folder / "pipc_rules.csv").read_text("utf-8"))}
    resources = {r["name"]: r for r in meta["resources"]}

    def opt(value: str) -> str | None:
        return value or None

    rows = [
        PipcRowOut(
            position=int(r["position"]),
            system=r["system"],
            kind=r["kind"],
            drug_a=r["drug_a"],
            adverse_event=r["adverse_event"],
            drug_b=r["drug_b"],
            locator=r["locator"],
            index_class=opt(rules[r["position"]]["index_class"]),
            marker_class=opt(rules[r["position"]]["marker_class"]),
            unmatchable_role=opt(rules[r["position"]]["unmatchable_role"]),
            unmatchable_reason=opt(rules[r["position"]]["unmatchable_reason"]),
            supporting=[x for x in rules[r["position"]]["supporting"].split(";") if x],
            note=opt(rules[r["position"]]["note"]),
        )
        for r in pipc
    ]
    return CascadePackageOut(
        package=meta["name"],
        version=meta["version"],
        created=meta["created"],
        citation=pkg.PIPC_SOURCE["title"],
        citation_url=pkg.PIPC_SOURCE["path"],
        licenses={
            "pipc": [LicenseOut.model_validate(x) for x in resources["pipc"]["licenses"]],
            "pipc_rules": [
                LicenseOut.model_validate(x) for x in resources["pipc_rules"]["licenses"]
            ],
        },
        rows=rows,
    )


@router.get("/open/cascade-package/pipc", response_model=CascadePackageOut)
def cascade_package_pipc() -> Any:
    """The 65 PIPC rows (CC BY 4.0) with Janus's class mapping (Apache-2.0), package version and
    citation. Published data only; no personal data."""
    try:
        out = read_pipc_package(PACKAGE_DIR)
    except (OSError, KeyError, ValueError):
        return JSONResponse({"error": "package_unavailable"}, status_code=503)
    return JSONResponse(out.model_dump(mode="json"))
