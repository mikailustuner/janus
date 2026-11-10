"""Loader: pipeline artifacts → PostgreSQL resolution tables (drug-resolution design §6, Req 9).

`python -m janus.resolution.load [--data-dir PATH] [--activate DATASET]`

Reads the `current` artifact of `titck`, `us_ndc` and `wikidata_ingredients` and, if they exist,
of `eu_fr_bdpm`, `eu_es_cima`, `ca_dpd` and `eu_it_aifa` (optional, Req 9.7), refuses any
artifact whose rows do not hash to its manifest, prepares the dataset (pure, `prepare.py`) and
writes it in one transaction that also switches `res_current`. A failure before commit leaves
the served dataset untouched. The previous dataset is kept for `--activate`. Only reference data
is written; this module and `contributions/repository.py` are the only users of `write_tx`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

import duckdb
import psycopg

from janus.db.pool import Database
from janus.integrity.registry import read_sources
from janus.observability.logging import LogEvent, configure_logging, log_event
from janus.regions.base import GS1_PREFIXES
from janus.resolution import (
    anion_acid,
    atc,
    canonical,
    code_exclusions,
    component_codes,
    matching,
    name_lists,
    names,
    ndc,
    prepare,
    prepare_eu,
    prepare_national,
)
from janus.resolution.anion_acid import AnionAcidTable
from janus.resolution.atc import DATA_DIR, CombinationRules, RouteMap
from janus.resolution.code_exclusions import (
    CodeExclusion,
    parse_code_exclusions,
)
from janus.resolution.code_exclusions import version_of as exclusions_version
from janus.resolution.component_codes import ComponentCode, parse_component_codes, version_of
from janus.resolution.prepare import (
    JANUS_CURATED,
    OPENFDA,
    TITCK,
    WIKIDATA,
    PreparedDataset,
    prepare_dataset,
)
from janus.resolution.prepare_eu import ES_CIMA, FR_BDPM
from janus.resolution.prepare_national import CA_DPD, IT_AIFA
from janus.settings import Settings

PIPELINES: dict[str, str] = {
    TITCK: "titck",
    OPENFDA: "us_ndc",
    WIKIDATA: "wikidata_ingredients",
    FR_BDPM: "eu_fr_bdpm",
    ES_CIMA: "eu_es_cima",
    CA_DPD: "ca_dpd",
    IT_AIFA: "eu_it_aifa",
}
# A dataset without them still loads (Req 9.7).
OPTIONAL: tuple[str, ...] = (FR_BDPM, ES_CIMA, CA_DPD, IT_AIFA)
SCHEMAS: dict[str, frozenset[str]] = {
    TITCK: frozenset({"titck-2"}),
    OPENFDA: frozenset({"us_ndc-2"}),
    WIKIDATA: frozenset({"wikidata_ingredients-1"}),
    FR_BDPM: frozenset({"eu_fr_bdpm-1"}),
    ES_CIMA: frozenset({"eu_es_cima-1"}),
    CA_DPD: frozenset({"ca_dpd-1"}),
    IT_AIFA: frozenset({"eu_it_aifa-1"}),
}
# The pipelines' manifests and the source registry (pipelines/sources.toml) name the French,
# Spanish, Canadian and Italian sources `bdpm`, `cima`, `dpd` and `aifa`; the resolution tables
# use the pipeline names.
REGISTRY_ID: dict[str, str] = {FR_BDPM: "bdpm", ES_CIMA: "cima", CA_DPD: "dpd", IT_AIFA: "aifa"}
SYNONYMS_FILE = DATA_DIR / "ingredient_synonyms.csv"
CURATED_FILE = DATA_DIR / "janus_ingredients.csv"
COMPONENT_FILE = DATA_DIR / "component_codes.csv"
EXCLUSIONS_FILE = DATA_DIR / "atc_code_exclusions.csv"
CURATED_HEADER = [
    "key", "label_en", "label_tr", "label_de", "label_fr", "label_es", "atc_codes", "added_on",
    "note",
]  # fmt: skip
CURATED_KEY = re.compile(r"^J[1-9][0-9]{0,5}$")
CURATED_SCHEMA = "janus_ingredients-1"
REGISTRY_FILE = DATA_DIR.parent / "pipelines" / "sources.toml"
_CODE_MODULES = (
    anion_acid,
    atc,
    canonical,
    code_exclusions,
    component_codes,
    matching,
    name_lists,
    names,
    ndc,
    prepare,
    prepare_eu,
    prepare_national,
)

type Hook = Callable[[str], None]


class LoadError(RuntimeError):
    """An artifact cannot be loaded. The message names the source and the check, no row data."""


@dataclass(frozen=True)
class Artifact:
    source_id: str
    manifest: Mapping[str, Any]
    evidence: Mapping[str, Any]
    rows: Sequence[Mapping[str, Any]]

    def verify(self) -> None:
        m = self.manifest
        if m.get("source_id") != REGISTRY_ID.get(self.source_id, self.source_id):
            raise LoadError(f"{self.source_id}: manifest names another source")
        if m.get("schema_version") not in SCHEMAS[self.source_id]:
            raise LoadError(f"{self.source_id}: unsupported schema version")
        if m.get("outcome") not in ("succeeded", "needs_review"):
            raise LoadError(f"{self.source_id}: run did not succeed")
        digest = canonical.content_hash(self.rows, str(m["schema_version"]))
        if digest != m.get("content_sha256"):
            raise LoadError(f"{self.source_id}: rows do not match the manifest content hash")


def read_rows(parquet: Path) -> list[dict[str, Any]]:
    con = duckdb.connect()
    try:
        cur = con.execute("SELECT * FROM read_parquet(?)", [str(parquet)])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
    finally:
        con.close()


def read_artifact(data_dir: Path, source_id: str) -> Artifact:
    run = data_dir / "artifacts" / PIPELINES[source_id] / "current"
    manifest_path = run / "manifest.json"
    if not manifest_path.exists():
        raise LoadError(f"{source_id}: no current artifact")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("outcome") == "needs_review" and not (run / "promotion.json").exists():
        raise LoadError(f"{source_id}: needs_review run was not promoted")
    evidence = json.loads((run / "evidence_source.json").read_text(encoding="utf-8"))
    return Artifact(source_id, manifest, evidence, read_rows(run / "rows.parquet"))


def read_synonyms(path: Path = SYNONYMS_FILE) -> tuple[tuple[str, str], ...]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["name", "qid", "note"]:
            raise LoadError("ingredient_synonyms.csv: header must be name,qid,note")
        return tuple((r["name"], r["qid"]) for r in reader)


LOCAL_SYNONYMS = "local_synonyms.csv"


def read_local_synonyms(data_dir: Path) -> tuple[tuple[str, str], ...]:
    """Synonym rows that stay in the data directory and are never committed (owner decision
    2026-11-08: the Turkish spelling of fenofibric acid). Optional; part of the dataset version."""
    path = data_dir / "resolution" / LOCAL_SYNONYMS
    return read_synonyms(path) if path.is_file() else ()


@dataclass(frozen=True)
class Curated:
    """Janus ingredient keys from `data/janus_ingredients.csv` (owner decision 2026-11-07)."""

    rows: tuple[dict[str, Any], ...] = ()  # Wikidata-shaped rows, qid = the Janus key
    sha256: str = ""
    added_on: str = ""


def parse_curated(text: str, codeless: frozenset[str] = frozenset()) -> Curated:
    """Pure. Refuses a bad header, key, code or date; names the row, never the content.

    A key in `codeless` (a key of `data/component_codes.csv`) may have no `atc_codes`: its one
    code is the reviewed combination-code pair (DP43)."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != CURATED_HEADER:
        raise LoadError("janus_ingredients.csv: header is not the expected one")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    dates: list[str] = []
    for n, r in enumerate(reader, start=2):
        key = (r["key"] or "").strip()
        codes = [c.strip() for c in (r["atc_codes"] or "").split(";") if c.strip()]
        if not CURATED_KEY.fullmatch(key) or key in seen:
            raise LoadError(f"janus_ingredients.csv row {n}: bad or repeated key")
        if (not codes and key not in codeless) or not all(
            atc.is_ingredient_level(c) for c in codes
        ):
            raise LoadError(f"janus_ingredients.csv row {n}: codes must be ingredient-level")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["added_on"] or "") or not r["label_en"]:
            raise LoadError(f"janus_ingredients.csv row {n}: missing label or date")
        seen.add(key)
        dates.append(r["added_on"])
        row: dict[str, Any] = {"qid": key, "atc_codes": codes, "rxcuis": []}
        for lang in prepare.LANGS:
            row[f"label_{lang}"] = (r[f"label_{lang}"] or "").strip() or None
            row[f"aliases_{lang}"] = []
        rows.append(row)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest() if rows else ""
    return Curated(tuple(rows), digest, max(dates) if dates else "")


