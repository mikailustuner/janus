"""Expert validation round (plan E): assignment, consensus, kappa and answer files."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.expert_validation import (
    CAP_MINUTES,
    FIELDS,
    MINUTES,
    PER_EXPERT_LIMIT,
    SECTION_GROUPS,
    SECTIONS,
    assign,
    check_value,
    consensus,
    kappa,
    kappa_interval,
    make_experts,
    read_answer_file,
    write_csv,
    write_xlsx,
)

PROTOCOL_SIZES = {"A1": 100, "A2": 40, "B": 50, "C1": 50, "C2": 20, "D": 24, "E": 90, "F": 20}


def items(sizes: dict[str, int]) -> dict[str, list[tuple[str, str | None]]]:
    return {s: [(f"{s}-{i:03d}", None) for i in range(1, n + 1)] for s, n in sizes.items()}


def default_experts():
    return make_experts({"pharmacologist": 2, "clinician": 2, "pharmacist": 2})


def test_experts_are_numbered_by_group_and_never_named() -> None:
    ex = default_experts()
    assert [(e.id, e.group) for e in ex] == [
        ("E01", "pharmacologist"), ("E02", "pharmacologist"), ("E03", "clinician"),
        ("E04", "clinician"), ("E05", "pharmacist"), ("E06", "pharmacist"),
    ]  # fmt: skip
    with pytest.raises(ValueError, match="unknown experts"):
        make_experts({"pharmacist": 1}, {"E09": frozenset({"tr"})})


def test_shared_sections_pair_one_expert_of_each_group() -> None:
    """Amendment 1, point 3: each A1, A2 and B item goes to one geriatrician or family physician
    and one clinical pharmacist, also when the groups differ in size."""
    ex = make_experts({"clinician": 3, "pharmacist": 2})
    group = {e.id: e.group for e in ex}
    res = assign(items({"A1": 30, "B": 12}), ex)
    for s in ("A1", "B"):
        assert all(
            sorted(group[e] for e in v) == ["clinician", "pharmacist"]
            for v in res.assigned[s].values()
        )
    load = [sum(e in v for v in res.assigned["A1"].values()) for e in ("E01", "E02", "E03")]
    assert load == [10, 10, 10]
    assert assign(items({"A1": 4}), default_experts()).assigned["A1"]["A1-001"] == ["E03", "E05"]


def test_protocol_workload_at_two_experts_per_group() -> None:
    """Protocol section 4 sizes: every item judged twice, no item dropped, C2 reaches 6
    documents, the pharmacologists' share is 3 h 38 min, nobody passes the cap."""
    res = assign(items(PROTOCOL_SIZES), default_experts())
    assert all(len(v) == 2 and len(set(v)) == 2 for s in res.assigned.values() for v in s.values())
    assert len(res.assigned["C2"]) == 6
    assert res.dropped["C2"] == [f"C2-{i:03d}" for i in range(7, 21)]
    assert all(not res.dropped[s] for s in SECTIONS if s != "C2")
    assert res.minutes["E01"] == res.minutes["E02"] == 50 + 48 + 60 + 60
    # A and B are shared by four experts, so each judges half of them
    assert res.minutes["E03"] == 50 + 10 + 50
    assert res.minutes["E05"] == 50 + 10 + 50 + 45
    assert max(res.minutes.values()) <= CAP_MINUTES


def test_c2_documents_alternate_in_the_order() -> None:
    res = assign(items(PROTOCOL_SIZES), default_experts())
    assert list(res.assigned["C2"]) == [f"C2-{i:03d}" for i in range(1, 7)]


def test_further_pharmacologist_adds_three_documents() -> None:
    ex = make_experts({"pharmacologist": 3, "clinician": 2, "pharmacist": 2})
    assert len(assign(items(PROTOCOL_SIZES), ex).assigned["C2"]) == 9


def test_one_expert_cannot_make_a_pair_so_the_section_is_dropped() -> None:
    ex = make_experts({"pharmacologist": 1, "clinician": 2, "pharmacist": 2})
    res = assign(items(PROTOCOL_SIZES), ex)
    for s in ("C1", "C2", "D", "F"):
        assert res.assigned[s] == {}
        assert len(res.dropped[s]) == PROTOCOL_SIZES[s]


