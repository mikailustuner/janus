# ruff: noqa: E501 - synthetic frames on one line each
"""Expert validation packet tools (plan E): the sampler (protocol sections 4-5) and the scorer
(sections 6-7), on the committed inputs and on synthetic private frames and answers."""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from janus_pipelines.expert_validation import make_experts, read_answer_file, write_csv

TOOLS = Path(__file__).resolve().parents[1] / "tools"
REPO = Path(__file__).resolve().parents[2]


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses look their module up
    spec.loader.exec_module(mod)
    return mod


S = load("validation_packet_sample")
SC = load("score_validation_packet")


def read(path: str) -> list[dict[str, str]]:
    with (REPO / path).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def flagged() -> dict[str, bool | None]:
    out: dict[str, bool | None] = {}
    for f in ("pairs_positive", "pairs_negative"):
        for p in json.loads((REPO / f"data/validation/cascades/results/{f}.json").read_text()):
            out[p["id"]] = None if p.get("error") else bool(p["flagged"])
    return out


def a1() -> list[Any]:
    return S.draw_a1(
        read("data/validation/cascades/positive_pairs.csv"),
        read("data/validation/cascades/negative_pairs.csv"),
        flagged(),
    )


def b_items() -> list[Any]:
    web = {
        lg: json.loads((REPO / f"apps/web/messages/{lg}.json").read_text()) for lg in ("en", "tr")
    }
    note = {r["id"]: r for r in read("apps/api/janus/notes/glossary/sentences.csv")}
    return S.texts_b(web, note)


def a2() -> list[Any]:
    return S.draw_a2(
        read("data/cascade_classes.csv"), read("data/pipc_rules.csv"), read("data/pipc.csv")
    )


# ---------------------------------------------------------------- synthetic private frames


def release_frame() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for src, studies, per in (
        ("clinicaltrials_gov", 40, 4),
        ("pmc_oa", 12, 3),
        ("drugsatfda_review", 8, 3),
    ):
        for s in range(studies):
            study = {
                "clinicaltrials_gov": f"NCT{s:08d}",
                "pmc_oa": f"PMC{s:07d}",
                "drugsatfda_review": f"FDA {s}",
            }[src]
            for v in range(per):
                loc = (
                    f"https://www.accessdata.fda.gov/x{s}.pdf page 3"
                    if src == "drugsatfda_review"
                    else f"{study} table 1, row {v}"
                )
                rows.append({"source_id": src, "study_id": study, "source_locator": loc, "parameter": "cmax",
                             "analyte": "d", "value": float(10 + v), "unit": "ng/mL", "drug_key": f"drug{s}",
                             "quote": "q"})  # fmt: skip
                if src != "clinicaltrials_gov":
                    rows[-1] |= {
                        "frame": "P2" if src == "pmc_oa" else "D2",
                        "automated_verdicts": ["correct", "incorrect"],
                    }
    return rows


def atlas() -> list[dict[str, Any]]:
    return [{"row": f"OA-{i:03d}", "drug": f"drug {i}", "quote": "label text", "cut": False, "numeric": True,
             "measure": "AUC", "kind": "pct", "measure_ratio": "1.3", "measure_change": "30% higher",
             "atlas_ratio": "1.3", "atlas_change": "30% higher", "flags": ["known problem"],
             "set_id": "abc", "version": "1"} for i in range(80)]  # fmt: skip


def forms() -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    ca_it = [{"source_id": src, "published_form": f"FORM {i}", "route": "ORAL", "group": "oral_solid" if i % 5 else "",
              "evidence_examples": "X; Y", "confidence": "high", "rule": "r", "n_products": "3"}
             for src in ("ca_dpd", "eu_it_aifa") for i in range(60)]  # fmt: skip
    es = [{"form": f"COMPRIMIDO {i}", "route": "*", "routes_seen": "VÍA ORAL (1)", "n": 1,
           "group": "oral_solid" if i % 4 else "", "reason": "r"} for i in range(60)]  # fmt: skip
    return ca_it, es


def method20() -> list[dict[str, Any]]:
    return [{"key": f"drug{i}", "name": f"drug{i}", "status": "not_validated", "reasons": ["no_independent_observation"],
             "params": [{"name": "cl", "label": "CL/F", "value": 1.0, "unit": "L/h", "cls": "A", "n_studies": 2}],
             "points": []} for i in range(20)]  # fmt: skip


