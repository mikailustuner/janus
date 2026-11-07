"""Parse and validate the curated rule-base files (cascade-engine design §3, §5.1). Pure.

Inputs are file texts, so the loader (I/O) and the tests share one code path. The first defect
found raises `RuleBaseError` with a fixed code, the file, the row number and the column; the
message never contains cell values.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from janus.cascades.model import (
    BASES,
    DEFAULT_WINDOW_MONTHS,
    MATCH_KINDS,
    MEASURE_UNITS,
    PIPC_COUNT,
    PIPC_SCHEMA_VERSION,
    REQUIRED_ABRUPT_GROUPS,
    SCOPES,
    UNMATCHABLE_REASONS,
    WINDOW_RANGE,
    AbruptGroup,
    AtcClass,
    Basis,
    MatchKind,
    Measure,
    Pattern,
    Priority,
    Rule,
    RuleBase,
    Scope,
    Unit,
    UnmatchableReason,
)
from janus.cascades.patterns import is_ingredient_code, is_prefix_pattern
from janus.resolution.atc import CombinationCheck, CombinationRules, RulesFileError
from janus.resolution.canonical import canonical_line, content_hash

PIPC_FILE = "pipc.csv"
PIPC_META_FILE = "pipc.meta.json"
CLASSES_FILE = "cascade_classes.csv"
RULES_FILE = "pipc_rules.csv"
PRIORITY_FILE = "cascade_priority.csv"
ABRUPT_FILE = "abrupt_stop_classes.csv"
COMBINATION_FILE = "atc_combination_rules.csv"
PAPERS_FILE = "evidence_papers.csv"

PIPC_HEADER = ["position", "system", "kind", "drug_a", "adverse_event", "drug_b", "locator"]
CLASSES_HEADER = ["class_id", "pattern", "match", "scope", "basis", "evidence_id", "note"]
RULES_HEADER = [
    "position",
    "index_class",
    "marker_class",
    "unmatchable_role",
    "unmatchable_reason",
    "supporting",
    "note",
]
PRIORITY_HEADER = [
    "position",
    "evidence_id",
    "measure",
    "value",
    "ci_low",
    "ci_high",
    "unit",
    "locator",
    "note",
]
ABRUPT_HEADER = ["pattern", "match", "group", "note"]
PAPERS_HEADER = ["key", "doi", "source_id", "title", "verified_on", "note"]

CLASS_ID = re.compile(r"^[a-z0-9_]{2,40}$")
GROUP_ID = re.compile(r"^[a-z_]{2,40}$")
WHOCC_URL = "https://atcddd.fhi.no/"
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
UNMATCHABLE_ROLES = ("index", "marker", "both")


class RuleBaseError(ValueError):
    """A curated rule-base input is invalid. Names the file, row and column, never a value."""

    def __init__(
        self, code: str, file: str, row: int | None = None, column: str | None = None
    ) -> None:
        self.code = code
        self.file = file
        self.row = row
        self.column = column
        where = file + (f" row {row}" if row is not None else "")
        where += f" column {column}" if column is not None else ""
        super().__init__(f"{where}: {code}")


@dataclass(frozen=True)
class RuleBaseInputs:
    pipc_csv: str
    pipc_meta_json: str
    classes_csv: str
    rules_csv: str
    priority_csv: str
    abrupt_csv: str
    combination_csv: str
    papers_csv: str
    window_months: int = DEFAULT_WINDOW_MONTHS


def _rows(text: str, header: Sequence[str], file: str) -> list[tuple[int, dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != list(header):
        raise RuleBaseError("bad_header", file)
    out: list[tuple[int, dict[str, str]]] = []
    for n, raw in enumerate(reader, start=2):
        if None in raw:  # more cells than columns
            raise RuleBaseError("bad_row", file, n)
        out.append((n, {k: (v or "").strip() for k, v in raw.items()}))
    return out


def _position(value: str) -> int | None:
    if not re.fullmatch(r"[1-9][0-9]{0,2}", value):
        return None
    n = int(value)
    return n if 1 <= n <= PIPC_COUNT else None


# --- PIPC rows -----------------------------------------------------------------------------


@dataclass(frozen=True)
class PipcRow:
    position: int
    system: str
    kind: str
    drug_a: str
    adverse_event: str
    drug_b: str
    locator: str


def parse_pipc(csv_text: str, meta_json: str) -> tuple[PipcRow, ...]:
    """The 65 published rows; their content hash must equal `pipc.meta.json`'s."""
    rows = _rows(csv_text, PIPC_HEADER, PIPC_FILE)
    if len(rows) != PIPC_COUNT:
        raise RuleBaseError("pipc_row_count", PIPC_FILE)
    seen: set[int] = set()
    out: list[PipcRow] = []
    for n, r in rows:
        pos = _position(r["position"])
        if pos is None or pos in seen:
            raise RuleBaseError("pipc_position", PIPC_FILE, n, "position")
        seen.add(pos)
        out.append(
            PipcRow(
                pos,
                r["system"],
                r["kind"],
                r["drug_a"],
                r["adverse_event"],
                r["drug_b"],
                r["locator"],
            )
        )
    try:
        meta = cast(dict[str, Any], json.loads(meta_json))
    except json.JSONDecodeError:
        raise RuleBaseError("pipc_hash_mismatch", PIPC_META_FILE) from None
    raw_rows = [_pipc_raw(csv_text_row) for csv_text_row in csv.DictReader(io.StringIO(csv_text))]
    if content_hash(raw_rows, PIPC_SCHEMA_VERSION) != meta.get("content_sha256"):
        raise RuleBaseError("pipc_hash_mismatch", PIPC_FILE)
    return tuple(sorted(out, key=lambda p: p.position))


