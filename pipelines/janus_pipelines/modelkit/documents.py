"""Review PDFs and PMC articles -> paired candidates (spec model-kit, milestone M5). The only place
where the document readers A (`doc_a`) and B (`doc_b`) meet: pairing on the shared locator,
confirmation by code (`confirm`), and in addition the two readers must name the same study. Research
use only. Not for clinical decisions."""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from janus_pipelines.modelkit import doc_a, doc_b
from janus_pipelines.modelkit.confirm import Confirmation, confirm
from janus_pipelines.modelkit.formref import BrandTable
from janus_pipelines.modelkit.model import Candidate, ReaderStats
from janus_pipelines.modelkit.pairing import Paired, pair
from janus_pipelines.modelkit.pmc_jats import Article
from janus_pipelines.modelkit.resolver import IdentityTable
from janus_pipelines.modelkit.review_text import Page
from janus_pipelines.modelkit.species import article_is_human, table_is_human


def _study_check(pairs: list[Paired], counts: Counter[str]) -> list[Paired]:
    out: list[Paired] = []
    for p in pairs:
        if p.b is not None and p.result.confirmed and p.a.study_id != p.b.study_id:
            counts["studies_differ"] += 1
            out.append(Paired(p.a, p.b, Confirmation(False, "studies_differ")))
        else:
            out.append(p)
    return out


_PLAIN_ORAL = re.compile(
    r"^(?:TABLET|CAPSULE)(?:, (?:FILM COATED|COATED|GELATIN COATED|SUGAR COATED))?;\s*ORAL$"
)


def application_forms(zip_path: Path) -> dict[str, frozenset[str]]:
    """Dosage forms ('TABLET;ORAL', ...) of every application in the Drugs@FDA data file."""
    out: dict[str, set[str]] = defaultdict(set)
    with zipfile.ZipFile(zip_path) as zf:
        text = zf.read("Products.txt").decode("latin-1")
    for r in csv.DictReader(io.StringIO(text), delimiter="\t"):
        out[r["ApplNo"]].add(r["Form"].strip().upper())
    return {k: frozenset(v) for k, v in out.items()}


def plain_oral(forms: frozenset[str]) -> bool:
    """Every product of the application is a plain oral tablet or capsule (no release-modifying
    word)."""
    return bool(forms) and all(_PLAIN_ORAL.match(f) for f in forms)


def _fill_from_products(c: Candidate) -> Candidate:
    if c.context.formulation != "unspecified" or c.context.route not in ("oral", "unknown"):
        return c
    return replace(
        c,
        context=replace(c.context, formulation="immediate_release", route="oral"),
        notes=(*c.notes, "formulation:application_products"),
    )


def products_rule(pairs: list[Paired], forms: frozenset[str], counts: Counter[str]) -> list[Paired]:
    """Addendum 2 of the M5 pre-registration (the label rule DP-M15 for reviews): where the table
    and its study text are silent on formulation and route, they are taken from the application's
    products in the Drugs@FDA data file, only if every product is a plain oral tablet or capsule.
    Applied to both candidates alike; confirmation is decided again."""
    if not plain_oral(forms):
        return pairs
    out: list[Paired] = []
    for p in pairs:
        if p.b is None:
            out.append(p)
            continue
        a2, b2 = _fill_from_products(p.a), _fill_from_products(p.b)
        if a2 is p.a and b2 is p.b:
            out.append(p)
            continue
        counts["formulation_from_application_products"] += 1
        out.append(Paired(a2, b2, confirm(a2.reading(), b2.reading())))
    return out


def read_review(
    pages: Sequence[Page],
    doc: doc_a.ReviewDoc,
    table: IdentityTable,
    brands: BrandTable,
    stats: dict[str, ReaderStats],
    counts: Counter[str],
    forms: frozenset[str] = frozenset(),
) -> list[Paired]:
    a = doc_a.read_review(pages, doc, table, brands, stats["a"])
    b = doc_b.read_review(pages, doc, table, brands, stats["b"])
    pairs, left = pair(a, b)
    counts["review_candidates_a"] += len(a)
    counts["review_candidates_b"] += len(b)
    counts["review_only_b"] += len(left)
    return _study_check(products_rule(pairs, forms, counts), counts)


@dataclass(frozen=True)
class HumanCheck:
    human: bool
    tables_dropped: int


def human_tables(art: Article) -> tuple[Article, HumanCheck]:
    """The article with its non-human tables removed, and whether the article itself is about
    people."""
    if not article_is_human(art.title, art.journal, art.keywords, art.abstract, art.methods):
        return art, HumanCheck(False, len(art.tables))
    keep = tuple(
        t
        for t in art.tables
        if table_is_human(
            t.caption, t.footnotes, " ".join(" ".join(r) for r in t.grid[: max(1, t.head_rows)])
        )
    )
    return replace(art, tables=keep), HumanCheck(True, len(art.tables) - len(keep))


def read_article(
    art: Article,
    drug_key: str,
    table: IdentityTable,
    brands: BrandTable,
    stats: dict[str, ReaderStats],
    counts: Counter[str],
    version: str,
) -> list[Paired]:
    kept, check = human_tables(art)
    if not check.human:
        counts["articles_not_human"] += 1
        return []
    counts["tables_not_human"] += check.tables_dropped
    a = doc_a.read_pmc(kept, drug_key, table, brands, stats["a"], version)
    b = doc_b.read_pmc(kept, drug_key, table, brands, stats["b"], version)
    pairs, left = pair(a, b)
    counts["pmc_candidates_a"] += len(a)
    counts["pmc_candidates_b"] += len(b)
    counts["pmc_only_b"] += len(left)
    return _study_check(pairs, counts)


_NCT = re.compile(r"\bNCT\s?\d{8}\b")


def review_study_keys(pages: Sequence[Page]) -> list[str]:
    """NCT numbers written anywhere in a review's readable text (identity keys of its document-level
    study)."""
    found: set[str] = set()
    for p in pages:
        for line in p.lines:
            found |= {re.sub(r"\s", "", m.group(0)) for m in _NCT.finditer(line)}
    return sorted(found)
