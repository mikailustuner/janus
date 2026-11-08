"""Coverage snapshots and before/after comparison (drug-resolution Req 13, design §16.1).

`python -m janus.resolution.coverage_snapshot snapshot --label baseline [--data-dir PATH]`
maps the ingredient names of TİTCK, openFDA, BDPM, the Nomenclátor and FAERS with the current
name functions and writes, under `$JANUS_DATA_DIR/resolution/`:

- `coverage-<label>-<dataset 8>.json`: counts only (names, occurrences, products, steps);
- `names-<label>-<dataset 8>.json`: the per-name result (name, occurrences, status, keys, step).
  It holds source names, so it is never written to a tracked path of the repository.

`compare --before FILE --after FILE` prints and writes the counts of names that changed, by kind
(Req 13.3). A mapped name that changes key, becomes ambiguous or unmapped is listed by count and in
the sidecar of the comparison. The pure parts (`summarise`, `compare_names`) have no I/O.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from janus.resolution import name_lists
from janus.resolution.anion_acid import AnionAcidRow, AnionAcidTable
from janus.resolution.atc import DATA_DIR
from janus.resolution.load import Inputs, gather, prepare_inputs, read_rows
from janus.resolution.matching import Match, NameIndex, map_name
from janus.resolution.name_lists import Lang
from janus.resolution.names import fold
from janus.resolution.prepare import (
    OPENFDA,
    TITCK,
    WIKIDATA,
    PreparedDataset,
    build_name_index,
)
from janus.resolution.prepare_eu import (
    UNNAMED,
    bdpm_ingredients,
    cima_ingredients,
    is_homeopathic_name,
)

SNAPSHOT_VERSION = "coverage_snapshot-1"
REPO = DATA_DIR.parent
SOURCES = ("titck", "openfda_ndc", "eu_fr_bdpm", "eu_es_cima", "faers")

Status = str  # "mapped" | "ambiguous" | "unmapped"


@dataclass(frozen=True)
class NameResult:
    occurrences: int
    status: Status
    keys: tuple[str, ...]
    step: str | None

    def as_json(self) -> list[Any]:
        return [self.occurrences, self.status, list(self.keys), self.step]

    @classmethod
    def from_json(cls, raw: Sequence[Any]) -> NameResult:
        return cls(int(raw[0]), str(raw[1]), tuple(str(k) for k in raw[2]), raw[3])


def status_of(match: Match) -> Status:
    """`none` and `unsplit` are both "not mapped" for the comparison."""
    return match.status if match.status in ("mapped", "ambiguous") else "unmapped"


# --- pure parts ------------------------------------------------------------------------------


def summarise(
    products: Sequence[Sequence[str]], results: Mapping[str, NameResult]
) -> dict[str, Any]:
    """Counts for one source: `products` are lists of published names (may be empty)."""
    occ = sum(r.occurrences for r in results.values())
    mapped_occ = sum(r.occurrences for r in results.values() if r.status == "mapped")
    by_step: Counter[str] = Counter()
    for r in results.values():
        if r.status == "mapped":
            by_step[str(r.step)] += r.occurrences
    with_ings = [p for p in products if p]
    full = [p for p in with_ings if all(results[n].status == "mapped" for n in p)]
    multi = [p for p in with_ings if len(p) >= 2]
    multi_full = [p for p in multi if all(results[n].status == "mapped" for n in p)]

    def share(a: int, b: int) -> float:
        return round(a / b, 4) if b else 0.0

    names_mapped = sum(1 for r in results.values() if r.status == "mapped")
    return {
        "products": len(products),
        "products_with_ingredients": len(with_ings),
        "products_fully_mapped": len(full),
        "products_fully_mapped_share": share(len(full), len(with_ings)),
        "multi_ingredient_products": len(multi),
        "multi_ingredient_fully_mapped": len(multi_full),
        "distinct_names": len(results),
        "names_mapped": names_mapped,
        "names_mapped_share": share(names_mapped, len(results)),
        "occurrences": occ,
        "occurrences_mapped": mapped_occ,
        "occurrences_mapped_share": share(mapped_occ, occ),
        "occurrences_by_step": dict(sorted(by_step.items())),
        "ambiguous_names": sum(1 for r in results.values() if r.status == "ambiguous"),
        "ambiguous_occurrences": sum(
            r.occurrences for r in results.values() if r.status == "ambiguous"
        ),
    }


def change_kind(before: NameResult, after: NameResult) -> str | None:
    """Req 13.3 kinds; None if the name did not change."""
    if before.status == after.status:
        if before.status == "mapped" and before.keys != after.keys:
            return "mapped_to_other_key"
        return None
    return f"{before.status}_to_{after.status}"


def compare_names(
    before: Mapping[str, NameResult], after: Mapping[str, NameResult]
) -> dict[str, dict[str, int]]:
    """Counts of changed names and occurrences by kind. Names in only one side are counted as
    `new_name` / `gone_name` (the sources moved between the snapshots)."""
    names: Counter[str] = Counter()
    occ: Counter[str] = Counter()
    for name in sorted(set(before) | set(after)):
        b, a = before.get(name), after.get(name)
        if b is None and a is not None:
            kind: str | None = "new_name"
            n = a.occurrences
        elif a is None and b is not None:
            kind, n = "gone_name", b.occurrences
        elif a is not None and b is not None:
            kind, n = change_kind(b, a), a.occurrences
        else:  # pragma: no cover
            continue
        if kind is not None:
            names[kind] += 1
            occ[kind] += n
    return {"names": dict(sorted(names.items())), "occurrences": dict(sorted(occ.items()))}


# --- data access ------------------------------------------------------------------------------


def _map(name: str, index: NameIndex, lang: Lang) -> Match:
    return map_name(name, index, lang=lang)


def results_for(
    counts: Mapping[str, int], index: NameIndex, lang: Lang, mapper: Callable[[str], Match] | None
) -> dict[str, NameResult]:
    out: dict[str, NameResult] = {}
    for name in sorted(counts):
        m = mapper(name) if mapper else _map(name, index, lang)
        out[name] = NameResult(
            counts[name], status_of(m), m.keys if m.status == "mapped" else (), m.step
        )
    return out


def _from_prepared(prepared: PreparedDataset, source_id: str) -> dict[str, NameResult]:
    """Per published name: the first occurrence's status, key(s) and step, with the counts."""
    first: dict[str, tuple[str, tuple[str, ...], str | None]] = {}
    counts: Counter[str] = Counter()
    for p in prepared.products:
        if p.source_id != source_id:
            continue
        for ing in p.ingredients:
            counts[ing.published_name] += 1
            if ing.published_name not in first:
                keys = (ing.qid,) if ing.qid else ing.key_candidates
                first[ing.published_name] = (ing.status, tuple(keys), ing.match_step)
    return {n: NameResult(counts[n], first[n][0], first[n][1], first[n][2]) for n in sorted(counts)}