def _pipc_raw(row: Mapping[str, str | None]) -> dict[str, Any]:
    """A row as the pipeline hashed it: `position` an integer, the other cells as published."""
    out: dict[str, Any] = {k: (v or "") for k, v in row.items()}
    out["position"] = int(out["position"])
    return out


# --- Papers ----------------------------------------------------------------------------------


def paper_ids(papers_csv: str) -> frozenset[str]:
    """Evidence ids `paper:<source_id>:<key>` of the curated paper list."""
    return frozenset(
        f"paper:{r['source_id']}:{r['key']}"
        for _, r in _rows(papers_csv, PAPERS_HEADER, PAPERS_FILE)
    )


# --- Combination check of patterns -----------------------------------------------------------


def _combination_rules(text: str) -> CombinationRules:
    try:
        return CombinationRules.from_csv_text(text)
    except RulesFileError:
        raise RuleBaseError("bad_combination_rules", COMBINATION_FILE) from None


def is_combination_pattern(prefix: str, rules: CombinationRules) -> bool:
    """A 7-character pattern that is a combination code, or a shorter one inside a group."""
    if is_ingredient_code(prefix):
        return CombinationCheck(rules).is_combination(prefix)
    if any(prefix.startswith(e) for e in rules.exceptions):
        return False
    return any(prefix.startswith(g) for g in rules.groups)


# --- Classes ---------------------------------------------------------------------------------


