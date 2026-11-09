"""Weekly data-quality build (data-quality design §8). Offline; nothing here runs on a request.

    python -m janus.quality.build [--data-dir PATH] [--publish]

Reads the current `titck`, `us_ndc`, `wikidata_ingredients`, `eu_fr_bdpm` and `eu_es_cima`
artifacts through the resolution loader (`gather`, `prepare_inputs`: the same prepared dataset
the API serves), reduces it to counts, runs the checks and writes

    <JANUS_DATA_DIR>/quality/runs/<run_id>/{report.json, findings.csv, summary.md}

then moves `<JANUS_DATA_DIR>/quality/current` to the new run. The previous run (the old
`current`) gives the diff. `--publish` also writes the open copy, `data/open/data-quality/`
(the same three files and a Frictionless `datapackage.json`), to be committed.

Runs after the weekly `titck` pipeline (cadence in `pipelines/sources.toml`, source
`data_quality`). It prints counts only: no ingredient, code or product.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

from janus.paths import repo_root
from janus.quality import checks as c
from janus.quality import report as r
from janus.resolution import load
from janus.resolution.atc import CombinationCheck
from janus.resolution.prepare import JANUS_CURATED, PreparedDataset
from janus.settings import Settings

REPORT: Final = "report.json"
FINDINGS: Final = "findings.csv"
SUMMARY: Final = "summary.md"
OPEN_DIR: Final = repo_root() / "data" / "open" / "data-quality"
SOURCE_IDS: Final = {
    "titck": "titck",
    "openfda_ndc": "us_ndc",
    "wikidata": "wikidata_ingredients",
    "eu_fr_bdpm": "eu_fr_bdpm",
    "eu_es_cima": "eu_es_cima",
}


def views(ds: PreparedDataset) -> Iterable[c.ProductView]:
    for p in ds.products:
        yield c.ProductView(
            p.source_id,
            p.published_atc,
            tuple(i.qid if i.status == "mapped" else None for i in p.ingredients),
        )


def items(inputs: load.Inputs) -> dict[str, c.Item]:
    out = {
        str(row["qid"]): c.Item(
            str(row["qid"]),
            row.get("label_en"),
            tuple(sorted(str(x) for x in cast(list[Any], row.get("atc_codes") or []))),
        )
        for row in inputs.artifacts["wikidata"].rows
    }
    for row in inputs.curated.rows:
        key = str(row["qid"])
        out[key] = c.Item(key, row.get("label_en"), tuple(sorted(row["atc_codes"])), JANUS_CURATED)
    return out


def _lines(rows: Sequence[Mapping[str, Any]], field: str) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []
    for row in rows:
        out.extend(cast(list[Mapping[str, Any]], row.get(field) or []))
    return out


def substance_lines(inputs: load.Inputs) -> list[tuple[str, str, str]]:
    """(source, substance code, published name) of every BDPM composition line and CIMA
    ingredient."""
    lines: list[tuple[str, str, str]] = []
    for source, field, code, name in (
        (c.BDPM, "composition", "substance_code", "substance_name"),
        (c.CIMA, "ingredients", "code", "name"),
    ):
        if source in inputs.artifacts:
            for x in _lines(inputs.artifacts[source].rows, field):
                if x.get(code) and x.get(name):
                    lines.append((source, str(x[code]), str(x[name])))
    return lines


def name_keys(ds: PreparedDataset) -> dict[tuple[str, str], list[str]]:
    keys: dict[tuple[str, str], set[str]] = defaultdict(set)
    for p in ds.products:
        if p.source_id in c.SUBSTANCE_SOURCES:
            for i in p.ingredients:
                if i.status == "mapped" and i.qid is not None:
                    keys[(p.source_id, i.published_name)].add(i.qid)
    return {k: sorted(v) for k, v in keys.items()}


def check_inputs(inputs: load.Inputs, ds: PreparedDataset) -> c.Inputs:
    obs, presence = c.reduce_products(views(ds))
    combination = CombinationCheck(inputs.rules)
    return c.Inputs(
        observations=obs,
        items=items(inputs),
        exclusions=tuple(
            c.Exclusion(e.key, e.code, e.source, e.reason, e.whocc_url, e.whocc_date)
            for e in inputs.code_exclusions
        ),
        substance_codes=c.substance_codes(substance_lines(inputs), name_keys(ds)),
        combination_codes=frozenset(o.code for o in obs if combination.is_combination(o.code)),
        presence=presence,
    )


def metrics(inp: c.Inputs) -> dict[str, Any]:
    by_source: dict[str, dict[str, int]] = defaultdict(lambda: {"pairs": 0, "products": 0})
    for o in inp.observations:
        by_source[o.source]["pairs"] += 1
        by_source[o.source]["products"] += o.products
    keys_by_source: dict[str, int] = defaultdict(int)
    for per in inp.presence.values():
        for s in per:
            keys_by_source[s] += 1
    return {
        "single_ingredient_code_pairs": dict(sorted(by_source.items())),
        "keys_with_products": dict(sorted(keys_by_source.items())),
        "items_with_codes": sum(1 for i in inp.items.values() if i.codes),
        "substance_codes_mapped": {
            s: sum(1 for x in inp.substance_codes if x.source == s) for s in c.SUBSTANCE_SOURCES
        },
        "exclusion_rows": len(inp.exclusions),
        "compared": (
            "ATC codes: TİTCK and CIMA single-ingredient products against the key's Wikidata "
            "item and against each other. Substance codes: BDPM and CIMA. openFDA NDC publishes "
            "no ATC code and only product-level RxCUIs, so it adds presence counts only."
        ),
    }


def source_meta(inputs: load.Inputs) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for sid, art in sorted(inputs.artifacts.items()):
        m = art.manifest
        out[sid] = {
            "pipeline": SOURCE_IDS.get(sid, sid),
            "run_id": m.get("run_id"),
            "snapshot_date": m.get("snapshot_date"),
            "license": m.get("license"),
        }
    return out


def _previous(root: Path) -> dict[str, Any] | None:
    path = root / "current" / REPORT
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def write_files(target: Path, report: Mapping[str, Any]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / REPORT).write_text(
        json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (target / FINDINGS).write_text(r.to_csv(report), encoding="utf-8")
    (target / SUMMARY).write_text(r.to_markdown(report), encoding="utf-8")


def datapackage(target: Path, report: Mapping[str, Any]) -> str:
    def res(name: str, path: str, fmt: str, media: str, title: str) -> dict[str, Any]:
        text = (target / path).read_text(encoding="utf-8")
        return {
            "name": name,
            "path": path,
            "title": title,
            "format": fmt,
            "mediatype": media,
            "encoding": "utf-8",
            "hash": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }

    meta = {
        "name": r.DATASET,
        "title": "Janus data-quality report: ingredient identity fields across sources",
        "version": report["version"],
        "created": report["run_date"],
        "homepage": "https://github.com/mikailustuner/janus",
        "description": (
            "Weekly comparison of ingredient-level ATC codes and substance codes across TİTCK, "
            "Wikidata, openFDA NDC, BDPM and AEMPS CIMA: findings classified as confirmed error, "
            "needs pharmacist or benign difference, with the diff against the previous run. "
            "Codes and counts only. " + r.DISCLAIMER
        ),
        "licenses": [
            {
                "name": "CC-BY-4.0",
                "path": r.LICENSE_URL,
                "title": "Creative Commons Attribution 4.0",
            }
        ],
        "sources": source_list(report),
        "x_janus": {
            "run_id": report["run_id"],
            "previous_run_id": report["previous_run_id"],
            "summary": report["summary"],
            "review_status": report["review_status"],
        },
        "resources": [
            res(
                "report",
                REPORT,
                "json",
                "application/json",
                "Full report (findings, diff, sources)",
            ),
            res("findings", FINDINGS, "csv", "text/csv", "One row per finding"),
            res("summary", SUMMARY, "md", "text/markdown", "Readable summary"),
        ],
    }
    return json.dumps(meta, ensure_ascii=False, indent=2) + "\n"


def source_list(report: Mapping[str, Any]) -> list[dict[str, str]]:
    src: Mapping[str, Mapping[str, Any]] = report["sources"]

    def date(sid: str) -> str:
        return str(src.get(sid, {}).get("snapshot_date") or "unknown date")

    return [
        {"title": "Wikidata (CC0 1.0)", "path": "https://www.wikidata.org/"},
        {
            "title": f"AEMPS CIMA / Nomenclátor, data of {date(c.CIMA)} (reuse with attribution, "
            "Ley 37/2007); not an AEMPS endorsement",
            "path": "https://cima.aemps.es/",
        },
        {
            "title": f"Base de données publique des médicaments, version of {date(c.BDPM)} "
            "(Licence Ouverte); used unaltered as input; no official status or endorsement",
            "path": "https://base-donnees-publique.medicaments.gouv.fr/",
        },
        {
            "title": f"TİTCK licensed human medicines list of {date(c.TITCK)}: counts only, no row "
            "is republished (terms unclear)",
            "path": "https://www.titck.gov.tr/dinamikmodul/85",
        },
        {
            "title": f"openFDA NDC directory of {date(c.OPENFDA)} (CC0 1.0): presence counts only",
            "path": "https://open.fda.gov/",
        },
        {
            "title": "ATC codes: WHO Collaborating Centre for Drug Statistics Methodology; group "
            "page addresses only, no index text",
            "path": "https://atcddd.fhi.no/atc_ddd_index/",
        },
    ]


def run_id(now: dt.datetime, version: str) -> str:
    return f"{now.strftime('%Y%m%dT%H%M%SZ')}-{version.rsplit('+', 1)[-1][:8]}"


def build(data_dir: Path, publish: bool = False, now: dt.datetime | None = None) -> Path:
    now = now or dt.datetime.now(dt.UTC)
    inputs = load.gather(data_dir)
    ds = load.prepare_inputs(inputs)
    inp = check_inputs(inputs, ds)
    found = c.run_checks(inp)
    root = data_dir / "quality"
    previous = _previous(root)
    version = r.version([r.finding_record(f, inp.items) for f in found])
    meta = r.RunMeta(
        run_id=run_id(now, version),
        run_date=now.date().isoformat(),
        previous_run_id=previous["run_id"] if previous is not None else None,
        resolution_dataset=inputs.dataset_version(),
        sources=source_meta(inputs),
        code_version=load.code_version(),
    )
    report = r.build_report(found, inp.items, meta, previous, metrics(inp))
    run = root / "runs" / meta.run_id
    write_files(run, report)
    tmp = root / "current.tmp"
    if tmp.is_symlink():
        tmp.unlink()
    tmp.symlink_to(Path("runs") / meta.run_id, target_is_directory=True)
    os.replace(tmp, root / "current")
    if publish:
        write_files(OPEN_DIR, report)
        (OPEN_DIR / "datapackage.json").write_text(datapackage(OPEN_DIR, report), encoding="utf-8")
    return run


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m janus.quality.build")
    ap.add_argument("--data-dir", type=Path)
    ap.add_argument("--publish", action="store_true", help="also write data/open/data-quality/")
    args = ap.parse_args(argv)
    data_dir = args.data_dir or Settings.from_env(dict(os.environ)).data_dir
    if data_dir is None:
        print("JANUS_DATA_DIR is not set", file=sys.stderr)
        return 2
    try:
        run = build(data_dir, publish=args.publish)
    except load.LoadError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 4
    s = json.loads((run / REPORT).read_text(encoding="utf-8"))["summary"]
    total, by_class, by_status = s["findings"], s["by_class"], s["by_status"]
    print(f"wrote {run.name}: {total} items, classes {by_class}")  # counts only
    print(f"  against the previous run {by_status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