def full_draw() -> Any:
    d = S.Draw()
    d.items["A1"] = a1()
    d.items["A2"] = a2()
    d.items["B"] = b_items()
    d.items["C1"] = S.draw_c1(release_frame(), {})
    d.items["C2"] = S.draw_c2(release_frame())
    d.items["D"] = S.draw_d(atlas())
    ca_it, es = forms()
    d.items["E"] = S.draw_e(ca_it, es)
    d.items["F"] = S.all_f(method20())
    for s in list(d.items):
        d.items[s] = S.ordered(s, d.items[s])
    return d


@pytest.fixture
def packet(tmp_path: Path) -> Path:
    out = tmp_path / "packet"
    S.write(out, full_draw(), make_experts({"pharmacologist": 2, "clinician": 2, "pharmacist": 2}))
    return out


# ---------------------------------------------------------------- sampler


def test_counts_per_section_match_the_protocol() -> None:
    d = full_draw()
    got = {s: len(v) for s, v in d.items.items()}
    assert got == {"A1": 100, "A2": 40, "B": 50, "C1": 50, "C2": 20, "D": 24, "E": 90, "F": 20}
    refs = [it.key["reference"] for it in d.items["A1"]]
    assert refs.count("positive") == 60 and refs.count("negative") == 40
    assert [it.language for it in d.items["B"]].count("tr") == 25
    srcs = [it.key["source"] for it in d.items["C1"]]
    assert (
        srcs.count("clinicaltrials_gov"),
        srcs.count("pmc_oa"),
        srcs.count("drugsatfda_review"),
    ) == (30, 10, 10)
    studies = [it.key["study"] for it in d.items["C1"]]
    assert max(studies.count(s) for s in set(studies)) <= 2
    assert sorted({it.key["country"] for it in d.items["E"]}) == ["CA", "ES", "IT"]
    assert all(it.show["group"] for it in d.items["E"])
    assert all(r["match"] == "include" for r in read("data/cascade_classes.csv")
               if f"{r['class_id']}: {r['pattern']}" in {it.label for it in d.items["A2"]})  # fmt: skip


def test_sampling_is_deterministic_with_the_seed() -> None:
    one, two = full_draw(), full_draw()
    for s in one.items:
        assert [(i.item_id, i.label) for i in one.items[s]] == [
            (i.item_id, i.label) for i in two.items[s]
        ]
    # positives and negatives are mixed in one order
    refs = [it.key["reference"] for it in one.items["A1"]]
    assert refs[:60].count("negative") > 0


def test_a_short_frame_stops_the_draw() -> None:
    small = [
        r for r in release_frame() if r["source_id"] != "pmc_oa" or r["study_id"] < "PMC0000002"
    ]
    with pytest.raises(S.ShortfallError, match="C1 pmc_oa: needs 10 values"):
        S.draw_c1(small, {})
    with pytest.raises(S.ShortfallError, match="C2 pmc_oa"):
        S.draw_c2(small)


def test_c1_keeps_the_b3a_verdicts_in_the_key_only() -> None:
    d = full_draw()
    b3a = [it for it in d.items["C1"] if it.key["source"] != "clinicaltrials_gov"]
    assert len(b3a) == 20 and all(
        it.key["automated_verdicts"] == ["correct", "incorrect"] for it in b3a
    )
    assert {it.key["frame"] for it in b3a} == {"P2", "D2"}
    assert not any("automated_verdicts" in it.show or "frame" in it.show for it in d.items["C1"])


def test_c2_alternates_sources_each_in_its_own_order() -> None:
    d = full_draw()
    assert [it.key["source"] for it in d.items["C2"]] == ["clinicaltrials_gov", "pmc_oa"] * 10
    # one source's order does not depend on the other source's documents
    extra = [r | {"study_id": "PMC9999999"} for r in release_frame() if r["source_id"] == "pmc_oa"][
        :3
    ]
    one = S.ordered("C2", S.draw_c2(release_frame()))
    two = S.ordered("C2", S.draw_c2(release_frame() + extra))
    ct = [i.label for i in one if i.key["source"] == "clinicaltrials_gov"]
    assert ct == [i.label for i in two if i.key["source"] == "clinicaltrials_gov"]


BLINDED_KEYS = {"reference", "b1_flagged", "pair_id", "from_pair_id", "sources", "confidence", "rule", "flags",
                "numeric", "classes", "cls", "automated_verdicts", "stratum", "level", "confirmed", "reason",
                "frame", "band"}  # fmt: skip