def parse_classes(
    text: str, papers: frozenset[str], combination: CombinationRules
) -> dict[str, AtcClass]:
    by_class: dict[str, list[Pattern]] = {}
    for n, r in _rows(text, CLASSES_HEADER, CLASSES_FILE):
        cid, prefix = r["class_id"], r["pattern"]
        if not CLASS_ID.fullmatch(cid):
            raise RuleBaseError("bad_class_id", CLASSES_FILE, n, "class_id")
        if not is_prefix_pattern(prefix):
            raise RuleBaseError("bad_pattern", CLASSES_FILE, n, "pattern")
        for col, allowed in (("match", MATCH_KINDS), ("scope", SCOPES), ("basis", BASES)):
            if r[col] not in allowed:
                raise RuleBaseError("bad_value", CLASSES_FILE, n, col)
        scope = cast(Scope, r["scope"])
        evidence = r["evidence_id"] or None
        if scope == "form_extension":
            if r["match"] != "include":
                raise RuleBaseError("bad_value", CLASSES_FILE, n, "match")
            if evidence is None:
                raise RuleBaseError("extension_without_evidence", CLASSES_FILE, n, "evidence_id")
            if evidence not in papers:
                raise RuleBaseError("extension_evidence_unknown", CLASSES_FILE, n, "evidence_id")
        elif evidence is not None:
            raise RuleBaseError("evidence_without_extension", CLASSES_FILE, n, "evidence_id")
        if not r["note"]:
            raise RuleBaseError("missing_note", CLASSES_FILE, n, "note")
        if r["basis"] == "whocc_lookup" and not (
            WHOCC_URL in r["note"] and ISO_DATE.search(r["note"])
        ):
            raise RuleBaseError("whocc_note_incomplete", CLASSES_FILE, n, "note")
        patterns = by_class.setdefault(cid, [])
        if any(p.prefix == prefix for p in patterns):
            raise RuleBaseError("duplicate_pattern", CLASSES_FILE, n, "pattern")
        if is_combination_pattern(prefix, combination):
            raise RuleBaseError("combination_pattern", CLASSES_FILE, n, "pattern")
        patterns.append(
            Pattern(
                prefix=prefix,
                match=cast(MatchKind, r["match"]),
                scope=scope,
                evidence_id=evidence,
                basis=cast(Basis, r["basis"]),
                note=r["note"],
            )
        )
    out: dict[str, AtcClass] = {}
    for cid in sorted(by_class):
        pats = tuple(sorted(by_class[cid], key=lambda p: p.prefix))
        if not any(p.match == "include" for p in pats):
            raise RuleBaseError("no_include_pattern", CLASSES_FILE, None, "class_id")
        out[cid] = AtcClass(cid, pats)
    return out


# --- Rules -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class RuleRow:
    position: int
    index_class: str | None
    marker_class: str | None
    unmatchable: tuple[str, UnmatchableReason] | None
    supporting: tuple[str, ...]
    note: str


def parse_rules(
    text: str, classes: Mapping[str, AtcClass], papers: frozenset[str]
) -> dict[int, RuleRow]:
    out: dict[int, RuleRow] = {}
    for n, r in _rows(text, RULES_HEADER, RULES_FILE):
        pos = _position(r["position"])
        if pos is None:
            raise RuleBaseError("unknown_position", RULES_FILE, n, "position")
        if pos in out:
            raise RuleBaseError("duplicate_position", RULES_FILE, n, "position")
        role, reason = r["unmatchable_role"], r["unmatchable_reason"]
        if role and role not in UNMATCHABLE_ROLES:
            raise RuleBaseError("bad_value", RULES_FILE, n, "unmatchable_role")
        if role and reason not in UNMATCHABLE_REASONS:
            raise RuleBaseError("unmatchable_without_reason", RULES_FILE, n, "unmatchable_reason")
        if not role and reason:
            raise RuleBaseError("bad_value", RULES_FILE, n, "unmatchable_reason")
        names: dict[str, str | None] = {}
        for col, r_role in (("index_class", "index"), ("marker_class", "marker")):
            value = r[col] or None
            off = role in (r_role, "both")
            if off and value is not None:
                raise RuleBaseError("bad_value", RULES_FILE, n, col)
            if not off and value is None:
                raise RuleBaseError("missing_class", RULES_FILE, n, col)
            if value is not None and value not in classes:
                raise RuleBaseError("unknown_class", RULES_FILE, n, col)
            names[col] = value
        marker = names["marker_class"]
        if marker is not None and any(
            p.scope == "form_extension" for p in classes[marker].patterns
        ):
            raise RuleBaseError("extension_in_marker", RULES_FILE, n, "marker_class")
        supporting = tuple(sorted({s.strip() for s in r["supporting"].split(";")} - {""}))
        if any(s not in papers for s in supporting):
            raise RuleBaseError("bad_supporting_id", RULES_FILE, n, "supporting")
        out[pos] = RuleRow(
            position=pos,
            index_class=names["index_class"],
            marker_class=marker,
            unmatchable=(role, cast(UnmatchableReason, reason)) if role else None,
            supporting=supporting,
            note=r["note"],
        )
    if len(out) != PIPC_COUNT:
        raise RuleBaseError("missing_position", RULES_FILE, None, "position")
    return out


# --- Priority --------------------------------------------------------------------------------


