"""FAERS count builder (data-pipelines design §14, Req 15).

`python -m janus.memory.faers_build [--data-dir PATH]`

Reads the current `faers` artifact (one row per deduplicated report, ingredient names as
published), refuses it unless its rows hash to the manifest, maps every distinct ingredient name
to an ingredient key with the `drug-resolution` name ladder (non-Turkish mode), and writes a
read-only DuckDB file with report facts and count tables for Collective Memory:

    faers_totals(region, reports_mapped, reports_all)
    faers_ingredient_counts(ingredient_key, region, scope, reports)
    faers_event_counts(pt, region, reports_mapped, reports_all)
    faers_pair_counts(ingredient_key, pt, region, scope, reports)

From them the 2x2 table follows with N = reports_mapped (owner decision 2026-11-08, DP32):
a = pair, b = ingredient - a, c = event(mapped) - a, d = N - ingredient - event(mapped) + a.
`reports_all` is the sensitivity figure. Counts are reports, never people. Event terms are the
MedDRA Preferred Terms as published in FAERS; no MedDRA hierarchy is stored.

The pure reference `aggregate()` defines the counts; the SQL path is tested against it.

Schema `faers_counts-2` (collective-memory Req 11): the tables are written physically sorted by
their lookup keys (a pair lookup reads few row groups: p95 14 ms -> 5 ms on the real file),
`faers_report` carries `mapped` (the report has a mapped ingredient), and `faers_region_basis`
counts reports by region and by the country field that gave the region. Table hashes are
computed on rows in sorted order, so the layout never changes them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from janus.observability.logging import LogEvent, configure_logging, log_event
from janus.resolution import load as resolution_load
from janus.resolution import names
from janus.resolution.canonical import content_hash_stream
from janus.resolution.matching import Match, NameIndex, map_name
from janus.resolution.prepare import build_name_index
from janus.settings import Settings

SCHEMA_VERSION = "faers-1"
REGIONS = ("TR", "EU", "US", "OTHER", "UNKNOWN")
ALL = "ALL"
SUSPECT_ROLES = frozenset({"PS", "SS", "I"})
EXPOSURE_ROLES = SUSPECT_ROLES | {"C"}
MEDDRA_NOTICE = (
    "MedDRA® the Medical Dictionary for Regulatory Activities terminology is the international "
    "medical terminology developed under the auspices of ICH. MedDRA® trademark is registered "
    "by IFPMA on behalf of ICH."
)
EVENT_TERMS_NOTE = "Event terms are MedDRA Preferred Terms as published in FAERS."
COUNTS_DB = "faers_counts.duckdb"
META = "meta.json"

COUNTS_SCHEMA = "faers_counts-2"

TABLES: tuple[str, ...] = (
    "faers_report",
    "faers_report_ingredient",
    "faers_report_event",
    "faers_totals",
    "faers_ingredient_counts",
    "faers_event_counts",
    "faers_pair_counts",
    "faers_unmapped",
    "faers_region_basis",
)


class BuildError(RuntimeError):
    """The build was refused or could not complete; the current counts file is unchanged."""


type Fault = Callable[[str], None]


def no_fault(_step: str) -> None:
    return None


# --- pure reference ------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportFact:
    """One deduplicated report: region, drug lines (role, ingredient names) and event terms."""

    primaryid: str
    quarter: str
    region: str
    lines: tuple[tuple[str, tuple[str, ...]], ...]  # (role, ingredient names) per drug line
    events: tuple[str, ...]


@dataclass
class Counts:
    totals: dict[str, tuple[int, int]] = field(default_factory=dict[str, tuple[int, int]])
    ingredient: dict[tuple[str, str, str], int] = field(
        default_factory=dict[tuple[str, str, str], int]
    )
    event: dict[tuple[str, str], tuple[int, int]] = field(
        default_factory=dict[tuple[str, str], tuple[int, int]]
    )
    pair: dict[tuple[str, str, str, str], int] = field(
        default_factory=dict[tuple[str, str, str, str], int]
    )
    unmapped: dict[str, tuple[str, int, int, int]] = field(
        default_factory=dict[str, tuple[str, int, int, int]]
    )
    occurrences: Counter[str] = field(default_factory=Counter[str])
    roles_excluded: Counter[str] = field(default_factory=Counter[str])


def aggregate(reports: Iterable[ReportFact], matches: Mapping[str, Match]) -> Counts:
    """Reference definition of the count tables (Req 15.2-15.5)."""
    totals: Counter[tuple[str, str]] = Counter()  # (region, "mapped"|"all")
    ingredient: Counter[tuple[str, str, str]] = Counter()
    event_all: Counter[tuple[str, str]] = Counter()
    event_mapped: Counter[tuple[str, str]] = Counter()
    pair: Counter[tuple[str, str, str, str]] = Counter()
    unmapped_occ: Counter[str] = Counter()
    unmapped_reports: Counter[str] = Counter()
    unmapped_suspect: Counter[str] = Counter()
    out = Counts()
    for r in reports:
        keys: dict[str, bool] = {}  # ingredient key -> suspect in this report
        seen_unmapped: dict[str, bool] = {}
        for role, ingredients in r.lines:
            for name in ingredients:
                out.occurrences[name] += 1
                m = matches[name]
                if m.status != "mapped":
                    unmapped_occ[name] += 1
                if role not in EXPOSURE_ROLES:
                    out.roles_excluded[role] += 1
                    continue
                if m.status == "mapped":
                    key = m.keys[0]
                    keys[key] = keys.get(key, False) or role in SUSPECT_ROLES
                else:
                    seen_unmapped[name] = seen_unmapped.get(name, False) or role in SUSPECT_ROLES
        for name, suspect in seen_unmapped.items():
            unmapped_reports[name] += 1
            unmapped_suspect[name] += suspect
        events = set(r.events)
        mapped = bool(keys)
        for region in (r.region, ALL):
            totals[(region, "all")] += 1
            totals[(region, "mapped")] += mapped
            for pt in events:
                event_all[(pt, region)] += 1
                event_mapped[(pt, region)] += mapped
            for key, suspect in keys.items():
                ingredient[(key, region, "any")] += 1
                if suspect:
                    ingredient[(key, region, "suspect")] += 1
                for pt in events:
                    pair[(key, pt, region, "any")] += 1
                    if suspect:
                        pair[(key, pt, region, "suspect")] += 1
    out.totals = {
        region: (totals[(region, "mapped")], totals[(region, "all")])
        for region in {k[0] for k in totals}
    }
    out.ingredient = dict(ingredient)
    out.event = {k: (event_mapped[k], event_all[k]) for k in event_all}
    out.pair = dict(pair)
    for name, occ in unmapped_occ.items():
        out.unmapped[name] = (
            matches[name].status,
            occ,
            unmapped_reports[name],
            unmapped_suspect[name],
        )
    return out


# --- mapping -------------------------------------------------------------------------------


def map_names(candidates: Iterable[str], index: NameIndex) -> dict[str, Match]:
    """The resolution ladder in non-Turkish mode (steps 0, 2-5 and the unsplit check)."""
    return {name: map_name(name, index, lang="en") for name in sorted(set(candidates))}


# --- artifact ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Artifact:
    run_dir: Path
    manifest: dict[str, Any]

    @property
    def rows(self) -> Path:
        return self.run_dir / "rows.parquet"


def read_artifact(data_dir: Path) -> Artifact:
    run = data_dir / "artifacts" / "faers" / "current"
    manifest_path = run / "manifest.json"
    if not manifest_path.exists():
        raise BuildError("faers: no current artifact")
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("outcome") == "needs_review" and not (run / "promotion.json").exists():
        raise BuildError("faers: needs_review run was not promoted")
    if manifest.get("outcome") not in ("succeeded", "needs_review"):
        raise BuildError("faers: current run did not succeed")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise BuildError(f"faers: unexpected schema version {manifest.get('schema_version')}")
    return Artifact(run.resolve(), manifest)


def iter_parquet_rows(path: Path, batch: int = 50_000) -> Iterator[dict[str, Any]]:
    con = duckdb.connect()
    try:
        cur = con.execute("SELECT * FROM read_parquet(?)", [str(path)])
        cols = [c[0] for c in cur.description]
        while True:
            chunk = cur.fetchmany(batch)
            if not chunk:
                return
            for row in chunk:
                yield dict(zip(cols, row, strict=True))
    finally:
        con.close()


def verify_artifact(art: Artifact, tmp_dir: Path | None = None) -> None:
    """Refuse an artifact whose rows do not hash to its manifest (Req 15.1)."""
    digest = content_hash_stream(iter_parquet_rows(art.rows), SCHEMA_VERSION, tmp_dir=tmp_dir)
    if digest != art.manifest.get("content_sha256"):
        raise BuildError("faers: rows do not match the manifest's content hash")


# --- DuckDB writer -------------------------------------------------------------------------

_SQL_ROLES = "('PS','SS','I')"
_SQL_EXPOSURE = "('PS','SS','I','C')"


def sha256_of_table(con: duckdb.DuckDBPyConnection, table: str, scratch: Path) -> str:
    """SHA-256 of the table's rows in a sorted CSV form (order independent)."""
    path = scratch / f"{table}.csv"
    con.execute(f"COPY (SELECT * FROM {table} ORDER BY ALL) TO '{path}' (FORMAT csv, HEADER)")
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    path.unlink()
    return digest.hexdigest()