def all_keys(o: Any) -> set[str]:
    if isinstance(o, dict):
        d = cast(dict[str, Any], o)
        return set(d) | {k for v in d.values() for k in all_keys(v)}
    if isinstance(o, list):
        return {k for v in cast(list[Any], o) for k in all_keys(v)}
    return set()


def test_nothing_blinded_reaches_an_expert(packet: Path) -> None:
    items = json.loads((packet / "items.json").read_text())
    assert not all_keys(items) & BLINDED_KEYS
    seen = (packet / "items.json").read_text().lower()
    for f in (packet / "answers").glob("*.csv"):
        seen += f.read_text().lower()
    assert "probable" not in seen and "possible" not in seen and "positive" not in seen
    assert not re.search(r"\b[pn]\d{3}\b", seen)  # reference pair identifiers
    srcs = {
        s
        for r in read("data/validation/cascades/positive_pairs.csv")
        for s in r["sources"].split(";")
    }
    assert not any(
        re.search(rf"\b{re.escape(s.strip().lower())}\b", seen) for s in srcs if s.strip()
    )
    from openpyxl import load_workbook

    for f in (packet / "answers").glob("*.xlsx"):
        wb = load_workbook(f, read_only=True)
        text = " ".join(
            str(c) for ws in wb for row in ws.iter_rows(values_only=True) for c in row if c
        )
        assert "positive" not in text.lower() and "probable" not in text.lower()


def test_each_answer_file_holds_only_its_experts_items(packet: Path) -> None:
    mapping = json.loads((packet / "mapping.json").read_text())
    assert not {"name", "email", "e-mail"} & all_keys(mapping)
    for e in mapping["experts"]:
        rows = read_answer_file(packet / "answers" / f"{e['id']}.csv")
        assert {r["expert_id"] for r in rows} == {e["id"]}
        assert sorted(r["item_id"] for r in rows) == sorted(
            i for v in e["item_ids"].values() for i in v
        )
    assert mapping["experts"][0]["minutes"] == 50 + 48 + 60 + 60  # C1 + C2 (6 x 8) + D + F


# ---------------------------------------------------------------- scorer


def fill(packet: Path, tmp: Path, answer: Any) -> list[Path]:
    """Answer files filled by `answer(expert, row) -> dict` (C2: a list of dicts)."""
    out: list[Path] = []
    for f in sorted((packet / "answers").glob("*.csv")):
        rows = read_answer_file(f)
        filled: list[dict[str, str]] = []
        for r in rows:
            a = answer(r["expert_id"], r)
            many = (
                cast(list[dict[str, str]], a) if isinstance(a, list) else [cast(dict[str, str], a)]
            )
            filled += [r | x for x in many]
        p = tmp / f.name
        write_csv(p, filled, list(rows[0]) + sorted({k for r in filled for k in r} - set(rows[0])))
        out.append(p)
    return out


def all_agree(expert: str, r: dict[str, str]) -> Any:
    answers: dict[str, Any] = {"A1": {"realistic": "5"}, "A2": {"describes_class": "yes"},
            "B": {"accuracy": "4", "harm": "1", "clarity": "4"}, "C1": {"verdict": "correct"},
            "C2": [], "D": {"says_label": "yes", "direction": "yes"}, "E": {"decision": "accept"},
            "F": {"method_sound": "yes", "status_justified": "yes"}}  # fmt: skip
    return answers[r["section"]]


def test_score_known_results(packet: Path, tmp_path: Path) -> None:
    """Everyone says realistic (5) and correct: positives 60/60 realistic, negatives 0/40 not
    realistic; kappa undefined (no variation); C1 precision 1 per source with the B3a fields."""
    res = SC.score(packet, fill(packet, tmp_path, all_agree))
    p = res["A1"]["primary"]
    assert p["positives_called_realistic"]["k"] == 60 and p["positives_called_realistic"]["n"] == 60
    assert p["negatives_called_not_realistic"]["k"] == 0
    assert p["positives_called_realistic"]["wilson"][0] == pytest.approx(0.9398, abs=1e-3)
    c1 = res["C1"]["primary"]["tier2_precision_by_source"]["clinicaltrials_gov"]
    assert c1["precision"] == 1.0 and c1["n"] == 30 and "cluster_lower" in c1
    assert c1["decides_shipping"] is True
    pmc = res["C1"]["primary"]["tier2_precision_by_source"]["pmc_oa"]
    assert pmc["n"] == 10 and pmc["decides_shipping"] is False
    # tier 1: the automated passes disagree on every B3a value, so no pair enters kappa
    assert res["C1"]["secondary"]["tier1_agreement_with_expert_consensus"]["n"] == 0
    assert res["E"]["primary"]["CA"]["accept"] == 30
    assert res["agreement"]["A1"]["realistic"][0]["kappa"] is None
    assert res["needs_third_expert"] == []
    assert res["dropped"] == {"C2": 14}