def _decimal(value: str) -> Decimal | None:
    if not re.fullmatch(r"-?[0-9]+(\.[0-9]+)?", value):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:  # pragma: no cover - the pattern already excludes this
        return None


def parse_priority(text: str, papers: frozenset[str]) -> dict[int, Priority]:
    out: dict[int, Priority] = {}
    for n, r in _rows(text, PRIORITY_HEADER, PRIORITY_FILE):
        pos = _position(r["position"])
        if pos is None:
            raise RuleBaseError("priority_unknown_position", PRIORITY_FILE, n, "position")
        if pos in out:
            raise RuleBaseError("priority_duplicate", PRIORITY_FILE, n, "position")
        if r["evidence_id"] not in papers:
            raise RuleBaseError("priority_evidence_unknown", PRIORITY_FILE, n, "evidence_id")
        if r["measure"] not in MEASURE_UNITS:
            raise RuleBaseError("bad_value", PRIORITY_FILE, n, "measure")
        measure = cast(Measure, r["measure"])
        if r["unit"] != MEASURE_UNITS[measure]:
            raise RuleBaseError("bad_value", PRIORITY_FILE, n, "unit")
        value, low, high = (_decimal(r[c]) for c in ("value", "ci_low", "ci_high"))
        if value is None or low is None or high is None or not (low <= value <= high):
            raise RuleBaseError("priority_bad_ci", PRIORITY_FILE, n, "value")
        if not r["locator"]:
            raise RuleBaseError("bad_value", PRIORITY_FILE, n, "locator")
        out[pos] = Priority(
            evidence_id=r["evidence_id"],
            measure=measure,
            value=r["value"],
            ci_low=r["ci_low"],
            ci_high=r["ci_high"],
            unit=cast(Unit, r["unit"]),
            locator=r["locator"],
            note=r["note"],
        )
    return out


# --- Abrupt-stop list ------------------------------------------------------------------------


def parse_abrupt_stop(
    text: str, combination: CombinationRules
) -> tuple[AtcClass, tuple[AbruptGroup, ...]]:
    patterns: list[Pattern] = []
    groups: list[AbruptGroup] = []
    for n, r in _rows(text, ABRUPT_HEADER, ABRUPT_FILE):
        prefix = r["pattern"]
        if not is_prefix_pattern(prefix):
            raise RuleBaseError("bad_pattern", ABRUPT_FILE, n, "pattern")
        if r["match"] not in MATCH_KINDS:
            raise RuleBaseError("bad_value", ABRUPT_FILE, n, "match")
        if not GROUP_ID.fullmatch(r["group"]):
            raise RuleBaseError("bad_value", ABRUPT_FILE, n, "group")
        if not r["note"]:
            raise RuleBaseError("missing_note", ABRUPT_FILE, n, "note")
        if any(p.prefix == prefix for p in patterns):
            raise RuleBaseError("duplicate_pattern", ABRUPT_FILE, n, "pattern")
        if is_combination_pattern(prefix, combination):
            raise RuleBaseError("combination_pattern", ABRUPT_FILE, n, "pattern")
        patterns.append(Pattern(prefix, r["match"], note=r["note"]))
        groups.append(AbruptGroup(prefix, r["group"]))
    if not any(p.match == "include" for p in patterns):
        raise RuleBaseError("no_include_pattern", ABRUPT_FILE)
    included = {g.group for g, p in zip(groups, patterns, strict=True) if p.match == "include"}
    if any(g not in included for g in REQUIRED_ABRUPT_GROUPS):
        raise RuleBaseError("abrupt_stop_missing_group", ABRUPT_FILE, None, "group")
    cls = AtcClass("abrupt_stop", tuple(sorted(patterns, key=lambda p: p.prefix)))
    return cls, tuple(sorted(groups, key=lambda g: g.prefix))


# --- Build and version -----------------------------------------------------------------------