def write_counts(
    db_path: Path,
    rows_parquet: Path,
    matches: Mapping[str, Match],
    scratch: Path,
) -> dict[str, Any]:
    """Create the DuckDB file; returns facts for the metadata (row counts, table hashes,
    occurrence and role statistics). `matches` maps every ingredient name in the artifact."""
    con = duckdb.connect(str(db_path))
    try:
        con.execute(f"SET temp_directory = '{scratch}'")
        con.execute("PRAGMA enable_progress_bar = false")
        if "'" in str(rows_parquet):
            raise BuildError("the artifact path must not contain a quote")
        # A path cannot be a bound parameter in DDL; it is our own data-directory path.
        con.execute(f"CREATE VIEW src AS SELECT * FROM read_parquet('{rows_parquet}')")
        con.execute(
            "CREATE TABLE name_map (name VARCHAR, status VARCHAR, step VARCHAR, "
            "ingredient_key VARCHAR)"
        )
        if matches:
            con.executemany(
                "INSERT INTO name_map VALUES (?, ?, ?, ?)",
                [
                    (n, m.status, m.step, m.keys[0] if m.status == "mapped" else None)
                    for n, m in sorted(matches.items())
                ],
            )
        con.execute(
            """
            CREATE TEMP TABLE rep_base AS
            SELECT CAST(row_number() OVER (ORDER BY CAST(primaryid AS BIGINT), quarter) AS INTEGER)
                     AS report_id,
                   primaryid, caseid, quarter, region, region_basis
            FROM src
            """
        )
        con.execute(
            """
            CREATE TEMP TABLE drug_lines AS
            WITH d AS (SELECT primaryid, quarter, unnest(drugs) AS drug FROM src)
            SELECT r.report_id, drug.role AS role, unnest(drug.ingredients) AS name
            FROM d JOIN rep_base r ON r.primaryid = d.primaryid AND r.quarter = d.quarter
            """
        )
        con.execute(
            f"""
            CREATE TABLE faers_report_ingredient AS
            SELECT l.report_id, m.ingredient_key,
                   bool_or(l.role IN {_SQL_ROLES}) AS suspect
            FROM drug_lines l JOIN name_map m ON m.name = l.name AND m.status = 'mapped'
            WHERE l.role IN {_SQL_EXPOSURE}
            GROUP BY l.report_id, m.ingredient_key
            ORDER BY m.ingredient_key, l.report_id
            """
        )
        con.execute(
            """
            CREATE TABLE faers_report_event AS
            WITH e AS (SELECT primaryid, quarter, unnest(events) AS pt FROM src)
            SELECT DISTINCT r.report_id, e.pt
            FROM e JOIN rep_base r ON r.primaryid = e.primaryid AND r.quarter = e.quarter
            ORDER BY r.report_id, e.pt
            """
        )
        con.execute(
            """
            CREATE TABLE faers_report AS
            SELECT r.report_id, r.primaryid, r.caseid, r.quarter, r.region, r.region_basis,
                   EXISTS (SELECT 1 FROM faers_report_ingredient i WHERE i.report_id = r.report_id)
                     AS mapped
            FROM rep_base r
            ORDER BY r.report_id
            """
        )
        con.execute("CREATE TEMP VIEW rep AS SELECT report_id, region, mapped FROM faers_report")
        con.execute(
            """
            CREATE TABLE faers_region_basis AS
            WITH by_region AS (
              SELECT region, region_basis AS basis, CAST(count(*) AS BIGINT) AS reports
              FROM faers_report GROUP BY region, region_basis)
            SELECT * FROM (
              SELECT * FROM by_region
              UNION ALL
              SELECT 'ALL', basis, CAST(sum(reports) AS BIGINT) FROM by_region GROUP BY basis)
            ORDER BY region, basis
            """
        )
        con.execute(
            """
            CREATE TABLE faers_totals AS
            WITH by_region AS (
              SELECT region, CAST(sum(CASE WHEN mapped THEN 1 ELSE 0 END) AS BIGINT)
                       AS reports_mapped, CAST(count(*) AS BIGINT) AS reports_all
              FROM rep GROUP BY region)
            SELECT * FROM by_region
            UNION ALL
            SELECT 'ALL', CAST(sum(reports_mapped) AS BIGINT), CAST(sum(reports_all) AS BIGINT)
            FROM by_region
            """
        )
        con.execute(
            """
            CREATE TABLE faers_ingredient_counts AS
            WITH x AS (
              SELECT i.ingredient_key, r.region, s.scope
              FROM faers_report_ingredient i JOIN rep r ON r.report_id = i.report_id
              JOIN (SELECT 'any' AS scope UNION ALL SELECT 'suspect') s
                ON s.scope = 'any' OR i.suspect),
            by_region AS (
              SELECT ingredient_key, region, scope, CAST(count(*) AS BIGINT) AS reports
              FROM x GROUP BY ALL)
            SELECT * FROM (
              SELECT * FROM by_region
              UNION ALL
              SELECT ingredient_key, 'ALL', scope, CAST(sum(reports) AS BIGINT)
              FROM by_region GROUP BY ingredient_key, scope)
            ORDER BY ingredient_key, scope, region
            """
        )
        con.execute(
            """
            CREATE TABLE faers_event_counts AS
            WITH by_region AS (
              SELECT e.pt, r.region,
                     CAST(sum(CASE WHEN r.mapped THEN 1 ELSE 0 END) AS BIGINT) AS reports_mapped,
                     CAST(count(*) AS BIGINT) AS reports_all
              FROM faers_report_event e JOIN rep r ON r.report_id = e.report_id
              GROUP BY e.pt, r.region)
            SELECT * FROM (
              SELECT * FROM by_region
              UNION ALL
              SELECT pt, 'ALL', CAST(sum(reports_mapped) AS BIGINT),
                     CAST(sum(reports_all) AS BIGINT)
              FROM by_region GROUP BY pt)
            ORDER BY pt, region
            """
        )
        con.execute(
            """
            CREATE TABLE faers_pair_counts AS
            WITH x AS (
              SELECT i.ingredient_key, e.pt, r.region, s.scope
              FROM faers_report_ingredient i
              JOIN faers_report_event e ON e.report_id = i.report_id
              JOIN rep r ON r.report_id = i.report_id
              JOIN (SELECT 'any' AS scope UNION ALL SELECT 'suspect') s
                ON s.scope = 'any' OR i.suspect),
            by_region AS (
              SELECT ingredient_key, pt, region, scope, CAST(count(*) AS BIGINT) AS reports
              FROM x GROUP BY ALL)
            SELECT * FROM (
              SELECT * FROM by_region
              UNION ALL
              SELECT ingredient_key, pt, 'ALL', scope, CAST(sum(reports) AS BIGINT)
              FROM by_region GROUP BY ingredient_key, pt, scope)
            ORDER BY ingredient_key, pt, scope, region
            """
        )
        con.execute(
            f"""
            CREATE TABLE faers_unmapped AS
            WITH occ AS (
              SELECT name, count(*) AS occurrences FROM drug_lines GROUP BY name),
            exp AS (
              SELECT name, count(DISTINCT report_id) AS reports,
                     count(DISTINCT CASE WHEN role IN {_SQL_ROLES} THEN report_id END)
                       AS suspect_reports
              FROM drug_lines WHERE role IN {_SQL_EXPOSURE} GROUP BY name)
            SELECT m.name, m.status, CAST(o.occurrences AS BIGINT) AS occurrences,
                   CAST(coalesce(e.reports, 0) AS BIGINT) AS reports,
                   CAST(coalesce(e.suspect_reports, 0) AS BIGINT) AS suspect_reports
            FROM name_map m JOIN occ o ON o.name = m.name LEFT JOIN exp e ON e.name = m.name
            WHERE m.status <> 'mapped'
            ORDER BY m.name
            """
        )
        stats: dict[str, Any] = {}
        stats["rows"] = {
            t: int(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0])  # type: ignore[index]
            for t in TABLES
        }
        stats["occurrences_total"] = int(
            con.execute("SELECT count(*) FROM drug_lines").fetchone()[0]  # type: ignore[index]
        )
        stats["occurrences_by_status"] = {
            str(k): int(v)
            for k, v in con.execute(
                "SELECT m.status, count(*) FROM drug_lines l JOIN name_map m ON m.name = l.name "
                "GROUP BY m.status"
            ).fetchall()
        }
        stats["mapped_occurrences_by_step"] = {
            str(k): int(v)
            for k, v in con.execute(
                "SELECT m.step, count(*) FROM drug_lines l JOIN name_map m ON m.name = l.name "
                "WHERE m.status = 'mapped' GROUP BY m.step"
            ).fetchall()
        }
        stats["occurrences_by_role"] = {
            str(k): int(v)
            for k, v in con.execute(
                "SELECT role, count(*) FROM drug_lines GROUP BY role"
            ).fetchall()
        }
        stats["scope_coverage"] = {
            scope: [
                int(x)
                for x in con.execute(
                    f"SELECT count(*) FILTER (WHERE m.status = 'mapped'), count(*) "
                    f"FROM drug_lines l JOIN name_map m ON m.name = l.name WHERE l.role IN {roles}"
                ).fetchone()  # type: ignore[union-attr]
            ]
            for scope, roles in (("suspect", _SQL_ROLES), ("any", _SQL_EXPOSURE))
        }
        stats["top_unmapped"] = [
            {"name": n, "status": s, "occurrences": int(o), "reports": int(r)}
            for n, s, o, r in con.execute(
                "SELECT name, status, occurrences, reports FROM faers_unmapped "
                "ORDER BY occurrences DESC, name LIMIT 50"
            ).fetchall()
        ]
        stats["candidates"] = _candidate_impact(con)
        stats["table_sha256"] = {t: sha256_of_table(con, t, scratch) for t in TABLES}
        return stats
    finally:
        con.close()