def test_cap_drops_from_the_end_of_the_order() -> None:
    """One expert per shared group takes every A and B item: past 225 minutes the last B items
    are dropped; the single pharmacist cannot pair in E, so E is dropped."""
    ex = make_experts({"clinician": 1, "pharmacist": 1})
    res = assign(items({"A1": 200, "A2": 40, "B": 50, "E": 10}), ex)
    assert res.minutes == {"E01": 224.0, "E02": 224.0}  # 200 + 20 + 2 x 2
    assert res.dropped["B"] == [f"B-{i:03d}" for i in range(3, 51)]
    assert len(res.dropped["E"]) == 10 and res.assigned["E"] == {}


def test_without_a_group_a_shared_section_is_dropped() -> None:
    ex = make_experts({"pharmacologist": 2, "clinician": 0, "pharmacist": 2})
    res = assign(items(PROTOCOL_SIZES), ex)
    assert res.assigned["A1"] == {} and len(res.dropped["A1"]) == 100
    assert len(res.assigned["E"]) == 90


def test_language_is_respected_in_section_b() -> None:
    ex = make_experts(
        {"clinician": 2, "pharmacist": 2},
        {"E01": frozenset({"en"}), "E02": frozenset({"tr"})},
    )  # fmt: skip
    b = {"B": [("B-001", "en"), ("B-002", "tr"), ("B-003", "tr")]}
    res = assign(b, ex)
    assert "E01" not in res.assigned["B"]["B-002"]
    assert "E02" not in res.assigned["B"]["B-001"]


sizes_st = st.fixed_dictionaries({s: st.integers(0, 60) for s in SECTIONS})
counts_st = st.fixed_dictionaries(
    {g: st.integers(0, 4) for g in ("pharmacologist", "clinician", "pharmacist")}
)


@given(sizes_st, counts_st)
def test_assignment_invariants(sizes: dict[str, int], counts: dict[str, int]) -> None:
    ex = make_experts(counts)
    group = {e.id: e.group for e in ex}
    order = items(sizes)
    res = assign(order, ex)
    for s, assigned in res.assigned.items():
        ids = [i for i, _ in order[s]]
        # every item is judged by two different experts of the section's groups, or dropped
        assert sorted(assigned) + sorted(res.dropped[s]) == sorted(ids)
        for v in assigned.values():
            assert len(set(v)) == 2 and all(group[e] in SECTION_GROUPS[s] for e in v)
            if len(SECTION_GROUPS[s]) == 2:
                assert sorted(group[e] for e in v) == sorted(SECTION_GROUPS[s])
        # dropped items are the end of the fixed order
        assert res.dropped[s] == ids[len(ids) - len(res.dropped[s]) :]
        for e, n in PER_EXPERT_LIMIT.items():
            if s == e:
                per = [x for v in assigned.values() for x in v]
                assert all(per.count(x) <= n for x in set(per))
    assert all(m <= CAP_MINUTES + 1e-9 for m in res.minutes.values())
    total = sum(MINUTES[s] * 2 * len(a) for s, a in res.assigned.items())
    assert abs(total - sum(res.minutes.values())) < 1e-6


@pytest.mark.parametrize(
    ("answers", "kind", "want"),
    [
        (["4", "5"], "scale", ("agreed", "high")),
        (["2", "1"], "scale", ("agreed", "low")),
        (["3", "3"], "scale", ("not_settled", None)),
        (["3", "3", "4"], "scale", ("third", "high")),
        (["4", "2", "3"], "scale", ("not_settled", None)),
        (["4", "2", "1"], "scale", ("third", "low")),
        (["5"], "scale", ("not_settled", None)),
        (["yes", "yes"], "choice", ("agreed", "yes")),
        (["yes", "no", "no"], "choice", ("third", "no")),
        (["cannot_judge", "cannot_judge"], "choice", ("agreed", "cannot_judge")),
        (["correct", "incorrect"], "choice", ("not_settled", None)),
    ],
)
def test_consensus(answers: list[str], kind: str, want: tuple[str, str | None]) -> None:
    assert consensus(answers, kind) == want


