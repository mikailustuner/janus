"""The template catalogue of the note and the outcome page (doctor-loop design §5.2). Pure.

The code fixes each template's id, kind, evidence roles and typed parameters; the glossary file
`glossary/sentences.csv` supplies the reviewed wording in five languages and must agree with this
catalogue row for row. Claim templates carry evidence roles and contain no digit; fixed texts
(headings, labels, the disclaimer, the abrupt-stop line, safety lines, limits) carry none.
`shared` names the message-file key whose five values a shared row must equal (P23).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

Kind = Literal["claim", "fixed", "heading", "label", "option"]
ParamType = Literal[
    "int", "ratio", "percent", "decimal_text", "month", "date", "quarter", "term", "code", "version"
]
Role = Literal[
    "rule",
    "pipc",
    "window",
    "priority",
    "supporting",
    "extension",
    "faers",
    "integrity_root",
    "finding",
]
KINDS: Final = ("claim", "fixed", "heading", "label", "option")
PARAM_TYPES: Final = (
    "int", "ratio", "percent", "decimal_text", "month", "date", "quarter", "term", "code",
    "version",
)  # fmt: skip
ROLES: Final = (
    "rule", "pipc", "window", "priority", "supporting", "extension", "faers", "integrity_root",
    "finding",
)  # fmt: skip


@dataclass(frozen=True)
class Spec:
    id: str
    kind: Kind
    evidence: tuple[Role, ...] = ()
    params: tuple[tuple[str, ParamType], ...] = ()
    shared: str | None = None


def _s(
    id_: str,
    kind: Kind,
    evidence: tuple[Role, ...] = (),
    params: str = "",
    shared: str | None = None,
) -> Spec:
    ps: list[tuple[str, ParamType]] = []
    for part in params.split(";") if params else []:
        name, _, typ = part.partition(":")
        ps.append((name, typ))  # pyright: ignore[reportArgumentType]
    return Spec(id_, kind, evidence, tuple(ps), shared)


NOT_CHECKED_REASONS: Final = (
    "homeopathic_product",
    "ambiguous",
    "no_ingredient_key",
    "possible_unsplit_combination",
    "no_ingredient_atc",
    "no_ingredient_atc_for_route",
)
SAFETY_LINES: Final = (
    "crisis_support",
    "urgent_care_skin",
    "urgent_care_heart",
    "urgent_care_gi",
    "urgent_care_seizure",
    "urgent_care_breathing",
)
USER_REGIONS: Final = ("US", "TR", "EU", "OTHER", "UNKNOWN")
STAT_REGIONS: Final = ("ALL", "TR", "EU", "US")
ASSESSMENT_CODES: Final = ("disproportionate", "not_disproportionate", "weak")
LIMIT_CODES: Final = ("spontaneous_reporting", "not_incidence", "deduplicated_by_case_version_only")

_FINDING = "drug_a:term;event:term;drug_b:term;index:term;marker:term;row:int"

SPECS: Final[tuple[Spec, ...]] = (
    # header
    _s("header.title", "heading"),
    _s("header.prepared", "fixed", params="month:month"),
    _s("header.purpose", "fixed"),
    _s("disclaimer", "fixed", shared="Disclaimer.text"),
    _s("section.empty", "fixed"),
    # safety (design §4.4: before the findings)
    _s("safety.heading", "heading"),
    _s("safety.emergency_first", "fixed", params="emergency:term"),
    *(
        _s(
            f"safety.{line}",
            "fixed",
            params="crisis:term" if line == "crisis_support" else "emergency:term",
            shared=f"Memory.codes.{line}",
        )
        for line in SAFETY_LINES
    ),
    *(_s(f"emergency.{r}", "label", shared=f"Memory.emergency.{r}") for r in USER_REGIONS),
    *(_s(f"crisis.{r}", "label", shared=f"Memory.crisis.{r}") for r in USER_REGIONS),
    # medicines
    _s("medicines.heading", "heading"),
    _s("medicine.started", "label", params="month:month"),
    _s("medicine.start_unknown", "label"),
    _s("medicine.codes", "label", params="codes:code"),
    _s("medicine.product_name", "label"),
    _s("abrupt_stop", "fixed"),
    _s("name.not_translated", "label"),
    _s("name.not_reviewed", "label"),
    _s("name.combination_code", "label"),
    *(_s(f"not_checked.{r}", "label") for r in NOT_CHECKED_REASONS),
    # findings
    _s("findings.heading", "heading"),
    _s("findings_form_unconfirmed.heading", "heading"),
    _s("findings_form_unconfirmed.explanation", "fixed"),
    _s("finding.cascade", "claim", ("rule", "pipc"), _FINDING),
    _s(
        "finding.timing.within_window",
        "claim",
        ("rule", "window"),
        "index:term;marker:term;months:int;window:int",
    ),
    _s(
        "finding.timing.after_window",
        "claim",
        ("rule", "window"),
        "index:term;marker:term;months:int;window:int",
    ),
    _s("finding.timing.same_month", "claim", ("rule",)),
    _s("finding.timing.date_unknown", "claim", ("rule",)),
    _s(
        "finding.priority.incidence",
        "claim",
        ("priority",),
        "value:percent;low:percent;high:percent",
    ),
    _s(
        "finding.priority.adjusted_sequence_ratio",
        "claim",
        ("priority",),
        "value:decimal_text;low:decimal_text;high:decimal_text",
    ),
    _s("finding.row49", "claim", ("rule", "pipc"), "row:int;supplements:term"),
    _s("label.row49_supplements", "label"),
    _s("finding.supporting", "claim", ("supporting",)),
    _s("finding.form_extension", "claim", ("extension",)),
    _s("finding.notice.corrected", "claim", ("integrity_root",)),
    _s("finding.notice.expression_of_concern", "claim", ("integrity_root",)),
    _s("finding.review", "fixed"),
    # chains
    _s("chains.heading", "heading"),
    _s("chain.sequence", "claim", ("finding",), "sequence:term"),
    # statistics
    _s("statistics.heading", "heading"),
    _s(
        "stat.reports_ratio",
        "claim",
        ("faers",),
        "reports:int;ingredient:term;event:term;region:term;ror:ratio;low:ratio;high:ratio",
    ),
    _s("stat.coverage.no_reports", "claim", ("faers",), "ingredient:term;event:term;region:term"),
    _s("stat.coverage.insufficient", "claim", ("faers",), "ingredient:term;event:term;region:term"),
    *(
        _s(f"stat.assessment.{c}", "claim", ("faers",), shared=f"Memory.codes.{c}")
        for c in ASSESSMENT_CODES
    ),
    _s("stat.pts", "label", params="pts:term"),
    _s("stat.interval_approximate", "fixed", shared="Memory.codes.interval_approximate"),
    _s(
        "stat.continuity_correction",
        "fixed",
        shared="Memory.codes.estimate_uses_continuity_correction",
    ),
    *(_s(f"stat.limit.{c}", "fixed", shared=f"Memory.codes.{c}") for c in LIMIT_CODES),
    _s("stat.screening", "fixed", shared="Memory.screening"),
    _s("stat.absence", "fixed"),
    _s(
        "stat.window",
        "fixed",
        params="first:quarter;last:quarter",
        shared="Memory.codes.window_includes_follow_ups",
    ),
    _s("stat.denominator", "fixed", params="share:percent"),
    _s("stat.attribution", "fixed", params="date:date", shared="Memory.attribution"),
    _s("stat.source_may_be_outdated", "fixed", shared="Memory.codes.source_may_be_outdated"),
    _s("stat.meddra_long", "fixed"),
    _s("statistics_unavailable", "fixed"),
    *(_s(f"region.{r}", "label") for r in STAT_REGIONS),
    # scope
    _s("scope.heading", "heading"),
    _s("scope.checked", "claim", ("pipc",), "checked:int;total:int"),
    _s("scope.not_checked_rule", "claim", ("pipc",), "row:int;drug_a:term;event:term;drug_b:term"),
    _s("scope.no_pattern", "claim", ("pipc",)),
    _s("scope.rule_base_unavailable", "fixed"),
    # integrity
    _s("integrity.heading", "heading"),
    _s("integrity.sources", "claim", ("integrity_root",), "total:int;by_doi:int"),
    _s(
        "integrity.by_status",
        "claim",
        ("integrity_root",),
        "ok:int;corrected:int;expression_of_concern:int;unknown:int",
    ),
    _s("integrity.checks_between", "claim", ("integrity_root",), "first:date;last:date"),
    _s("integrity.stale_source", "claim", ("integrity_root",), "source:term;date:date"),
    _s("integrity.no_retracted", "claim", ("integrity_root",)),
    # about
    _s("about.heading", "heading"),
    _s(
        "about.versions",
        "fixed",
        params="rule_base:version;dataset:version;integrity:version;counts:version;glossary:version",
    ),
    _s("about.pipc", "fixed"),
    _s("about.faers", "fixed"),
    _s("about.glossary_status", "fixed"),
    # outcome loop section (notes from POST /notes/token)
    _s("outcome_loop.heading", "heading"),
    _s("outcome_loop.how", "fixed"),
    _s("outcome_loop.coverage", "fixed", params="covered:int;total:int"),
    # outcome page
    _s("outcome.heading", "heading"),
    _s("outcome.intro", "fixed"),
    _s("outcome.stored_fields", "fixed"),
    _s("outcome.limits", "fixed"),
    _s("outcome.question.assessment", "label"),
    _s("outcome.option.confirmed", "option"),
    _s("outcome.option.not_a_cascade", "option"),
    _s("outcome.question.action", "label"),
    _s("outcome.option.dose_changed", "option"),
    _s("outcome.option.medicine_changed", "option"),
    _s("outcome.option.stopped", "option"),
    _s("outcome.option.no_change", "option"),
    _s("outcome.action_on.index", "option", params="name:term"),
    _s("outcome.action_on.marker", "option", params="name:term"),
)

CATALOGUE: Final[dict[str, Spec]] = {s.id: s for s in SPECS}
assert len(CATALOGUE) == len(SPECS), "duplicate template id"  # noqa: S101 (import-time invariant)
