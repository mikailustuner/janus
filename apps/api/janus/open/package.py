"""The open cascade data package (open-data design §5, Req 4-6).

`python -m janus.open.package` writes `data/open/cascade-package/`: the PIPC rule base with
Janus's mappings, the name rules, the ATC exclusions and the dose-form groups, each file with its
own licence and source, a Frictionless `datapackage.json` and a README. `--check` compares the
committed package with what the builder would write (CI). Pure apart from reading `data/` and
writing the package.

No TİTCK string is ever written (structure.md, data-sources.md): an ingredient-synonym row is left
out when its evidence note cites TİTCK or the TİTCK-based coverage report, or when the casefolded
name's SHA-256 is in `titck_name_hashes.txt` (names that occur in the TİTCK list; only hashes
are committed, written by `--refresh-titck-hashes` from the local, uncommitted TİTCK artifact).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REPO: Final = Path(__file__).resolve().parents[4]
DATA: Final = REPO / "data"
OUT: Final = DATA / "open" / "cascade-package"
# What the web app's Open data page shows about the package (no data rows).
WEB_SUMMARY: Final = REPO / "apps" / "web" / "src" / "open" / "package-summary.json"
HASHES: Final = Path(__file__).with_name("titck_name_hashes.txt")

NAME: Final = "janus-cascade-package"
VERSION: Final = "1.0.0"
# The day the package content was last rebuilt from data/ (bump with the version).
SNAPSHOT: Final = "2026-11-09"
JANUS_LICENSE: Final = {
    "name": "Apache-2.0",
    "path": "https://www.apache.org/licenses/LICENSE-2.0",
    "title": "Apache License 2.0 (Janus curated mappings)",
}
CC_BY: Final = {
    "name": "CC-BY-4.0",
    "path": "https://creativecommons.org/licenses/by/4.0/",
    "title": "Creative Commons Attribution 4.0",
}
CC0: Final = {
    "name": "CC0-1.0",
    "path": "https://creativecommons.org/publicdomain/zero/1.0/",
    "title": "CC0 1.0 (openFDA dose-form names)",
}
ETALAB: Final = {
    "name": "etalab-2.0",
    "path": "https://www.etalab.gouv.fr/licence-ouverte-open-licence/",
    "title": "Licence Ouverte 2.0 (BDPM dose-form names, shown as published)",
}


@dataclass(frozen=True)
class Resource:
    name: str
    source_file: str
    title: str
    description: str
    licenses: tuple[Mapping[str, str], ...]
    sources: tuple[Mapping[str, str], ...]


PIPC_SOURCE: Final = {
    "title": (
        "Rochon PA et al. Potentially inappropriate prescribing cascades (PIPC) list. "
        "Eur Geriatr Med 2025;16(5):1573-1584. doi:10.1007/s41999-025-01215-x, Table 1"
    ),
    "path": "https://doi.org/10.1007/s41999-025-01215-x",
}
JANUS_SOURCE: Final = {
    "title": "Janus (curated, reviewed by the project owner with AI assistance)",
    "path": "https://github.com/mikailustuner/janus",
}
WHOCC_NOTE: Final = {
    "title": (
        "ATC codes checked by hand on the WHOCC ATC/DDD index pages named in the rows; codes "
        "only, no WHO index text is copied"
    ),
    "path": "https://atcddd.fhi.no/atc_ddd_index/",
}

RESOURCES: Final = (
    Resource(
        "pipc",
        "pipc.csv",
        "PIPC list, Table 1 (65 prescribing cascades)",
        "Cell text as published; only whitespace changed.",
        (CC_BY,),
        (PIPC_SOURCE,),
    ),
    Resource(
        "pipc_rules",
        "pipc_rules.csv",
        "Janus mapping of each PIPC row to its index and marker drug classes",
        "One row per PIPC row 1-65: index class, marker class, or why the row cannot be matched.",
        (JANUS_LICENSE,),
        (JANUS_SOURCE, PIPC_SOURCE),
    ),
    Resource(
        "cascade_classes",
        "cascade_classes.csv",
        "Drug classes as ATC prefix patterns",
        "class_id -> ATC pattern (include/exclude), scope and basis of each row.",
        (JANUS_LICENSE,),
        (JANUS_SOURCE, WHOCC_NOTE),
    ),
    Resource(
        "atc_code_exclusions",
        "atc_code_exclusions.csv",
        "ATC codes dropped from an ingredient key",
        "Reviewed (key, code, source) triples that a source gives wrongly (wrong substance, "
        "old code, not a medicine).",
        (JANUS_LICENSE,),
        (JANUS_SOURCE, WHOCC_NOTE),
    ),
    Resource(
        "ingredient_synonyms",
        "ingredient_synonyms.csv",
        "Ingredient name -> Wikidata item (name rules)",
        "Published ingredient names the matching ladder cannot map, with the evidence for each. "
        "Rows citing or matching the TİTCK list are left out of this package.",
        (JANUS_LICENSE,),
        (JANUS_SOURCE,),
    ),
    Resource(
        "anion_acid_forms",
        "anion_acid_forms.csv",
        "Anion -> acid ingredient forms (name rules)",
        "Reviewed rows of the anion_acid step of the matching ladder.",
        (JANUS_LICENSE,),
        (JANUS_SOURCE, WHOCC_NOTE),
    ),
    Resource(
        "dose_form_groups",
        "dose_form_groups.csv",
        "Published dose form -> Janus dose-form group",
        "openFDA SPL dosage form names and BDPM pharmaceutical forms as published, each mapped "
        "to one of fourteen Janus groups.",
        (JANUS_LICENSE, CC0, ETALAB),
        (
            JANUS_SOURCE,
            {"title": "openFDA NDC directory (CC0 1.0)", "path": "https://open.fda.gov/"},
            {
                "title": "Base de données publique des médicaments (BDPM); the BDPM does not "
                "endorse Janus",
                "path": "https://base-donnees-publique.medicaments.gouv.fr/",
            },
        ),
    ),
)


def _norm(name: str) -> str:
    return " ".join(name.casefold().split())


def name_hash(name: str) -> str:
    return hashlib.sha256(_norm(name).encode("utf-8")).hexdigest()


def cites_titck(note: str) -> bool:
    # casefold turns "İ" into "i" + combining dot; drop the dot before matching.
    return "titck" in note.casefold().replace("\u0307", "")


def from_coverage_report(note: str) -> bool:
    """Rows proposed from the PIPC coverage report: its names came from the TİTCK list too."""
    return "pipc coverage report" in note.casefold()


def titck_hashes(path: Path = HASHES) -> frozenset[str]:
    if not path.is_file():
        return frozenset()
    return frozenset(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )


def _read(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text))
    return list(reader.fieldnames or []), list(reader)


def _write(header: Sequence[str], rows: Iterable[Mapping[str, str]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(header), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in header})
    return buf.getvalue()


def synonyms(text: str, hashes: frozenset[str]) -> tuple[str, int]:
    """The synonym rows that may be published, and how many were left out."""
    header, rows = _read(text)
    kept = [
        r
        for r in rows
        if not cites_titck(r["note"])
        and not from_coverage_report(r["note"])
        and name_hash(r["name"]) not in hashes
    ]
    return _write(header, kept), len(rows) - len(kept)


def _schema(header: Sequence[str]) -> dict[str, object]:
    return {"fields": [{"name": h, "type": "string"} for h in header]}


def build(data: Path = DATA, hashes: frozenset[str] | None = None) -> dict[str, str]:
    """Every file of the package, path -> text."""
    hashes = titck_hashes() if hashes is None else hashes
    files: dict[str, str] = {}
    left_out = 0
    resources: list[dict[str, object]] = []
    for res in RESOURCES:
        text = (data / res.source_file).read_text(encoding="utf-8")
        if res.name == "ingredient_synonyms":
            text, left_out = synonyms(text, hashes)
        header, rows = _read(text)
        files[res.source_file] = text
        resources.append(
            {
                "name": res.name,
                "path": res.source_file,
                "title": res.title,
                "description": res.description,
                "format": "csv",
                "mediatype": "text/csv",
                "encoding": "utf-8",
                "hash": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "rows": len(rows),
                "licenses": [dict(x) for x in res.licenses],
                "sources": [dict(x) for x in res.sources],
                "schema": _schema(header),
            }
        )
    package = {
        "name": NAME,
        "title": "Janus prescribing-cascade data package",
        "version": VERSION,
        "created": SNAPSHOT,
        "homepage": "https://github.com/mikailustuner/janus",
        "description": (
            "The PIPC prescribing-cascade rule base with Janus's mappings to ATC classes, the "
            "ingredient name rules, the ATC exclusions and the dose-form groups that Janus uses. "
            "Each resource carries its own licence. Not medical advice."
        ),
        "licenses": [CC_BY, JANUS_LICENSE, CC0, ETALAB],
        "contributors": [{"title": "Janus contributors", "role": "author"}],
        "x_janus": {
            "synonym_rows_left_out_for_titck": left_out,
            "titck_content": (
                "no TİTCK list row, product name or barcode; some notes state codes or row "
                "counts observed in the TİTCK list"
            ),
        },
        "resources": resources,
    }
    files["datapackage.json"] = json.dumps(package, ensure_ascii=False, indent=2) + "\n"
    files["README.md"] = readme(resources, left_out)
    return files


def readme(resources: Sequence[Mapping[str, object]], left_out: int) -> str:
    lines = [
        f"# Janus prescribing-cascade data package {VERSION} ({SNAPSHOT})",
        "",
        "The rule base Janus uses to find prescribing cascades, as open data. Generated by",
        "`python -m janus.open.package` from `data/`; do not edit by hand. Described in",
        "`docs/open-data.md` (data dictionary, how to cite) and `datapackage.json` (Frictionless).",
        "",
        "| File | Rows | Licence | Content |",
        "|---|---|---|---|",
    ]
    for r in resources:
        lic = ", ".join(str(x["name"]) for x in r["licenses"])  # type: ignore[union-attr]
        lines.append(f"| `{r['path']}` | {r['rows']} | {lic} | {r['title']} |")
    lines += [
        "",
        "## Licences and attribution",
        "",
        "- `pipc.csv` is Table 1 of Rochon PA et al., *Potentially inappropriate prescribing",
        "  cascades (PIPC) list*, Eur Geriatr Med 2025;16(5):1573-1584,",
        "  doi:10.1007/s41999-025-01215-x, under CC BY 4.0. Cite the paper when you use it.",
        "- The Janus mappings (`pipc_rules.csv`, `cascade_classes.csv`, `atc_code_exclusions.csv`,",
        "  `ingredient_synonyms.csv`, `anion_acid_forms.csv` and the group column of",
        "  `dose_form_groups.csv`) are Apache-2.0, like the Janus code.",
        "- `dose_form_groups.csv` quotes dose-form names as published by openFDA (CC0 1.0) and by",
        "  the BDPM (Licence Ouverte 2.0; shown as published; the BDPM does not endorse Janus).",
        "- ATC codes were checked by hand against the WHOCC ATC/DDD index; no WHO index text is",
        "  copied. The WHO ATC/DDD index itself is not open data.",
        "- No TİTCK list row, product name or barcode is included; some notes state codes or row",
        "  counts observed in the TİTCK list.",
        f"- {left_out} ingredient-synonym rows that cite or match the TİTCK list, or come from the",
        "  coverage report that was built on it, are left out.",
        "",
        "## Status",
        "",
        "Reviewed by the project owner with AI assistance; not yet reviewed by a pharmacist or a",
        "physician. Not medical advice. Report errors as described in",
        "`docs/contributing-corrections.md`.",
        "",
    ]
    return "\n".join(lines)


def web_summary(files: Mapping[str, str]) -> str:
    meta = json.loads(files["datapackage.json"])
    return (
        json.dumps(
            {
                "name": meta["name"],
                "version": meta["version"],
                "created": meta["created"],
                "resources": [
                    {
                        "path": r["path"],
                        "rows": r["rows"],
                        "licenses": [x["name"] for x in r["licenses"]],
                    }
                    for r in meta["resources"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def check(out: Path = OUT) -> list[str]:
    """Paths whose committed text differs from the builder's (empty when up to date)."""
    want = build()
    summary = web_summary(want)
    bad = [
        p
        for p, text in want.items()
        if not (out / p).is_file() or (out / p).read_text(encoding="utf-8") != text
    ]
    extra = (
        [p.name for p in out.iterdir() if p.is_file() and p.name not in want]
        if out.is_dir()
        else []
    )
    web = (
        []
        if WEB_SUMMARY.is_file() and WEB_SUMMARY.read_text(encoding="utf-8") == summary
        else [str(WEB_SUMMARY.relative_to(REPO))]
    )
    return sorted(bad + extra + web)


