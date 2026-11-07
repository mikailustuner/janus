"""Property P22 and examples for the PIPC coverage report (cascade-engine design §7; task 12)."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.cascades.coverage import (
    BUCKETS,
    IngredientRow,
    KeyRow,
    ProductRow,
    bucket,
    build_coverage,
    name_key,
    trigram_similarity,
)
from janus.cascades.model import AtcClass, Pattern, Rule, RuleBase
from janus.cascades.patterns import class_match
from janus.cascades.report import REPO, OutputPathError, check_output_path
from tests.cascades_strategies import QIDS, ingredient_codes, rule_bases

TYPES = ["HUMAN PRESCRIPTION DRUG", "HUMAN OTC DRUG", "BULK INGREDIENT"]
NAMES = st.sampled_from(
    ["amlodipin", "amlodipine", "furosemid", "laktuloz", "lactulose", "xyz", "abc def"]
)


@st.composite
def datasets(draw: st.DrawFn) -> tuple[list[ProductRow], list[IngredientRow], list[KeyRow]]:
    keys = [
        KeyRow(
            q,
            None,
            tuple(sorted(set(draw(st.lists(ingredient_codes(), min_size=1, max_size=3))))),
            (draw(NAMES),),
        )
        for q in QIDS
    ]
    products: list[ProductRow] = []
    rows: list[IngredientRow] = []
    for pid in range(draw(st.integers(0, 12))):
        region = draw(st.sampled_from(["TR", "US"]))
        src = "titck" if region == "TR" else "openfda_ndc"
        published = draw(st.one_of(st.none(), ingredient_codes())) if region == "TR" else None
        homeo = region == "US" and draw(st.booleans())
        products.append(
            ProductRow(
                src,
                pid,
                region,
                None if region == "TR" else draw(st.sampled_from(TYPES)),
                published,
                homeo,
            )
        )
        for _ in range(draw(st.integers(1, 3))):
            status = draw(st.sampled_from(["mapped", "mapped", "unmapped", "ambiguous"]))
            if status == "mapped":
                k = draw(st.sampled_from(keys))
                rows.append(IngredientRow(src, pid, draw(NAMES), status, k.qid, (), k.codes))
            elif status == "ambiguous":
                cands = tuple(sorted(draw(st.sets(st.sampled_from(QIDS), min_size=2, max_size=3))))
                rows.append(IngredientRow(src, pid, draw(NAMES), status, None, cands, ()))
            else:
                rows.append(IngredientRow(src, pid, draw(NAMES), status, None, (), ()))
    return products, rows, keys


@given(rb=rule_bases(), ds=datasets())
def test_p22_honest_coverage(
    rb: RuleBase, ds: tuple[list[ProductRow], list[IngredientRow], list[KeyRow]]
) -> None:
    """Feature: cascade-engine, Property 22. Validates: Req 8.1-8.4.

    Member, product and OTC counts equal an independent recount with `class_match`; hints come
    only from non-mapped rows and are ranked by product count.
    """
    products, rows, keys = ds
    report = build_coverage(rb, products, rows, keys)
    by_id = {(p.source_id, p.product_id): p for p in products}
    non_mapped_live = {
        name_key(r.published_name)
        for r in rows
        if r.status != "mapped" and not by_id[(r.source_id, r.product_id)].homeopathic
    }
    for cid, cls in rb.classes.items():
        got = report["classes"][cid]
        ext = cls.extension_ids
        members = {k.qid for k in keys if any(class_match(c, cls, ext) for c in k.codes)}
        assert got["members"] == len(members)
        recount: dict[str, set[tuple[str, int]]] = {b: set() for b in BUCKETS}
        for r in rows:
            if (
                not by_id[(r.source_id, r.product_id)].homeopathic
                and r.status == "mapped"
                and r.qid in members
                and any(class_match(c, cls, ext) for c in r.codes)
            ):
                p = by_id[(r.source_id, r.product_id)]
                recount[bucket(p)].add((r.source_id, r.product_id))
        assert got["products"] == {b: len(v) for b, v in recount.items()}
        rx, otc = len(recount["US_RX"]), len(recount["US_OTC"])
        assert got["otc_share"] == (None if rx + otc == 0 else round(otc / (rx + otc), 4))
        totals = [h["total"] for h in got["hints"]]
        assert totals == sorted(totals, reverse=True)
        for h in got["hints"]:
            assert h["name"] in non_mapped_live
            assert set(h["kinds"]) <= {"titck_product_code", "ambiguous_member", "similar_name"}
    for r in report["rules"]:
        assert r["matchable"] == (r["unmatchable"] is None)


@given(a=st.text(max_size=20), b=st.text(max_size=20))
def test_p22_trigram_similarity(a: str, b: str) -> None:
    """Feature: cascade-engine, Property 22. Validates: Req 8.2 (similar-name hints)."""
    s = trigram_similarity(a, b)
    assert 0.0 <= s <= 1.0
    assert s == trigram_similarity(b, a)
    if any(ch.isalnum() for ch in name_key(a)):
        assert trigram_similarity(a, a) == 1.0


def test_combination_code_gives_a_hint_never_a_finding() -> None:
    """A published combination code hints at its group (report only). Req 8.2, 8.3."""
    acei = AtcClass("acei", (Pattern("C09", "include"),))
    rule = Rule(
        1,
        "s",
        "drug_class",
        "ACE inhibitor",
        "Cough",
        "Cough remedy",
        "Table 1, row 1",
        "acei",
        "acei",
        None,
        (),
        None,
    )
    rb = RuleBase(
        12, (rule,), {"acei": acei}, AtcClass("abrupt_stop", (Pattern("C07", "include"),)), (), "v"
    )
    products = [ProductRow("titck", 1, "TR", None, "C09BB03")]
    rows = [IngredientRow("titck", 1, "lisinoprilx dihidrat", "unmapped", None, (), ())]
    report = build_coverage(
        rb, products, rows, [KeyRow("Q1", "lisinopril", ("C09AA03",), ("lisinopril",))]
    )
    (hint,) = report["classes"]["acei"]["hints"]
    assert "titck_product_code" in hint["kinds"] and hint["products"]["TR"] == 1
    assert report["classes"]["acei"]["products"]["TR"] == 0  # hints never count as matches


def test_output_path_guard() -> None:
    """The report never lands in a tracked path of the repository. Req 8.5."""
    with pytest.raises(OutputPathError):
        check_output_path(REPO / "apps" / "api" / "coverage.json")
    assert check_output_path(REPO / ".data" / "cascades" / "x.json").name == "x.json"
    assert (
        check_output_path(Path("/nonexistent-janus/coverage-test.json")).name
        == "coverage-test.json"
    )
