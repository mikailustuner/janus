"""End-to-end build on synthetic artifacts, the store, cards, export and wording.

Feature: light-face, Properties P1, P3, P4, P14 (and the store half of P13).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import duckdb
import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.integrity.model import (
    EvidenceRecord,
    IntegritySnapshot,
    IntegrityState,
    SourceInfo,
    Status,
)
from janus.light import build as light_build
from janus.light import messages
from janus.light.cards import goal_cards
from janus.light.curation import read_texts
from janus.light.model import LANGS as LANGUAGES  # Wikidata and curated labels: five languages
from janus.light.schemas import LightFile
from janus.light.service import export
from janus.light.store import LightHolder, LightUnavailableError
from janus.memory.faers_build import ReportFact
from janus.notes.phrases import violations
from tests.memory_counts import make_counts

PAPER = "paper:yang_2011:pone.0028025"
PAPER2 = "paper:zappacosta_1980:nejm198012183032516"

GOALS = (
    "key,label_en,label_tr,label_de,label_fr,label_es,faers_pts,benefit_keys,note\n"
    "goal_a,Condition A,Durum A,Zustand A,État A,Estado A,Nausea|Pain,improvement_pain,\n"
    "goal_b,Condition B,Durum B,Zustand B,État B,Estado B,,,\n"
)
MAPPING = (
    "term,goal,status,nonspecific,evidence,rationale\n"
    f"Term alpha,goal_a,active,no,{PAPER};{PAPER2},Rationale alpha.\n"
    f"Term beta,goal_b,active,yes,{PAPER},Rationale beta.\n"
    f"Term gamma,goal_a,excluded,no,{PAPER},Rationale gamma.\n"
)
CASES = (
    "id,ingredient_name,ingredient_key,goal,original_use,later_year,indication_terms,evidence,note\n"
    f"aspirin_goal_a,aspirin,Q1,goal_a,pain,1999,condition a,{PAPER},Synthetic case.\n"
)
MEDDRA = [
    (1, "Term alpha", "PT"),
    (2, "Term beta", "LLT"),
    (3, "Term gamma", "PT"),
    (4, "Other", "PT"),
]
# label id, source, set id, ingredient ids, effect ids
LABELS = [
    (1, "US", "s1.1", ["101"], [1, 4]),
    (2, "US", "s2.1", ["101"], [4]),
    (3, "UK", "x3", ["101"], [1]),
    (4, "US", "s4.1", ["102"], [1, 2]),
    (5, "EU", "x5", ["102", "103"], [1]),
    (6, "US", "s6.1", ["103"], [2, 3]),
    (7, "JP", "x7", ["OMOP9"], [1]),
]
INGREDIENTS = [("101", "aspirin"), ("102", "metformin"), ("103", "amlodipine"), ("OMOP9", "twin")]
WIKIDATA = [("Q1", ["101"], "aspirin"), ("Q2", ["102"], "metformin"), ("Q3", ["103"], "amlodipine")]
OPENFDA = [("s1", "Used for condition A."), ("s2", "Used for pain.")]


def _artifact(root: Path, pipeline: str, run: str, snapshot: str) -> Path:
    d = root / "artifacts" / pipeline / "runs" / run
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps({"run_id": run, "snapshot_date": snapshot}))
    link = root / "artifacts" / pipeline / "current"
    if link.is_symlink():
        link.unlink()
    link.symlink_to(Path("runs") / run)
    return d


def write_world(root: Path, labels: list[tuple[int, str, str, list[str], list[int]]]) -> Path:
    con = duckdb.connect()
    try:
        d = _artifact(root, "onsides", "o1", "2026-04-22")
        con.execute(
            "CREATE TABLE r (label_id BIGINT, source VARCHAR, product_name VARCHAR, "
            "source_product_id VARCHAR, url VARCHAR, ingredient_ids VARCHAR[], "
            "effects STRUCT(meddra_id BIGINT, section VARCHAR)[])"
        )
        for lid, src, spid, ing, eff in labels:
            con.execute(
                "INSERT INTO r VALUES (?, ?, 'P', ?, '', ?, ?)",
                [lid, src, spid, ing, [{"meddra_id": e, "section": "AR"} for e in eff]],
            )
        con.execute(f"COPY r TO '{d / 'rows.parquet'}' (FORMAT parquet)")
        con.execute("CREATE TABLE m (meddra_id BIGINT, name VARCHAR, term_type VARCHAR)")
        con.executemany("INSERT INTO m VALUES (?, ?, ?)", MEDDRA)
        con.execute(f"COPY m TO '{d / 'meddra.parquet'}' (FORMAT parquet)")
        con.execute("CREATE TABLE i (rxnorm_id VARCHAR, name VARCHAR)")
        con.executemany("INSERT INTO i VALUES (?, ?)", INGREDIENTS)
        con.execute(f"COPY i TO '{d / 'ingredients.parquet'}' (FORMAT parquet)")
        d = _artifact(root, "wikidata_ingredients", "w1", "2026-11-07")
        con.execute(
            "CREATE TABLE w (qid VARCHAR, rxcuis VARCHAR[], label_en VARCHAR, label_tr VARCHAR, "
            "label_de VARCHAR, label_fr VARCHAR, label_es VARCHAR)"
        )
        for q, rx, en in WIKIDATA:
            con.execute("INSERT INTO w VALUES (?, ?, ?, NULL, NULL, NULL, NULL)", [q, rx, en])
        con.execute(f"COPY w TO '{d / 'rows.parquet'}' (FORMAT parquet)")
        d = _artifact(root, "openfda_label", "f1", "2026-11-08")
        con.execute("CREATE TABLE f (set_id VARCHAR, indications VARCHAR)")
        con.executemany("INSERT INTO f VALUES (?, ?)", OPENFDA)
        con.execute(f"COPY f TO '{d / 'rows.parquet'}' (FORMAT parquet)")
    finally:
        con.close()
    facts = [
        ReportFact(str(100000 + i), "2026Q1", "US", (("PS", (name,)),), events)
        for i, (name, events) in enumerate(
            [("ASPIRIN", ("Rash",))] * 40
            + [("METFORMIN", ("Nausea",))] * 30
            + [("AMLODIPINE BESYLATE", ("Pain",))] * 20
            + [("ASPIRIN", ("Nausea",))] * 3
        )
    ]
    make_counts(root, facts)
    cur = root / "curated"
    cur.mkdir(exist_ok=True)
    (cur / "goals.csv").write_text(GOALS, encoding="utf-8")
    (cur / "effect_goal_map.csv").write_text(MAPPING, encoding="utf-8")
    (cur / "validation_cases.csv").write_text(CASES, encoding="utf-8")
    return cur


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, LightFile]:
    root = tmp_path_factory.mktemp("light")
    cur = write_world(root, LABELS)
    return root, cur, light_build.build(root, cur)


def test_build_is_byte_identical_and_order_independent(
    world: tuple[Path, Path, LightFile], tmp_path: Path
) -> None:
    """Feature: light-face, Property P4: the same inputs give the same file, in any row order."""
    root, cur, light = world
    assert light_build.dump(light_build.build(root, cur)) == light_build.dump(light)
    other = tmp_path / "w"
    cur2 = write_world(other, list(reversed(LABELS)))
    again = light_build.build(other, cur2)
    a, b = light.model_dump(mode="json"), again.model_dump(mode="json")
    for d in (a, b):
        d.pop("build_id")
        d["inputs"].pop("faers_build_id")
    assert a == b


def test_build_content(world: tuple[Path, Path, LightFile]) -> None:
    _root, _cur, light = world
    cands = {c.ingredient: c for c in light.candidates["goal_a"]}
    # aspirin: labels 1 and 3 list Term alpha (2 of 3 single-ingredient labels), US and UK
    assert cands["Q1"].label is not None and cands["Q1"].label.labels_with_effect == 2
    assert cands["Q1"].label.labels_total == 3 and cands["Q1"].label.regions == ["US", "UK"]
    # the combination label 5 and the unmapped OMOP label never count
    assert cands["Q2"].label is not None and cands["Q2"].label.labels_total == 1
    assert "Term gamma" not in {t for c in cands.values() if c.label for t in c.label.terms}
    assert light.candidates["goal_b"][0].label is not None
    assert light.candidates["goal_b"][0].label.nonspecific
    case = light.validation.cases[0]
    # label 1 names the later use (removed), label 2 does not list the term, label 3 is UK
    assert case.primary_strict.labels_removed_indication == 1
    assert case.sensitivity.rank is not None
    assert light.coverage.single_ingredient_labels == 5


def test_store_round_trip_and_fail_closed(
    world: tuple[Path, Path, LightFile], tmp_path: Path
) -> None:
    """Feature: light-face, Property P13 (store): a missing or broken build is refused."""
    _root, _cur, light = world
    holder = LightHolder(tmp_path)
    with pytest.raises(LightUnavailableError):
        holder.current()
    light_build.write(tmp_path, light)
    assert holder.current() == light
    path = tmp_path / "light" / "runs" / light.build_id / "light.json"
    path.write_text(path.read_text().replace('"light-1"', '"light-0"'), encoding="utf-8")
    assert LightHolder(tmp_path).current is not None
    with pytest.raises(LightUnavailableError):
        LightHolder(tmp_path).current()
    with pytest.raises(LightUnavailableError):
        LightHolder(None).current()


# --- cards and integrity (P1, P14) -----------------------------------------------------------

IDS = ["dataset:onsides", "dataset:faers", PAPER, PAPER2]


def snapshot(retracted: set[str], registered: set[str]) -> IntegritySnapshot:
    recs: dict[str, EvidenceRecord] = {}
    states: dict[str, IntegrityState] = {}
    for i in registered:
        kind, source = i.split(":")[:2]
        doi = None if kind == "dataset" else "10.1000/" + source
        recs[i] = EvidenceRecord(
            i,
            kind,
            source,
            "https://example.org/x",
            "CC0",
            None,
            dt.date(2026, 11, 8),
            False,
            doi,
            None,
            "T",
        )
        if doi is not None:
            s = Status.RETRACTED if i in retracted else Status.OK
            states[i] = IntegrityState(s, s, None, dt.date(2026, 11, 8), "r1")
    return IntegritySnapshot(recs, states, {"x": SourceInfo("x", "x", "cache", 7)})


@given(st.sets(st.sampled_from([PAPER, PAPER2])), st.sets(st.sampled_from(IDS)))
def test_cards_keep_only_citable_signals(
    world_cached: LightFile, retracted: set[str], gone: set[str]
) -> None:  # type: ignore[no-untyped-def]
    """Feature: light-face, Property P1: no card without a signal backed by a citable source."""
    light = world_cached
    snap = snapshot(retracted, set(IDS) - gone)
    for goal in light.goals:
        gc = goal_cards(light, goal, snap, {})
        assert len(gc.cards) + gc.removed_by_integrity == len(light.candidates[goal.key])
        for card in gc.cards:
            assert card.signals and "candidate_not_treatment" in card.codes
            assert card.sources
            for s in card.sources:
                assert s.id not in retracted and s.id not in gone
            for sig in card.signals:
                ids = (sig.label.evidence_ids if sig.label else []) + (
                    sig.inverse.evidence_ids if sig.inverse else []
                )
                assert any(i not in retracted and i not in gone for i in ids)
    ex = export(light, snap, None)
    total = sum(len(goal_cards(light, g, snap, {}).cards) for g in light.goals)
    assert len(ex.rows) == total and ex.licence == "CC BY 4.0"
    assert all(r.patient_reported_released is None for r in ex.rows)


@pytest.fixture(scope="module")
def world_cached(world: tuple[Path, Path, LightFile]) -> LightFile:
    return world[2]


# --- wording (P3) ----------------------------------------------------------------------------


def test_canonical_sentences_have_no_forbidden_phrase() -> None:
    """Feature: light-face, Property P3: English canonical sentences pass rule 2 and rule 3."""
    for code, text in messages.SENTENCES.items():
        assert violations(text, "en") == ([], []), code
    assert (
        "treatment"
        not in " ".join(
            t for c, t in messages.SENTENCES.items() if c != "candidate_not_treatment"
        ).lower()
    )


def test_curated_texts_have_no_forbidden_phrase() -> None:
    """Feature: light-face, Property P3: goal names in five languages, rationales and notes."""
    import csv
    import io

    texts = read_texts()
    for row in csv.DictReader(io.StringIO(texts["goals.csv"])):
        for lang in LANGUAGES:
            assert violations(row[f"label_{lang}"], lang)[0] == [], (row["key"], lang)
    for row in csv.DictReader(io.StringIO(texts["effect_goal_map.csv"])):
        assert violations(row["rationale"], "en")[0] == [], row["term"]
        assert "possible use" not in row["rationale"]
    for row in csv.DictReader(io.StringIO(texts["validation_cases.csv"])):
        assert violations(row["note"], "en")[0] == [], row["id"]