def test_score_kappa_consensus_and_third_expert(packet: Path, tmp_path: Path) -> None:
    mapping = json.loads((packet / "mapping.json").read_text())
    first = {i: ids[0] for i, ids in mapping["assignment"]["A2"].items()}
    a2_ids = sorted(first)

    def answer(expert: str, r: dict[str, str]) -> Any:
        if r["section"] != "A2":
            return all_agree(expert, r)
        n = a2_ids.index(r["item_id"])
        if expert == first[r["item_id"]]:
            return {"describes_class": "yes" if n % 2 else "no"}
        return {"describes_class": "yes" if n % 4 in (1, 2) else "no"}  # agrees on half the rows

    res = SC.score(packet, fill(packet, tmp_path, answer))
    kap = res["agreement"]["A2"]["describes_class"]
    assert sum(k["n"] for k in kap) == 40
    assert all(k["kappa"] == pytest.approx(0.0, abs=0.25) for k in kap)
    assert res["consensus"]["A2"]["describes_class"] == {
        "agreed": 20,
        "third": 0,
        "not_settled": 20,
    }
    needs = [n for n in res["needs_third_expert"] if n["section"] == "A2"]
    assert len(needs) == 20 and all(len(n["eligible_third_experts"]) == 2 for n in needs)
    # a third expert answers one of them: it is settled by the third answer
    t = needs[0]
    third = t["eligible_third_experts"][0]
    extra = tmp_path / "third.csv"
    write_csv(extra, [{"expert_id": third, "section": "A2", "item_id": t["item_id"], "describes_class": "yes"}],
              ["expert_id", "section", "item_id", "describes_class"])  # fmt: skip
    res2 = SC.score(packet, [*fill(packet, tmp_path, answer), extra])
    assert res2["consensus"]["A2"]["describes_class"] == {
        "agreed": 20,
        "third": 1,
        "not_settled": 19,
    }


def test_score_c2_recall(packet: Path, tmp_path: Path) -> None:
    key = json.loads((packet / "key.json").read_text())

    def answer(expert: str, r: dict[str, str]) -> Any:
        if r["section"] != "C2":
            return all_agree(expert, r)
        conf = key["C2"][r["item_id"]]["confirmed"]
        marks = [
            {"drug": c["drug"], "parameter": c["parameter"], "value": str(c["value"])} for c in conf
        ]
        return [
            *marks,
            {"drug": "other", "parameter": "tmax", "value": "2"},
        ]  # one value the readers missed

    res = SC.score(packet, fill(packet, tmp_path, answer))
    rec = res["C2"]["primary"]["recall_by_source"]
    docs = res["judged"]["C2"]
    assert sum(v["documents"] for v in rec.values()) == docs == 6
    for v in rec.values():
        assert (
            v["k"] == v["n"] - v["documents"]
        )  # every confirmed value found, one miss per document
    assert sum(res["C2"]["secondary"]["kinds_missed"][s]["tmax"] for s in rec) == 6


def test_score_rejects_bad_files(packet: Path, tmp_path: Path) -> None:
    good = fill(packet, tmp_path, all_agree)
    rows = read_answer_file(good[0])
    bad = tmp_path / "bad.csv"
    write_csv(bad, [rows[0] | {"verdict": "maybe"}], list(rows[0]))
    with pytest.raises(ValueError, match="verdict must be one of"):
        SC.score(packet, [bad])
    write_csv(bad, [rows[0] | {"verdict": "incorrect", "error": ""}], list(rows[0]))
    with pytest.raises(ValueError, match="error type"):
        SC.score(packet, [bad])
    write_csv(bad, [rows[0] | {"section": "A1", "item_id": "A1-001"}], list(rows[0]))
    with pytest.raises(ValueError, match="not in the groups"):
        SC.score(packet, [bad])


def test_synthetic_fill_passes_the_scorer(packet: Path, tmp_path: Path) -> None:
    files = SC.synthetic_fill(packet, tmp_path / "fill")
    assert len(files) == 6
    res = SC.score(packet, files)
    assert set(res) >= {"A1", "A2", "B", "C1", "C2", "D", "E", "F", "agreement"}