def read_curated(path: Path = CURATED_FILE, codeless: frozenset[str] = frozenset()) -> Curated:
    return (
        parse_curated(path.read_text(encoding="utf-8"), codeless) if path.is_file() else Curated()
    )


def read_code_exclusions(path: Path = EXCLUSIONS_FILE) -> tuple[CodeExclusion, ...]:
    """The reviewed (Wikidata key, wrong code) pairs; an invalid file refuses the load."""
    if not path.is_file():
        return ()
    try:
        return parse_code_exclusions(path.read_text(encoding="utf-8"))
    except atc.RulesFileError as exc:
        raise LoadError(str(exc)) from exc


def read_component_codes(path: Path = COMPONENT_FILE) -> tuple[ComponentCode, ...]:
    """The reviewed (key, combination code) pairs; an invalid file refuses the load."""
    if not path.is_file():
        return ()
    try:
        return parse_component_codes(path.read_text(encoding="utf-8"))
    except atc.RulesFileError as exc:
        raise LoadError(str(exc)) from exc


def code_version() -> str:
    digest = hashlib.sha256()
    for module in _CODE_MODULES:
        digest.update(Path(module.__file__ or "").read_bytes())
    return digest.hexdigest()


@dataclass(frozen=True)
class Inputs:
    artifacts: Mapping[str, Artifact]
    rules: CombinationRules
    route_map: RouteMap
    synonyms: tuple[tuple[str, str], ...]
    code: str
    # source id -> cadence_days from pipelines/sources.toml (freshness rule, DP17)
    cadences: Mapping[str, int | None] = field(default_factory=dict[str, int | None])
    curated: Curated = field(default_factory=Curated)
    acid: AnionAcidTable = field(default_factory=AnionAcidTable)
    component_codes: tuple[ComponentCode, ...] = ()
    code_exclusions: tuple[CodeExclusion, ...] = ()

    def describe(self) -> dict[str, Any]:
        syn = hashlib.sha256(json.dumps(self.synonyms, ensure_ascii=False).encode()).hexdigest()
        return {
            "sources": {
                s: {
                    "run_id": a.manifest["run_id"],
                    "content_sha256": a.manifest["content_sha256"],
                    "schema_version": a.manifest["schema_version"],
                }
                for s, a in sorted(self.artifacts.items())
            },
            "combination_rules": self.rules.version,
            "route_map": self.route_map.version,
            "synonyms": syn,
            "name_rules": names.rules_version(),
            "anion_acid": self.acid.version,
            "cadences": dict(sorted(self.cadences.items())),
            "curated_keys": self.curated.sha256,
            "component_codes": version_of(
                json.dumps([asdict(c) for c in self.component_codes], sort_keys=True)
                if self.component_codes
                else ""
            ),
            "code_exclusions": exclusions_version(self.code_exclusions),
            "country_table": hashlib.sha256(repr(GS1_PREFIXES).encode()).hexdigest(),
            "code": self.code,
        }

    def dataset_version(self) -> str:
        """Same inputs → same version (Req 9.4). Run ids are excluded: content decides."""
        d = self.describe()
        for s in d["sources"].values():
            del s["run_id"]
        return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()


