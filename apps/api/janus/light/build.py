"""`python -m janus.light.build`: the light-face build (design §3.3, §8.4, DP11; P4).

Reads the current `onsides`, `openfda_label` and `wikidata_ingredients` artifacts, the current FAERS
counts file (read-only, the reader's settings) and the curated files; runs the pure core; writes
`$JANUS_DATA_DIR/light/runs/<build_id>/light.json` (sorted keys, no timestamp) and moves the
`current` link. With `--docs PATH` it also writes the validation report. Nothing is logged but the
build id and counts; no ingredient, term or condition is printed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import duckdb

from janus.light import curation, report
from janus.light.candidates import rank_all
from janus.light.inverse import Counts, faers_stats, inverse_signal, is_inverse
from janus.light.keys import Item, build_key_map, map_ingredients
from janus.light.labels import label_signals, single_key
from janus.light.model import (
    INGREDIENT_LANGS,
    Candidate,
    CaseFaers,
    Curated,
    InverseSignal,
    Label,
    LabelSignal,
    Validation,
)
from janus.light.ranking import wilson_low
from janus.light.schemas import (
    SCHEMA_VERSION,
    CandidateOut,
    CaseOut,
    CaseResultOut,
    CaseRunOut,
    CoverageOut,
    GoalOut,
    InputsOut,
    InverseOut,
    LabelSignalOut,
    LightFile,
    MappingOut,
    RankOut,
    SummaryOut,
    ValidationPart,
)
from janus.light.validation import evaluate
from janus.memory.evidence import FAERS_EVIDENCE_ID, EventRef, faers_locator
from janus.memory.faers_build import COUNTS_DB, counts_root
from janus.memory.reader import DUCKDB_SETTINGS, CountsReader, RawCells
from janus.memory.service import stats_out
from janus.memory.stats import PARAMS, Sensitivity, Stats
from janus.memory.vocabulary import load_events
from janus.paths import repo_root
from janus.settings import EVENT_VOCABULARY

LIGHT_DIR: Final = "light"
LIGHT_FILE: Final = "light.json"
REPO: Final = repo_root()
PAPERS: Final = REPO / "data" / "evidence_papers.csv"


class BuildError(RuntimeError):
    """A missing or inconsistent input. The message names the input, never a medicine."""


@dataclass(frozen=True)
class Artifact:
    run_id: str
    snapshot_date: str
    path: Path


def artifact(data_dir: Path, pipeline: str) -> Artifact:
    link = data_dir / "artifacts" / pipeline / "current"
    try:
        manifest = json.loads((link / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BuildError(f"no current {pipeline} artifact") from exc
    return Artifact(str(manifest["run_id"]), str(manifest.get("snapshot_date") or ""), link)


def paper_ids(path: Path = PAPERS) -> set[str]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {f"paper:{r['source_id']}:{r['key']}" for r in csv.DictReader(fh)}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def code_sha256() -> str:
    here = Path(__file__).resolve().parent
    h = hashlib.sha256()
    for p in sorted(here.glob("*.py")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


# --- reading the inputs ------------------------------------------------------------------------


def read_onsides(
    con: duckdb.DuckDBPyConnection, art: Path, terms: Sequence[str]
) -> tuple[list[Label], dict[str, str], set[str]]:
    """Labels (effects restricted to `terms`), OnSIDES ingredient names, the term vocabulary."""
    rows_p, meddra_p, ingr_p = (
        str(art / f) for f in ("rows.parquet", "meddra.parquet", "ingredients.parquet")
    )
    vocabulary = {
        str(r[0]) for r in con.execute("SELECT name FROM read_parquet(?)", [meddra_p]).fetchall()
    }
    names = {
        str(i): str(n)
        for i, n in con.execute("SELECT rxnorm_id, name FROM read_parquet(?)", [ingr_p]).fetchall()
    }
    effects: dict[int, list[tuple[str, str]]] = {}
    for label_id, name, section in con.execute(
        "WITH e AS (SELECT label_id, unnest(effects) AS e FROM read_parquet(?)) "
        "SELECT e.label_id, m.name, e.e.section FROM e JOIN read_parquet(?) m "
        "ON m.meddra_id = e.e.meddra_id WHERE m.name IN (SELECT unnest(?::VARCHAR[])) "
        "ORDER BY 1, 2, 3",
        [rows_p, meddra_p, list(terms)],
    ).fetchall():
        effects.setdefault(int(label_id), []).append((str(name), str(section)))
    labels: list[Label] = []
    for label_id, source, spid, ingredients in con.execute(
        "SELECT label_id, source, source_product_id, ingredient_ids "
        "FROM read_parquet(?) ORDER BY 1",
        [rows_p],
    ).fetchall():
        set_id = str(spid).split(".", 1)[0] if source == "US" else ""
        labels.append(
            Label(
                int(label_id),
                str(source),
                set_id,
                tuple(sorted(str(i) for i in ingredients)),
                tuple(effects.get(int(label_id), ())),
            )
        )
    return labels, names, vocabulary


def read_wikidata(
    con: duckdb.DuckDBPyConnection, art: Path
) -> tuple[list[Item], dict[str, dict[str, str]]]:
    items: list[Item] = []
    labels: dict[str, dict[str, str]] = {}
    for row in con.execute(
        "SELECT qid, rxcuis, label_en, label_tr, label_de, label_fr, label_es, label_pt "
        "FROM read_parquet(?) ORDER BY qid",
        [str(art / "rows.parquet")],
    ).fetchall():
        qid = str(row[0])
        items.append(Item(qid, tuple(str(r) for r in (row[1] or ())), str(row[2] or "")))
        labels[qid] = {lang: str(v) for lang, v in zip(INGREDIENT_LANGS, row[2:], strict=True) if v}
    return items, labels


def read_openfda(con: duckdb.DuckDBPyConnection, art: Path) -> dict[str, str]:
    return {
        str(s): str(t)
        for s, t in con.execute(
            "SELECT set_id, indications FROM read_parquet(?) ORDER BY 1",
            [str(art / "rows.parquet")],
        ).fetchall()
    }


@dataclass(frozen=True)
class Faers:
    build_id: str
    snapshot_date: str
    window: tuple[str, ...]
    n_mapped: int
    n_all: int
    ingredient: Mapping[str, int]  # scope any, region ALL
    by_goal: Mapping[
        str, tuple[int, int, Mapping[str, int]]
    ]  # goal -> (ev_mapped, ev_all, a per key)


def read_faers(data_dir: Path, pts_by_goal: Mapping[str, Sequence[str]]) -> Faers:
    path = counts_root(data_dir) / "current" / COUNTS_DB
    reader = CountsReader(path)  # checks the schema version and the tables
    meta = reader.meta
    reader.close()
    con = duckdb.connect(str(path), read_only=True)
    try:
        for stmt in DUCKDB_SETTINGS:
            con.execute(stmt)
        row = con.execute(
            "SELECT reports_mapped, reports_all FROM faers_totals WHERE region = 'ALL'"
        ).fetchone()
        if row is None:
            raise BuildError("faers_totals has no ALL row")
        ingredient = {
            str(k): int(n)
            for k, n in con.execute(
                "SELECT ingredient_key, reports FROM faers_ingredient_counts "
                "WHERE region = 'ALL' AND scope = 'any'"
            ).fetchall()
        }
        by_goal: dict[str, tuple[int, int, Mapping[str, int]]] = {}
        for goal in sorted(pts_by_goal):
            pts = list(pts_by_goal[goal])
            if not pts:
                continue
            ev = con.execute(
                "WITH ev AS (SELECT DISTINCT report_id FROM faers_report_event "
                "WHERE pt IN (SELECT unnest(?::VARCHAR[]))) "
                "SELECT count(*) FILTER (WHERE r.mapped), count(*) "
                "FROM ev JOIN faers_report r USING (report_id)",
                [pts],
            ).fetchone()
            a = {
                str(k): int(n)
                for k, n in con.execute(
                    "WITH ev AS (SELECT DISTINCT report_id FROM faers_report_event "
                    "WHERE pt IN (SELECT unnest(?::VARCHAR[]))) "
                    "SELECT i.ingredient_key, count(DISTINCT i.report_id) "
                    "FROM faers_report_ingredient i JOIN ev USING (report_id) GROUP BY 1",
                    [pts],
                ).fetchall()
            }
            by_goal[goal] = (int(ev[0]) if ev else 0, int(ev[1]) if ev else 0, a)
    finally:
        con.close()
    return Faers(
        meta.build_id,
        meta.snapshot_date,
        meta.window,
        int(row[0]),
        int(row[1]),
        ingredient,
        by_goal,
    )


def faers_counts(f: Faers, goal: str, key: str) -> Counts | None:
    g = f.by_goal.get(goal)
    ing = f.ingredient.get(key, 0)
    if g is None or ing == 0:
        return None
    ev_mapped, ev_all, a = g
    return Counts(a.get(key, 0), ing, ev_mapped, ev_all, f.n_mapped, f.n_all)


def inverse_signals(
    cur: Curated, f: Faers
) -> tuple[dict[tuple[str, str], InverseSignal], dict[str, int]]:
    """Inverse signals, and per goal the number of pairs tested (at least MIN_REPORTS reports)."""
    out: dict[tuple[str, str], InverseSignal] = {}
    tested: dict[str, int] = {}
    for goal, g in sorted(cur.goals.items()):
        if goal not in f.by_goal:
            continue
        for key in sorted(f.by_goal[goal][2]):
            c = faers_counts(f, goal, key)
            if c is None:
                continue
            if c.a >= PARAMS.min_reports:
                tested[goal] = tested.get(goal, 0) + 1
            found = inverse_signal(c)
            if found is not None:
                out[(key, goal)] = InverseSignal(key, goal, found[0], found[1], g.faers_pts)
    return out, tested


# --- output --------------------------------------------------------------------------------------


def _stats_out(c: Counts) -> Any:
    raw = RawCells(c.n_mapped, c.n_all, c.ingredient, c.event_mapped, c.event_all, c.a)
    return stats_out(raw, "ALL", "any")


def _counts_of(stats: Stats, sens: Sensitivity) -> Counts:
    t, s = stats.cells, sens.stats.cells
    return Counts(t.a, t.a + t.b, t.a + t.c, s.a + s.c, t.n, s.n)


def label_out(s: LabelSignal) -> LabelSignalOut:
    return LabelSignalOut(
        regions=list(s.regions),
        labels_with_effect=s.labels_with_effect,
        labels_total=s.labels_total,
        share_low=wilson_low(s.labels_with_effect, s.labels_total),
        sections=list(s.sections),
        terms=list(s.terms),
        evidence_ids=list(s.evidence),
        nonspecific=s.nonspecific,
    )


def inverse_out(s: InverseSignal) -> InverseOut:
    c = _counts_of(s.stats, s.sensitivity)
    expected = c.ingredient * c.event_mapped / c.n_mapped
    sens = s.sensitivity.stats.estimates
    return InverseOut(
        stats=_stats_out(c),
        pts=list(s.pts),
        reports=s.stats.cells.a,
        expected=expected,
        observed_over_expected=s.stats.cells.a / expected,
        upper_bound_sensitive=sens is None or sens.ror_ci.high >= 1.0,
        evidence_ids=[FAERS_EVIDENCE_ID],
        locator=faers_locator((s.key,), EventRef(), "ALL", "any"),
    )


def candidate_out(c: Candidate) -> CandidateOut:
    return CandidateOut(
        ingredient=c.key,
        goal=c.goal,
        rank=RankOut(best=c.rank.best, worst=c.rank.worst, population=c.rank.population),
        label=label_out(c.label) if c.label else None,
        inverse=inverse_out(c.inverse) if c.inverse else None,
    )


def validation_out(
    v: Validation, faers_counts_by_case: Mapping[str, Counts | None]
) -> ValidationPart:
    cases: list[CaseResultOut] = []
    for r in v.results:
        c = r.case
        runs = [
            CaseRunOut(
                run=x.run,
                rank=RankOut(best=x.rank.best, worst=x.rank.worst, population=x.rank.population)
                if x.rank
                else None,
                population=x.population,
                hit=x.hit,
                informative=x.informative,
                labels_used=x.labels_used,
                labels_removed_indication=x.labels_removed_indication,
                labels_removed_not_in_openfda=x.labels_removed_not_in_openfda,
                signal_types=list(x.signal_types),
                reason=x.reason,
                chance_hit=x.chance_hit,
                percentile=x.percentile,
            )
            for x in (r.primary, r.primary_indication, r.primary_strict, r.sensitivity)
        ]
        counts = faers_counts_by_case.get(c.id)
        cases.append(
            CaseResultOut(
                case=CaseOut(
                    id=c.id,
                    ingredient_name=c.ingredient_name,
                    ingredient_key=c.ingredient_key,
                    goal=c.goal,
                    original_use=c.original_use,
                    later_year=c.later_year,
                    indication_terms=list(c.indication_terms),
                    evidence_ids=list(c.evidence),
                    note=c.note,
                ),
                primary=runs[0],
                primary_indication=runs[1],
                primary_strict=runs[2],
                sensitivity=runs[3],
                faers=_stats_out(counts) if counts else None,
                faers_inverse=bool(r.faers and r.faers.inverse),
                faers_includes_later_use=True,
            )
        )

    def summ(s: Any) -> SummaryOut:
        return SummaryOut(
            hits=s.hits,
            informative_hits=s.informative_hits,
            misses=s.misses,
            not_evaluable=s.not_evaluable,
            expected_hits_by_chance=s.expected_hits_by_chance,
        )

    return ValidationPart(
        top_k=v.top_k,
        status=v.status,
        cases=cases,
        primary=summ(v.primary),
        sensitivity=summ(v.sensitivity),
    )


def build(data_dir: Path, curated_dir: Path = curation.DATA_DIR) -> LightFile:
    onsides = artifact(data_dir, "onsides")
    openfda = artifact(data_dir, "openfda_label")
    wikidata = artifact(data_dir, "wikidata_ingredients")
    texts = curation.read_texts(curated_dir)
    benefit = {k.key for k in load_events(EVENT_VOCABULARY).active() if k.direction == "benefit"}
    papers = paper_ids()
    pre = curation.parse_all(texts, benefit_keys=benefit, papers=papers)
    con = duckdb.connect()
    try:
        labels, names, vocabulary = read_onsides(con, onsides.path, sorted(pre.active_terms()))
        items, ingredient_labels = read_wikidata(con, wikidata.path)
        indications = read_openfda(con, openfda.path)
    finally:
        con.close()
    cur = curation.parse_all(texts, benefit_keys=benefit, papers=papers, vocabulary=vocabulary)
    active = cur.active_terms()
    key_of, methods = map_ingredients(names, build_key_map(items))
    faers = read_faers(data_dir, {g: v.faers_pts for g, v in cur.goals.items()})

    signals = label_signals(labels, active, key_of)
    inverse, tested = inverse_signals(cur, faers)
    ranked = rank_all(cur.goals, signals, inverse)

    inverse_by_goal: dict[str, list[InverseSignal]] = {}
    for s in inverse.values():
        inverse_by_goal.setdefault(s.goal, []).append(s)
    case_counts: dict[str, Counts | None] = {}
    case_faers: dict[str, CaseFaers | None] = {}
    for case in cur.cases:
        c = faers_counts(faers, case.goal, case.ingredient_key)
        case_counts[case.id] = c
        if c is None:
            case_faers[case.id] = None
        else:
            st, se = faers_stats(c)
            case_faers[case.id] = CaseFaers(st, se, is_inverse(st))
    validation = evaluate(
        cur.cases, labels, active, key_of, inverse_by_goal, indications, case_faers
    )

    used_keys = sorted(
        {c.key for cs in ranked.values() for c in cs} | {c.ingredient_key for c in cur.cases}
    )
    onsides_name = {key_of[i]: names[i] for i in sorted(key_of)}
    ingredients = {k: ingredient_labels.get(k) or {"en": onsides_name.get(k, k)} for k in used_keys}
    inputs = InputsOut(
        onsides_run_id=onsides.run_id,
        onsides_release="v3.1.1",
        onsides_date=onsides.snapshot_date,
        openfda_run_id=openfda.run_id,
        openfda_date=openfda.snapshot_date,
        faers_build_id=faers.build_id,
        faers_snapshot_date=faers.snapshot_date,
        faers_window=list(faers.window),
        wikidata_run_id=wikidata.run_id,
        curated_sha256={name: _sha(t) for name, t in sorted(texts.items())},
        code_sha256=code_sha256(),
    )
    build_id = _sha(inputs.model_dump_json())[:16]
    single = sum(1 for lb in labels if single_key(lb, key_of) is not None)
    return LightFile(
        schema_version=SCHEMA_VERSION,
        build_id=build_id,
        inputs=inputs,
        goals=[
            GoalOut(
                key=g.key,
                labels=dict(g.labels),
                faers_pts=list(g.faers_pts),
                benefit_keys=list(g.benefit_keys),
                label_terms=sorted(t for t, m in active.items() if m.goal == g.key),
                note=g.note,
                inverse_tested=tested.get(g.key, 0),
                inverse_found=sum(1 for s in inverse.values() if s.goal == g.key),
                inverse_expected_by_chance=0.025 * tested.get(g.key, 0),
            )
            for g in sorted(cur.goals.values(), key=lambda g: g.key)
        ],
        mapping=[
            MappingOut(
                term=m.term,
                goal=m.goal,
                status=m.status,
                evidence_ids=list(m.evidence),
                rationale=m.rationale,
                nonspecific=m.nonspecific,
            )
            for m in cur.mapping
        ],
        ingredients=ingredients,
        candidates={g: [candidate_out(c) for c in cs] for g, cs in ranked.items()},
        validation=validation_out(validation, case_counts),
        coverage=CoverageOut(
            labels=len(labels),
            single_ingredient_labels=single,
            ingredients_by_method={str(k): v for k, v in methods.items()},
            candidates_by_goal={g: len(cs) for g, cs in ranked.items()},
            inverse_by_goal={g: len(v) for g, v in sorted(inverse_by_goal.items())},
        ),
    )


def dump(light: LightFile) -> str:
    return (
        json.dumps(light.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, indent=1)
        + "\n"
    )


def write(data_dir: Path, light: LightFile) -> Path:
    root = data_dir / LIGHT_DIR
    run = root / "runs" / light.build_id
    run.mkdir(parents=True, exist_ok=True)
    tmp = run / (LIGHT_FILE + ".tmp")
    tmp.write_text(dump(light), encoding="utf-8")
    os.replace(tmp, run / LIGHT_FILE)
    link_tmp = root / "current.tmp"
    if link_tmp.is_symlink() or link_tmp.exists():
        link_tmp.unlink()
    link_tmp.symlink_to(Path("runs") / light.build_id)
    os.replace(link_tmp, root / "current")
    return run / LIGHT_FILE


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m janus.light.build")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--docs", type=Path, default=None, help="write the validation report here")
    args = parser.parse_args(argv)
    data_dir = args.data_dir or Path(os.environ.get("JANUS_DATA_DIR", ".data"))
    try:
        light = build(data_dir)
    except (BuildError, curation.CurationError) as exc:
        print(f"light build failed: {exc}", file=sys.stderr)
        return 1
    path = write(data_dir, light)
    if args.docs is not None:
        args.docs.write_text(report.render(light), encoding="utf-8")
    v = light.validation
    print(
        f"light build {light.build_id}: "
        f"{sum(light.coverage.candidates_by_goal.values())} candidates; "
        f"validation primary hits {v.primary.hits} (informative {v.primary.informative_hits}); "
        f"status {v.status}; written {path.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
