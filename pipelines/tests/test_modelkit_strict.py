"""Strict publication checks (precision work): the CT.gov record check, the label-statement check,
reader C (list alignment) and the PMC table check. Abstention only: a check never confirms a value
the two readers did not confirm."""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.modelkit import sp_c, strict_ctgov, strict_pmc, strict_sp
from janus_pipelines.modelkit.confirm import Confirmation, Context
from janus_pipelines.modelkit.formref import BrandTable
from janus_pipelines.modelkit.model import Candidate
from janus_pipelines.modelkit.pairing import Paired
from janus_pipelines.modelkit.pmc_jats import Article, Table
from janus_pipelines.modelkit.resolver import IdentityTable
from janus_pipelines.modelkit.units import Stat

REPO = Path(__file__).resolve().parents[2]
IDS = IdentityTable.from_csv((REPO / "data" / "modelkit" / "identity_m2.csv").read_text("utf-8"))
BRANDS = BrandTable.from_csv(
    "brand,drug_key,form_class,route\nslowpril xr,lisinopril,modified_release,oral\n"
)
LOC = "NCT00000001#outcome-1/OG000"


def record(
    group_title: str = "Lisinopril 10 mg",
    group_desc: str = "Single oral dose of lisinopril 10 mg tablet.",
    outcome_title: str = "Maximum Plasma Concentration (Cmax) of Lisinopril",
    interventions: tuple[tuple[str, str], ...] = (("Lisinopril", ""),),
    ages: tuple[str, ...] = ("ADULT",),
    classes: tuple[str, ...] = (),
) -> dict[str, Any]:
    ivs = [{"type": "DRUG", "name": n, "description": d} for n, d in interventions]
    return {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT00000001"},
            "armsInterventionsModule": {
                "interventions": ivs,
                "armGroups": [
                    {
                        "label": group_title,
                        "interventionNames": [f"Drug: {n}" for n, _ in interventions],
                    }
                ],
            },
            "eligibilityModule": {"stdAges": list(ages)},
        },
        "resultsSection": {
            "outcomeMeasuresModule": {
                "outcomeMeasures": [
                    {
                        "title": outcome_title,
                        "description": "",
                        "groups": [
                            {"id": "OG000", "title": group_title, "description": group_desc}
                        ],
                        "classes": [{"title": t, "categories": [{"title": ""}]} for t in classes],
                    }
                ]
            }
        },
    }


def ct_level(study: dict[str, Any], locator: str = LOC, **kw: Any) -> int:
    args: dict[str, Any] = {
        "formulation": "immediate_release",
        "route": "oral",
        "regimen": "single",
        "dose_claimed": True,
        "coadministered": False,
        "parameter": "cmax",
        "brands": BRANDS,
    }
    args.update(kw)
    fails = strict_ctgov.check(
        study,
        "lisinopril",
        locator,
        args["formulation"],
        args["route"],
        args["regimen"],
        IDS,
        args["dose_claimed"],
        args["coadministered"],
        args["parameter"],
        args["brands"],
    )
    return strict_ctgov.level(fails)


def test_plain_single_agent_value_passes_every_level() -> None:
    assert ct_level(record()) == max(strict_ctgov.LEVELS)


def test_error_classes_of_the_reports_abstain() -> None:
    assert ct_level(record(outcome_title="Cmax of Lisinopril Metabolite M2")) == 0
    assert ct_level(record(outcome_title="Renal Clearance of Lisinopril"), parameter="cl") == 0
    assert ct_level(record(outcome_title="Ln-transformed Cmax of Lisinopril")) == 0
    assert ct_level(record(group_title="Lisinopril in Moderate Hepatic Impairment")) == 0
    assert ct_level(record(ages=("CHILD",))) == 0
    assert ct_level(record(group_desc="Lisinopril 10 mg plus metformin 500 mg")) == 0
    assert (
        ct_level(record(group_desc="Lisinopril 10 mg/m2 single dose")) < strict_ctgov.PUBLISH_LEVEL
    )
    assert (
        ct_level(record(group_desc="Lisinopril extended-release tablet"))
        < strict_ctgov.PUBLISH_LEVEL
    )
    assert ct_level(record(), regimen="multiple") == 1  # "single oral dose" contradicts "multiple"
    assert ct_level(record(group_desc="Lisinopril 10 mg tablet"), regimen="multiple") == 5
    assert (
        ct_level(record(group_desc="Single dose on Day 1"), regimen="multiple")
        < strict_ctgov.PUBLISH_LEVEL
    )
    assert ct_level(record(), coadministered=True) < strict_ctgov.PUBLISH_LEVEL
    assert ct_level(record(), route="unknown") < strict_ctgov.PUBLISH_LEVEL


