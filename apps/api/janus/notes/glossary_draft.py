"""Draft ingredient rows of the clinical glossary (doctor-loop design §11, task 14).

Usage: `python -m janus.notes.glossary_draft [--out PATH]` with `DATABASE_URL` (a loaded database).
Reads, in one read-only transaction, the current rule base and the current resolution dataset, and
writes one row per ingredient key that can appear in a finding or an abrupt-stop warning: members
of the classes the 65 rules use (form extensions included) and of the abrupt-stop list. Names are
the dataset's labels (Wikidata, CC0; curated labels for `J` keys); no TİTCK string is read. New rows
are `proposed`; a row already reviewed (`accepted` or `rejected`) is kept unchanged. A label that
fails a glossary check (word lists, NFC, length) is left empty and counted. Prints counts only.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import unicodedata
from collections.abc import Iterable, Mapping
from pathlib import Path

import psycopg

from janus.cascades import repository as cascade_repository
from janus.cascades.model import RuleBase
from janus.cascades.patterns import class_match
from janus.notes import phrases
from janus.notes.glossary import (
    GLOSSARY_DIR,
    INGREDIENT_HEADER,
    LANGUAGES,
    MAX_NAME,
    GlossaryError,
    parse_ingredients,
)
from janus.settings import Settings


def in_scope(rb: RuleBase, codes_by_key: Mapping[str, Iterable[str]]) -> set[str]:
    """Keys with a code in a class a rule uses (extensions active) or on the abrupt-stop list."""
    used = {c for r in rb.rules for c in (r.index_class, r.marker_class) if c}
    active = frozenset(
        p.evidence_id
        for cls in rb.classes.values()
        for p in cls.patterns
        if p.scope == "form_extension" and p.evidence_id
    )
    out: set[str] = set()
    for key, codes in codes_by_key.items():
        for code in codes:
            if class_match(code, rb.abrupt_stop) or any(
                class_match(code, rb.classes[c], active) for c in used
            ):
                out.add(key)
                break
    return out


def clean(value: object, lang: str) -> str:
    """A label usable as a glossary cell, or "" (counted by the caller)."""
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFC", value.strip())
    if not text or "\n" in text or len(text) > MAX_NAME or not any(ch.isalpha() for ch in text):
        return ""
    forbidden, reassurance = phrases.violations(text, lang)
    return "" if forbidden or reassurance else text


def draft_rows(
    keys: Iterable[str],
    labels: Mapping[str, Mapping[str, object]],
    source: str,
    existing: Mapping[str, dict[str, str]],
) -> tuple[list[dict[str, str]], int]:
    rows: list[dict[str, str]] = []
    dropped = 0
    for key in sorted(keys, key=lambda k: (k[0], int(k[1:]))):
        if key in existing and existing[key]["status"] in ("accepted", "rejected"):
            rows.append(existing[key])
            continue
        row = {h: "" for h in INGREDIENT_HEADER}
        row["key"], row["status"] = key, "proposed"
        row["source"] = "janus_curated" if key.startswith("J") else source
        for lang in LANGUAGES:
            raw = labels.get(key, {}).get(lang)
            row[lang] = clean(raw, lang)
            dropped += bool(raw) and not row[lang]
        rows.append(row)
    return rows, dropped


def render(rows: list[dict[str, str]]) -> str:
    buf = io.StringIO()
    fields: list[str] = list(INGREDIENT_HEADER)
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=GLOSSARY_DIR / "ingredients.csv")
    args = ap.parse_args(argv)
    settings = Settings.from_env()
    if not settings.database_url:
        sys.stderr.write("DATABASE_URL is required\n")
        return 2
    with psycopg.connect(settings.database_url) as conn:
        conn.read_only = True
        rb = cascade_repository.current_rule_base(conn)
        row = conn.execute("SELECT dataset_id FROM res_current").fetchone()
        if rb is None or row is None:
            sys.stderr.write("rule base or resolution dataset not loaded\n")
            return 2
        dataset = str(row[0])
        data = conn.execute(
            "SELECT qid, labels, ingredient_atc FROM res_ingredient WHERE dataset_id = %s",
            (dataset,),
        ).fetchall()
    codes: dict[str, list[str]] = {}
    labels: dict[str, dict[str, object]] = {}
    for qid, lab, atc in data:
        codes[str(qid)] = [str(a["code"]) for a in atc]
        labels[str(qid)] = dict(lab or {})
    existing: dict[str, dict[str, str]] = {}
    if args.out.exists():
        text = args.out.read_text(encoding="utf-8")
        try:
            parse_ingredients(text)
        except GlossaryError as exc:
            sys.stderr.write(f"existing file is invalid: {exc}\n")
            return 2
        existing = {r["key"]: r for r in csv.DictReader(io.StringIO(text))}
    keys = in_scope(rb, codes)
    rows, dropped = draft_rows(keys, labels, f"dataset:{dataset[:8]}", existing)
    output = render(rows)
    parse_ingredients(output)  # the draft must load
    args.out.write_text(output, encoding="utf-8")
    filled = {lang: sum(1 for r in rows if r[lang]) for lang in LANGUAGES}
    print(  # log-guard: ignore (counts only)
        f"rows={len(rows)} kept_reviewed={sum(1 for r in rows if r['status'] != 'proposed')} "
        f"labels_left_out={dropped} " + " ".join(f"{lang}={n}" for lang, n in filled.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
