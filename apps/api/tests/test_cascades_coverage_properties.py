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
    [
        "amlodipin",
        "amlodipine",
        "furosemid",
        "laktuloz",
        "lactulose",
        "xyz",
        "abc def",
        "amlodipine tablet",  # a member name as a whole-word part (P49)
        "xyz lactulose",
        "furosemid abc def",
    ]
)
SOURCES = {"TR": "titck", "US": "openfda_ndc", "EU": "eu_fr_bdpm"}


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
        region = draw(st.sampled_from(["TR", "US", "EU"]))
        src = SOURCES[region]
        published = draw(st.one_of(st.none(), ingredient_codes())) if region == "TR" else None
        homeo = region != "TR" and draw(st.booleans())
        products.append(
            ProductRow(
                src,
                pid,
                region,
                draw(st.sampled_from(TYPES)) if region == "US" else None,
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
            assert set(h["kinds"]) <= {
                "titck_product_code",
                "ambiguous_member",
                "similar_name",
                "member_name_part",
            }
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


@given(rb=rule_bases(), ds=datasets())
def test_p22_eu_bucket_and_the_region_lists(
    rb: RuleBase, ds: tuple[list[ProductRow], list[IngredientRow], list[KeyRow]]
) -> None:
    """Feature: cascade-engine, Property 22 with the EU bucket. Validates: Req 8.1, 8.2.

    EU products are counted in the `EU` bucket only; `members_without_products` names a member
    for each region that has no product of it; `cannot_fire_in` mentions the EU only if the
    dataset holds EU products, and then exactly when a role has no EU product.
    """
    products, rows, keys = ds
    report = build_coverage(rb, products, rows, keys)
    has_eu = any(p.region == "EU" for p in products)
    by_id = {(p.source_id, p.product_id): p for p in products}
    for cid, cls in rb.classes.items():
        got = report["classes"][cid]
        ext = cls.extension_ids
        seen: dict[str, set[str]] = {"TR": set(), "US": set(), "EU": set()}
        eu_products: set[tuple[str, int]] = set()
        for r in rows:
            p = by_id[(r.source_id, r.product_id)]
            if (
                p.homeopathic
                or r.status != "mapped"
                or not any(class_match(c, cls, ext) for c in r.codes)
            ):
                continue
            members = {k.qid for k in keys if any(class_match(c, cls, ext) for c in k.codes)}
            if r.qid not in members:
                continue
            seen[p.region].add(str(r.qid))
            if p.region == "EU":
                eu_products.add((r.source_id, r.product_id))
        assert got["products"]["EU"] == len(eu_products)
        for region in ("TR", "US", "EU"):
            without = {m["qid"] for m in got["members_without_products"][region]}
            assert (
                without
                == {k.qid for k in keys if any(class_match(c, cls, ext) for c in k.codes)}
                - seen[region]
            )
    for entry in report["rules"]:
        assert ("EU" in entry["cannot_fire_in"]) <= has_eu
        if has_eu:
            roles = [c for c in (entry["index_class"], entry["marker_class"]) if c]
            lacking = len(roles) < 2 or any(
                report["classes"][c]["products"]["EU"] == 0 for c in roles
            )
            assert ("EU" in entry["cannot_fire_in"]) == lacking


@given(rb=rule_bases(), ds=datasets())
def test_p49_member_name_part_hints(
    rb: RuleBase, ds: tuple[list[ProductRow], list[IngredientRow], list[KeyRow]]
) -> None:
    """Feature: cascade-engine, Property 49 (drug-resolution design §16.4). Validates: Req 8.7, 8.8.

    An unmapped name (not mapped, not ambiguous, not homeopathic) whose words contain the words
    of a class member's label as a contiguous run (at least five characters, belonging to that
    member only) is hinted with that member; nothing else gets this kind; hints never count as
    matches.
    """
    products, rows, keys = ds
    report = build_coverage(rb, products, rows, keys, top=10_000)
    by_id = {(p.source_id, p.product_id): p for p in products}
    base = build_coverage(rb, products, rows, keys, top=10_000)
    for cid, cls in rb.classes.items():
        ext = cls.extension_ids
        members = [k for k in keys if any(class_match(c, cls, ext) for c in k.codes)]
        owners: dict[tuple[str, ...], set[str]] = {}
        for k in members:
            for n in k.names:
                words = tuple(name_key(n).split())
                if words and len(" ".join(words)) >= 5:
                    owners.setdefault(words, set()).add(k.qid)
        unique = {w: next(iter(q)) for w, q in owners.items() if len(q) == 1}
        expected: dict[str, set[str]] = {}
        for r in rows:
            p = by_id[(r.source_id, r.product_id)]
            if p.homeopathic or r.status != "unmapped":
                continue
            words = tuple(name_key(r.published_name).split())
            hit = {
                unique[words[i:j]]
                for i in range(len(words))
                for j in range(i + 1, len(words) + 1)
                if words[i:j] in unique
            }
            if hit:
                expected.setdefault(name_key(r.published_name), set()).update(hit)
        got = {
            h["name"]: set(h["members"])
            for h in report["classes"][cid]["hints"]
            if "member_name_part" in h["kinds"]
        }
        assert set(got) == set(expected)
        for name, found in got.items():
            assert found & expected[name]  # the longest match is one of the contained members
        assert report["classes"][cid]["products"] == base["classes"][cid]["products"]


def test_member_name_part_examples() -> None:
    """Feature: cascade-engine, Property 49 (examples). `lithium carbonate` finds `lithium`; a
    short name, a shared name, a half word, a mapped, an ambiguous and a homeopathic row do not."""
    cls = AtcClass("mood", (Pattern("N05AN", "include"), Pattern("N06AB", "include")))
    rule = Rule(
        1,
        "s",
        "drug_class",
        "Lithium",
        "Tremor",
        "Remedy",
        "Table 1, row 1",
        "mood",
        "mood",
        None,
        (),
        None,
    )
    rb = RuleBase(
        12, (rule,), {"mood": cls}, AtcClass("abrupt_stop", (Pattern("C07", "include"),)), (), "v"
    )
    keys = [
        KeyRow("Q1", "lithium", ("N05AN01",), ("lithium",)),
        KeyRow("Q2", "iron", ("N05AN02",), ("iron", "sertraline")),
        KeyRow("Q3", "sertralinum", ("N06AB06",), ("sertralinum", "sertraline")),  # shared alias
    ]
    products = [
        ProductRow("openfda_ndc", i, "US", "HUMAN PRESCRIPTION DRUG", None, i == 7)
        for i in range(1, 8)
    ]
    names = [
        ("lithium bioactive", "unmapped"),  # a member name as a whole-word part: hinted
        ("lithiumx tablet", "unmapped"),  # half a word: not hinted
        ("iron sucrose", "unmapped"),  # member name shorter than five characters: not hinted
        ("sertraline forte", "unmapped"),  # alias of two members: not hinted
        ("lithium special", "mapped"),  # mapped: not hinted
        ("lithium plus", "ambiguous"),  # ambiguous: handled by its own hint kind
        ("lithium homeo", "unmapped"),  # homeopathic product: not hinted
    ]
    rows = [
        IngredientRow(
            "openfda_ndc",
            i,
            n,
            status,
            "Q1" if status == "mapped" else None,
            ("Q1", "Q3") if status == "ambiguous" else (),
            ("N05AN01",) if status == "mapped" else (),
        )
        for i, (n, status) in enumerate(names, start=1)
    ]
    report = build_coverage(rb, products, rows, keys, top=100)
    hints = {h["name"]: h["kinds"] for h in report["classes"]["mood"]["hints"]}
    assert "member_name_part" in hints["lithium bioactive"]
    assert all("member_name_part" not in k for n, k in hints.items() if n != "lithium bioactive")
    # other hint kinds (a similar name) may still apply to some of them; this kind may not
    for name in ("lithiumx tablet", "iron sucrose", "sertraline forte", "lithium homeo"):
        assert "member_name_part" not in hints.get(name, [])
    assert "lithium homeo" not in hints  # a homeopathic product is never hinted at all
    assert hints["lithium plus"] == ["ambiguous_member"]
