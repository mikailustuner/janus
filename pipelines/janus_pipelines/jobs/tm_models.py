# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""Offline model jobs (time-machine design §6.5, Req 5).

* `tm_pbpk`: runs `janus/timemachine/httk_run.R` with Rscript against the user R library under
  `.data/tools/R-library` (httk, MIT). Every package version the run used is recorded in the
  manifest, so a result can be reproduced. Refused (exit 4) when Rscript or the library is
  absent: the API only ever serves precomputed artifacts, and CI never needs R.
* `tm_admet`: runs `tools/admet_predict.py` with the pinned CPU environment under
  `.data/tools/admet-ai-env` (ADMET-AI, MIT). Structures come from PubChem *by name* and are
  checked against the curated InChIKey before use (DP-T6).

Both are deterministic given their seed and write no health data.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import polars as pl

from janus_pipelines.core.canonical import Row, sha256_bytes
from janus_pipelines.core.http import make_fetcher
from janus_pipelines.core.runner import (
    Job,
    ParseResult,
    RawInput,
    RunContext,
    ToolUnavailableError,
)
from janus_pipelines.core.validation import ExpectedSchema, Field, SchemaReport
from janus_pipelines.jobs.time_machine import PUG, read_comparators, read_constituents

TOOLS = Path("tools")
R_LIBRARY = "R-library"
ADMET_ENV = "admet-ai-env"
SEED = 20261109
HTTK_SAMPLES = 1000
R_TIMEOUT = 3600
ADMET_TIMEOUT = 1800

# Drugs validated against published human PK, and the cascade drugs httk has human parameters
# for. `days` is the simulated window; it must cover the published sampling window.
VALIDATION: tuple[tuple[str, float, int], ...] = (
    ("Risperidone", 2.0, 4),
    ("Midazolam", 2.0, 2),
    ("Metoclopramide", 20.0, 4),
    ("Haloperidol", 5.0, 12),
)
POPULATION_DRUGS: tuple[str, ...] = ("Haloperidol", "Risperidone", "Metoclopramide")


def _tools_dir(ctx: RunContext) -> Path:
    return ctx.data_dir / "tools"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# --- tm_pbpk ---------------------------------------------------------------------------------

PBPK_SCHEMA = ExpectedSchema(
    version="tm-pbpk-1",
    fields=(Field("kind", frozenset({"str"})), Field("drug", frozenset({"str"}))),
)

PBPK_ROW: Mapping[str, pl.DataType] = {
    "kind": pl.String(),  # validation | population | steady_state
    "drug": pl.String(),
    "dose_mg": pl.Float64(),
    "bw_kg": pl.Float64(),
    "cmax_ng_ml": pl.Float64(),
    "tmax_h": pl.Float64(),
    "auc_ng_h_ml": pl.Float64(),
    "group": pl.String(),
    "age_low": pl.Float64(),
    "age_high": pl.Float64(),
    "css_p5_mg_l": pl.Float64(),
    "css_p50_mg_l": pl.Float64(),
    "css_p95_mg_l": pl.Float64(),
    "day_90pct_ss": pl.Float64(),
}


def _f(row: Mapping[str, str], key: str) -> float | None:
    v = row.get(key, "")
    return float(v) if v not in ("", "NA") else None


def pbpk_rows(out: Path) -> list[Row]:
    rows: list[Row] = []
    for r in _read_csv(out / "validation.csv"):
        rows.append(
            {
                "kind": "validation",
                "drug": r["chem"],
                "dose_mg": _f(r, "dose_mg"),
                "bw_kg": _f(r, "bw_kg"),
                "cmax_ng_ml": _f(r, "cmax_ng_ml"),
                "tmax_h": _f(r, "tmax_h"),
                "auc_ng_h_ml": _f(r, "auc_ng_h_ml"),
                "group": None,
                "age_low": None,
                "age_high": None,
                "css_p5_mg_l": None,
                "css_p50_mg_l": None,
                "css_p95_mg_l": None,
                "day_90pct_ss": None,
            }
        )
    for r in _read_csv(out / "population.csv"):
        rows.append(
            {
                "kind": "population",
                "drug": r["chem"],
                "dose_mg": None,
                "bw_kg": None,
                "cmax_ng_ml": None,
                "tmax_h": None,
                "auc_ng_h_ml": None,
                "group": r["group"],
                "age_low": _f(r, "age_low"),
                "age_high": _f(r, "age_high"),
                "css_p5_mg_l": _f(r, "css_p5_mg_l"),
                "css_p50_mg_l": _f(r, "css_p50_mg_l"),
                "css_p95_mg_l": _f(r, "css_p95_mg_l"),
                "day_90pct_ss": None,
            }
        )
    for r in _read_csv(out / "steady_state.csv"):
        rows.append(
            {
                "kind": "steady_state",
                "drug": r["chem"],
                "dose_mg": None,
                "bw_kg": None,
                "cmax_ng_ml": None,
                "tmax_h": None,
                "auc_ng_h_ml": None,
                "group": None,
                "age_low": None,
                "age_high": None,
                "css_p5_mg_l": None,
                "css_p50_mg_l": None,
                "css_p95_mg_l": None,
                "day_90pct_ss": _f(r, "day_90pct_ss"),
            }
        )
    return rows