def _strip_names(cov: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in cov.items():
        if k == "unmapped_top":
            continue
        out[k] = _strip_names(v) if isinstance(v, Mapping) else v  # pyright: ignore[reportUnknownArgumentType]
    return out


def artifact_rows(data_dir: Path, pipeline: str) -> list[dict[str, Any]] | None:
    run = data_dir / "artifacts" / pipeline / "current"
    return read_rows(run / "rows.parquet") if (run / "rows.parquet").exists() else None


def faers_counts(data_dir: Path) -> dict[str, int] | None:
    parquet = data_dir / "artifacts" / "faers" / "current" / "rows.parquet"
    if not parquet.exists():
        return None
    con = duckdb.connect()
    try:
        rows = con.execute(
            "SELECT n, count(*) FROM (SELECT unnest(d.ingredients) AS n FROM "
            "(SELECT unnest(drugs) AS d FROM read_parquet(?))) GROUP BY n",
            [str(parquet)],
        ).fetchall()
    finally:
        con.close()
    return {str(n): int(c) for n, c in rows}


def take_snapshot(data_dir: Path, inputs: Inputs) -> tuple[dict[str, Any], dict[str, Any]]:
    """(summary, names) for every source whose artifact exists. Names stay in the second value."""
    prepared = prepare_inputs(inputs)
    index = build_name_index(
        inputs.artifacts[WIKIDATA].rows,
        inputs.rules,
        inputs.synonyms,
        inputs.curated.rows,
        inputs.acid,
    )
    summary: dict[str, Any] = {
        "version": SNAPSHOT_VERSION,
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset_inputs": inputs.dataset_version(),
        "sources": {},
    }
    names: dict[str, Any] = {}

    for sid, label in ((TITCK, "titck"), (OPENFDA, "openfda_ndc")):
        res = _from_prepared(prepared, sid)
        names[label] = {n: r.as_json() for n, r in res.items()}
        summary["sources"][label] = _strip_names(prepared.coverage.get(sid, {}))

    fr = artifact_rows(data_dir, "eu_fr_bdpm")
    if fr is not None:
        plists: list[list[str]] = []
        counts: Counter[str] = Counter()
        homeopathic = 0
        for row in fr:
            ings, _stats = bdpm_ingredients(row.get("composition") or [])
            ns = [i.name for i in ings]
            if any(is_homeopathic_name(n) for n in ns):
                homeopathic += 1
                continue
            plists.append(ns)
            counts.update(ns)
        res = results_for(counts, index, "fr", None)
        names["eu_fr_bdpm"] = {n: r.as_json() for n, r in res.items()}
        summary["sources"]["eu_fr_bdpm"] = {
            **summarise(plists, res),
            "homeopathic_presentations_left_out": homeopathic,
        }

    es = artifact_rows(data_dir, "eu_es_cima")
    if es is not None:
        plists = []
        counts = Counter()
        for row in es:
            ns = [
                i.name for i in cima_ingredients(row.get("ingredients") or []) if i.name != UNNAMED
            ]
            plists.append(ns)
            counts.update(ns)
        res = results_for(counts, index, "es", None)
        names["eu_es_cima"] = {n: r.as_json() for n, r in res.items()}
        summary["sources"]["eu_es_cima"] = summarise(plists, res)

    fc = faers_counts(data_dir)
    if fc is not None:
        res = results_for(fc, index, "en", None)
        names["faers"] = {n: r.as_json() for n, r in res.items()}
        summary["sources"]["faers"] = summarise([], res)
    return summary, names


# --- files and CLI ----------------------------------------------------------------------------


def check_output_path(path: Path, repo: Path = REPO) -> Path:
    """Refuse a path inside the repository unless git ignores it (the sidecar holds names)."""
    resolved = path.resolve()
    try:
        resolved.relative_to(repo.resolve())
    except ValueError:
        return resolved
    ignored = subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), "check-ignore", "-q", str(resolved)],  # noqa: S607
        check=False,
    )
    if ignored.returncode != 0:
        raise ValueError("the snapshot must not be written to a tracked path")
    return resolved