def gather(
    data_dir: Path,
    rules: CombinationRules | None = None,
    route_map: RouteMap | None = None,
    synonyms: tuple[tuple[str, str], ...] | None = None,
    registry: Path = REGISTRY_FILE,
) -> Inputs:
    artifacts = {s: read_artifact(data_dir, s) for s in PIPELINES if s not in OPTIONAL}
    for s in OPTIONAL:
        # Absent: the dataset loads without it. Present but invalid: read_artifact refuses.
        if (data_dir / "artifacts" / PIPELINES[s] / "current" / "manifest.json").exists():
            artifacts[s] = read_artifact(data_dir, s)
    try:
        sources = read_sources(registry)
    except (OSError, ValueError) as exc:
        raise LoadError("source registry (pipelines/sources.toml) cannot be read") from exc
    cadences: dict[str, int | None] = {}
    for s in artifacts:
        rid = REGISTRY_ID.get(s, s)
        cadences[s] = sources[rid].cadence_days if rid in sources else None
    exclusions = read_code_exclusions()
    components = read_component_codes()
    curated = read_curated(codeless=frozenset(c.key for c in components))
    unknown = {c.key for c in components} - {str(r["qid"]) for r in curated.rows}
    if unknown:
        raise LoadError("component_codes.csv: a key is not a curated Janus key")
    return Inputs(
        artifacts,
        rules or CombinationRules.load(),
        route_map or RouteMap.load(),
        (*read_synonyms(), *read_local_synonyms(data_dir)) if synonyms is None else synonyms,
        code_version(),
        cadences,
        curated,
        AnionAcidTable.load(),
        components,
        exclusions,
    )