@dataclass(frozen=True)
class PbpkPayload:
    out: Path
    versions: list[dict[str, str]]
    script_sha256: str


class TmPbpkJob(Job[PbpkPayload]):
    name = "tm_pbpk"
    source_id = "httk"
    schema = PBPK_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = PBPK_ROW

    def fetch(self, ctx: RunContext) -> RawInput[PbpkPayload]:
        rscript = shutil.which("Rscript")
        library = _tools_dir(ctx) / R_LIBRARY
        if rscript is None or not (library / "httk").is_dir():
            raise ToolUnavailableError(
                "tm_pbpk needs Rscript and httk in .data/tools/R-library; "
                "install them before running this job (the API serves precomputed artifacts)"
            )
        script = ctx.repo_root / "apps" / "api" / "janus" / "timemachine" / "httk_run.R"
        out = ctx.scratch_dir(self.name)
        out.mkdir(parents=True, exist_ok=True)
        with (out / "validation_input.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["chem", "dose_mg", "days"])
            w.writerows(VALIDATION)
        with (out / "population_input.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["chem"])
            w.writerows([[d] for d in POPULATION_DRUGS])
        env = {**os.environ, "R_LIBS_USER": str(library)}
        retrieved = ctx.now()
        proc = subprocess.run(  # noqa: S603 - fixed argv, our own script
            [rscript, str(script), str(out), str(SEED), str(HTTK_SAMPLES)],
            env=env,
            capture_output=True,
            text=True,
            timeout=R_TIMEOUT,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Rscript failed ({proc.returncode}): {proc.stderr[-400:]}")
        versions = _read_csv(out / "versions.csv")
        digest = sha256_bytes(script.read_bytes() + json.dumps(versions, sort_keys=True).encode())
        return RawInput(
            payload=PbpkPayload(out, versions, sha256_bytes(script.read_bytes())),
            source_urls=("https://cran.r-project.org/package=httk",),
            source_sha256=digest,
            retrieved_at=retrieved,
            snapshot_date=retrieved.date().isoformat(),
            snapshot_date_is_retrieval_time=True,
        )

    def parse(self, raw: RawInput[PbpkPayload]) -> ParseResult:
        p = raw.payload
        rows = pbpk_rows(p.out)
        kinds = {str(r["kind"]) for r in rows}
        return ParseResult(
            rows=rows,
            input_rows=len(rows),
            excluded={},
            schema=SchemaReport(),
            metrics={
                "tool_versions": {v["package"]: v["version"] for v in p.versions},
                "script_sha256": p.script_sha256,
                "seed": SEED,
                "httkpop_samples": HTTK_SAMPLES,
                "kinds": sorted(kinds),
                "httk_options": "package defaults (restrictive.clearance = TRUE), model pbtk",
                "population_age_range": "65-79 (older) vs 20-50 (younger); HTTK-Pop draws "
                "NHANES ages 0-79, so 80+ cannot be simulated",
            },
        )


# --- tm_admet --------------------------------------------------------------------------------

ADMET_SCHEMA = ExpectedSchema(
    version="tm-admet-1",
    fields=(Field("name", frozenset({"str"})), Field("pubchem_cid", frozenset({"str"}))),
)

# The predictions Janus reads (TDC task names as ADMET-AI returns them).
ADMET_COLUMNS: tuple[str, ...] = (
    "Half_Life_Obach",
    "VDss_Lombardo",
    "PPBR_AZ",
    "Clearance_Hepatocyte_AZ",
    "Clearance_Microsome_AZ",
    "Bioavailability_Ma",
    "HIA_Hou",
    "Caco2_Wang",
    "CYP3A4_Veith",
    "CYP3A4_Substrate_CarbonMangels",
    "CYP2D6_Veith",
    "hERG",
    "DILI",
    "AMES",
)

ADMET_ROW: Mapping[str, pl.DataType] = {
    "name": pl.String(),
    "pubchem_cid": pl.String(),
    "inchikey": pl.String(),
    "smiles": pl.String(),
    "molecular_weight": pl.Float64(),
    "kind": pl.String(),  # constituent | comparator
    **{c: pl.Float64() for c in ADMET_COLUMNS},
}


class StructureMismatchError(ValueError):
    """A structure fetched from PubChem does not match the curated InChIKey (P1)."""


@dataclass(frozen=True)
class Structure:
    name: str
    cid: str
    inchikey: str
    smiles: str
    mw: float
    kind: str


def check_structures(
    wanted: Sequence[tuple[str, str, str | None, str]], fetched: Mapping[str, dict[str, str]]
) -> list[Structure]:
    """`wanted`: (name, cid, curated InChIKey or None, kind). Every fetched structure must carry
    the curated InChIKey; a mismatch fails the run rather than producing a wrong prediction."""
    out: list[Structure] = []
    for name, cid, key, kind in wanted:
        row = fetched.get(cid)
        if row is None:
            raise StructureMismatchError(f"{name}: no PubChem structure for CID {cid}")
        got = row["InChIKey"]
        if key is not None and got != key:
            raise StructureMismatchError(f"{name}: InChIKey {got} does not match curated {key}")
        out.append(Structure(name, cid, got, row["SMILES"], float(row["MolecularWeight"]), kind))
    return out


def admet_rows(structures: Sequence[Structure], predictions: Sequence[dict[str, str]]) -> list[Row]:
    by_name = {p["name"]: p for p in predictions}
    rows: list[Row] = []
    for s in structures:
        p = by_name[s.name]
        rows.append(
            {
                "name": s.name,
                "pubchem_cid": s.cid,
                "inchikey": s.inchikey,
                "smiles": s.smiles,
                "molecular_weight": s.mw,
                "kind": s.kind,
                **{c: (float(p[c]) if p.get(c) not in (None, "") else None) for c in ADMET_COLUMNS},
            }
        )
    return rows


@dataclass(frozen=True)
class AdmetPayload:
    structures: list[Structure]
    predictions: list[dict[str, str]]
    freeze: str


class TmAdmetJob(Job[AdmetPayload]):
    name = "tm_admet"
    source_id = "admet_ai"
    schema = ADMET_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = ADMET_ROW

    def fetch(self, ctx: RunContext) -> RawInput[AdmetPayload]:
        env_dir = _tools_dir(ctx) / ADMET_ENV
        python = env_dir / "bin" / "python"
        if not python.is_file():
            raise ToolUnavailableError(
                "tm_admet needs the pinned environment in .data/tools/admet-ai-env; "
                "install it before running this job"
            )
        base = ctx.repo_root / "data" / "time_machine"
        cons = read_constituents(base / "constituents.csv")
        comps = read_comparators(base / "comparators.csv")
        fetcher = make_fetcher(require_contact=False)
        wanted: list[tuple[str, str, str | None, str]] = [
            (c.compound, c.cid, c.inchikey, "constituent") for c in cons
        ]
        # Comparator drugs: resolve the CID from the name (never a hard-coded id, DP-T6).
        for drug in sorted({c.drug for c in comps} | set(POPULATION_DRUGS)):
            cid = fetcher.get(f"{PUG}/compound/name/{drug.lower()}/cids/TXT").text.split()[0]
            wanted.append((drug.lower(), cid, None, "comparator"))
        cids = ",".join(sorted({c for _, c, _, _ in wanted}, key=int))
        body = fetcher.get(
            f"{PUG}/compound/cid/{cids}/property/InChIKey,SMILES,MolecularWeight/CSV"
        ).content
        fetched = {r["CID"]: r for r in csv.DictReader(body.decode().splitlines())}
        structures = check_structures(wanted, fetched)

        out = ctx.scratch_dir(self.name)
        out.mkdir(parents=True, exist_ok=True)
        src, dst = out / "admet_in.csv", out / "admet_out.csv"
        with src.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["name", "smiles"])
            w.writerows([[s.name, s.smiles] for s in structures])
        retrieved = ctx.now()
        script = ctx.repo_root / "pipelines" / TOOLS / "admet_predict.py"
        proc = subprocess.run(  # noqa: S603 - fixed argv, our own script
            [str(python), "-I", str(script), str(src), str(dst)],
            capture_output=True,
            text=True,
            timeout=ADMET_TIMEOUT,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ADMET-AI failed ({proc.returncode}): {proc.stderr[-400:]}")
        # Versions from the tool environment's own installed metadata (uv venvs have no pip).
        freeze = subprocess.run(  # noqa: S603 - fixed argv
            [
                str(python),
                "-I",
                "-c",
                "from importlib.metadata import version\n"
                "for p in ('admet-ai', 'chemprop', 'torch', 'rdkit'):\n"
                "    print(f'{p}=={version(p)}')",
            ],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        predictions = _read_csv(dst)
        return RawInput(
            payload=AdmetPayload(structures, predictions, freeze),
            source_urls=("https://github.com/swansonk14/admet_ai", PUG),
            source_sha256=sha256_bytes(body + dst.read_bytes()),
            retrieved_at=retrieved,
            snapshot_date=retrieved.date().isoformat(),
            snapshot_date_is_retrieval_time=True,
        )

    def parse(self, raw: RawInput[AdmetPayload]) -> ParseResult:
        p = raw.payload
        rows = admet_rows(p.structures, p.predictions)
        pinned = {
            line.split("==")[0].lower(): line.split("==")[1]
            for line in p.freeze.splitlines()
            if "==" in line
        }
        return ParseResult(
            rows=rows,
            input_rows=len(p.structures),
            excluded={},
            schema=SchemaReport(),
            metrics={
                "tool_versions": pinned,
                "predictions": list(ADMET_COLUMNS),
                "structures_checked_against_curated_inchikey": sum(
                    1 for s in p.structures if s.kind == "constituent"
                ),
                "note": "machine-learning predictions, not measurements",
            },
        )
