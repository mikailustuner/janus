"""Read side of the FAERS counts file (collective-memory design §4, Req 7, 9).

`CountsReader` opens `faers_counts.duckdb` read-only (no spill to disk, no external access, bounded
memory), checks the schema version and the tables, and hands out per-request `Session`s. Sessions
run parameterised statements only and count them (the budget of Req 9.6 is a property).
`CountsHolder` follows the atomic `current` link, so a newly promoted build is picked up without a
restart; a missing, half-written or wrong-schema file fails closed with `CountsError`.

Cells are returned as raw integers (`RawCells`); the statistics are `stats.py`'s job. Counts are
reports, never people.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import duckdb

from janus.integrity.freshness import Freshness, freshness, parse_snapshot_date
from janus.memory.faers_build import COUNTS_DB, COUNTS_SCHEMA, TABLES, counts_root
from janus.memory.model import ALL_REGION, REGIONS, RESPONSE_REGIONS

FAERS_CADENCE_DAYS: Final = 91  # pipelines/sources.toml, source `faers` (checked by a test)
REQUIRED_META: Final = (
    "build_id",
    "schema_version",
    "faers_run_id",
    "snapshot_date",
    "window",
    "resolution_dataset_version",
    "code_version",
    "built_at",
    "meddra_notice",
)
DUCKDB_SETTINGS: Final = (
    "SET memory_limit = '1GB'",
    "SET threads TO 4",
    "SET max_temp_directory_size = '0GB'",
    "SET enable_external_access = false",
)


class CountsError(RuntimeError):
    """The counts file is missing, unreadable or invalid. Never carries a medicine or event."""


@dataclass(frozen=True)
class SnapshotMeta:
    build_id: str
    schema_version: str
    faers_run_id: str
    snapshot_date: str
    window: tuple[str, ...]
    resolution_dataset_version: str
    code_version: str
    built_at: str
    meddra_notice: str


@dataclass(frozen=True)
class RawCells:
    """Counts behind one 2x2 table, in one region and scope (all reports, never people)."""

    n_mapped: int  # primary N: reports with a mapped ingredient
    n_all: int  # sensitivity N: all deduplicated reports
    exposure: int  # reports with the ingredient / all ingredients of the set (mapped by definition)
    event_mapped: int  # reports with the event among mapped reports
    event_all: int  # reports with the event among all reports
    a: int  # exposure and event


def _int(v: Any) -> int:
    return 0 if v is None else int(v)


# --- pure helpers --------------------------------------------------------------------------


def snapshot_freshness(snapshot_date: str, today: Any) -> Freshness:
    """Twice the FAERS cadence (the freshness rule of evidence-integrity)."""
    return freshness(parse_snapshot_date(snapshot_date), today, FAERS_CADENCE_DAYS)


def counts_match_served(counts_version: str, served_version: str | None) -> bool | None:
    """None when no resolution dataset is served; else whether the versions are equal."""
    return None if served_version is None else counts_version == served_version


# --- the reader ----------------------------------------------------------------------------


def _read_meta(con: duckdb.DuckDBPyConnection) -> SnapshotMeta:
    try:
        rows = dict(con.execute("SELECT key, value FROM faers_meta").fetchall())
    except duckdb.Error as exc:
        raise CountsError("counts metadata cannot be read") from exc
    for key in REQUIRED_META:
        if key not in rows:
            raise CountsError("counts metadata is incomplete")
    if rows["schema_version"] != COUNTS_SCHEMA:
        raise CountsError("counts file has another schema version")
    try:
        window = tuple(str(q) for q in json.loads(rows["window"]))
    except (ValueError, TypeError) as exc:
        raise CountsError("counts metadata is invalid") from exc
    return SnapshotMeta(
        build_id=rows["build_id"],
        schema_version=rows["schema_version"],
        faers_run_id=rows["faers_run_id"],
        snapshot_date=rows["snapshot_date"],
        window=window,
        resolution_dataset_version=rows["resolution_dataset_version"],
        code_version=rows["code_version"],
        built_at=rows["built_at"],
        meddra_notice=rows["meddra_notice"],
    )


def _verify_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Every table exists, and the row counts agree with the metadata written at build time."""
    try:
        row = con.execute("SELECT value FROM faers_meta WHERE key = 'stats'").fetchone()
        if row is None:
            raise CountsError("counts metadata is incomplete")
        expected: Mapping[str, int] = json.loads(str(row[0]))["rows"]
        for table in TABLES:
            found = con.execute(f"SELECT count(*) FROM {table}").fetchone()  # noqa: S608
            if found is None or _int(found[0]) != int(expected[table]):
                raise CountsError("a counts table does not match its metadata")
    except (duckdb.Error, KeyError, ValueError, TypeError) as exc:
        raise CountsError("counts tables cannot be verified") from exc


