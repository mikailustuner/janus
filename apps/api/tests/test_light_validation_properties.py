"""Properties of the retrospective validation and of the curated loaders (design §4, §8).

Feature: light-face, Properties P4, P10, P11.
"""

from __future__ import annotations

import csv
import io
import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.light import curation
from janus.light.build import paper_ids
from janus.light.curation import CurationError, parse_all
from janus.light.model import TOP_K, Case, Label
from janus.light.validation import evaluate, mentions, run_case, status_of, summarise
from janus.memory.vocabulary import load_events
from janus.settings import EVENT_VOCABULARY
from tests.light_world import KEY_OF, MAPPING, ONSIDES_IDS, PAPER, labels

CASE = Case(
    id="q1_goal_a",
    ingredient_name="sentinel",
    ingredient_key="Q1",
    goal="goal_a",
    original_use="x",
    later_year=2000,
    indication_terms=("later use",),
    evidence=(PAPER,),
    note="n",
)


@st.composite
def openfda(draw: st.DrawFn, rows: list[Label]) -> dict[str, str]:
    out: dict[str, str] = {}
    for lb in rows:
        choice = draw(st.sampled_from(["missing", "plain", "names"]))
        if choice == "plain":
            out[lb.set_id] = "Indicated for the original use."
        elif choice == "names":
            out[lb.set_id] = "Indicated for the LATER USE in adults."
    return out


@given(st.data())
def test_published_primary_is_never_better_than_either_variant(data: st.DataObject) -> None:
    """Feature: light-face, Property P11: the worse variant is published; a hit needs both."""
    rows = data.draw(labels(ids=tuple(ONSIDES_IDS[:12]), max_size=60))
    fda = data.draw(openfda(rows))
    v = evaluate([CASE], rows, MAPPING, KEY_OF, {}, fda, {"q1_goal_a": None})
    r = v.results[0]
    a, b, p = r.primary_indication, r.primary_strict, r.primary
    assert p.hit == (a.hit and b.hit)
    for x in (a, b):
        if p.rank is not None and x.rank is not None:
            assert p.rank.worst / p.population >= x.rank.worst / x.population - 1e-12
        if x.rank is None:
            assert p.rank is None
    # removed counts: (a) never removes unreadable labels
    assert a.labels_removed_not_in_openfda == 0
    assert (
        b.labels_removed_indication + b.labels_removed_not_in_openfda >= a.labels_removed_indication
    )
    for run in (a, b, p, r.sensitivity):
        if run.hit:
            assert run.rank is not None and run.rank.worst <= TOP_K
        assert run.informative == (run.population > TOP_K)
        if run.rank is not None:
            assert run.chance_hit == pytest.approx(min(1.0, TOP_K / run.population))
    assert v.status == status_of(v.primary)
    assert (v.status == "experimental") == (v.primary.informative_hits == 0)


@given(st.data())
def test_case_without_labels_is_not_evaluable(data: st.DataObject) -> None:
    """Feature: light-face, Property P11: no case-drug label left -> not evaluable, never a hit."""
    rows = [lb for lb in data.draw(labels()) if "1001" not in lb.ingredients]
    run = run_case(CASE, "primary_strict", rows, MAPPING, KEY_OF, (), {})
    assert run.reason == "not_evaluable" and not run.hit and run.rank is None


def test_goal_without_terms_is_no_label_mapping() -> None:
    lb = Label(1, "US", "s", ("1001",), (("Term alpha", "AR"),))
    case = Case("q1_goal_c", "sentinel", "Q1", "goal_c", "x", 2000, ("y",), (PAPER,), "n")
    run = run_case(case, "sensitivity", [lb], MAPPING, KEY_OF, (), {})
    assert run.reason == "no_label_mapping"


@given(st.data(), st.randoms(use_true_random=False))
def test_evaluation_is_deterministic(data: st.DataObject, rnd: random.Random) -> None:
    """Feature: light-face, Property P4: same inputs in any order give the same evaluation."""
    rows = data.draw(labels(max_size=30))
    fda = data.draw(openfda(rows))
    cases = [CASE, Case("q2_goal_b", "s2", "Q2", "goal_b", "x", 2001, ("y",), (PAPER,), "n")]
    base = evaluate(cases, rows, MAPPING, KEY_OF, {}, fda, {})
    rows2, cases2 = list(rows), list(cases)
    rnd.shuffle(rows2)
    rnd.shuffle(cases2)
    assert evaluate(cases2, rows2, MAPPING, KEY_OF, {}, dict(reversed(fda.items())), {}) == base
    assert summarise(r.primary for r in base.results) == base.primary