def build_rule_base(inputs: RuleBaseInputs) -> RuleBase:
    """Validate every input and build the rule base. Raises `RuleBaseError` on the first defect."""
    lo, hi = WINDOW_RANGE
    if not (lo <= inputs.window_months <= hi):
        raise RuleBaseError("window_out_of_range", "window_months")
    pipc = parse_pipc(inputs.pipc_csv, inputs.pipc_meta_json)
    papers = paper_ids(inputs.papers_csv)
    combination = _combination_rules(inputs.combination_csv)
    classes = parse_classes(inputs.classes_csv, papers, combination)
    rule_rows = parse_rules(inputs.rules_csv, classes, papers)
    priority = parse_priority(inputs.priority_csv, papers)
    abrupt, abrupt_groups = parse_abrupt_stop(inputs.abrupt_csv, combination)
    used = {c for r in rule_rows.values() for c in (r.index_class, r.marker_class) if c}
    if set(classes) - used:
        raise RuleBaseError("unused_class", CLASSES_FILE, None, "class_id")
    rules = tuple(
        Rule(
            position=p.position,
            system=p.system,
            kind=p.kind,
            drug_a=p.drug_a,
            adverse_event=p.adverse_event,
            drug_b=p.drug_b,
            locator=p.locator,
            index_class=rule_rows[p.position].index_class,
            marker_class=rule_rows[p.position].marker_class,
            unmatchable=cast(Any, rule_rows[p.position].unmatchable),
            supporting=rule_rows[p.position].supporting,
            priority=priority.get(p.position),
            note=rule_rows[p.position].note,
        )
        for p in pipc
    )
    draft = RuleBase(
        window_months=inputs.window_months,
        rules=rules,
        classes=classes,
        abrupt_stop=abrupt,
        abrupt_groups=abrupt_groups,
        version="",
    )
    return RuleBase(
        window_months=draft.window_months,
        rules=draft.rules,
        classes=draft.classes,
        abrupt_stop=draft.abrupt_stop,
        abrupt_groups=draft.abrupt_groups,
        version=version(draft),
    )


def _pattern_json(p: Pattern) -> dict[str, Any]:
    return {
        "prefix": p.prefix,
        "match": p.match,
        "scope": p.scope,
        "evidence_id": p.evidence_id,
        "basis": p.basis,
        "note": p.note,
    }


def rule_base_content(rb: RuleBase) -> dict[str, Any]:
    """Canonical, JSON-ready content of a rule base (everything except its version)."""
    return {
        "engine_version": rb.engine_version,
        "window_months": rb.window_months,
        "source_paper_id": rb.source_paper_id,
        "window_evidence_id": rb.window_evidence_id,
        "rules": [
            {
                "position": r.position,
                "system": r.system,
                "kind": r.kind,
                "drug_a": r.drug_a,
                "adverse_event": r.adverse_event,
                "drug_b": r.drug_b,
                "locator": r.locator,
                "index_class": r.index_class,
                "marker_class": r.marker_class,
                "unmatchable": list(r.unmatchable) if r.unmatchable else None,
                "supporting": list(r.supporting),
                "priority": None
                if r.priority is None
                else {
                    "evidence_id": r.priority.evidence_id,
                    "measure": r.priority.measure,
                    "value": r.priority.value,
                    "ci_low": r.priority.ci_low,
                    "ci_high": r.priority.ci_high,
                    "unit": r.priority.unit,
                    "locator": r.priority.locator,
                    "note": r.priority.note,
                },
                "note": r.note,
            }
            for r in sorted(rb.rules, key=lambda r: r.position)
        ],
        "classes": {
            cid: [_pattern_json(p) for p in rb.classes[cid].patterns] for cid in sorted(rb.classes)
        },
        "abrupt_stop": [
            {"prefix": p.prefix, "match": p.match, "group": g.group, "note": p.note}
            for p, g in zip(rb.abrupt_stop.patterns, rb.abrupt_groups, strict=True)
        ],
    }


def version(rb: RuleBase) -> str:
    """SHA-256 of the canonical content: same content, same version; any change, a new one."""
    return hashlib.sha256(canonical_line(rule_base_content(rb)).encode("utf-8")).hexdigest()


def ids_used(rb: RuleBase) -> Iterable[str]:
    """Every evidence id the rule base cites besides its rule records."""
    yield rb.source_paper_id
    yield rb.window_evidence_id
    for r in rb.rules:
        yield from r.supporting
        if r.priority is not None:
            yield r.priority.evidence_id
    for c in rb.classes.values():
        yield from sorted(c.extension_ids)
