"""Hypothesis strategies and reference implementations for the cascade engine
(cascade-engine design §8). Synthetic data only: codes, classes and PIPC-like text are generated.
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Sequence, Set
from dataclasses import dataclass, field, replace
from typing import Any

from hypothesis import strategies as st

from janus.cascades.model import (
    PIPC_COUNT,
    PIPC_SCHEMA_VERSION,
    REQUIRED_ABRUPT_GROUPS,
    AtcClass,
    MatchKind,
    Pattern,
    Scope,
)
from janus.cascades.rulebase import (
    ABRUPT_HEADER,
    CLASSES_HEADER,
    PAPERS_HEADER,
    PIPC_HEADER,
    PRIORITY_HEADER,
    RULES_HEADER,
    RuleBaseInputs,
)
from janus.resolution.canonical import content_hash

# Small alphabets so that prefixes nest often. Letters A, N, R carry rule classes; C is reserved
# for the synthetic combination rules, so generated patterns never collide with them by chance.
LETTERS = "ANR"
# File-set properties build 65-row files per example; they run fewer examples, like the
# database-backed properties (design §8).
FILE_SET_EXAMPLES = 50 if os.environ.get("HYPOTHESIS_PROFILE") == "ci" else 20
LAST_TWO = [f"{n:02d}" for n in range(1, 20)]  # outside the WHO numbering series (20, 30, 50-79)


@st.composite
def ingredient_codes(draw: st.DrawFn, letters: str = LETTERS) -> str:
    return (
        draw(st.sampled_from(letters))
        + draw(st.sampled_from(["01", "02", "03"]))
        + draw(st.sampled_from("AB"))
        + draw(st.sampled_from("AB"))
        + draw(st.sampled_from(LAST_TWO[:4]))
    )


def prefix_of(code: str, level: int) -> str:
    """ATC prefix of `code` at level 1-5 (1, 3, 4, 5, 7 characters)."""
    return code[: (1, 3, 4, 5, 7)[level - 1]]


@st.composite
def prefixes(draw: st.DrawFn) -> str:
    return prefix_of(draw(ingredient_codes()), draw(st.integers(1, 5)))


EXTENSION_IDS = ["paper:src_a:ext1", "paper:src_b:ext2"]


@st.composite
def atc_classes(draw: st.DrawFn, class_id: str = "cls", extensions: bool = True) -> AtcClass:
    chosen = draw(st.lists(prefixes(), min_size=1, max_size=6, unique=True))
    pats: list[Pattern] = []
    for i, prefix in enumerate(chosen):
        ext = extensions and draw(st.booleans()) and draw(st.booleans())
        if ext:
            pats.append(
                Pattern(prefix, "include", "form_extension", draw(st.sampled_from(EXTENSION_IDS)))
            )
        else:
            match: MatchKind = (
                "include" if i == 0 else draw(st.sampled_from(["include", "exclude"]))
            )
            pats.append(Pattern(prefix, match))
    return AtcClass(class_id, tuple(sorted(pats, key=lambda p: p.prefix)))


def ref_class_match(code: str, cls: AtcClass, active: Set[str]) -> Scope | None:
    """Brute force: among all active patterns that prefix the code, the longest decides."""
    live = [
        p
        for p in cls.patterns
        if code.startswith(p.prefix) and (p.scope == "pipc" or p.evidence_id in active)
    ]
    if not live:
        return None
    longest = max(len(p.prefix) for p in live)
    (best,) = [p for p in live if len(p.prefix) == longest]
    return best.scope if best.match == "include" else None


# --- Rule-base file sets ---------------------------------------------------------------------

COMBINATION_CSV = (
    "pattern,kind,note\n"
    "C09B,combination_group,synthetic group\n"
    "C10BA02,combination_code,synthetic code\n"
    "C09BX,exception,synthetic exception\n"
)
WHOCC_NOTE = "checked on https://atcddd.fhi.no/atc_ddd_index/?code=X 2026-11-07"
TEXT = st.text(alphabet="abcdefgh ,()/-", min_size=1, max_size=12).map(lambda s: s.strip() or "x")


def render(header: Sequence[str], rows: Sequence[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(header), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: "" if r.get(k) is None else r[k] for k in header})
    return buf.getvalue()


@dataclass
class FileSet:
    """Row lists of every curated file; `inputs()` renders them as CSV text."""

    pipc: list[dict[str, Any]]
    papers: list[dict[str, Any]]
    classes: list[dict[str, Any]]
    rules: list[dict[str, Any]]
    priority: list[dict[str, Any]]
    abrupt: list[dict[str, Any]]
    window: int = 12
    meta_hash: str | None = None  # None = computed from `pipc`
    combination: str = COMBINATION_CSV
    extra: dict[str, Any] = field(default_factory=dict[str, Any])

    def inputs(self) -> RuleBaseInputs:
        pipc_rows = [{**r, "position": int(r["position"])} for r in self.pipc]
        meta = {"content_sha256": self.meta_hash or content_hash(pipc_rows, PIPC_SCHEMA_VERSION)}
        return RuleBaseInputs(
            pipc_csv=render(PIPC_HEADER, self.pipc),
            pipc_meta_json=json.dumps(meta),
            classes_csv=render(CLASSES_HEADER, self.classes),
            rules_csv=render(RULES_HEADER, self.rules),
            priority_csv=render(PRIORITY_HEADER, self.priority),
            abrupt_csv=render(ABRUPT_HEADER, self.abrupt),
            combination_csv=self.combination,
            papers_csv=render(PAPERS_HEADER, self.papers),
            window_months=self.window,
        )

    def copy(self) -> FileSet:
        return replace(
            self,
            pipc=[dict(r) for r in self.pipc],
            papers=[dict(r) for r in self.papers],
            classes=[dict(r) for r in self.classes],
            rules=[dict(r) for r in self.rules],
            priority=[dict(r) for r in self.priority],
            abrupt=[dict(r) for r in self.abrupt],
        )


PAPERS = [
    {
        "key": key,
        "doi": f"10.1000/{key}",
        "source_id": src,
        "title": "t",
        "verified_on": "2026-11-07",
        "note": "n",
    }
    for key, src in (("ext1", "src_a"), ("ext2", "src_b"), ("prio", "src_p"), ("supp", "src_s"))
]
PRIORITY_ID = "paper:src_p:prio"
SUPPORT_ID = "paper:src_s:supp"


def class_rows(cls: AtcClass, basis: str) -> list[dict[str, Any]]:
    return [
        {
            "class_id": cls.class_id,
            "pattern": p.prefix,
            "match": p.match,
            "scope": p.scope,
            "basis": basis,
            "evidence_id": p.evidence_id,
            "note": WHOCC_NOTE if basis == "whocc_lookup" else "synthetic note",
        }
        for p in cls.patterns
    ]


@st.composite
def file_sets(draw: st.DrawFn) -> FileSet:
    """A valid set of curated files; class 'ext_index' always carries a form extension."""
    word = draw(TEXT)  # one drawn word keeps the rows varied without 65 x 4 draws
    pipc = [
        {
            "position": n,
            "system": f"system {n % 7}",
            "kind": "individual_drug" if n % 5 == 0 else "drug_class",
            "drug_a": f"{word} a{n}",
            "adverse_event": f"event {n}",
            "drug_b": f"{word} b{n}",
            "locator": f"Table 1, row {n}",
        }
        for n in range(1, PIPC_COUNT + 1)
    ]
    n_plain = draw(st.integers(2, 5))
    plain = [draw(atc_classes(f"cls_{i}", extensions=False)) for i in range(n_plain)]
    ext_base = draw(atc_classes("ext_index", extensions=False))
    ext_prefix = draw(prefixes().filter(lambda p: p not in {q.prefix for q in ext_base.patterns}))
    ext = AtcClass(
        "ext_index",
        tuple(
            sorted(
                (
                    *ext_base.patterns,
                    Pattern(ext_prefix, "include", "form_extension", EXTENSION_IDS[0]),
                ),
                key=lambda p: p.prefix,
            )
        ),
    )
    classes: list[dict[str, Any]] = []
    for c in [*plain, ext]:
        classes += class_rows(
            c, draw(st.sampled_from(["whocc_lookup", "pharmacology", "wikidata"]))
        )
    plain_ids = [c.class_id for c in plain]
    rules: list[dict[str, Any]] = []
    for n in range(1, PIPC_COUNT + 1):
        if n == 1:
            index, marker = "ext_index", plain_ids[0]
        elif n - 2 < len(plain_ids):
            index, marker = plain_ids[n - 2], plain_ids[(n - 1) % len(plain_ids)]
        else:
            index, marker = draw(st.sampled_from(plain_ids)), draw(st.sampled_from(plain_ids))
        role = draw(st.sampled_from(["", "", "", "marker"])) if n > len(plain_ids) + 2 else ""
        rules.append(
            {
                "position": n,
                "index_class": index,
                "marker_class": "" if role == "marker" else marker,
                "unmatchable_role": role,
                "unmatchable_reason": "no_atc_code" if role else "",
                "supporting": SUPPORT_ID if draw(st.booleans()) else "",
                "note": "",
            }
        )
    prio_positions = draw(st.lists(st.integers(1, PIPC_COUNT), max_size=3, unique=True))
    priority = [
        {
            "position": p,
            "evidence_id": PRIORITY_ID,
            "measure": "incidence",
            "value": "10.9",
            "ci_low": "10.7",
            "ci_high": "11.0",
            "unit": "percent",
            "locator": "Abstract, Results",
            "note": "",
        }
        for p in prio_positions
    ]
    abrupt = [
        {"pattern": p, "match": "include", "group": g, "note": "n"}
        for p, g in zip(ABRUPT_PATTERNS, REQUIRED_ABRUPT_GROUPS, strict=True)
    ]
    return FileSet(pipc, [dict(p) for p in PAPERS], classes, rules, priority, abrupt)


ABRUPT_PATTERNS = ["N01A", "N02A", "N03A", "R01A", "R02A", "R03A"]
