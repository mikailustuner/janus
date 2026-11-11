"""Analyte and arm-context resolver."""

from __future__ import annotations

from pathlib import Path

from janus_pipelines.modelkit.resolver import IdentityTable, arm_context, classify_analyte

REPO = Path(__file__).resolve().parents[2]
TABLE = IdentityTable.from_csv(
    (REPO / "data" / "modelkit" / "identity_m1.csv").read_text(encoding="utf-8")
)


def cls(text: str, drug: str) -> str:
    return classify_analyte(text, drug, TABLE)[0]


def test_company_codes_and_names_resolve_to_the_ingredient() -> None:
    assert TABLE.drugs_in("GSK1349572 50 mg tablets") == ["dolutegravir"]
    assert TABLE.drugs_in("MK-8835 and PF-04971729") == ["ertugliflozin"]
    assert TABLE.drugs_in("Cardizem CD") == ["diltiazem"]
    assert cls("AUC of GSK 1349572", "dolutegravir") == "parent"


def test_parent_metabolite_enantiomer_total_partner() -> None:
    assert cls("AUC(0-inf) of Sunitinib", "sunitinib") == "parent"
    assert cls("Cmax of SU012662", "sunitinib") == "metabolite"
    assert cls("Cmax of the primary active metabolite", "sunitinib") == "metabolite"
    assert cls("AUC of O-desmethyltramadol", "tramadol") == "metabolite"
    assert cls("Cmax of (R)-methadone", "methadone") == "enantiomer"
    assert cls("Unbound concentration of tramadol", "tramadol") == "parent_unbound"
    assert cls("Total sunitinib (sunitinib + SU12662)", "sunitinib") == "total"
    assert cls("AUC of rilpivirine", "dolutegravir") == "combination_partner"
    assert cls("CL/F of Amlodipine", "telmisartan") == "combination_partner"
    assert cls("AUC of AGI-16903", "enasidenib") == "metabolite"
    assert cls("AUC of ZZZ-12345", "tramadol") == "unconfirmed"
    assert cls("Cmax of TCV-116", "candesartan") == "prodrug"
    assert cls("Maximum plasma concentration", "tramadol") == "unspecified"


def test_what_follows_with_is_context_not_the_analyte() -> None:
    assert cls("AUC of dolutegravir when co-administered with rifampin", "dolutegravir") == "parent"
    assert cls("AUC of rifampin with dolutegravir", "dolutegravir") == "combination_partner"
    assert cls("dolutegravir and rilpivirine AUC", "dolutegravir") == "unconfirmed"


def test_arm_context_interaction_food_formulation_population_species() -> None:
    a = arm_context("Dolutegravir 50 mg with rifampin 600 mg once daily", "dolutegravir", TABLE)
    assert a.interaction and a.context.coadministered and "rifampin" in a.context.coadministered
    a = arm_context(
        "Dolutegravir tablets 50 mg alone, fasted, healthy adults", "dolutegravir", TABLE
    )
    assert not a.interaction and a.context.food == "fasted"
    assert a.context.population == "healthy_adult" and a.context.formulation == "immediate_release"
    assert a.route == "oral"
    a = arm_context("Tramadol extended-release 100 mg", "tramadol", TABLE)
    assert a.context.formulation == "modified_release"
    a = arm_context("Fixed-dose combination tablet", "telmisartan", TABLE)
    assert a.context.formulation == "fixed_dose_combination"
    a = arm_context("Single dose in horses", "canagliflozin", TABLE)
    assert not a.human
    a = arm_context("Children 6 to 11 years", "gabapentin", TABLE)
    assert a.context.population == "special"
    a = arm_context("Test formulation, period 1, high-fat meal", "gabapentin", TABLE)
    assert a.context.arm and a.context.food == "fed"
    a = arm_context("Women only", "gabapentin", TABLE)
    assert a.context.sex == "female"
