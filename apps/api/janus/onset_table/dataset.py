"""The open FAERS onset dataset: metadata, caveats, version and CSV (faers-onset-table design §5).
Pure."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

from janus.onset_table.table import (
    BOOTSTRAP,
    CLUSTER_SHARE_MAX,
    COUNT_ONLY_BELOW,
    SEED,
    SENSITIVITY_MIN,
    SHAPE_MIN_DISTINCT,
    SHAPE_ZERO_SHARE_MAX,
    SMALL_SAMPLE_BELOW,
    counts_by_status,
)

RULE_VERSION: Final = "faers-onset-pipc-1"
DATASET: Final = "janus-faers-onset-pipc"
LICENSE: Final = "CC BY 4.0"
LICENSE_URL: Final = "https://creativecommons.org/licenses/by/4.0/"
ATTRIBUTION: Final = (
    "Janus FAERS time-to-onset table for the PIPC prescribing cascades, CC BY 4.0. PIPC columns: "
    "Rochon PA et al., Potentially inappropriate prescribing cascades (PIPC) list, Eur Geriatr "
    "Med 2025;16(5):1573-1584, doi:10.1007/s41999-025-01215-x, Table 1 (CC BY 4.0). Counts and "
    "intervals derived from the FDA Adverse Event Reporting System quarterly data files (CC0 "
    "1.0); not an FDA endorsement."
)
MEDDRA_NOTICE: Final = (
    "Event terms are MedDRA Preferred Terms as published in FAERS. MedDRA® the Medical "
    "Dictionary for Regulatory Activities terminology is the international medical terminology "
    "developed under the auspices of ICH. MedDRA® trademark is registered by IFPMA on behalf of "
    "ICH."
)
DISCLAIMER: Final = (
    "Janus provides information, not medical advice. Research prototype — not a medical device."
)
REVIEW_STATUS: Final = (
    "Methods and class and event mappings passed automated statistical and pharmacological "
    "review passes (findings applied or listed as open items in .kiro/specs/faers-onset-table/). "
    "Expert review has not yet been done."
)
CAVEATS: Final[dict[str, str]] = {
    "descriptive": (
        "Descriptive only. A time to onset here is the interval between a therapy start date "
        "and the event date that a reporter wrote down; it is not a causal estimate, it does "
        "not show that the medicine caused the event and it is not onset measured in people."
    ),
    "not_incidence": (
        "FAERS is spontaneous reporting: not incidence and no denominator of exposed patients. "
        "Case versions are collapsed to the latest one, but duplicate cases sent by different "
        "reporters are not merged, so one patient can appear under several case ids. Counts are "
        "reports, never people."
    ),
    "receipt_window": (
        "The window is four quarters of reports by date received; event dates can be years "
        "earlier (see event_year_min and event_year_max). Old or rarely used medicines can have "
        "few or no reports in the window."
    ),
    "selection": (
        "Only reports with both a complete therapy start date and a complete event date carry an "
        "interval. That subset may not be representative of all reports (date completeness may "
        "differ by reporter type and by seriousness), and long-standing therapy is less often "
        "dated. candidates_without_interval_by_reason shows why the others have no interval."
    ),
    "event_date_report_level": (
        "FAERS gives one event date per report, not per event term. In reports with several "
        "terms (multi_event_reports) the date may belong to another event than this row's."
    ),
    "zero_day": (
        "A same-day interval (0 days) often means the reporter gave one date for both fields "
        "rather than a genuine same-day onset; heaping at zero pulls the median down. The "
        "zero-day count is published with every row. When more than half the intervals are 0 "
        "days (median_reflects_zero_heaping), the median and both intervals are 0 and show "
        "same-day heaping, not timing."
    ),
    "day_one": (
        "Dates on the 1st of a month are far more common in FAERS than chance (a month- or "
        "year-only date filled in with day 01), and a 1 January date can be off by most of a "
        "year. Each row gives day_one_reports and jan_one_reports and, as a sensitivity check, "
        "median_days_without_day_one; that check also drops genuine day-01 dates, so it is not "
        "a correction."
    ),
    "clusters": (
        "Several distinct cases sometimes share the exact same therapy start and event dates: "
        "possible duplicate patients, a case series, or a literature or litigation batch. Each "
        "row gives largest_date_cluster and reports_in_clusters_ge3; when one identical date "
        f"pair holds more than {CLUSTER_SHARE_MAX:.0%} of a row's reports the row publishes "
        "counts only (status cluster_dominated)."
    ),
    "shortest_interval": (
        "Per report the interval is taken from the most recently started class-member suspect "
        "line; after a switch within the class this is shorter than the time since the class "
        "was first started (median_days_earliest_class_start gives the other reading)."
    ),
    "weibull": (
        "The Weibull shape class reflects reporting artefacts (zero-day and day-01 heaping, the "
        "receipt window that cuts off late onsets) as much as timing; it is not a mechanism. It "
        f"is published only for rows with at least {SMALL_SAMPLE_BELOW} reports, at most "
        f"{SHAPE_ZERO_SHARE_MAX:.0%} same-day intervals and at least {SHAPE_MIN_DISTINCT} "
        "distinct intervals."
    ),
    "median_interval": (
        "Use the exact order-statistic interval of the median (median_exact_ci_*). The "
        "percentile bootstrap interval is kept for comparison with the time machine and can "
        "understate the uncertainty on tied or small data (median_ci_degenerate marks a "
        "zero-width one)."
    ),
    "shared_rows": (
        "PIPC rows that share drug A's class and the event key (they differ in drug B) have the "
        "same numbers; shared_with_positions names them."
    ),
    "class_membership": (
        "Drug A's class is matched on the ingredient-level ATC codes of each ingredient key with "
        "the cascade engine's matcher. This build uses the FAERS route field: suspect lines "
        "given by a local route (skin, eye, ear, nose, airways, vagina or uterus, mouth, joints, "
        "bladder) are not counted, except eye drops for row 3, rectal laxatives for row 47, "
        "nasal and inhaled forms of opioids, antipsychotics, benzodiazepines and dopaminergic "
        "medicines, and joint or lesion injections of systemic corticosteroids; "
        "lines without a route count. Exposure through the placenta or breast milk is never "
        "counted. Some keys are left out per class (excluded_class_keys, with reasons in "
        "data/onset_key_exclusions.csv); members_with_reports shows which keys drive a row."
    ),
    "small_sample": (
        f"Rows with fewer than {COUNT_ONLY_BELOW} reports with an interval publish counts only; "
        f"rows with {COUNT_ONLY_BELOW}-{SMALL_SAMPLE_BELOW - 1} are flagged small_sample and "
        "their estimates are unstable; the intervals may understate the uncertainty."
    ),
}
METHOD: Final[dict[str, Any]] = {
    "unit": "report: one case id of the faers pipeline (latest case version)",
    "suspect_roles": ["PS", "SS"],
    "interval": (
        "per report, the interval from the most recently started class-member suspect line: the "
        "earliest complete THER.start_dt of that line to DEMO.event_dt, 0 to 3650 days"
    ),
    "median": (
        "empirical median; quartiles by linear interpolation between order statistics "
        "(interpolated at small n)"
    ),
    "median_interval_bootstrap": (
        f"95 % percentile bootstrap interval of the median, {BOOTSTRAP} resamples, Python 3.12 "
        f"random.Random seeded from (seed {SEED}, class, event key); intervals are sorted first, "
        "so the order of the reports does not matter"
    ),
    "median_interval_exact": (
        "distribution-free interval (x_(k), x_(n-k+1)) with the largest k such that "
        "P(Bin(n, 1/2) <= k-1) <= 0.025; median_exact_ci_coverage is its achieved coverage"
    ),
    "weibull": (
        "maximum likelihood with a half-day shift (same-day intervals are 0 days); 95 % "
        "likelihood-ratio interval of the shape; shape class early (interval below 1), random "
        "(contains 1) or wear_out (above 1). Cornelius 2012, Hatahira 2017, Hasegawa 2020"
    ),
    "primary_median_interval": "exact",
    "count_only_below": COUNT_ONLY_BELOW,
    "small_sample_below": SMALL_SAMPLE_BELOW,
    "cluster_share_max": CLUSTER_SHARE_MAX,
    "shape_zero_day_share_max": SHAPE_ZERO_SHARE_MAX,
    "shape_min_distinct_intervals": SHAPE_MIN_DISTINCT,
    "sensitivity_min_reports": SENSITIVITY_MIN,
    "references": [
        "doi:10.2165/11599740-000000000-00000",
        "doi:10.1186/s40780-017-0088-5",
        "doi:10.1002/pds.5108",
    ],
}
CSV_COLUMNS: Final = (
    "dataset_version",
    "pipc_position",
    "pipc_drug_a",
    "pipc_adverse_event",
    "pipc_drug_b",
    "index_class",
    "class_ingredient_key_count",
    "excluded_class_keys",
    "route_groups_counted",
    "event_key",
    "event_pts",
    "shared_with_positions",
    "candidate_reports",
    "reports_with_interval",
    "usable_share",
    "distinct_intervals",
    "multi_line_reports",
    "multi_event_reports",
    "event_year_min",
    "event_year_max",
    "status",
    "small_sample",
    "omitted_reason",
    "median_days",
    "q25_days",
    "q75_days",
    "median_exact_ci_low_days",
    "median_exact_ci_high_days",
    "median_exact_ci_coverage",
    "median_ci_low_days",
    "median_ci_high_days",
    "median_ci_degenerate",
    "median_reflects_zero_heaping",
    "median_days_earliest_class_start",
    "median_days_distinct_date_pairs",
    "zero_day_reports",
    "zero_day_share",
    "day_one_reports",
    "jan_one_reports",
    "day_one_share",
    "reports_without_day_one",
    "median_days_without_day_one",
    "largest_date_cluster",
    "reports_in_clusters_ge3",
    "weibull_shape",
    "weibull_shape_ci_low",
    "weibull_shape_ci_high",
    "weibull_scale_days",
    "weibull_shape_class",
    "shape_omitted_reason",
    "row_note_codes",
    "descriptive_only",
    "causal",
    "incidence",
    "counts_are",
)


def version(rows: Sequence[Mapping[str, Any]]) -> str:
    blob = json.dumps(list(rows), sort_keys=True, ensure_ascii=False)
    return f"{RULE_VERSION}+{hashlib.sha256(blob.encode('utf-8')).hexdigest()[:12]}"


def payload(rows: Sequence[Mapping[str, Any]], meta: Mapping[str, Any]) -> dict[str, Any]:
    with_interval = sum(1 for r in rows if r["reports_with_interval"] > 0)
    usable = sum(1 for r in rows if r["median_days"] is not None)
    return {
        "dataset": DATASET,
        "version": version(rows),
        **meta,
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "attribution": ATTRIBUTION,
        "meddra_notice": MEDDRA_NOTICE,
        "dictionary_url": "https://github.com/mikailustuner/janus/blob/main/docs/open-data.md",
        "review_status": REVIEW_STATUS,
        "disclaimer": DISCLAIMER,
        "descriptive_only": True,
        "causal": False,
        "incidence": False,
        "counts_are": "reports",
        "caveats": CAVEATS,
        "method": METHOD,
        "summary": {
            "rows": len(rows),
            "by_status": counts_by_status(rows),
            "rows_with_any_interval": with_interval,
            "rows_with_median": usable,
            "rows_with_weibull_shape": sum(1 for r in rows if r["weibull_shape"] is not None),
            "weibull_shape_classes": {
                c: sum(1 for r in rows if r["weibull_shape_class"] == c)
                for c in ("early", "random", "wear_out")
            },
            "distinct_class_event_pairs": len({(r["index_class"], r["event_key"]) for r in rows}),
        },
        "rows": list(rows),
    }


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "|".join(str(v) for v in value)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return str(value)


def to_csv(data: Mapping[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for r in data["rows"]:
        values = {
            **r,
            "dataset_version": data["version"],
            "class_ingredient_key_count": len(r["class_ingredient_keys"]),
            "row_note_codes": [n["code"] for n in r["row_notes"]],
        }
        w.writerow([_cell(values[c]) for c in CSV_COLUMNS])
    return buf.getvalue()
