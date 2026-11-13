"""Fill empty ingredient names of the clinical glossary from Wikidata labels (plan D4.2).

The glossary (`apps/api/janus/notes/glossary/ingredients.csv`) gives the web and the doctor note
their ingredient names. A missing name is printed as the English INN with "name not translated".
This tool fills only empty cells of one language, only in `accepted` rows, from the `label_<lang>`
column of a Wikidata ingredients run (CC0). A filled name gets these checks, so a doubtful label
stays empty (the English fallback is shown):

- NFC; at most 60 characters; no brackets, semicolons or commas;
- parentheses only for an oxidation state such as "(II)";
- the first letter lower-cased when the second is lower case (INNs are common nouns; the glossary
  review of 2026-11-08 did the same), so acronyms stay as they are.

The row's note records the source and that native-speaker and expert review have not yet been done.
Existing names are never changed. Prints counts only.

    uv run --project pipelines python pipelines/tools/glossary_fill_names.py --lang pt \
        --run .data/artifacts/wikidata_ingredients/current --date 2026-11-13
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path

GLOSSARY = Path(__file__).resolve().parents[2] / "apps/api/janus/notes/glossary/ingredients.csv"
LANGS = ("tr", "de", "fr", "es", "pt")
MAX_LEN = 60
OXIDATION = re.compile(r"\((?:I|II|III|IV|V|VI)\)")


def clean(label: str) -> str | None:
    """The label as a glossary name, or None when it fails a check."""
    name = unicodedata.normalize("NFC", label.strip())
    if not name or len(name) > MAX_LEN or re.search(r"[\[\];,]", name):
        return None
    if "(" in OXIDATION.sub("", name) or ")" in OXIDATION.sub("", name):
        return None
    if len(name) > 1 and name[0].isupper() and name[1].islower():
        name = name[0].lower() + name[1:]
    return name


def note_line(lang: str, date: str) -> str:
    return (
        f"{lang} ({date}): Wikidata label (CC0), automated checks only; "
        "native-speaker and expert review not yet done."
    )


def fill(text: str, labels: Mapping[str, str], lang: str, date: str) -> tuple[str, dict[str, int]]:
    """The glossary text with empty `lang` cells filled; and counts."""
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames
    if header is None or lang not in header:
        raise ValueError(f"glossary has no {lang!r} column")
    rows = list(reader)
    counts = {"accepted": 0, "had_name": 0, "filled": 0, "no_label": 0, "rejected": 0}
    for r in rows:
        if r["status"] != "accepted":
            continue
        counts["accepted"] += 1
        if r[lang]:
            counts["had_name"] += 1
            continue
        label = labels.get(r["key"])
        if not label:
            counts["no_label"] += 1
            continue
        name = clean(label)
        if name is None:
            counts["rejected"] += 1
            continue
        r[lang] = name
        r["note"] = "; ".join(x for x in (r["note"], note_line(lang, date)) if x)
        counts["filled"] += 1
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue(), counts


def read_labels(run: Path, lang: str) -> dict[str, str]:
    import polars as pl

    df = pl.read_parquet(run / "rows.parquet").select("qid", f"label_{lang}")
    return {q: v for q, v in df.iter_rows() if v}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lang", choices=LANGS, required=True)
    ap.add_argument("--run", type=Path, required=True, help="a wikidata_ingredients run directory")
    ap.add_argument("--date", required=True, help="date written to the row notes (YYYY-MM-DD)")
    ap.add_argument("--glossary", type=Path, default=GLOSSARY)
    a = ap.parse_args()
    text, counts = fill(
        a.glossary.read_text(encoding="utf-8"), read_labels(a.run, a.lang), a.lang, a.date
    )
    a.glossary.write_text(text, encoding="utf-8")
    named = counts["had_name"] + counts["filled"]
    print(
        f"{a.lang}: {counts['filled']} filled, {counts['no_label']} without a Wikidata label, "
        f"{counts['rejected']} rejected by the checks; "
        f"{named}/{counts['accepted']} accepted rows now have a name"
    )


if __name__ == "__main__":
    main()