def test_other_agent_in_the_record_or_marketed_modified_product_abstains() -> None:
    two = record(interventions=(("Lisinopril", ""), ("Andexanet alfa", "")))
    assert ct_level(two) < strict_ctgov.PUBLISH_LEVEL
    assert (
        ct_level(record(interventions=(("Slowpril XR", "lisinopril"),)))
        < strict_ctgov.PUBLISH_LEVEL
    )


def test_cell_title_naming_another_parameter_abstains() -> None:
    study = record(classes=("T-half",))
    assert ct_level(study, locator=LOC + "/c0.0", parameter="tmax") == 0
    assert ct_level(study, locator=LOC + "/c0.0", parameter="t_half") == max(strict_ctgov.LEVELS)


def test_unlocated_value_is_level_zero() -> None:
    assert ct_level(record(), locator="NCT00000001#outcome-9/OG000") == 0


def _cand(confirmed_ctx: Context) -> Candidate:
    return Candidate(
        "lisinopril", "clinicaltrials_gov", "NCT00000001", "OG000", LOC, "cmax", 10.0, "ng/mL",
        Stat(10.0, "arithmetic"), "parent", confirmed_ctx, 10.0, 12, "q", "v",
    )  # fmt: skip


def test_apply_only_removes_confirmations() -> None:
    ok = _cand(Context(formulation="immediate_release", route="oral", regimen="single"))
    bad = _cand(Context(formulation="unspecified", route="unknown"))
    pairs = [
        Paired(ok, ok, Confirmation(True, "both_readers_agree")),
        Paired(bad, bad, Confirmation(True, "both_readers_agree")),
        Paired(ok, None, Confirmation(False, "reader_b_found_nothing")),
    ]
    counts: Counter[str] = Counter()
    out = strict_ctgov.apply(pairs, record(), IDS, BRANDS, counts)
    assert [p.result.confirmed for p in out] == [True, False, False]
    assert out[1].result.reason == "strict_check" and "route_not_plain" in out[1].result.differing
    assert out[2] is pairs[2]
    assert counts == Counter({"strict_check_passed": 1, "strict_check_abstained": 1})


@given(
    st.text(max_size=80), st.text(max_size=80), st.sampled_from(["oral", "iv", "unknown", "other"])
)
def test_property_level_is_monotone_in_rules(title: str, desc: str, route: str) -> None:
    study = record(group_title="Lisinopril", group_desc=desc, outcome_title="Cmax " + title)
    fails = strict_ctgov.check(study, "lisinopril", LOC, "immediate_release", route, "single", IDS)
    lv = strict_ctgov.level(fails)
    assert not any(f in strict_ctgov.LEVELS[k] for k in range(1, lv + 1) for f in fails)
    if lv < max(strict_ctgov.LEVELS):
        assert any(f in strict_ctgov.LEVELS[lv + 1] for f in fails)


def test_checks_import_no_reader_code() -> None:
    for name in ("strict_ctgov", "strict_sp", "sp_c", "strict_pmc"):
        tree = ast.parse(
            (REPO / "pipelines/janus_pipelines/modelkit" / f"{name}.py").read_text("utf-8")
        )
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        bad = {"reader_a", "reader_b", "sp_a", "sp_b", "doc_a", "doc_b"}
        imported = {m.rsplit(".", 1)[-1] for m in mods if m} | {
            a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names
        }
        assert not (imported & bad), (name, imported & bad)


# --- special-population statements -------------------------------------------------------------