def _load_names(path: Path) -> dict[str, dict[str, NameResult]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {src: {n: NameResult.from_json(r) for n, r in rows.items()} for src, rows in raw.items()}


def run_compare(before: Path, after: Path) -> dict[str, Any]:
    b, a = _load_names(before), _load_names(after)
    return {
        src: compare_names(b.get(src, {}), a.get(src, {}))
        for src in SOURCES
        if src in b or src in a
    }


def _print_counts(summary: Mapping[str, Any]) -> None:
    def line(label: str, part: Mapping[str, Any]) -> None:
        print(
            f"{label}: occurrences {part.get('occurrences')} mapped "
            f"{part.get('occurrences_mapped_share', 0):.1%}; products fully mapped "
            f"{part.get('products_fully_mapped_share', 0):.1%}"
        )

    for src, s in summary["sources"].items():
        if "occurrences_mapped_share" in s:
            line(src, s)
        else:  # prepare_dataset sections (openFDA: all, rx, rx_otc)
            for k, part in s.items():
                if isinstance(part, Mapping) and "occurrences_mapped_share" in part:
                    line(f"{src}/{k}", part)  # pyright: ignore[reportUnknownArgumentType]


def load_rule_file(path: Path, inputs: Inputs) -> tuple[dict[str, Any], Inputs]:
    """What-if rule data for a snapshot: `(name_lists overrides, inputs with the extra rows)`.

    The JSON file may hold (all keys optional):
    `extra_salt_words`, `extra_not_alone`, `connectors`: language -> list of words;
    `switches`: list of `biologic_suffix`, `es_final_vowel`, `acid_word_order`;
    `anion_acid`: list of `[lang, anion, acid, note]`; `synonyms`: list of `[name, key]`.
    Nothing is written to the repository; the rows only exist for the run (review, task 20).
    """
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    def per_lang(key: str, current: Mapping[Lang, frozenset[str]]) -> dict[Lang, frozenset[str]]:
        given: Mapping[str, Sequence[str]] = raw.get(key, {})
        return {lg: current[lg] | frozenset(given.get(lg, ())) for lg in name_lists.LANGS}

    changes: dict[str, Any] = {
        "EXTRA_SALT_WORDS": per_lang("extra_salt_words", name_lists.EXTRA_SALT_WORDS),
        "EXTRA_NOT_ALONE": per_lang("extra_not_alone", name_lists.EXTRA_NOT_ALONE),
        "CONNECTORS": per_lang("connectors", name_lists.CONNECTORS),
    }
    switches = {
        "biologic_suffix": "BIOLOGIC_SUFFIX_ENABLED",
        "es_final_vowel": "ES_FINAL_VOWEL_ENABLED",
        "acid_word_order": "ACID_WORD_ORDER_ENABLED",
    }
    for name in raw.get("switches", ()):
        changes[switches[name]] = True
    rows = [
        AnionAcidRow(str(lg), fold(str(a)), fold(str(b)), str(n))
        for lg, a, b, n in raw.get("anion_acid", ())
    ]
    new_inputs = replace(
        inputs,
        acid=AnionAcidTable((*inputs.acid.rows, *rows), "what-if"),
        synonyms=(*inputs.synonyms, *((str(a), str(b)) for a, b in raw.get("synonyms", ()))),
    )
    return changes, new_inputs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m janus.resolution.coverage_snapshot")
    sub = parser.add_subparsers(dest="cmd", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--label", required=True)
    snap.add_argument("--data-dir", type=Path, default=None)
    snap.add_argument(
        "--rules",
        type=Path,
        default=None,
        help="JSON what-if rule data (see `load_rule_file`); nothing is committed or enabled",
    )
    cmp_ = sub.add_parser("compare")
    cmp_.add_argument("--before", type=Path, required=True)
    cmp_.add_argument("--after", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.cmd == "compare":
        result = run_compare(args.before, args.after)
        for src, r in result.items():
            print(
                f"{src}: names {r['names'] or 'unchanged'}; occurrences {r['occurrences'] or '-'}"
            )
        return 0
    from janus.settings import Settings  # local: only the CLI needs settings

    data_dir = args.data_dir or Settings.from_env().data_dir
    if data_dir is None:
        print("set --data-dir or JANUS_DATA_DIR", file=sys.stderr)
        return 2
    inputs = gather(data_dir)
    changes: dict[str, Any] = {}
    if args.rules is not None:
        changes, inputs = load_rule_file(args.rules, inputs)
    with name_lists.override(**changes):
        summary, names = take_snapshot(data_dir, inputs)
        tag = f"{args.label}-{inputs.dataset_version()[:8]}"
    out = data_dir / "resolution"
    summary_path = check_output_path(out / f"coverage-{tag}.json")
    names_path = check_output_path(out / f"names-{tag}.json")
    out.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=1, sort_keys=True), encoding="utf-8")
    names_path.write_text(json.dumps(names, sort_keys=True), encoding="utf-8")
    _print_counts(summary)
    print(f"wrote {summary_path.name} and {names_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