def prepare_inputs(inputs: Inputs) -> PreparedDataset:
    try:
        return _prepare(inputs)
    except atc.RulesFileError as exc:
        text = str(exc)
        named = text.startswith("component_codes.csv")  # the message names its own file
        raise LoadError(text if named else f"data/anion_acid_forms.csv: {text}") from exc


def _prepare(inputs: Inputs) -> PreparedDataset:
    return prepare_dataset(
        inputs.artifacts[TITCK].rows,
        inputs.artifacts[OPENFDA].rows,
        inputs.artifacts[WIKIDATA].rows,
        inputs.rules,
        inputs.route_map,
        inputs.synonyms,
        inputs.curated.rows,
        inputs.acid,
        component_codes=inputs.component_codes,
        code_exclusions=inputs.code_exclusions,
        fr_rows=inputs.artifacts[FR_BDPM].rows if FR_BDPM in inputs.artifacts else None,
        es_rows=inputs.artifacts[ES_CIMA].rows if ES_CIMA in inputs.artifacts else None,
        ca_rows=inputs.artifacts[CA_DPD].rows if CA_DPD in inputs.artifacts else None,
        it_rows=inputs.artifacts[IT_AIFA].rows if IT_AIFA in inputs.artifacts else None,
    )


def missing_sources(inputs: Inputs) -> tuple[str, ...]:
    """The optional sources this dataset is loaded without (printed and logged by `main`)."""
    return tuple(s for s in OPTIONAL if s not in inputs.artifacts)


def current_dataset(conn: psycopg.Connection) -> str | None:
    row = conn.execute("SELECT dataset_id FROM res_current").fetchone()
    return None if row is None else str(row[0])


def _atc_json(codes: Iterable[atc.AtcCode]) -> str:
    return json.dumps(
        [{"code": a.code, "source_id": a.source_id, "product_ref": a.product_ref} for a in codes]
    )


def _copy(
    conn: psycopg.Connection,
    table: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    hook: Hook | None,
) -> None:
    if hook is not None:
        hook(table)
    cols = ", ".join(columns)
    with conn.cursor() as cur, cur.copy(f"COPY {table} ({cols}) FROM STDIN") as copy:  # pyright: ignore[reportArgumentType]
        for row in rows:
            copy.write_row(row)