def sp_level(
    quote: str, measure: str = "auc", ratio: float = 1.3, grade: str = "", cls: str = "hepatic"
) -> int:
    return strict_sp.level(strict_sp.check(quote, "lisinopril", cls, IDS, measure, ratio, grade))


def test_sp_plain_statement_passes() -> None:
    q = (
        "In patients with moderate hepatic impairment, lisinopril AUC was 30% higher "
        "than in healthy subjects."
    )
    assert sp_level(q, grade="moderate") == max(strict_sp.LEVELS)


def test_sp_error_classes_abstain() -> None:
    assert sp_level("Lisinopril metabolite M-II AUC was 30% higher in hepatic impairment.") == 0
    assert sp_level("In hepatic impairment the AUC of lisinopril increased at least 30%.") == 0
    assert sp_level("Modeling showed lisinopril AUC 30% higher in hepatic impairment.") == 0
    assert sp_level("In hepatic impairment lisinopril AUC was 2 to 3 times higher.", ratio=2.0) < 2
    q = "In hepatic impairment lisinopril AUC and Cmax were 30% and 20% higher; half-life rose 50%."
    assert sp_level(q) < 2
    q = (
        "In hepatic impairment, increases in lisinopril AUC and Cmax were seen, "
        "with an increase in AUC of about 30%."
    )
    assert sp_level(q, measure="cmax") < 2


def test_reader_c_aligns_grade_and_measure_lists() -> None:
    q = (
        "In patients with mild, moderate, and severe hepatic impairment, AUC of lisinopril "
        "increased by approximately 23%, 47%, and 75%, and C max increased by approximately "
        "4%, 23%, and 48%, respectively."
    )
    got = sp_c.read(q)
    assert got[("auc", "severe")] == 1.75 and got[("cmax", "mild")] == 1.04
    assert sp_c.agrees(q, "auc", "cp_b", 1.47)
    assert not sp_c.agrees(q, "auc", "mild", 1.75)
    assert sp_level(q, ratio=1.75, grade="severe") == max(strict_sp.LEVELS)
    assert sp_level(q, ratio=1.23, grade="severe") < 2


def test_reader_c_leaves_ambiguous_lists_unread() -> None:
    assert (
        sp_c.read(
            "The AUC and Cmax of the drug were increased by 30 and 13%, respectively, "
            "in elderly subjects."
        )
        == {}
    )
    assert sp_c.read("AUC was 2 to 3 times higher in severe hepatic impairment.") == {}
    assert (
        sp_c.read("AUC increased 40%, 60% and 80% in mild and moderate impairment, respectively.")
        == {}
    )


@given(st.floats(min_value=1, max_value=95), st.sampled_from(["higher", "lower"]))
def test_property_reader_c_convention(x: float, word: str) -> None:
    x = round(x, 1)
    got = sp_c.read(f"In elderly subjects, AUC was {x}% {word} than in young subjects.")
    want = 1 + x / 100 if word == "higher" else 1 - x / 100
    assert abs(got[("auc", "")] - want) < 1e-9


# --- PMC tables ----------------------------------------------------------------------------------


def article(
    caption: str,
    grid: tuple[tuple[str, ...], ...],
    methods: str = "Healthy adults received lisinopril.",
) -> tuple[Article, Table]:
    t = Table("T1", "Table 1", caption, grid, 1, "")
    a = Article(
        "PMC1",
        "Lisinopril pharmacokinetics",
        "J",
        "2020",
        "",
        (),
        "",
        "",
        methods,
        (t,),
        (),
        "CC BY",
    )
    return a, t


def test_pmc_plain_cell_passes_and_statistic_columns_abstain() -> None:
    grid = (("Parameter", "Lisinopril 10 mg", "CV%"), ("Cmax (ng/mL)", "45.2 ± 8.1", "17.9"))
    a, t = article("Pharmacokinetic parameters of lisinopril", grid)
    assert strict_pmc.level(strict_pmc.check(a, t, 1, 1, "lisinopril", IDS)) == max(
        strict_pmc.LEVELS
    )
    assert strict_pmc.level(strict_pmc.check(a, t, 1, 2, "lisinopril", IDS)) == 0