class CountsReader:
    def __init__(self, path: Path) -> None:
        try:
            con = duckdb.connect(str(path), read_only=True)
        except duckdb.Error as exc:
            raise CountsError("counts file cannot be opened") from exc
        try:
            for stmt in DUCKDB_SETTINGS:
                con.execute(stmt)
            self.meta = _read_meta(con)
            _verify_tables(con)
        except BaseException:
            con.close()
            raise
        self._con = con
        self.path = path

    def session(self) -> Session:
        return Session(self)

    def close(self) -> None:
        self._con.close()


class Session:
    """One request's view: its own cursor and statement counter."""

    def __init__(self, reader: CountsReader) -> None:
        self.reader = reader
        self.meta = reader.meta
        self.statements = 0
        self._cur = reader._con.cursor()  # pyright: ignore[reportPrivateUsage]

    def close(self) -> None:
        self._cur.close()

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _all(self, sql: str, params: Sequence[Any] = ()) -> list[tuple[Any, ...]]:
        self.statements += 1
        try:
            return self._cur.execute(sql, list(params)).fetchall()
        except duckdb.Error as exc:
            raise CountsError("a counts query failed") from exc

    # --- global facts ---

    def totals(self) -> dict[str, tuple[int, int]]:
        rows = self._all("SELECT region, reports_mapped, reports_all FROM faers_totals")
        return {str(r): (_int(m), _int(a)) for r, m, a in rows}

    def region_basis(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for region, basis, n in self._all("SELECT region, basis, reports FROM faers_region_basis"):
            out.setdefault(str(region), {})[str(basis)] = _int(n)
        return out

    # --- single ingredient, single PT (precomputed tables, design §4.2) ---

    def pair_cells(
        self, key: str, pt: str, scope: str, regions: Sequence[str]
    ) -> dict[str, RawCells]:
        rows = self._all(
            "WITH r AS (SELECT unnest(?::VARCHAR[]) AS region) "
            "SELECT r.region, t.reports_mapped, t.reports_all, i.reports, "
            "e.reports_mapped, e.reports_all, p.reports "
            "FROM r LEFT JOIN faers_totals t USING (region) "
            "LEFT JOIN faers_ingredient_counts i "
            "  ON i.ingredient_key = ? AND i.region = r.region AND i.scope = ? "
            "LEFT JOIN faers_event_counts e ON e.pt = ? AND e.region = r.region "
            "LEFT JOIN faers_pair_counts p "
            "  ON p.ingredient_key = ? AND p.pt = ? AND p.region = r.region AND p.scope = ?",
            [list(regions), key, scope, pt, key, pt, scope],
        )
        return {
            str(r[0]): RawCells(
                _int(r[1]), _int(r[2]), _int(r[3]), _int(r[4]), _int(r[5]), _int(r[6])
            )
            for r in rows
        }

    # --- report-level paths (Janus key = union of PTs; sets of ingredients) ---

    def _set_ids_sql(self) -> str:
        return (
            "SELECT report_id FROM faers_report_ingredient "
            "WHERE ingredient_key IN (SELECT unnest(?::VARCHAR[])) AND (NOT ? OR suspect) "
            "GROUP BY report_id HAVING count(*) = ?"
        )

    def exposure_by_region(self, keys: Sequence[str], scope: str) -> dict[str, int]:
        """Reports naming all `keys` (in the scope), by region, plus ALL."""
        ordered = sorted(set(keys))
        rows = self._all(
            f"WITH ids AS ({self._set_ids_sql()}) "  # noqa: S608
            "SELECT r.region, count(*) FROM ids JOIN faers_report r USING (report_id) "
            "GROUP BY r.region",
            [ordered, scope == "suspect", len(ordered)],
        )
        out = {r: 0 for r in REGIONS}
        for region, n in rows:
            out[str(region)] = _int(n)
        out[ALL_REGION] = sum(out[r] for r in REGIONS)
        return out

    def event_and_exposure_by_region(
        self, keys: Sequence[str], pts: Sequence[str], scope: str
    ) -> dict[str, tuple[int, int, int]]:
        """Reports with any of `pts`, once per report, by region + ALL, in one statement:
        (among mapped, among all, among those also naming all `keys` in the scope)."""
        ordered = sorted(set(keys))
        rows = self._all(
            f"WITH ids AS ({self._set_ids_sql()}), "  # noqa: S608
            "ev AS (SELECT DISTINCT report_id FROM faers_report_event "
            "       WHERE pt IN (SELECT unnest(?::VARCHAR[]))), "
            "evr AS (SELECT r.region, r.mapped, ids.report_id IS NOT NULL AS exposed "
            "        FROM ev JOIN faers_report r USING (report_id) "
            "        LEFT JOIN ids USING (report_id)) "
            "SELECT region, count(*) FILTER (WHERE mapped), count(*), "
            "       count(*) FILTER (WHERE exposed) "
            "FROM evr GROUP BY region",
            [ordered, scope == "suspect", len(ordered), sorted(set(pts))],
        )
        out = {r: (0, 0, 0) for r in REGIONS}
        for region, m, a, both in rows:
            out[str(region)] = (_int(m), _int(a), _int(both))
        out[ALL_REGION] = (
            sum(out[r][0] for r in REGIONS),
            sum(out[r][1] for r in REGIONS),
            sum(out[r][2] for r in REGIONS),
        )
        return out

    def ingredient_counts(
        self, keys: Sequence[str], scope: str, regions: Sequence[str]
    ) -> dict[tuple[str, str], int]:
        rows = self._all(
            "SELECT ingredient_key, region, reports FROM faers_ingredient_counts "
            "WHERE scope = ? AND ingredient_key IN (SELECT unnest(?::VARCHAR[])) "
            "AND region IN (SELECT unnest(?::VARCHAR[]))",
            [scope, sorted(set(keys)), list(regions)],
        )
        return {(str(k), str(r)): _int(n) for k, r, n in rows}

    def cells(
        self,
        keys: Sequence[str],
        pts: Sequence[str],
        scope: str,
        regions: Sequence[str] = RESPONSE_REGIONS,
        *,
        force_report_level: bool = False,
    ) -> dict[str, RawCells]:
        """The 2x2 raw cells for (all `keys`) x (any of `pts`) in each region.

        One ingredient and one PT use the precomputed tables (2 statements fewer); everything else
        uses the report-level tables. Both paths give identical cells (differential property).
        """
        ordered = sorted(set(keys))
        if len(ordered) == 1 and len(set(pts)) == 1 and not force_report_level:
            return self.pair_cells(ordered[0], next(iter(pts)), scope, regions)
        totals = self.totals()
        if len(ordered) == 1:
            counts = self.ingredient_counts(ordered, scope, regions)
            exposure = {r: counts.get((ordered[0], r), 0) for r in regions}
        else:
            by_region = self.exposure_by_region(ordered, scope)
            exposure = {r: by_region[r] for r in regions}
        combined = self.event_and_exposure_by_region(ordered, pts, scope)
        return {
            r: RawCells(
                n_mapped=totals.get(r, (0, 0))[0],
                n_all=totals.get(r, (0, 0))[1],
                exposure=exposure[r],
                event_mapped=combined[r][0],
                event_all=combined[r][1],
                a=combined[r][2],
            )
            for r in regions
        }

    # --- combination view (design §4.4) ---

    def event_totals(self, pts: Sequence[str], region: str) -> dict[str, tuple[int, int]]:
        rows = self._all(
            "SELECT pt, reports_mapped, reports_all FROM faers_event_counts "
            "WHERE region = ? AND pt IN (SELECT unnest(?::VARCHAR[]))",
            [region, sorted(set(pts))],
        )
        return {str(pt): (_int(m), _int(a)) for pt, m, a in rows}

    def pair_report_counts(
        self, keys: Sequence[str], pts: Sequence[str], scope: str, region: str
    ) -> dict[tuple[str, str], int]:
        """Precomputed (ingredient, PT) counts: the members-alone figures."""
        rows = self._all(
            "SELECT ingredient_key, pt, reports FROM faers_pair_counts "
            "WHERE region = ? AND scope = ? AND ingredient_key IN (SELECT unnest(?::VARCHAR[])) "
            "AND pt IN (SELECT unnest(?::VARCHAR[]))",
            [region, scope, sorted(set(keys)), sorted(set(pts))],
        )
        return {(str(k), str(pt)): _int(n) for k, pt, n in rows}

    def top_events_for_set(
        self, keys: Sequence[str], scope: str, region: str, limit: int
    ) -> list[tuple[str, int]]:
        """Events of the reports naming all `keys`: by reports descending, then PT ascending."""
        ordered = sorted(set(keys))
        rows = self._all(
            f"WITH ids AS ({self._set_ids_sql()}), "  # noqa: S608
            "sel AS (SELECT ids.report_id FROM ids JOIN faers_report r USING (report_id) "
            "        WHERE ? = 'ALL' OR r.region = ?) "
            "SELECT e.pt, count(*) AS a FROM sel JOIN faers_report_event e USING (report_id) "
            "GROUP BY e.pt ORDER BY a DESC, e.pt LIMIT ?",
            [ordered, scope == "suspect", len(ordered), region, region, limit],
        )
        return [(str(pt), _int(a)) for pt, a in rows]

    def pairwise(
        self,
        keys: Sequence[str],
        scope: str,
        region: str,
        threshold: int,
        per_pair: int,
        with_events: int = 10,
    ) -> tuple[dict[tuple[str, str], int], dict[tuple[str, str], list[tuple[str, int]]]]:
        """Reports naming both ingredients of every pair among `keys`, and for the pairs that reach
        `threshold` their top `per_pair` events (one statement)."""
        ordered = sorted(set(keys))
        region_join = (
            ""
            if region == ALL_REGION
            else "JOIN faers_report r ON r.report_id = i.report_id AND r.region = ? "
        )
        params: list[Any] = [ordered, scope == "suspect"]
        if region != ALL_REGION:
            params.insert(0, region)
        params += [threshold, with_events, per_pair]
        # Filter first: only reports naming at least two of the keys are self-joined.
        rows = self._all(
            "WITH sel AS ("  # noqa: S608  (region_join is one of two constant fragments)
            "  SELECT i.report_id, i.ingredient_key AS k FROM faers_report_ingredient i "
            + region_join
            + "  WHERE i.ingredient_key IN (SELECT unnest(?::VARCHAR[])) "
            "AND (NOT ? OR i.suspect)), "
            "multi AS (SELECT report_id FROM sel GROUP BY report_id HAVING count(*) >= 2), "
            "sel2 AS (SELECT sel.report_id, sel.k FROM sel JOIN multi USING (report_id)), "
            "pr AS (SELECT x.report_id, x.k AS k1, y.k AS k2 FROM sel2 x JOIN sel2 y "
            "  ON x.report_id = y.report_id AND x.k < y.k), "
            "reach AS (SELECT k1, k2, count(*) AS n FROM pr GROUP BY k1, k2), "
            "top AS (SELECT k1, k2 FROM reach WHERE n >= ? ORDER BY n DESC, k1, k2 LIMIT ?), "
            "ev AS (SELECT pr.k1, pr.k2, e.pt, count(*) AS a FROM pr "
            "  JOIN top ON top.k1 = pr.k1 AND top.k2 = pr.k2 "
            "  JOIN faers_report_event e ON e.report_id = pr.report_id "
            "  GROUP BY pr.k1, pr.k2, e.pt), "
            "ranked AS (SELECT *, row_number() "
            "  OVER (PARTITION BY k1, k2 ORDER BY a DESC, pt) AS rn FROM ev) "
            "SELECT 'pair' AS kind, k1, k2, NULL AS pt, n AS v FROM reach "
            "UNION ALL SELECT 'event', k1, k2, pt, a FROM ranked WHERE rn <= ?",
            params,
        )
        pair_counts: dict[tuple[str, str], int] = {}
        events: dict[tuple[str, str], list[tuple[str, int]]] = {}
        for kind, k1, k2, pt, v in rows:
            pair = (str(k1), str(k2))
            if kind == "pair":
                pair_counts[pair] = _int(v)
            else:
                events.setdefault(pair, []).append((str(pt), _int(v)))
        for lst in events.values():
            lst.sort(key=lambda x: (-x[1], x[0]))
        return pair_counts, events

    def top_events_single(
        self, keys: Sequence[str], scope: str, region: str, limit: int
    ) -> dict[str, list[tuple[str, int]]]:
        rows = self._all(
            "SELECT ingredient_key, pt, reports FROM ("
            "  SELECT *, row_number() OVER (PARTITION BY ingredient_key "
            "                               ORDER BY reports DESC, pt) AS rn "
            "  FROM faers_pair_counts WHERE region = ? AND scope = ? "
            "    AND ingredient_key IN (SELECT unnest(?::VARCHAR[]))) WHERE rn <= ? "
            "ORDER BY ingredient_key, reports DESC, pt",
            [region, scope, sorted(set(keys)), limit],
        )
        out: dict[str, list[tuple[str, int]]] = {}
        for k, pt, n in rows:
            out.setdefault(str(k), []).append((str(pt), _int(n)))
        return out


# --- holder: follows the atomic `current` link -----------------------------------------------


class CountsHolder:
    def __init__(self, data_dir: Path | None) -> None:
        self._root = None if data_dir is None else counts_root(data_dir)
        self._reader: CountsReader | None = None
        self._lock = threading.Lock()

    def current(self) -> CountsReader:
        if self._root is None:
            raise CountsError("no data directory is configured")
        link = self._root / "current"
        try:
            build = Path(os.readlink(link)).name
        except OSError as exc:
            raise CountsError("there is no current counts build") from exc
        reader = self._reader
        if reader is not None and reader.meta.build_id == build:
            return reader
        with self._lock:
            reader = self._reader
            if reader is not None and reader.meta.build_id == build:
                return reader
            opened = CountsReader(link / COUNTS_DB)
            self._reader = opened  # sessions of the old reader keep their own reference
            return opened

    def peek(self) -> CountsReader | None:
        return self._reader


def region_rows(values: Iterable[str]) -> list[str]:
    """Request regions in response order (TR, EU, US, OTHER, UNKNOWN, ALL)."""
    wanted = set(values)
    return [r for r in RESPONSE_REGIONS if r in wanted]