def write_dataset(
    conn: psycopg.Connection,
    version: str,
    inputs: Inputs,
    ds: PreparedDataset,
    hook: Hook | None = None,
) -> None:
    """Insert one dataset and make it current. Must run inside the caller's transaction."""
    conn.execute(
        "INSERT INTO res_dataset (id, status, inputs) VALUES (%s, 'ready', %s::jsonb)",
        (version, json.dumps(inputs.describe())),
    )
    _copy(
        conn,
        "res_source_version",
        (
            "dataset_id", "source_id", "run_id", "region", "snapshot_date",
            "snapshot_is_retrieval_time", "content_sha256", "schema_version", "license",
            "source_url", "cadence_days",
        ),
        (
            (
                version, s, a.manifest["run_id"], a.manifest.get("region"),
                str(a.manifest["snapshot_date"]),
                bool(a.manifest.get("snapshot_date_is_retrieval_time")),
                a.manifest["content_sha256"], a.manifest["schema_version"],
                a.evidence.get("license") or a.manifest.get("license"),
                a.evidence.get("source_url") or "",
                inputs.cadences.get(s),
            )
            for s, a in sorted(inputs.artifacts.items())
        ),
        hook,
    )  # fmt: skip
    if inputs.curated.rows:
        c = inputs.curated
        conn.execute(
            "INSERT INTO res_source_version (dataset_id, source_id, run_id, region, snapshot_date, "
            "snapshot_is_retrieval_time, content_sha256, schema_version, license, source_url, "
            "cadence_days) VALUES (%s, %s, %s, NULL, %s, false, %s, %s, %s, %s, NULL)",
            (
                version, JANUS_CURATED, f"curated-{c.sha256[:8]}", c.added_on, c.sha256,
                CURATED_SCHEMA, "Apache-2.0 (Janus curated)", "data/janus_ingredients.csv",
            ),
        )  # fmt: skip
    _copy(
        conn,
        "res_product",
        (
            "dataset_id", "source_id", "product_id", "region", "product_name", "brand_name",
            "generic_name", "ingredient_text", "published_atc", "product_type", "routes",
            "dosage_form", "marketing_end_date", "suspension_status", "name_only",
            "product_rxcuis", "status_published",
        ),
        (
            (
                version, p.source_id, p.product_id, p.region, p.product_name, p.brand_name,
                p.generic_name, p.ingredient_text, p.published_atc, p.product_type,
                list(p.routes), p.dosage_form, p.marketing_end_date, p.suspension_status,
                p.name_only, list(p.product_rxcuis), list(p.status_published),
            )
            for p in ds.products
        ),
        hook,
    )  # fmt: skip
    _copy(
        conn,
        "res_product_code",
        ("dataset_id", "kind", "code", "code_published", "source_id", "product_id"),
        (
            (version, kind, code, published, p.source_id, p.product_id)
            for p in ds.products
            for kind, code, published in p.codes
        ),
        hook,
    )
    _copy(
        conn,
        "res_product_ingredient",
        (
            "dataset_id", "source_id", "product_id", "position", "published_name", "strength",
            "status", "reason", "qid", "key_candidates", "match_step", "atc", "atc_selection",
            "rxcuis", "rxcui_status",
        ),
        (
            (
                version, p.source_id, p.product_id, i.position, i.published_name, i.strength,
                i.status, i.reason, i.qid, list(i.key_candidates), i.match_step,
                _atc_json(i.atc), i.atc_selection, list(i.rxcuis), i.rxcui_status,
            )
            for p in ds.products
            for i in p.ingredients
        ),
        hook,
    )  # fmt: skip
    _copy(
        conn,
        "res_ingredient",
        ("dataset_id", "qid", "labels", "ingredient_atc", "rxcuis"),
        (
            (
                version,
                r.qid,
                json.dumps(dict(r.labels)),
                _atc_json(r.ingredient_atc),
                list(r.rxcuis),
            )
            for r in ds.ingredients.values()
        ),
        hook,
    )
    _copy(
        conn,
        "res_name",
        ("dataset_id", "name_key", "kind", "region", "ref", "display"),
        ((version, n.name_key, n.kind, n.region, n.ref, n.display) for n in ds.names),
        hook,
    )
    _copy(
        conn,
        "res_component_code",
        ("dataset_id", "key", "code", "evidence", "whocc_url", "whocc_date", "note"),
        (
            (version, c.key, c.code, c.evidence, c.whocc_url, c.whocc_date, c.note)
            for c in ds.component_codes
        ),
        hook,
    )
    _copy(
        conn,
        "res_combination_atc",
        ("dataset_id", "code", "reason"),
        ((version, code, reason) for code, reason in sorted(ds.combination_audit.items())),
        hook,
    )
    summary = _coverage_summary(ds.coverage)
    _copy(conn, "res_coverage", ("dataset_id", "report"), [(version, json.dumps(summary))], hook)
    _activate(conn, version)


