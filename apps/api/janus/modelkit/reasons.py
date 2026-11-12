"""Reason codes of the model kit and their English text. The API sends codes (the web app
translates them); exports and the MCP tools use the English text. Research use only."""

from __future__ import annotations

TEXT: dict[str, str] = {
    # why a row was not used
    "not_confirmed": "The two readers did not both agree with the extracted value.",
    "analyte_not_parent": "The value is not for the parent drug.",
    "coadministered": "The arm gave another active drug with it.",
    "fixed_dose_combination": "The product is a fixed-dose combination.",
    "formulation_not_immediate_release": "The formulation is not immediate-release or a solution.",
    "bound_not_a_value": "The source gives only a bound (for example 'more than'), not a value.",
    "per_kg_not_converted": "The value is per kilogram; there is no body weight, so it is not converted.",
    "held_out_study": "Held-out study: its observations only test a set, they never build one.",
    "observation_in_building_study": "An observation in a study that also reports building parameters; not tested.",
    "same_study_in_another_source": "May be the same study as one in another source (shared trial number, study code or identical results); kept on the building side, not tested.",
    "not_needed_preferred_basis": "Not needed: a preferred basis or a pooled value was used.",
    # why an observation was not tested
    "auc_to_last_sampling_time_not_comparable": "AUC to the last sampling time: that time is not in the evidence.",
    "not_an_observation": "Not an observation of Cmax or AUC.",
    "needs_oral_dose": "A test needs an oral dose.",
    "auc_tau_needs_multiple_dose_interval": "AUC over a dosing interval needs a multiple-dose arm with its interval.",
    "steady_state_cmax_not_modelled": "Steady-state Cmax is not modelled in this milestone.",
    "auc_inf_needs_single_dose": "AUC to infinity needs a single-dose arm.",
    "set_has_no_absorption_rate": "The set has no absorption rate, so it cannot predict Cmax.",
    "set_cannot_predict_metric": "The set cannot predict this metric.",
    # status reasons
    "no_parameter_set": "There is no parameter set to test.",
    "no_independent_observation": "No independent observation: no held-out study reports Cmax or AUC.",
    "auc_not_tested": "AUC was not tested.",
    "cmax_not_tested": "Cmax was not tested.",
    "point_outside_2_fold": "At least one held-out observation is outside 2-fold of the prediction.",
    "all_points_within_2_fold": "AUC and Cmax were tested and every held-out observation is within 2-fold.",
    # why there is no set
    "no_confirmed_clearance": "No confirmed clearance (intravenous CL or oral CL/F).",
    "no_confirmed_volume": "No confirmed volume (Vss or Vd, or V/F).",
    "iv_evidence_incomplete": "Intravenous evidence is incomplete: clearance and volume are both needed.",
    "iv_without_bioavailability": "Intravenous clearance and volume exist but no confirmed oral bioavailability.",
    "no_volume_and_no_half_life": "No volume (V/F) and no half-life to derive it.",
    # set notes
    "missing_absorption_no_peak_time": "Absorption rate missing: no confirmed time of peak concentration.",
    "missing_absorption_no_solution": "Absorption rate missing: the peak time is at or beyond what the elimination rate allows.",
    "bioavailability_capped": "A bioavailability above 1 was capped at 1.",
    "half_life_inconsistent": "The half-life implied by CL and V differs from the stated half-life by more than 1.5-fold; the curve tail is not supported.",
    "studies_disagree": "The studies disagree by more than 2-fold.",
    "healthy_adult_preferred": "Healthy-adult values were preferred.",
    "no_central_volume_evidence": "No central-volume evidence (no distribution phase): one compartment.",
    "two_volumes_differ": "Central and steady-state volumes differ by at least 25 %: two compartments.",
    "two_volumes_agree": "Central and steady-state volumes agree within 25 %: one compartment.",
    # derivations
    "v_from_clf_half_life": "V/F = CL/F x half-life / ln 2",
    "ka_from_tmax": "ka solves tmax = ln(ka/k) / (ka - k) with k = CL / V",
    "cl_from_dose_and_auc": "Derived: CL/F = dose / AUC to infinity of one study arm (CL for an intravenous dose).",
    "f_fixed_apparent": "Fixed at 1: apparent parameters already contain bioavailability.",
    # suspects
    "clearance_or_bioavailability": "Clearance (CL or CL/F) or bioavailability: AUC is outside 2-fold.",
    "absorption_rate_or_volume": "Absorption rate (derived from the time of peak concentration) or volume: Cmax is outside 2-fold.",
    # system caveats
    "n_very_small": "n is very small: shares and fold errors describe these drugs, not drugs in general.",
    "two_automated_passes": "Every held-out observation was read automatically and confirmed by two automated passes.",
    "confirmed_precision_below_target": (
        "On a blinded sample of confirmed values, two automated review passes found fewer correct "
        "values than the 90 % target of this milestone (the measured share, n and interval are in "
        "the report). Read every value as unverified."
    ),
    "expert_review_pending": "Expert review has not yet been done.",
    # special populations (older adults, renal and hepatic impairment) quoted from US labels
    "sp_statements_note": (
        "Exposure ratios as the US label states them, quoted. Two independent automated readers agree on each; "
        "no person has checked them. They are not carried into this drug's model and are not dose advice."
    ),
    "sp_atlas_note": (
        "Rows of the older-adult exposure atlas: one automated extraction that the two-reader rule did not "
        "confirm and that no person has checked. Evidence only, not a verdict."
    ),
    "sp_none": "No special-population statement was confirmed for this drug.",
    "two_readers_agree": "Two independent automated readers agree; not checked by a person.",
    "automated_extraction_unconfirmed": (
        "One automated extraction, not confirmed by the two-reader rule, not checked by a person."
    ),
    # interval
    "interval_n_too_small": "No interval is shown: fewer than 20 independent held-out studies.",
    "interval_system_level_only": "Intervals are given at system level only, not per drug.",
    "interval_shown": "Intervals are shown: at least 20 independent held-out studies.",
    # what the release still lacks (system report)
    "gate_not_interpretable": "Fewer than 10 drugs have both AUC and Cmax tested on held-out studies.",
    "no_drug_validated": "No drug is validated.",
    "intervals_not_shown": "No prediction intervals are shown: not enough held-out studies.",
    "formulation_often_unspecified": "More than a quarter of confirmed values have no stated formulation.",
    "fewer_than_150_sets": "Fewer than 150 drugs have a parameter set.",
}


def text(code: str) -> str:
    return TEXT.get(code, code)
