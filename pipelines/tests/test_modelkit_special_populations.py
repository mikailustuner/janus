"""Special populations from US labels (M4): readers A and B, confirmation, the CSV, properties."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.jobs import modelkit_special_populations as job
from janus_pipelines.modelkit import sp_a, sp_b
from janus_pipelines.modelkit.resolver import IdentityTable
from janus_pipelines.modelkit.sp_confirm import judge, pair_label
from janus_pipelines.modelkit.sp_model import SpCandidate, SpLabel, SpStats

REPO = Path(__file__).resolve().parents[2]
LABEL = SpLabel("set-1", "3", "2026-01-01", "drugx")

# (sentence, [(population class, grade, measure, ratio)]) that BOTH readers must give
CASES: list[tuple[str, list[tuple[str, str, str, float]]]] = [
    (
        "The AUC in elderly subjects (≥65 years) was 30% higher than in young subjects.",
        [("geriatric", "age65", "auc", 1.3)],
    ),
    (
        "Cmax and AUC were 1.5- and 2.1-fold higher in patients with moderate hepatic impairment "
        "(Child-Pugh B) "
        "compared to healthy subjects.",
        [("hepatic", "cp_b", "cmax", 1.5), ("hepatic", "cp_b", "auc", 2.1)],
    ),
    (
        "In subjects with mild, moderate, and severe renal impairment, AUC was increased by "
        "40%, 70% and 130% "
        "respectively compared to healthy subjects.",
        [
            ("renal", "mild", "auc", 1.4),
            ("renal", "moderate", "auc", 1.7),
            ("renal", "severe", "auc", 2.3),
        ],
    ),
    (
        "In patients with severe renal impairment (CLcr <30 mL/min), AUC increased 2-fold and "
        "half-life increased by 50%.",
        [("renal", "severe", "auc", 2.0)],
    ),
    (
        "Mean AUC was 25% to 45% lower in patients with Child-Pugh class C cirrhosis than in "
        "healthy subjects.",
        [("hepatic", "cp_c", "auc", 0.6423)],
    ),
    (
        "In subjects with mild hepatic impairment, the exposure was 2.4-fold higher based on "
        "C max (90% CI: 1.6 to 3.6) "
        "and 2.2-fold higher based on AUC 0-inf (90% CI: 1.4 to 3.5).",
        [("hepatic", "mild", "cmax", 2.4), ("hepatic", "mild", "auc", 2.2)],
    ),
    (
        "Following a 4-hour hemodialysis treatment, AUC of the drug is reduced by about 50%.",
        [],  # a dialysis session is not a population
    ),
]


def got(reader: str, sentence: str) -> list[tuple[str, str, str, float]]:
    if reader == "a":
        cands = sp_a.read_sentence(LABEL, "pharmacokinetics", sentence, SpStats())
    else:
        cands = sp_b.read_sentence(LABEL, "pharmacokinetics", None, sentence, SpStats())
    return sorted((c.pop_class, c.grade, c.measure, round(c.ratio, 4)) for c in cands)


@pytest.mark.parametrize(("sentence", "expected"), CASES)
@pytest.mark.parametrize("reader", ["a", "b"])
def test_both_readers_read_the_sentence_the_same_way(
    reader: str, sentence: str, expected: list[tuple[str, str, str, float]]
) -> None:
    assert got(reader, sentence) == sorted((c, g, m, round(r, 4)) for c, g, m, r in expected)


def test_a_magnitude_of_another_quantity_is_not_exposure() -> None:
    s = (
        "In patients with severe renal impairment, the half-life increased by 50% and "
        "clearance decreased by 40%."
    )
    assert got("a", s) == [] and got("b", s) == []


def test_percent_of_a_confidence_interval_is_not_a_magnitude() -> None:
    s = "AUC was higher in elderly subjects (90% CI: 1.1 to 1.4)."
    assert got("a", s) == [] and got("b", s) == []


@given(st.integers(min_value=1, max_value=400), st.sampled_from(["higher", "lower"]))
def test_property_percent_convention_is_the_same_in_both_readers(pct: int, word: str) -> None:
    s = f"AUC was {pct}% {word} in patients with severe renal impairment than in healthy subjects."
    want = 1 + pct / 100 if word == "higher" else 1 - pct / 100
    a, b = got("a", s), got("b", s)
    if want > 0:
        assert a == b == [("renal", "severe", "auc", round(want, 4))]
    else:
        assert a == b == []  # a decrease of 100 % or more is not a ratio


@given(st.floats(min_value=1.1, max_value=20.0, allow_nan=False).map(lambda x: round(x, 1)))
def test_property_fold_lower_is_the_inverse(fold: float) -> None:
    s = f"Cmax was {fold}-fold lower in elderly subjects compared to young subjects."
    a, b = got("a", s), got("b", s)
    assert a == b and len(a) == 1 and abs(a[0][3] - round(1 / fold, 4)) < 1e-3


def test_reader_b_shares_no_code_with_reader_a_or_the_pairing() -> None:
    src = (REPO / "pipelines" / "janus_pipelines" / "modelkit" / "sp_b.py").read_text(
        encoding="utf-8"
    )
    imported = {
        n.module for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom) and n.module
    } | {a.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Import) for a in n.names}
    assert not any(
        m.endswith(("sp_a", "sp_confirm", "reader_a", "reader_b", "formulation_a"))
        for m in imported
    )
    src_a = (REPO / "pipelines" / "janus_pipelines" / "modelkit" / "sp_a.py").read_text(
        encoding="utf-8"
    )
    assert "sp_b" not in src_a


def test_heading_context_reaches_only_comparing_sentences_near_the_heading() -> None:
    text = (
        "8.6 Renal Impairment Compared to subjects with normal function, AUC was 60% higher. "
        "Drug Interactions Administration with another drug increased AUC by 80% compared to "
        "healthy subjects."
    )
    label = SpLabel("s", "1", "", "drugx", {"use_in_specific_populations": (text,)})
    a = sp_a.read_label(label, SpStats())
    b = sp_b.read_label(label, SpStats())
    assert [(c.pop_class, c.ratio) for c in a] == [("renal", 1.6)]
    assert [(c.pop_class, c.ratio) for c in b] == [("renal", 1.6)]


TABLE = (
    "<table><tr><th>Population</th><th>AUC ratio</th><th>Cmax ratio</th></tr>"
    "<tr><td>Moderate hepatic impairment (Child-Pugh B)</td><td>1.8 (1.2-2.6)</td><td>1.3</td></tr>"
    "<tr><td>Healthy</td><td>1.0</td><td>1.0</td></tr></table>"
)
ABSOLUTE = (
    "<table><tr><th>Group</th><th>AUC (ng.h/mL)</th><th>Cmax (ng/mL)</th></tr>"
    "<tr><td>Severe renal impairment</td><td>5200</td><td>410</td></tr></table>"
)


def test_tables_are_read_by_both_readers_and_absolute_columns_are_not_ratios() -> None:
    label = SpLabel("s", "1", "", "drugx", {}, {"pharmacokinetics_table": (TABLE,)})
    want = [("hepatic", "cp_b", "auc", 1.8), ("hepatic", "cp_b", "cmax", 1.3)]
    for read in (sp_a.read_label, sp_b.read_label):
        cands = read(label, SpStats())
        assert sorted((c.pop_class, c.grade, c.measure, c.ratio) for c in cands) == sorted(want)
        assert all(c.from_table and "AUC ratio" in c.quote for c in cands)
    ab = SpLabel("s", "1", "", "drugx", {}, {"pharmacokinetics_table": (ABSOLUTE,)})
    assert sp_a.read_label(ab, SpStats()) == [] and sp_b.read_label(ab, SpStats()) == []


def cand(**kw: object) -> SpCandidate:
    base: dict[str, object] = dict(
        reader="a",
        drug_key="d",
        set_id="s",
        version="1",
        section="x",
        pop_class="renal",
        grade="severe",
        measure="auc",
        ratio=2.0,
        ratio_text="2-fold",
        definition="",
        reference="",
        quote="AUC was 2-fold higher in severe renal impairment",
    )
    return SpCandidate(**{**base, **kw})  # type: ignore[arg-type]


def test_confirmation_needs_same_class_grade_measure_value_and_no_context_flag() -> None:
    assert judge(cand(), cand(reader="b", ratio=2.015))[0]
    assert judge(cand(), cand(reader="b", ratio=2.1)) == (False, "value_differs")
    assert judge(cand(), cand(reader="b", grade="moderate")) == (False, "grade_differs")
    assert judge(cand(), cand(reader="b", measure="cmax")) == (False, "class_or_measure_differs")
    assert judge(cand(flags=("interaction",)), cand(reader="b"))[1].startswith("context_flag")
    assert (
        judge(cand(), cand(reader="b", quote="completely different words here"))[1]
        == "different_sentences"
    )


def test_pairing_leaves_unmatched_candidates_unconfirmed() -> None:
    pairs = pair_label(
        [cand(), cand(measure="cmax", ratio=1.2)], [cand(reader="b"), cand(reader="b", ratio=9.0)]
    )
    assert Counter(p.reason for p in pairs) == Counter(
        {"agree": 1, "only_reader_a": 1, "only_reader_b": 1}
    )
    assert sum(p.confirmed for p in pairs) == 1


@given(st.floats(min_value=0.05, max_value=40.0), st.floats(min_value=0.0, max_value=0.2))
def test_property_a_confirmed_pair_always_agrees_within_one_percent(x: float, d: float) -> None:
    ok, _ = judge(cand(ratio=x), cand(reader="b", ratio=x * (1 + d)))
    if ok:
        assert abs(x * (1 + d) - x) <= 0.01 * max(x, x * (1 + d)) + 1e-12


def test_label_of_keeps_single_substance_approved_prescription_labels_of_pool_drugs() -> None:
    table = IdentityTable.from_csv(
        (REPO / "data" / "modelkit" / "identity_m1.csv").read_text(encoding="utf-8")
    )
    openfda = {
        "spl_set_id": ["s1"],
        "product_type": ["HUMAN PRESCRIPTION DRUG"],
        "application_number": ["NDA021"],
        "substance_name": ["DOLUTEGRAVIR SODIUM"],
    }
    rec = {
        "set_id": "s1",
        "version": "4",
        "effective_time": "20250102",
        "openfda": openfda,
        "geriatric_use": ["x"],
    }
    counts: Counter[str] = Counter()
    lab = job.label_of(rec, table, counts)
    assert lab is not None and lab.drug_key == "dolutegravir" and lab.effective_date == "2025-01-02"
    bad = {**rec, "openfda": {**openfda, "substance_name": ["DOLUTEGRAVIR", "LAMIVUDINE"]}}
    assert job.label_of(bad, table, counts) is None and counts["skip_not_single_substance"] == 1
    bad = {**rec, "openfda": {**openfda, "application_number": ["unapproved drug other"]}}
    assert job.label_of(bad, table, counts) is None and counts["skip_no_approved_application"] == 1


def test_aggregate_csv_is_deterministic_and_counts_labels() -> None:
    def row(set_id: str, date: str) -> dict[str, object]:
        return {
            "drug_key": "d",
            "pop_class": "renal",
            "grade": "severe",
            "measure": "auc",
            "ratio": 2.0,
            "ratio_text": "2-fold",
            "definition": "",
            "reference": "",
            "quote": f"q {set_id}",
            "set_id": set_id,
            "version": "1",
            "effective_date": date,
            "section": "x",
            "from_table": False,
        }

    a = job.aggregate_csv([row("s1", "2024-01-01"), row("s2", "2025-01-01")])
    assert a == job.aggregate_csv([row("s2", "2025-01-01"), row("s1", "2024-01-01")])
    lines = a.strip().splitlines()
    assert (
        len(lines) == 2 and ",s2," in lines[1] and lines[1].count(",2,") >= 1
    )  # latest label quoted, n_labels = 2


def test_the_job_accounts_for_every_pair_and_every_excluded_label() -> None:
    """A real run failed twice in this check; the unit is a candidate pair or an excluded label."""
    from datetime import UTC, datetime

    from janus_pipelines.core.runner import RawInput
    from janus_pipelines.core.validation import check_accounting

    payload = job.Payload()
    label = SpLabel(
        "s1", "1", "2025-01-01", "drugx",
        {"geriatric_use": ("The AUC in elderly subjects was 30% higher than in young subjects.",)},
    )  # fmt: skip
    job.read_one(label, payload)
    job.read_one(
        SpLabel("s2", "1", "2025-01-01", "drugx", {"geriatric_use": ("Nothing numeric.",)}), payload
    )
    payload.counts["labels_read"] = 5
    payload.counts["skip_not_a_pool_drug"] = 3
    raw = RawInput(payload, (), "x", datetime(2026, 1, 1, tzinfo=UTC), "2026-01-01")
    result = job.ModelkitSpecialPopulationsJob().parse(raw)
    check_accounting(result.input_rows, result.n_output, result.excluded)
    assert result.n_output >= 1 and result.excluded["matched_label_without_a_candidate"] == 1
    assert result.metrics["labels_read"] == 5 and result.metrics["confirmed"] >= 1
