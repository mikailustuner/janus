"""Offline build of the FAERS onset table for the 65 PIPC rows (faers-onset-table design §6).

    python -m janus.onset_table.build [--data-dir PATH] [--publish]

Inputs: the curated rule base (`data/`: PIPC table, rules, classes), the event vocabulary
(`memory_events.csv`: PIPC row -> event key -> Preferred Terms), the prepared resolution dataset
(ingredient key -> ingredient-level ATC codes, the same codes the cascade engine matches), the
curated onset-table files (`data/onset_key_exclusions.csv`, `data/onset_row_notes.csv`), the
current `faers` and `faers_onset` artifacts (with the `pairs` side table: route and exclusion
reason of every report-drug pair) and the name map of the current FAERS count build (FAERS
ingredient name -> key). The count build must rest on the same FAERS run and resolution
dataset, otherwise the build is refused.

Writes `<JANUS_DATA_DIR>/onset_table/runs/<run>/{faers_onset_pipc.json,faers_onset_pipc.csv}`
and moves `current`; `--publish` also writes `data/open/faers-onset/` with a `datapackage.json`.
Prints counts only.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import duckdb

from janus.cascades.load import read_files
from janus.cascades.model import AtcClass
from janus.cascades.patterns import class_match
from janus.cascades.rulebase import build_rule_base
from janus.cascades.rulebase import version as rule_base_version
from janus.memory.vocabulary import EventVocabulary, load_events
from janus.onset_table import dataset as d
from janus.onset_table.routes import FORM_EXTENSIONS_ON, allowed_groups, route_group
from janus.onset_table.table import ReportInterval, RowInput, table
from janus.paths import repo_root
from janus.resolution import load
from janus.settings import EVENT_VOCABULARY, Settings

DATA: Final = repo_root() / "data"
KEY_EXCLUSIONS: Final = DATA / "onset_key_exclusions.csv"
ROW_NOTES: Final = DATA / "onset_row_notes.csv"
EXCLUSION_REASONS: Final = ("other_use_dominates", "not_used_for_the_indication")
PIPC_ROWS: Final = 65
JSON_FILE: Final = "faers_onset_pipc.json"
CSV_FILE: Final = "faers_onset_pipc.csv"
OPEN_DIR: Final = DATA / "open" / "faers-onset"
# The `faers_onset` exclusion reasons in the order its rule applies them; a candidate report
# without an interval is counted under the furthest reason any of its lines reached.
REASON_ORDER: Final = (
    "no_therapy_start",
    "start_date_partial",
    "event_date_missing",
    "event_date_partial",
    "negative_interval",
    "interval_over_max",
)


class BuildError(RuntimeError):
    """Inputs are missing or inconsistent; nothing is written."""


def _current(data_dir: Path, name: str) -> Path:
    path = data_dir / "artifacts" / name / "current"
    if not (path / "manifest.json").is_file():
        raise BuildError(f"no current {name} run")
    return path.resolve()


def _manifest(run: Path) -> dict[str, Any]:
    return json.loads((run / "manifest.json").read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def class_members(
    codes: Mapping[str, Sequence[str]],
    classes: Mapping[str, AtcClass],
    class_ids: Sequence[str],
    extensions_on: frozenset[str] = frozenset(),
) -> dict[str, list[str]]:
    """Class id -> ingredient keys with at least one code in the class. Form-extension patterns
    count only for the classes in `extensions_on`."""
    out: dict[str, list[str]] = {}
    for cid in class_ids:
        cls = classes[cid]
        active = cls.extension_ids if cid in extensions_on else frozenset[str]()
        out[cid] = sorted(
            k for k, cs in codes.items() if any(class_match(x, cls, active) for x in cs)
        )
    return out


def event_pts(vocab: EventVocabulary) -> dict[int, tuple[str, tuple[str, ...]]]:
    out: dict[int, tuple[str, tuple[str, ...]]] = {}
    for k in vocab.keys:
        if k.direction == "adverse" and k.status == "active":
            for p in k.pipc_positions:
                out[p] = (k.key, k.pts)
    return out


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def key_exclusions(path: Path = KEY_EXCLUSIONS) -> dict[str, frozenset[str]]:
    """Class id -> keys left out of the onset table (curated, each with a reason and a note)."""
    out: dict[str, set[str]] = defaultdict(set)
    for r in _csv(path):
        if r["reason"] not in EXCLUSION_REASONS or not r["note"] or not r["key"]:
            raise BuildError("onset_key_exclusions.csv: a row has no known reason, key or note")
        out[r["class_id"]].add(r["key"])
    return {k: frozenset(v) for k, v in out.items()}


def row_notes(path: Path = ROW_NOTES) -> dict[int, list[tuple[str, str]]]:
    out: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for r in _csv(path):
        position = int(r["position"])
        if not 1 <= position <= PIPC_ROWS or not r["code"] or not r["note"]:
            raise BuildError("onset_row_notes.csv: bad position, code or note")
        out[position].append((r["code"], r["note"]))
    return dict(out)


@dataclass(frozen=True)
class Group:
    candidates: int
    reports: tuple[ReportInterval, ...]
    excluded_by_reason: dict[str, int]
    per_key: tuple[tuple[str, int, int], ...]


class Faers:
    """Suspect lines of ingredient keys with route group, exclusion reason and interval."""

    def __init__(self, faers_rows: Path, onset_dir: Path, counts_db: Path) -> None:
        self.con = duckdb.connect()
        con = self.con
        con.execute("ATTACH ? AS fc (READ_ONLY)", [str(counts_db)])
        con.execute(
            "CREATE TEMP TABLE nm AS SELECT name, ingredient_key AS k FROM fc.name_map "
            "WHERE status = 'mapped'"
        )
        con.execute(
            "CREATE TEMP TABLE pr AS SELECT primaryid, drug_seq, reason, "
            "lower(trim(coalesce(route, ''))) AS route FROM read_parquet(?)",
            [str(onset_dir / "pairs.parquet")],
        )
        routes = [str(r[0]) for r in con.execute("SELECT DISTINCT route FROM pr").fetchall()]
        con.execute("CREATE TEMP TABLE rg (route VARCHAR, grp VARCHAR)")
        con.executemany("INSERT INTO rg VALUES (?, ?)", [(r, route_group(r).value) for r in routes])
        con.execute(
            "CREATE TEMP TABLE ln AS SELECT DISTINCT r.primaryid, x.drug_seq, nm.k "
            "FROM read_parquet(?) r, unnest(r.drugs) d(x), unnest(x.ingredients) u(n) "
            "JOIN nm ON nm.name = u.n WHERE x.role IN ('PS', 'SS')",
            [str(faers_rows)],
        )
        con.execute(
            "CREATE TEMP TABLE oo AS SELECT primaryid, drug_seq, onset_days, start_dt, event_dt "
            "FROM read_parquet(?)",
            [str(onset_dir / "rows.parquet")],
        )
        con.execute(
            "CREATE TEMP TABLE lines AS SELECT ln.primaryid, ln.drug_seq, ln.k, rg.grp, "
            "pr.reason, oo.onset_days, oo.start_dt, oo.event_dt FROM ln "
            "JOIN pr USING (primaryid, drug_seq) JOIN rg USING (route) "
            "LEFT JOIN oo USING (primaryid, drug_seq)"
        )
        con.execute(
            "CREATE TEMP TABLE ev AS SELECT DISTINCT primaryid, unnest(events) AS pt "
            "FROM read_parquet(?)",
            [str(faers_rows)],
        )
        con.execute("CREATE TEMP TABLE evn AS SELECT primaryid, count(*) AS n FROM ev GROUP BY 1")

    def group(self, keys: Sequence[str], pts: Sequence[str], groups: Sequence[str]) -> Group:
        con = self.con
        for name, col, values in (("ks", "k", keys), ("ps", "pt", pts), ("gs", "grp", groups)):
            con.execute(
                f"CREATE OR REPLACE TEMP TABLE {name} AS SELECT unnest(?::VARCHAR[]) AS {col}",
                [list(values)],
            )
        con.execute(
            "CREATE OR REPLACE TEMP TABLE c AS SELECT lines.* FROM lines JOIN ks USING (k) "
            "JOIN gs USING (grp) WHERE primaryid IN (SELECT primaryid FROM ev JOIN ps USING (pt))"
        )
        con.execute("CREATE OR REPLACE TEMP TABLE u AS SELECT * FROM c WHERE reason IS NULL")
        cand = con.execute("SELECT count(DISTINCT primaryid) FROM c").fetchone()
        rows = con.execute(
            "WITH m AS (SELECT primaryid, min(onset_days) AS mn, max(onset_days) AS mx, "
            "count(DISTINCT drug_seq) AS lines FROM u GROUP BY primaryid) "
            "SELECT m.mn, m.mx, min(u.start_dt) FILTER (WHERE u.onset_days = m.mn), "
            "min(u.event_dt), "
            "bool_or(u.start_dt LIKE '______01' OR u.event_dt LIKE '______01') "
            "FILTER (WHERE u.onset_days = m.mn), "
            "bool_or(u.start_dt LIKE '____0101' OR u.event_dt LIKE '____0101') "
            "FILTER (WHERE u.onset_days = m.mn), "
            "m.lines, coalesce(any_value(evn.n), 0) "
            "FROM m JOIN u USING (primaryid) LEFT JOIN evn USING (primaryid) "
            "GROUP BY m.primaryid, m.mn, m.mx, m.lines"
        ).fetchall()
        excluded = con.execute(
            "SELECT i, count(*) FROM (SELECT primaryid, "
            "max(list_position(?::VARCHAR[], reason)) AS i FROM c "
            "WHERE primaryid NOT IN (SELECT primaryid FROM u) GROUP BY primaryid) GROUP BY i",
            [list(REASON_ORDER)],
        ).fetchall()
        if any(i is None for i, _ in excluded):
            raise BuildError("a faers_onset exclusion reason is not known to the onset table")
        per_key = con.execute(
            "SELECT k, count(DISTINCT primaryid), "
            "count(DISTINCT primaryid) FILTER (WHERE reason IS NULL) FROM c GROUP BY k"
        ).fetchall()
        return Group(
            int(cand[0]) if cand else 0,
            tuple(
                sorted(
                    ReportInterval(
                        int(r[0]),
                        int(r[1]),
                        str(r[2]),
                        str(r[3]),
                        bool(r[4]),
                        bool(r[5]),
                        int(r[6]),
                        int(r[7]),
                    )
                    for r in rows
                )
            ),
            {REASON_ORDER[int(i) - 1]: int(n) for i, n in excluded},
            tuple(sorted((str(k), int(a), int(b)) for k, a, b in per_key)),
        )

    def close(self) -> None:
        self.con.close()


def build(data_dir: Path, publish: bool = False, now: dt.datetime | None = None) -> Path:
    now = now or dt.datetime.now(dt.UTC)
    faers_run, onset_run = _current(data_dir, "faers"), _current(data_dir, "faers_onset")
    faers_m, onset_m = _manifest(faers_run), _manifest(onset_run)
    if not (onset_run / "pairs.parquet").is_file():
        raise BuildError("the faers_onset run has no pairs side table; run faers_onset again")
    counts_dir = (data_dir / "memory" / "faers_counts" / "current").resolve()
    counts_meta = json.loads((counts_dir / "meta.json").read_text(encoding="utf-8"))
    if onset_m["metrics"]["faers_run_id"] != faers_m["run_id"]:
        raise BuildError("faers_onset rests on another faers run")
    if counts_meta["faers_run_id"] != faers_m["run_id"]:
        raise BuildError("the FAERS count build rests on another faers run")
    inputs = load.gather(data_dir)
    dataset_version = inputs.dataset_version()
    if counts_meta.get("resolution_dataset_version") != dataset_version:
        raise BuildError("the FAERS count build rests on another resolution dataset")
    ds = load.prepare_inputs(inputs)
    codes = {q: [a.code for a in r.ingredient_atc] for q, r in ds.ingredients.items()}

    rb = build_rule_base(read_files().inputs())
    class_ids = sorted({r.index_class for r in rb.rules if r.index_class})
    members = class_members(codes, rb.classes, class_ids, FORM_EXTENSIONS_ON)
    excluded = key_exclusions()
    if any(k not in members.get(c, []) for c, ks in excluded.items() for k in ks):
        raise BuildError("onset_key_exclusions.csv names a key that is not a class member")
    notes = row_notes()
    pts = event_pts(load_events(EVENT_VOCABULARY))
    fa = Faers(faers_run / "rows.parquet", onset_run, counts_dir / "faers_counts.duckdb")
    try:
        cache: dict[tuple[str, str], Group] = {}
        rows: list[RowInput] = []
        for rule in rb.rules:
            if rule.index_class is None:
                raise BuildError("a PIPC row has no index class")
            cid = rule.index_class
            event_key, event_terms = pts[rule.position]
            left_out = excluded.get(cid, frozenset[str]())
            keys = [k for k in members[cid] if k not in left_out]
            groups = sorted(g.value for g in allowed_groups(cid))
            if (cid, event_key) not in cache:
                cache[(cid, event_key)] = fa.group(keys, event_terms, groups)
            g = cache[(cid, event_key)]
            rows.append(
                RowInput(
                    rule.position,
                    rule.system,
                    rule.drug_a,
                    rule.adverse_event,
                    rule.drug_b,
                    rule.locator,
                    cid,
                    event_key,
                    event_terms,
                    tuple(keys),
                    g.candidates,
                    g.reports,
                    g.excluded_by_reason,
                    g.per_key,
                    tuple(sorted(left_out)),
                    tuple(groups),
                    cid in FORM_EXTENSIONS_ON,
                    tuple(notes.get(rule.position, ())),
                )
            )
    finally:
        fa.close()
    meta = {
        "built_at": now.isoformat(timespec="seconds"),
        "faers_receipt_quarters": faers_m["metrics"]["window"],
        "faers_snapshot_date": faers_m.get("snapshot_date"),
        "faers_run_id": faers_m["run_id"],
        "faers_onset_run_id": onset_m["run_id"],
        "faers_counts_build_id": counts_meta["build_id"],
        "resolution_dataset": dataset_version,
        "rule_base_version": rule_base_version(rb),
        "event_vocabulary_sha256": _sha(EVENT_VOCABULARY),
        "key_exclusions_sha256": _sha(KEY_EXCLUSIONS),
        "row_notes_sha256": _sha(ROW_NOTES),
        "faers_onset_quality": {
            "report_drug_pairs": onset_m["counts"]["input"],
            "usable_pairs": onset_m["counts"]["output"],
            "usable_pair_share": onset_m["metrics"]["usable_pair_share"],
            "complete_event_date_share": onset_m["metrics"]["complete_event_date_share"],
            "excluded_by_reason": onset_m["counts"]["excluded"],
        },
    }
    data = d.payload(table(rows), meta)
    root = data_dir / "onset_table"
    run = root / "runs" / f"{now.strftime('%Y%m%dT%H%M%SZ')}-{data['version'][-8:]}"
    write_files(run, data)
    tmp = root / "current.tmp"
    if tmp.is_symlink():
        tmp.unlink()
    tmp.symlink_to(Path("runs") / run.name, target_is_directory=True)
    os.replace(tmp, root / "current")
    if publish:
        write_files(OPEN_DIR, data)
        (OPEN_DIR / "datapackage.json").write_text(datapackage(OPEN_DIR, data), encoding="utf-8")
    return run


def write_files(target: Path, data: Mapping[str, Any]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / JSON_FILE).write_text(
        json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (target / CSV_FILE).write_text(d.to_csv(data), encoding="utf-8")


def datapackage(target: Path, data: Mapping[str, Any]) -> str:
    def res(name: str, path: str, fmt: str, media: str) -> dict[str, Any]:
        text = (target / path).read_text(encoding="utf-8")
        return {
            "name": name,
            "path": path,
            "format": fmt,
            "mediatype": media,
            "encoding": "utf-8",
            "hash": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }

    meta = {
        "name": d.DATASET,
        "title": "FAERS time to onset for the 65 PIPC prescribing cascades (descriptive)",
        "version": data["version"],
        "created": str(data["built_at"])[:10],
        "homepage": "https://github.com/mikailustuner/janus",
        "description": (
            "For every PIPC row (drug A class -> adverse event): FAERS reports with a class "
            "member as suspect and the event, how many carry a usable interval and why the "
            "others do not, and the reported time to onset (median, quartiles, intervals, "
            "Weibull shape) where the data allow it. Descriptive, not causal, not incidence; "
            "counts are reports, not people. " + d.DISCLAIMER
        ),
        "licenses": [
            {
                "name": "CC-BY-4.0",
                "path": d.LICENSE_URL,
                "title": "Creative Commons Attribution 4.0",
            }
        ],
        "sources": [
            {
                "title": "Rochon PA et al. PIPC list. Eur Geriatr Med 2025;16(5):1573-1584, "
                "Table 1 (CC BY 4.0)",
                "path": "https://doi.org/10.1007/s41999-025-01215-x",
            },
            {
                "title": "FDA Adverse Event Reporting System quarterly data files (CC0 1.0); not "
                "an FDA endorsement",
                "path": "https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html",
            },
            {
                "title": "Janus curation (Apache-2.0): data/onset_key_exclusions.csv, "
                "data/onset_row_notes.csv, data/cascade_classes.csv, data/pipc_rules.csv",
                "path": "https://github.com/mikailustuner/janus",
            },
        ],
        "x_janus": {
            "faers_receipt_quarters": data["faers_receipt_quarters"],
            "summary": data["summary"],
            "meddra_notice": d.MEDDRA_NOTICE,
            "review_status": data["review_status"],
        },
        "resources": [
            res("faers_onset_pipc_json", JSON_FILE, "json", "application/json"),
            res("faers_onset_pipc_csv", CSV_FILE, "csv", "text/csv"),
        ],
    }
    return json.dumps(meta, ensure_ascii=False, indent=2) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m janus.onset_table.build")
    ap.add_argument("--data-dir", type=Path)
    ap.add_argument("--publish", action="store_true", help="also write data/open/faers-onset/")
    args = ap.parse_args(argv)
    data_dir = args.data_dir or Settings.from_env(dict(os.environ)).data_dir
    if data_dir is None:
        print("JANUS_DATA_DIR is not set", file=sys.stderr)
        return 2
    try:
        run = build(data_dir, publish=args.publish)
    except (BuildError, load.LoadError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 4
    s = json.loads((run / JSON_FILE).read_text(encoding="utf-8"))["summary"]
    print(f"wrote {run.name}: rows by status {s['by_status']}")  # counts only
    return 0


if __name__ == "__main__":
    sys.exit(main())
