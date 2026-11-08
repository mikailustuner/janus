"""Closed set of light-face codes and their English canonical sentences (design §7, Req 4.5; P3).

The API returns codes; the screens show the `Light` namespace in five languages. These sentences
are the reference wording, scanned by the medical-language guard. Rule 7 of medical-safety.md:
every output is a candidate worth investigating, not a treatment. The only sentence that uses the
word "treatment" is that negation.
"""

from __future__ import annotations

from typing import Final

from janus.memory import messages as memory_messages

DISCLAIMER: Final = memory_messages.DISCLAIMER
ATTRIBUTION_ONSIDES: Final = (
    "Side effects: OnSIDES v3.1.1 (Tatonetti lab; Tanaka et al., Med 2025, "
    "doi:10.1016/j.medj.2025.100642), CC BY 4.0."
)
ATTRIBUTION_FAERS: Final = "Reports: FDA AEMS (formerly FAERS), CC0 1.0. Not an FDA endorsement."
EXPORT_LICENCE: Final = "CC BY 4.0"

SENTENCES: Final[dict[str, str]] = {
    "candidate_not_treatment": "Candidate worth investigating — not a treatment.",
    "researcher_only": "For researchers. These candidates are not shown in the patient pages.",
    "label_effect_meaning": (
        "The labels list this as an unwanted effect. An unwanted effect in one condition can point "
        "to a possible use in another; that has to be tested in studies before it means anything."
    ),
    "label_extraction_limits": (
        "Side effects come from OnSIDES, which extracts them from drug labels with a language "
        "model; some are missed and some are wrong."
    ),
    "inverse_meaning": (
        "The condition is reported less often than expected in the FAERS reports that name this "
        "medicine. This is not evidence that the medicine protects against it."
    ),
    "inverse_reporting_bias": (
        "Reporting bias: an event that is already known for a medicine is reported more often "
        "(notoriety bias), and a condition that is the reason a medicine is given is often "
        "recorded as the indication rather than as an event (indication bias). Both can create or "
        "hide a lower-than-expected count."
    ),
    "patient_reported_meaning": (
        "Donated reports of an improvement, counted only in groups of 20 or more, with noise "
        "added. The reports are not checked."
    ),
    "patient_layer_unavailable": "Donated reports cannot be counted right now.",
    "mechanism_source_not_connected": "No source for a possible mechanism is connected yet.",
    "not_checked_against_indications": (
        "Janus does not check whether a candidate is already an approved use of the medicine."
    ),
    "review_pending": (
        "The conditions, the side-effect mapping and the validation cases are AI-reviewed and "
        "pending expert review."
    ),
    "experimental": (
        "Experimental: in the retrospective check, no known repurposing ranked in the top 10 of "
        "its condition among more than 10 candidates."
    ),
    "prototype": (
        "Research prototype: some known repurposings were found again in the retrospective check. "
        "That is not proof that the method works for new candidates."
    ),
    "tied_ranks": "Equal positions are shown as a range of ranks.",
    "faers_includes_later_use": (
        "The FAERS reports of this window were sent after the later use was known; this number "
        "does not exclude it."
    ),
    "validation_not_blind": (
        "The side-effect mapping was written knowing these cases, so this check is not blind."
    ),
    "removed_by_integrity": "Sources that were retracted are not used.",
    "export_aggregated": (
        "Aggregated counts only. Donated reports are pseudonymous data and appear only as noisy "
        "counts of groups of 20 or more."
    ),
}

CODES: Final = frozenset(SENTENCES)
CARD_CODES: Final = ("candidate_not_treatment", "mechanism_source_not_connected")
LABEL_CODES: Final = ("label_effect_meaning", "label_extraction_limits")
INVERSE_CODES: Final = (
    "inverse_meaning",
    "inverse_reporting_bias",
    "screening_statistic",
    "spontaneous_reporting",
    "not_incidence",
)
PATIENT_CODES: Final = ("patient_reported_meaning",)
PAGE_CODES: Final = (
    "researcher_only",
    "not_checked_against_indications",
    "review_pending",
    "tied_ranks",
)
# Evidence behind the warnings of an inverse signal (papers in data/evidence_papers.csv).
INVERSE_WARNING_EVIDENCE: Final = (
    "paper:pariente_2007:00002018-200730100-00007",
    "paper:uesawa_2026:s40264-026-01726-x",
    "paper:faillie_2019:j.therap.2019.01.006",
)