def test_pmc_decimal_comma_other_drug_and_combination_abstain() -> None:
    grid = (("Parameter", "Lisinopril", "Metformin"), ("t1/2 (h)", "9,30", "4.1"))
    a, t = article("PK of lisinopril and metformin", grid)
    assert strict_pmc.level(strict_pmc.check(a, t, 1, 1, "lisinopril", IDS)) == 0
    grid2 = (("Parameter", "Lisinopril/HCTZ FDC"), ("Cmax (ng/mL)", "40.1"))
    a2, t2 = article("PK after a fixed-dose combination", grid2)
    assert strict_pmc.level(strict_pmc.check(a2, t2, 1, 1, "lisinopril", IDS)) < 2


# --- round 3: reference tables and arbitration -------------------------------------------------

REF = strict_ctgov.Reference.from_csv(
    "drug_key,name,relation,source\nlisinopril,desethyl lisinopril,metabolite,t\n"
    "lisinopril,andexanet alfa,reversal_agent,t\n",
    "brand,components,source\nzestoretic plus,hydrochlorothiazide|lisinopril,t\n",
)


def ref_level(study: dict[str, Any]) -> int:
    fails = strict_ctgov.check(
        study, "lisinopril", LOC, "immediate_release", "oral", "single", IDS, True, False, "cmax",
        BRANDS, REF,
    )  # fmt: skip
    return strict_ctgov.level(fails)


def test_reference_tables_catch_named_metabolites_reversal_agents_and_combinations() -> None:
    assert ref_level(record()) == max(strict_ctgov.LEVELS)
    assert ref_level(record(outcome_title="Cmax of Desethyl Lisinopril")) == 0
    assert ref_level(record(group_desc="Lisinopril then andexanet alfa bolus")) == 0
    zest = record(interventions=(("Zestoretic Plus", ""),))
    fails = strict_ctgov.check(
        zest,
        "lisinopril",
        LOC,
        "immediate_release",
        "oral",
        "single",
        IDS,
        True,
        False,
        "cmax",
        BRANDS,
        REF,
    )
    assert "combination_product" in fails


def test_committed_reference_tables_load_and_name_known_entries() -> None:
    ref = strict_ctgov.Reference.load()
    assert "dabigatran etexilate" in ref.analytes["dabigatran"]
    assert "andexanet alfa" in ref.reversal
    assert any("advil pm" == b for b in ref.combos_of("ibuprofen"))


def test_arbitration_settles_unspecified_analyte_only_in_a_single_agent_record() -> None:
    ctx = Context(formulation="immediate_release", route="oral", regimen="single")
    a = _cand(ctx)
    b = replace(a, analyte="unspecified")
    differs = Confirmation(False, "analytes_differ")
    counts: Counter[str] = Counter()
    got = strict_ctgov.apply([Paired(a, b, differs)], record(), IDS, BRANDS, counts, REF)[0]
    assert got.result.confirmed and got.result.reason == "strict_arbitration"
    assert got.b is not None and got.a.analyte == got.b.analyte == "parent"
    two = record(interventions=(("Lisinopril", ""), ("Metformin", "")))
    assert not strict_ctgov.apply([Paired(a, b, differs)], two, IDS, BRANDS, counts, REF)[
        0
    ].result.confirmed


def test_arbitration_drops_a_one_sided_dose_only_where_the_parameter_needs_none() -> None:
    ctx = Context(formulation="immediate_release", route="oral", regimen="single")
    a = replace(_cand(ctx), parameter="tmax")
    b = replace(a, dose_mg=None)
    differs = Confirmation(False, "doses_differ")
    counts: Counter[str] = Counter()
    got = strict_ctgov.apply([Paired(a, b, differs)], record(), IDS, BRANDS, counts, REF)[0]
    assert got.result.confirmed and got.a.dose_mg is None
    cmax_a, cmax_b = _cand(ctx), replace(_cand(ctx), dose_mg=None)
    kept = strict_ctgov.apply([Paired(cmax_a, cmax_b, differs)], record(), IDS, BRANDS, counts, REF)
    assert not kept[0].result.confirmed
