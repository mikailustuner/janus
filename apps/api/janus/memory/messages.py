"""Closed set of codes of Collective Memory and their English canonical sentences (design §7).

The API returns codes, numbers and these English sentences; the client renders the words in the
user's language (`Memory` namespace of the message files, task 12). Every sentence follows
`medical-safety.md`: it describes reports, never people; it does not say or imply causation,
risk, probability, safety or normality; it never advises starting, stopping or changing a medicine.
The one exception to the causal-word rule is `SCREENING_SENTENCE` (owner decision 2026-11-08), which
must stay exactly as written (a test lets only this exact string pass).
"""

from __future__ import annotations

from typing import Final

DISCLAIMER: Final = (
    "Janus provides information, not medical advice. Research prototype — not a medical device."
)
ATTRIBUTION: Final = "Source: FDA AEMS (formerly FAERS), snapshot {date}. Not an FDA endorsement."
MEDDRA_NOTICE: Final = "MedDRA® is a registered trademark of ICH"

# The single allow-listed exception to the causal-word rule (statistics review Q6).
SCREENING_SENTENCE: Final = (
    "This is a screening statistic. Many medicine–event pairs are examined at once and most of "
    "them meet these criteria, so meeting them is common and is not evidence that the medicine "
    "causes the event."
)

SENTENCES: Final[dict[str, str]] = {
    # --- notices ---
    "spontaneous_reporting": "Reports are sent voluntarily and are not verified.",
    "not_incidence": "The counts do not show how often an event happens.",
    "deduplicated_by_case_version_only": (
        "Only repeated versions of the same case are merged, so one event can still appear in "
        "more than one case."
    ),
    "screening_statistic": SCREENING_SENTENCE,
    "window_includes_follow_ups": (
        "Counts cover reports received or updated in the four quarters {first}–{last}, including "
        "follow-up versions of cases first received earlier."
    ),
    "denominator_mapped_reports": (
        "Counts use only reports that name at least one medicine Janus recognises ({share} of the "
        "reports in this window). Some spellings are not recognised, so a pattern can be missed. "
        "Figures for all reports are shown beside these."
    ),
    "region_is_report_origin": (
        "A report's region is the country where the event is said to have happened or, when that "
        "is missing, where the reporter is. It does not tell where the medicine was taken or "
        "where it was bought."
    ),
    "eu_member_states_not_separable": (
        "EU means the 27 member states pooled; FAERS cannot tell them apart."
    ),
    "regions_not_comparable": (
        "Regions are not comparable as rates, because reporting habits differ. A different label "
        "in two regions can come from different numbers of reports, not from a different pattern. "
        "Each region is compared only with the other reports from the same region."
    ),
    "absence_is_not_reassurance": (
        "No reports, or a pattern that is not clear, does not mean there is no association or "
        "that your medicines are free of problems."
    ),
    "counts_built_against_other_dataset": (
        "These counts were built with a different version of the medicine name list than the one "
        "now in use."
    ),
    "source_may_be_outdated": "The FAERS data is older than expected for its update schedule.",
    "reported_together_only": (
        "These counts only show that the medicines appear together in reports."
    ),
    # --- results ---
    "no_reports": "No reports were found in this window.",
    "insufficient_data": "Too few reports to show a pattern (fewer than 3).",
    "not_disproportionate": (
        "The event does not appear in a clearly larger share of the reports that name this "
        "medicine. This does not mean there is no association."
    ),
    "weak": "Few reports; treat as a weak pattern.",
    "weak_pattern": "Few reports; treat as a weak pattern.",
    "disproportionate": (
        "The event appears in a larger share of the reports that name this medicine than in the "
        "other reports that name a recognised medicine."
    ),
    "estimate_uses_continuity_correction": (
        "The size of this ratio depends on a small adjustment made because a count is zero."
    ),
    "interval_approximate": (
        "The range is approximate and is less reliable when few reports are involved."
    ),
    "denominator_sensitive": "The result changes when all reports are used as the comparison.",
    "combination_caveat": (
        "These counts are for reports that name all of these medicines. The comparison group is "
        "every other report, including reports that name only some of them, so a pattern here may "
        "come from just one of the medicines. It does not show that taking them together has an "
        "effect."
    ),
    "set_counts_are_lower_bounds": (
        "Counts for a set of medicines are lower bounds: a report counts only if every medicine "
        "in it was recognised."
    ),
    "below_display_threshold": (
        "Too few reports name all of these medicines, so smaller groups are shown."
    ),
    "pairwise_shown": "Showing pairs of these medicines.",
    "single_shown": "Showing each medicine on its own.",
    "event_not_reported_in_window": "This event was not reported in this window.",
    "benefit_not_in_faers": (
        "FAERS has no report type for improvements, so only Janus donated reports can show this."
    ),
    # --- user layers ---
    "hidden": "Not shown.",
    "hidden_under_20_noise_added": "Hidden under 20, noise added.",
    "layer_unavailable": "This layer is not available right now.",
    "not_available": "Not available yet.",
    "memory_unavailable": "Collective Memory data is not available right now.",
    # --- safety lines (owner decision 2026-11-08; experience Requirement 7) ---
    "crisis_support": (
        "If thoughts of self-harm come up, call your local emergency number (112 in Türkiye and "
        "the EU, 911 in the US) or a crisis line in your region."
    ),
    "urgent_care_skin": (
        "Get urgent medical care for a rash that is severe, spreading or blistering, or that comes "
        "with fever or mouth sores. If your face or lips swell, you find it hard to breathe or you "
        "feel very unwell, call emergency services (112 in Türkiye and the EU, 911 in the US)."
    ),
    "urgent_care_heart": (
        "Call emergency services (112 in Türkiye and the EU, 911 in the US) for chest pain, "
        "trouble breathing or fainting. A racing or irregular heartbeat also needs urgent medical "
        "care."
    ),
    # --- notices added by the safety review ---
    "tr_reports_small_self_selected": (
        "Reports from Türkiye are few and are sent by choice. They do not show how medicines are "
        "used in Türkiye."
    ),
}

CODES: Final[tuple[str, ...]] = tuple(SENTENCES)

# Notices on every FAERS response (Req 1.4, 1.8, 7.5).
BASE_NOTICES: Final[tuple[str, ...]] = (
    "spontaneous_reporting",
    "not_incidence",
    "deduplicated_by_case_version_only",
    "window_includes_follow_ups",
    "denominator_mapped_reports",
    "screening_statistic",
)