def refresh_titck_hashes(artifact: Path) -> int:
    """Hashes of synonym names that occur in the local TİTCK artifact (never the names)."""
    import duckdb  # the API already reads parquet with DuckDB

    con = duckdb.connect()
    values = con.execute(
        "SELECT product_name, ingredient_text FROM read_parquet(?)", [str(artifact)]
    ).fetchall()
    blob = "\n".join(_norm(str(v)) for row in values for v in row if v is not None)
    _, rows = _read((DATA / "ingredient_synonyms.csv").read_text(encoding="utf-8"))
    found = sorted({name_hash(r["name"]) for r in rows if _norm(r["name"]) in blob})
    HASHES.write_text(
        "# SHA-256 of casefolded ingredient-synonym names that occur in the TİTCK list.\n"
        "# Written by `python -m janus.open.package --refresh-titck-hashes`; hashes only.\n"
        + "".join(h + "\n" for h in found),
        encoding="utf-8",
    )
    return len(found)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m janus.open.package")
    ap.add_argument("--check", action="store_true", help="fail if the committed package is stale")
    ap.add_argument("--refresh-titck-hashes", type=Path, metavar="ROWS_PARQUET")
    args = ap.parse_args(argv)
    if args.refresh_titck_hashes:
        n = refresh_titck_hashes(args.refresh_titck_hashes)
        print(f"{n} hashes written")
        return 0
    if args.check:
        stale = check()
        for p in stale:
            print(f"stale: {p}", file=sys.stderr)
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    files = build()
    for path, text in files.items():
        (OUT / path).write_text(text, encoding="utf-8")
    WEB_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    WEB_SUMMARY.write_text(web_summary(files), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