def test_kappa_known_values() -> None:
    pairs = [("yes", "yes"), ("yes", "no"), ("no", "no"), ("no", "no")]
    assert kappa(pairs, ("yes", "no")) == pytest.approx(0.5)
    assert kappa([("1", "5"), ("5", "1")], tuple("12345"), weighted=True) == pytest.approx(-1.0)
    assert kappa([("2", "2"), ("4", "4")], tuple("12345"), weighted=True) == pytest.approx(1.0)
    assert kappa([("yes", "yes")] * 3, ("yes", "no")) is None  # chance agreement is 1
    assert kappa([], ("yes", "no")) is None


def weighted_kappa_reference(pairs: list[tuple[int, int]], k: int = 5) -> float:
    """Quadratic-weighted kappa as 1 - sum(d * O) / sum(d * E) with d = (i - j)^2."""
    n = len(pairs)
    obs = sum((a - b) ** 2 for a, b in pairs) / n
    ma = [sum(a == c for a, _ in pairs) / n for c in range(1, k + 1)]
    mb = [sum(b == c for _, b in pairs) / n for c in range(1, k + 1)]
    exp = sum(
        (i - j) ** 2 * ma[i - 1] * mb[j - 1] for i in range(1, k + 1) for j in range(1, k + 1)
    )
    return 1 - obs / exp


@given(st.lists(st.tuples(st.integers(1, 5), st.integers(1, 5)), min_size=2, max_size=40))
def test_weighted_kappa_matches_the_reference_formula(pairs: list[tuple[int, int]]) -> None:
    got = kappa([(str(a), str(b)) for a, b in pairs], tuple("12345"), weighted=True)
    ma = {a for a, _ in pairs}
    mb = {b for _, b in pairs}
    if len(ma) == 1 and ma == mb:
        assert got is None
        return
    assert got == pytest.approx(weighted_kappa_reference(pairs))


def test_kappa_interval_contains_the_estimate() -> None:
    pairs = [("yes", "yes")] * 20 + [("no", "no")] * 15 + [("yes", "no")] * 5
    k = kappa(pairs, ("yes", "no"))
    iv = kappa_interval(pairs, ("yes", "no"))
    assert k is not None and iv is not None and iv[0] <= k <= iv[1]
    assert kappa_interval(pairs, ("yes", "no")) == iv  # seeded


def test_check_value() -> None:
    realistic = FIELDS["A1"][0]
    assert check_value(realistic, "4.0", "f:2") == "4"
    with pytest.raises(ValueError, match="f:2: realistic"):
        check_value(realistic, "6", "f:2")
    verdict = FIELDS["C1"][0]
    assert check_value(verdict, "Cannot judge", "f") == "cannot_judge"
    value = FIELDS["C2"][2]
    assert check_value(value, "1,5", "f") == "1.5"
    with pytest.raises(ValueError, match="number"):
        check_value(value, "about 3", "f")


def test_answer_files_round_trip(tmp_path: Path) -> None:
    rows = [
        {"expert_id": "E03", "section": "A1", "item_id": "A1-001", "item": "a -> b"},
        {"expert_id": "E03", "section": "B", "item_id": "B-001", "item": "[en] text"},
    ]
    write_csv(tmp_path / "E03.csv", rows, ["expert_id", "section", "item_id", "item", "realistic"])
    assert read_answer_file(tmp_path / "E03.csv")[0]["item_id"] == "A1-001"
    write_xlsx(tmp_path / "E03.xlsx", "E03", rows, "note")
    from openpyxl import load_workbook

    wb = load_workbook(tmp_path / "E03.xlsx")
    assert wb.sheetnames == ["read_me", "A1", "B"]
    lists = [dv.formula1 for dv in wb["B"].data_validations.dataValidation]
    assert lists.count('"1,2,3,4,5"') == 3  # accuracy, harm, clarity
    ws = wb["A1"]
    ws["D2"] = 5
    wb.save(tmp_path / "E03.xlsx")
    back = read_answer_file(tmp_path / "E03.xlsx")
    assert {(r["section"], r["item_id"], r.get("realistic", "")) for r in back} == {
        ("A1", "A1-001", "5"), ("B", "B-001", ""),
    }  # fmt: skip