def _coverage_summary(coverage: object) -> object:
    """Coverage without the name lists (they stay in the local report file)."""
    if isinstance(coverage, Mapping):
        items = cast(Mapping[str, object], coverage)
        return {k: _coverage_summary(v) for k, v in items.items() if k != "unmapped_top"}
    return coverage


def _activate(conn: psycopg.Connection, version: str) -> None:
    conn.execute(
        "INSERT INTO res_current (one, dataset_id) VALUES (true, %s) "
        "ON CONFLICT (one) DO UPDATE SET dataset_id = EXCLUDED.dataset_id",
        (version,),
    )
    conn.execute("UPDATE res_dataset SET status = 'ready' WHERE id = %s", (version,))


def retire_old(conn: psycopg.Connection, keep_previous: str | None) -> int:
    """Delete every dataset except the current one and `keep_previous`."""
    current = current_dataset(conn)
    keep = [v for v in (current, keep_previous) if v]
    conn.execute("UPDATE res_dataset SET status = 'retired' WHERE NOT (id = ANY(%s))", (keep,))
    cur = conn.execute("DELETE FROM res_dataset WHERE NOT (id = ANY(%s))", (keep,))
    return cur.rowcount


@dataclass(frozen=True)
class LoadResult:
    dataset_version: str
    changed: bool
    products: int


def load(
    db: Database,
    inputs: Inputs,
    *,
    hook: Hook | None = None,
    report_dir: Path | None = None,
) -> LoadResult:
    for a in inputs.artifacts.values():
        a.verify()  # Req 9.1: refuse before touching the database
    version = inputs.dataset_version()
    with db.write_tx() as conn:
        previous = current_dataset(conn)
        exists = conn.execute("SELECT 1 FROM res_dataset WHERE id = %s", (version,)).fetchone()
        if previous == version:
            return LoadResult(version, False, 0)
        if exists:  # loaded before, e.g. a rollback target: just switch
            _activate(conn, version)
            return LoadResult(version, True, 0)
    ds = prepare_inputs(inputs)
    with db.write_tx() as conn:
        previous = current_dataset(conn)
        write_dataset(conn, version, inputs, ds, hook)
    with db.write_tx() as conn:
        retire_old(conn, previous)
    if report_dir is not None:
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / f"coverage-{version[:16]}.json"
        path.write_text(json.dumps(ds.coverage, ensure_ascii=False, indent=1), encoding="utf-8")
    return LoadResult(version, True, len(ds.products))


def activate(db: Database, version: str) -> None:
    with db.write_tx() as conn:
        if conn.execute("SELECT 1 FROM res_dataset WHERE id = %s", (version,)).fetchone() is None:
            raise LoadError("unknown dataset version")
        _activate(conn, version)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m janus.resolution.load")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--activate", default=None, help="switch back to a kept dataset version")
    args = parser.parse_args(argv)
    configure_logging()
    settings = Settings.from_env()
    if not settings.database_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    db = Database(settings.database_url)
    db.open()
    try:
        if args.activate:
            activate(db, args.activate)
            print(f"activated {args.activate}")
            return 0
        data_dir = args.data_dir or settings.data_dir
        if data_dir is None:
            print("set --data-dir or JANUS_DATA_DIR", file=sys.stderr)
            return 2
        inputs = gather(data_dir)
        held = sorted(inputs.artifacts)
        print(f"sources: {', '.join(held)}")
        absent = missing_sources(inputs)
        if absent:
            print(f"loaded without: {', '.join(absent)}", file=sys.stderr)
        log_event(LogEvent.resolution_sources, count=len(held))
        result = load(db, inputs, report_dir=data_dir / "resolution")
        log_event(LogEvent.resolution_load, count=result.products)
        state = "loaded" if result.changed else "unchanged"
        print(  # log-guard: ignore
            f"{state} dataset {result.dataset_version} ({result.products} products)"
        )
        return 0
    except LoadError as exc:
        print(f"load refused: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