def test_mentions_matches_whole_phrases_only() -> None:
    assert mentions("treats PAH (WHO group I)", ["pah"])
    assert not mentions("a pahlavi text", ["pah"])
    assert mentions("Hair loss in men", ["hair loss"])
    assert not mentions("hairy losses", ["hair loss"])


# --- P10: curated loaders -------------------------------------------------------------------------

BENEFIT = {k.key for k in load_events(EVENT_VOCABULARY).active() if k.direction == "benefit"}
PAPERS = paper_ids()


def test_committed_curated_files_load() -> None:
    """Feature: light-face, Property P10: the committed files load and are cited."""
    cur = parse_all(curation.read_texts(), benefit_keys=BENEFIT, papers=PAPERS)
    assert cur.goals and cur.mapping and len(cur.cases) >= 9
    assert {"minoxidil_alopecia", "sildenafil_ed", "thalidomide_mm", "thalidomide_enl"} <= {
        c.id for c in cur.cases
    }
    for m in cur.mapping:
        assert m.goal in cur.goals and (m.status == "excluded" or m.evidence)
    for c in cur.cases:
        assert c.goal in cur.goals and c.evidence


def _mutate(text: str, line: int, column: str, value: str) -> str:
    rows = list(csv.DictReader(io.StringIO(text)))
    rows[line][column] = value
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


DEFECTS = [
    (curation.GOALS_FILE, "key", "Bad Key", "bad_key"),
    (curation.GOALS_FILE, "label_de", "", "missing_label"),
    (curation.GOALS_FILE, "faers_pts", "Zeta|Alpha", "bad_faers_pts"),
    (curation.GOALS_FILE, "benefit_keys", "improvement_unknown", "bad_benefit_keys"),
    (curation.MAPPING_FILE, "goal", "no_such_goal", "unknown_goal"),
    (curation.MAPPING_FILE, "status", "maybe", "bad_status"),
    (curation.MAPPING_FILE, "evidence", "paper:none:x", "unknown_evidence"),
    (curation.MAPPING_FILE, "rationale", "", "no_rationale"),
    (curation.MAPPING_FILE, "nonspecific", "perhaps", "bad_nonspecific"),
    (curation.CASES_FILE, "ingredient_key", "X1", "bad_ingredient_key"),
    (curation.CASES_FILE, "later_year", "19xx", "bad_year"),
    (curation.CASES_FILE, "indication_terms", "", "bad_indication_terms"),
    (curation.CASES_FILE, "evidence", "", "bad_evidence"),
    (curation.CASES_FILE, "goal", "no_such_goal", "unknown_goal"),
]


@given(st.sampled_from(DEFECTS), st.integers(0, 3))
def test_each_injected_defect_is_named(defect: tuple[str, str, str, str], line: int) -> None:
    """Feature: light-face, Property P10: a defect stops the load and is named with its line."""
    file, column, value, code = defect
    texts = curation.read_texts()
    texts[file] = _mutate(texts[file], line, column, value)
    with pytest.raises(CurationError) as err:
        parse_all(texts, benefit_keys=BENEFIT, papers=PAPERS)
    assert err.value.defect == code and err.value.file == file and err.value.line == line + 2


def test_active_row_needs_evidence_and_term_in_vocabulary() -> None:
    texts = curation.read_texts()
    rows = list(csv.DictReader(io.StringIO(texts[curation.MAPPING_FILE])))
    first_active = next(i for i, r in enumerate(rows) if r["status"] == "active")
    bad = _mutate(texts[curation.MAPPING_FILE], first_active, "evidence", "")
    with pytest.raises(CurationError, match="no_evidence"):
        parse_all({**texts, curation.MAPPING_FILE: bad}, benefit_keys=BENEFIT, papers=PAPERS)
    with pytest.raises(CurationError, match="term_not_in_onsides"):
        parse_all(texts, benefit_keys=BENEFIT, papers=PAPERS, vocabulary={"Nothing"})
    dup = texts[curation.MAPPING_FILE] + texts[curation.MAPPING_FILE].splitlines()[1] + "\n"
    with pytest.raises(CurationError, match="duplicate_term"):
        parse_all({**texts, curation.MAPPING_FILE: dup}, benefit_keys=BENEFIT, papers=PAPERS)
