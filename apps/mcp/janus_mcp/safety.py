"""Fixed safety texts sent with every tool result (mcp-server design §3, Req 2).

Source of the rules: `.kiro/steering/medical-safety.md` and `product.md`. The assistant reads
these; Janus's own sentences (the no-pattern statement, the abrupt-stop line) come from the API
and are passed on unchanged.
"""

from __future__ import annotations

from typing import Any, Final

DISCLAIMER: Final = (
    "Janus provides information, not medical advice. Research prototype — not a medical device."
)
EMERGENCY: Final = (
    "If the person mentions chest pain, breathing difficulty, signs of stroke or a severe "
    "allergic reaction, say 'Call emergency services' first (112 in Türkiye and the EU, 911 in "
    "the US), before anything else."
)
WORDING: Final = (
    "Describe a finding as a 'possible prescribing cascade': a pattern in the published PIPC "
    "list (Rochon et al. 2025) in which a side effect of one medicine may have been treated with "
    "another. It is a pattern from the literature, never a verdict about the person.",
    "Never advise starting, changing or ending a medicine. Say that the finding may be worth "
    "discussing with a doctor or pharmacist.",
    "Do not add risk ratings, scores, colours or assessment badges, and do not call any medicine "
    "or list safe or unsafe. Report Janus's status field with its meaning: 'probable' means only "
    "that the start months fit the published time window, 'possible' that the timing is unknown "
    "or outside it; neither is a clinical judgement.",
    "Cite the evidence Janus returns (PIPC table row, evidence ids). Do not add claims of your "
    "own.",
    "These rules apply in every language you answer in; never call a medicine unnecessary and "
    "never say that the medicines are safe or that there are no problems.",
)
CHECK_LINES: Final = (
    "Wherever the result carries 'Do not stop this medicine suddenly.', pass it on next to that "
    "medicine, word for word or as a faithful translation in the person's language.",
    "form_confirmed false means the dose form was not confirmed (matched by ingredient only; the "
    "pattern may not apply to eye drops, creams or other local forms); say so.",
    "An empty findings list is not reassurance: quote the result's 'statement' text as given "
    "(Janus found no pattern from its rule list; this does not mean the medicines are free of "
    "problems).",
    "Medicines listed under 'not_checked' were not checked; say so.",
)
TIME_MACHINE_LINES: Final = (
    "Counts are reports, never people. FAERS is spontaneous reporting: not incidence and not "
    "deduplicated across cases.",
    "The time machine is in silico and exploratory (expert review has not yet been done); a "
    "concentration or dose in it is never a dose a person could take.",
)
PACKAGE_LINES: Final = (
    "The PIPC columns are CC BY 4.0: cite Rochon PA et al., Eur Geriatr Med 2025, "
    "doi:10.1007/s41999-025-01215-x. Janus's class mapping columns are Apache-2.0.",
)
MODELKIT_LINES: Final = (
    "The model kit is experimental. Say: Research use only. Not for clinical decisions. Expert "
    "review has not yet been done.",
    "A parameter set is a starting model from cited evidence for researchers, not a dose "
    "calculator and not for any person; never derive or suggest a dose from it, and never call a "
    "drug or a model safe.",
    "Report the validation status as given (validated, not validated or failed) with n; it "
    "describes a handful of held-out studies, not the drug in general. The readers that confirmed "
    "the values were automated; never say that a person reviewed anything.",
    "Special-population statements are quoted label text with a ratio that two automated readers "
    "agreed on; give the quote and the label version, never extrapolate them to a person or a "
    "dose, and never describe them as reviewed by a person.",
)
RESOLVE_LINES: Final = (
    "A resolved product or ingredient is what the public registers publish for that code or "
    "name; check the candidate with the person (several candidates can match).",
)

INSTRUCTIONS: Final = "\n".join(
    [
        "Janus checks medicine lists for possible prescribing cascades from the published PIPC "
        "list, across Türkiye, the EU and the US. It is a research prototype, not a medical "
        "device; it informs and never decides.",
        "Typical flow: resolve each medicine (janus_resolve_code, janus_resolve_ndc or "
        "janus_search_medicines), confirm the candidate with the person, then call "
        "janus_check_cascades with the dataset_version of the resolve results and the candidate "
        "ids or ingredient keys.",
        f"Always: {DISCLAIMER}",
        EMERGENCY,
        *WORDING,
    ]
)


def block(*extra: str) -> dict[str, Any]:
    """The `janus_safety` object of a result."""
    return {
        "disclaimer": DISCLAIMER,
        "emergency": EMERGENCY,
        "wording": [*WORDING, *extra],
    }