def _candidate_impact(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Occurrences that candidate `drug-resolution` name rules would affect (not applied)."""

    def one(sql: str) -> int:
        row = con.execute(sql).fetchone()
        return int(row[0] or 0) if row else 0

    return {
        "biologic_suffix": one(
            "SELECT sum(occurrences) FROM faers_unmapped WHERE regexp_matches(name, '-[A-Z]{4}$')"
        ),
        "mycophenolate_salt_form": one(
            "SELECT sum(occurrences) FROM faers_unmapped WHERE name LIKE 'MYCOPHENOLATE%'"
        ),
        "single_part_of_combination": one(
            "SELECT count(*) FROM (SELECT unnest(drug.ingredients) AS n, "
            "len(drug.ingredients) AS k FROM (SELECT unnest(drugs) AS drug FROM src)) x "
            "JOIN faers_unmapped u ON u.name = x.n WHERE x.k > 1"
        ),
    }


# --- build ---------------------------------------------------------------------------------


def build_id(faers_sha: str, resolution_version: str, now: datetime) -> str:
    stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{faers_sha[:8]}-{resolution_version[:8]}-{secrets.token_hex(2)}"


def counts_root(data_dir: Path) -> Path:
    return data_dir / "memory" / "faers_counts"


def current_build(data_dir: Path) -> str | None:
    link = counts_root(data_dir) / "current"
    return Path(os.readlink(link)).name if link.is_symlink() else None


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def swap_current(root: Path, run_id: str) -> None:
    """Point `current` at runs/<run_id> in one atomic step."""
    tmp = root / f"current.tmp-{run_id}"
    if tmp.is_symlink():
        tmp.unlink()
    os.symlink(Path("runs") / run_id, tmp)
    os.replace(tmp, root / "current")
    _fsync_dir(root)


@dataclass(frozen=True)
class BuildResult:
    build_id: str
    path: Path
    reports: int
    reports_mapped: int


def build_counts(
    data_dir: Path,
    index: NameIndex,
    *,
    resolution_version: str,
    rules_version: Mapping[str, Any],
    code_version: str,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    fault: Fault = no_fault,
) -> BuildResult:
    """Verify the artifact, map names, write the counts file, switch `current`."""
    art = read_artifact(data_dir)
    root = counts_root(data_dir)
    scratch_parent = root / "staging"
    scratch_parent.mkdir(parents=True, exist_ok=True)
    verify_artifact(art, tmp_dir=scratch_parent)
    names_in = _distinct_names(art.rows)
    matches = map_names(names_in, index)
    bid = build_id(str(art.manifest["content_sha256"]), resolution_version, now())
    staging = scratch_parent / bid
    staging.mkdir(parents=True, exist_ok=False)
    try:
        fault("write_db")
        stats = write_counts(staging / COUNTS_DB, art.rows, matches, staging)
        meta = {
            "build_id": bid,
            "schema_version": COUNTS_SCHEMA,
            "faers_run_id": art.manifest["run_id"],
            "faers_content_sha256": art.manifest["content_sha256"],
            "snapshot_date": art.manifest.get("snapshot_date"),
            "window": art.manifest.get("metrics", {}).get("window"),
            "region_rule": art.manifest.get("metrics", {}).get("region_rule"),
            "resolution_dataset_version": resolution_version,
            "rules_version": dict(rules_version),
            "code_version": code_version,
            "built_at": now().astimezone(UTC).isoformat(timespec="seconds"),
            "meddra_notice": MEDDRA_NOTICE,
            "event_terms": EVENT_TERMS_NOTE,
            "counts_are": (
                "reports, not people; FAERS reports are spontaneous and not deduplicated "
                "across cases"
            ),
            "primary_denominator": "reports_mapped",
            "stats": stats,
        }
        _store_meta(staging / COUNTS_DB, meta)
        (staging / META).write_text(
            json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        fault("finish")
        runs = root / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        os.replace(staging, runs / bid)
        _fsync_dir(runs)
        fault("promote_replace")
        swap_current(root, bid)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        for leftover in scratch_parent.glob("hash-*"):
            shutil.rmtree(leftover, ignore_errors=True)
    totals = {
        r: (m, a)
        for r, m, a in _read(runs / bid / COUNTS_DB, "SELECT * FROM faers_totals")
        if r == ALL
    }
    mapped, total = totals.get(ALL, (0, 0))
    return BuildResult(bid, runs / bid / COUNTS_DB, int(total), int(mapped))


def _store_meta(db_path: Path, meta: Mapping[str, Any]) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE TABLE faers_meta (key VARCHAR PRIMARY KEY, value VARCHAR)")
        con.executemany(
            "INSERT INTO faers_meta VALUES (?, ?)",
            [
                (k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, sort_keys=True))
                for k, v in sorted(meta.items())
            ],
        )
    finally:
        con.close()


def _read(db_path: Path, sql: str) -> list[tuple[Any, ...]]:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _distinct_names(rows: Path) -> list[str]:
    con = duckdb.connect()
    try:
        return [
            str(r[0])
            for r in con.execute(
                "SELECT DISTINCT n FROM (SELECT unnest(d.ingredients) AS n FROM "
                "(SELECT unnest(drugs) AS d FROM read_parquet(?)))",
                [str(rows)],
            ).fetchall()
        ]
    finally:
        con.close()


def write_coverage_report(meta_stats: Mapping[str, Any], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(meta_stats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m janus.memory.faers_build")
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    configure_logging()
    settings = Settings.from_env()
    data_dir = args.data_dir or settings.data_dir
    if data_dir is None:
        print("set --data-dir or JANUS_DATA_DIR", file=sys.stderr)
        return 2
    try:
        inputs = resolution_load.gather(data_dir)
        for a in inputs.artifacts.values():
            a.verify()
        wikidata = inputs.artifacts[resolution_load.WIKIDATA].rows
        index = build_name_index(
            wikidata, inputs.rules, inputs.synonyms, inputs.curated.rows, inputs.acid
        )
        described = inputs.describe()
        result = build_counts(
            data_dir,
            index,
            resolution_version=inputs.dataset_version(),
            rules_version={
                "name_rules": names.RULES_VERSION,
                "combination_rules": described["combination_rules"],
                "synonyms": described["synonyms"],
                "curated_keys": described["curated_keys"],
            },
            code_version=inputs.code,
        )
    except (BuildError, resolution_load.LoadError) as exc:
        print(f"build refused: {exc}", file=sys.stderr)
        return 1
    meta = json.loads(
        (counts_root(data_dir) / "runs" / result.build_id / META).read_text(encoding="utf-8")
    )
    write_coverage_report(meta["stats"], data_dir / "memory" / f"coverage-{result.build_id}.json")
    log_event(LogEvent.faers_build, count=result.reports)
    print(
        f"built {result.build_id}: {result.reports} reports, "
        f"{result.reports_mapped} with a mapped ingredient"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ALL",
    "REGIONS",
    "Artifact",
    "BuildError",
    "BuildResult",
    "Counts",
    "ReportFact",
    "aggregate",
    "build_counts",
    "current_build",
    "map_names",
    "write_counts",
]
