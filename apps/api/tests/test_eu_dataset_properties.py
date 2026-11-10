"""Properties of the EU part of the prepared dataset (drug-resolution tasks 22.2-22.8).

P41 homeopathic products, P42 French route selection, P43 Nomenclátor published ATC, P44 (pure
part) the Phase 1 invariants over French and Spanish sources, P45 coverage recount, P46 the
dataset version, P47 (gather part) optional sources. Synthetic data only.
"""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.regions.base import GS1_PREFIXES, PrefixRow
from janus.resolution import load as load_module
from janus.resolution import name_lists
from janus.resolution.anion_acid import AnionAcidTable
from janus.resolution.atc import CombinationCheck, RouteMap, is_ingredient_level
from janus.resolution.load import LoadError, gather, missing_sources
from janus.resolution.prepare import PreparedDataset, prepare_dataset
from janus.resolution.prepare_eu import (
    ES_CIMA,
    FR_BDPM,
    bdpm_ingredients,
    cima_ingredients,
    is_homeopathic_name,
)
from tests.resolution_db import artifact, inputs
from tests.resolution_strategies import (
    HOMEOPATHIC_SUFFIX,
    ROUTES,
    RULES,
    bdpm_row,
    cima_row,
    eu_rows,
    sources,
    wikidata_row,
)

type Src = tuple[list[Any], list[Any], list[Any]]
type Eu = tuple[list[Any], list[Any]]


def _prepare(src: Src, eu: Eu | None = None, **kw: Any) -> PreparedDataset:
    tr, us, wd = src
    fr, es = eu if eu is not None else (None, None)
    return prepare_dataset(tr, us, wd, RULES, ROUTES, fr_rows=fr, es_rows=es, **kw)


# --- P44 (pure part): the Phase 1 invariants hold with French and Spanish sources ------------


@given(src=sources(), eu=eu_rows())
def test_p44_invariants_over_french_and_spanish_sources(src: Src, eu: Eu) -> None:
    """Feature: drug-resolution, Property P44 (pure part: P5, P7, P17, P18).
    Validates Req 5.1, 5.2, 5.4, 5.8-5.10.

    No ingredient of any product carries a combination code; every code belongs to its key;
    every non-mapped entry has a reason or its candidate keys; every EU product keeps one entry
    per published ingredient, in published order.
    """
    ds = _prepare(src, eu)
    combo = set(ds.combination_audit)
    base = CombinationCheck(RULES)
    for p in ds.products:
        for ing in p.ingredients:
            for code in ing.rule_input():
                assert code not in combo and not base.is_combination(code)
                assert is_ingredient_level(code)
            if ing.reason == "possible_unsplit_combination":
                assert ing.atc == ()
            if ing.status == "mapped":
                assert ing.qid and ing.atc and ing.reason is None
                own = {a.code for a in ds.ingredients[ing.qid].ingredient_atc}
                assert {a.code for a in ing.atc} <= own
            else:
                assert ing.rule_input() == ()
                if ing.status == "ambiguous":
                    assert len(ing.key_candidates) >= 2
                else:
                    assert ing.reason is not None
    fr, es = eu
    fr_products = {p.product_name: p for p in ds.products if p.source_id == FR_BDPM}
    assert len(fr_products) == len(fr)
    for row in fr:
        got = [i.published_name for i in fr_products[row["denomination"]].ingredients]
        want, _ = bdpm_ingredients(row["composition"])
        assert got == [w.name for w in want]
    es_products = {p.brand_name: p for p in ds.products if p.source_id == ES_CIMA}
    assert len(es_products) == len(es)
    for row in es:
        got = [i.published_name for i in es_products[row["name"]].ingredients]
        assert got == [w.name for w in cima_ingredients(row["ingredients"])]
        assert [i.position for i in es_products[row["name"]].ingredients] == list(range(len(got)))


@given(src=sources(), eu=eu_rows())
def test_p44_french_rows_change_nothing_for_tr_and_us(src: Src, eu: Eu) -> None:
    """Feature: drug-resolution, Property P44. BDPM rows carry no published ATC code and feed no
    ingredient evidence: the Turkish and US products, the ingredient records and the combination
    audit are the same with and without them (only the name entries grow)."""
    fr, _ = eu
    without = _prepare(src)
    with_fr = _prepare(src, (fr, []))  # an empty Nomenclátor list: no products, no evidence
    tr_us = [p for p in with_fr.products if p.region != "EU"]
    assert tr_us == list(without.products)
    assert with_fr.ingredients == without.ingredients
    assert with_fr.combination_audit == without.combination_audit
    assert set(without.names) <= set(with_fr.names)


@given(src=sources(), eu=eu_rows())
def test_p44_nomenclator_adds_only_combination_evidence(src: Src, eu: Eu) -> None:
    """Feature: drug-resolution, Property P44 (DP34). A Nomenclátor product can only make the
    combination check stricter: no ingredient gains a code, and the ingredient records of the
    other sources keep at most the codes they had."""
    _, es = eu
    without = _prepare(src)
    with_es = _prepare(src, ([], es))
    for qid, record in with_es.ingredients.items():
        assert {a.code for a in record.ingredient_atc} <= {
            a.code for a in without.ingredients[qid].ingredient_atc
        }
    older = [p for p in with_es.products if p.region != "EU"]
    for new, old in zip(older, without.products, strict=True):
        for n, o in zip(new.ingredients, old.ingredients, strict=True):
            assert {a.code for a in n.atc} <= {a.code for a in o.atc}


# --- P41: French homeopathic products ---------------------------------------------------------


@given(src=sources(), eu=eu_rows())
def test_p41_homeopathic_products_are_findable_but_not_counted(src: Src, eu: Eu) -> None:
    """Feature: drug-resolution, Property P41. Validates Req 12.10, 5.11, 11.1.

    A presentation with a substance name that carries the homeopathic marker stays a product
    (findable by name) and is left out of the coverage section, which says how many.
    """
    fr, _ = eu
    ds = _prepare(src, (fr, []))
    homeopathic = [
        r
        for r in fr
        if any(is_homeopathic_name(i.name) for i in bdpm_ingredients(r["composition"])[0])
    ]
    products = [p for p in ds.products if p.source_id == FR_BDPM]
    assert len(products) == len(fr)
    names = {(n.kind, n.region, n.display) for n in ds.names}
    for r in fr:
        assert ("product", "EU", r["denomination"]) in names
    if products:
        cov = ds.coverage[FR_BDPM]
        assert cov["homeopathic_presentations_left_out"] == len(homeopathic)
        assert cov["products"] == len(fr) - len(homeopathic)
    else:
        assert FR_BDPM not in ds.coverage


def test_p41_example_marker_with_and_without_accents() -> None:
    wd = [wikidata_row("Q1", ["A02AA01"], {"en": "alfazin"})]
    fr = [
        bdpm_row(1, "HOMEO", ["arnica" + HOMEOPATHIC_SUFFIX]),
        bdpm_row(2, "HOMEO 2", ["ARNICA POUR PREPARATIONS HOMEOPATHIQUES"]),
        bdpm_row(3, "PLAIN", ["alfazin"]),
    ]
    ds = prepare_dataset([], [], wd, RULES, ROUTES, fr_rows=fr)
    cov = ds.coverage[FR_BDPM]
    assert (cov["products"], cov["homeopathic_presentations_left_out"]) == (1, 2)
    assert cov["products_fully_mapped"] == 1 and cov["occurrences_mapped_share"] == 1.0


# --- P42: French route selection --------------------------------------------------------------

FR_ROUTE_PREFIXES = {"orale": "ACJN", "cutanée": "D", "intraveineuse": "J"}
CODE_POOL = ["A02AA01", "C03AA01", "D07AA01", "J01AA01", "N02AA01", "R03AA01"]


@given(
    codes=st.lists(st.sampled_from(CODE_POOL), min_size=1, max_size=4, unique=True),
    routes=st.lists(
        st.sampled_from(["orale", "cutanée", "intraveineuse", "voie inconnue"]), max_size=3
    ),
)
def test_p42_french_route_selection(codes: list[str], routes: list[str]) -> None:
    """Feature: drug-resolution, Property P42. Validates Req 5.9.

    A BDPM product has no published ATC code: the ingredient's codes are selected by the mapped
    routes of the `routes` text (split at `;`); a route string that is not in the map counts as
    unmapped; no mapped route keeps all codes; no code allowed for the mapped routes leaves the
    ingredient unmapped with `no_ingredient_atc_for_route`.
    """
    wd = [wikidata_row("Q1", codes, {"en": "alfazin"})]
    fr = [bdpm_row(1, "P", ["alfazin"], routes=";".join(routes) or None)]
    ds = prepare_dataset([], [], wd, RULES, ROUTES, fr_rows=fr)
    (ing,) = ds.products[0].ingredients
    mapped = [r for r in routes if r in FR_ROUTE_PREFIXES]
    letters = {c for r in mapped for c in FR_ROUTE_PREFIXES[r]}
    if not mapped:
        assert ing.atc_selection == "all_codes"
        assert {a.code for a in ing.atc} == set(codes)
    elif any(c[0] in letters for c in codes):
        assert ing.atc_selection == "route_group"
        assert {a.code for a in ing.atc} == {c for c in codes if c[0] in letters}
    else:
        assert ing.status == "unmapped" and ing.reason == "no_ingredient_atc_for_route"
        assert ing.rule_input() == ()


def test_p42_routes_are_split_trimmed_and_exact() -> None:
    wd = [wikidata_row("Q1", ["A02AA01", "D07AA01"], {"en": "alfazin"})]
    fr = [bdpm_row(1, "P", ["alfazin"], routes="orale ; ")]
    (ing,) = prepare_dataset([], [], wd, RULES, ROUTES, fr_rows=fr).products[0].ingredients
    assert [a.code for a in ing.atc] == ["A02AA01"] and ing.atc_selection == "route_group"
    # the match is exact: a differently written route is not the mapped one
    fr = [bdpm_row(1, "P", ["alfazin"], routes="ORALE")]
    (ing,) = prepare_dataset([], [], wd, RULES, ROUTES, fr_rows=fr).products[0].ingredients
    assert ing.atc_selection == "all_codes"


# --- P43: Nomenclátor published ATC code ------------------------------------------------------


@given(
    codes=st.lists(st.sampled_from(CODE_POOL), min_size=1, max_size=4, unique=True),
    published=st.one_of(
        st.none(),
        st.sampled_from(
            [*CODE_POOL, "C03AB01", "D07BA01", "B05AA01", "C09BB03", "A10BD07", "J01CA51"]
        ),
    ),
)
def test_p43_nomenclator_published_code(codes: list[str], published: str | None) -> None:
    """Feature: drug-resolution, Property P43. Validates Req 5.10, 5.2.

    The published code is the product code `p` of design §5.5 for a single-ingredient
    presentation: it selects its own code (cited to the Nomenclátor presentation), else the
    codes of its therapeutic or anatomical group. A combination code there is display only.
    The presentation adds no code to the ingredient (DP34).
    """
    wd = [wikidata_row("Q1", codes, {"en": "alfazin"})]
    es = [cima_row(1, "MED", ["alfazin"], published)]
    ds = prepare_dataset([], [], wd, RULES, ROUTES, es_rows=es)
    (ing,) = ds.products[0].ingredients
    assert {a.code for a in ds.ingredients["Q1"].ingredient_atc} == set(codes)
    emitted = {a.code for a in ing.atc}
    assert emitted <= set(codes)
    check = CombinationCheck(RULES)
    if published is None:
        assert ing.atc_selection == "all_codes" and emitted == set(codes)
    elif published in codes:
        assert ing.atc_selection == "single_ingredient_product" and emitted == {published}
        (cited,) = ing.atc
        assert (cited.source_id, cited.product_ref) == (ES_CIMA, "EU:eu_es_cima:1")
    elif check.is_combination(published):
        assert published not in emitted and ing.atc_selection != "single_ingredient_product"
    else:
        group = [c for c in codes if c[:3] == published[:3]]
        anatomical = [c for c in codes if c[0] == published[0]]
        want = group or anatomical or codes
        assert emitted == set(want)


# --- P45: coverage recount for the EU sections ------------------------------------------------


@given(src=sources(), eu=eu_rows())
def test_p45_eu_coverage_equals_an_independent_recount(src: Src, eu: Eu) -> None:
    """Feature: drug-resolution, Property P45 (recount). Validates Req 13.2.

    The `eu_fr_bdpm` and `eu_es_cima` sections count the ingredient entries of the loaded
    products, leave out homeopathic BDPM presentations, and exist only when there are products.
    """
    fr, es = eu
    ds = _prepare(src, eu)
    for source, rows in ((FR_BDPM, fr), (ES_CIMA, es)):
        products = [p for p in ds.products if p.source_id == source]
        if source == FR_BDPM:
            products = [
                p
                for p in products
                if not any(is_homeopathic_name(i.published_name) for i in p.ingredients)
            ]
        if not rows:
            assert source not in ds.coverage
            continue
        cov = ds.coverage[source]
        entries = [i for p in products for i in p.ingredients]
        with_ings = [p for p in products if p.ingredients]
        assert cov["products"] == len(products)
        assert cov["occurrences"] == len(entries)
        assert cov["occurrences_mapped"] == sum(1 for i in entries if i.status == "mapped")
        assert cov["products_with_ingredients"] == len(with_ings)
        assert cov["products_fully_mapped"] == sum(
            1 for p in with_ings if all(i.status == "mapped" for i in p.ingredients)
        )
        assert cov["distinct_names"] == len({i.published_name for i in entries})
        assert "unmapped_top" in cov  # local report only; the loader strips it before storing


# --- P46: the dataset version follows every Phase 2 input -------------------------------------


def _inp(**kw: Any) -> load_module.Inputs:
    wd = [wikidata_row("Q1", ["A02AA01"], {"en": "alfazin"})]
    return inputs(
        [],
        [],
        wd,
        fr=[bdpm_row(1, "P", ["alfazin"])],
        es=[cima_row(1, "M", ["alfazin"], None)],
        **kw,
    )


def test_p46_version_follows_every_phase2_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: drug-resolution, Property P46. Validates Req 9.8, 9.4.

    The same inputs give the same version whatever the run ids; each of these changes it: an
    EU source's content or its absence, the route map, the anion-acid table, a language word list,
    a connector list, a switch, the synonyms and the country table.
    """
    base = _inp()
    version = base.dataset_version()
    assert _inp(run="another-run").dataset_version() == version

    versions = {"base": version}

    def check(label: str, value: str) -> None:
        assert value != version, label
        versions[label] = value

    wd = list(base.artifacts["wikidata"].rows)
    check(
        "fr rows",
        inputs(
            [], [], wd, fr=[bdpm_row(1, "Q", ["alfazin"])], es=[cima_row(1, "M", ["alfazin"], None)]
        ).dataset_version(),
    )
    check(
        "es rows",
        inputs(
            [], [], wd, fr=[bdpm_row(1, "P", ["alfazin"])], es=[cima_row(2, "M", ["alfazin"], None)]
        ).dataset_version(),
    )
    check("no fr", inputs([], [], wd, es=[cima_row(1, "M", ["alfazin"], None)]).dataset_version())
    check("no es", inputs([], [], wd, fr=[bdpm_row(1, "P", ["alfazin"])]).dataset_version())
    more_routes = RouteMap({**dict(ROUTES.allow), "sublinguale": ("A",)}, "t2")
    check("route map", replace(base, route_map=more_routes).dataset_version())
    check("anion acid", replace(base, acid=AnionAcidTable.load()).dataset_version())
    check("synonyms", replace(base, synonyms=(("x", "Q1"),)).dataset_version())
    with name_lists.override(
        EXTRA_SALT_WORDS={**name_lists.EXTRA_SALT_WORDS, "fr": frozenset({"zzz"})}
    ):
        check("salt words", base.dataset_version())
    with name_lists.override(CONNECTORS={**name_lists.CONNECTORS, "es": frozenset({"del"})}):
        check("connectors", base.dataset_version())
    with name_lists.override(BIOLOGIC_SUFFIX_ENABLED=not name_lists.BIOLOGIC_SUFFIX_ENABLED):
        check("switch", base.dataset_version())
    extra = PrefixRow(850, 851, "ES", False, "test", "2026-11-08")
    monkeypatch.setattr(load_module, "GS1_PREFIXES", (*GS1_PREFIXES, extra))
    check("country table", base.dataset_version())
    assert len(set(versions.values())) == len(versions)  # all distinct


# --- P47 (gather part): any subset of the EU sources; a present invalid one refuses ----------


def _fake_reader(invalid: frozenset[str]) -> Any:
    def read(data_dir: Path, source_id: str) -> Any:
        del data_dir
        if source_id in invalid:
            raise LoadError(f"{source_id}: rows do not match the manifest content hash")
        return artifact(source_id, [])

    return read


@settings(max_examples=40)
@given(
    present=st.sets(st.sampled_from(load_module.OPTIONAL)),
    invalid=st.sets(st.sampled_from(load_module.OPTIONAL)),
)
def test_p47_gather_any_subset_loads_and_a_present_invalid_source_refuses(
    present: set[str], invalid: set[str]
) -> None:
    """Feature: drug-resolution, Property P47 (gather part). Validates Req 9.7.

    An absent EU artifact is left out and reported; a present one is loaded; a present one that
    fails verification refuses the whole gather (an absent invalid one is never read).
    """
    pipelines = load_module.PIPELINES
    with tempfile.TemporaryDirectory() as tmp:
        for source in present:
            current = Path(tmp) / "artifacts" / pipelines[source] / "current"
            current.mkdir(parents=True)
            (current / "manifest.json").write_text("{}", encoding="utf-8")
        mp = pytest.MonkeyPatch()
        try:
            mp.setattr(load_module, "read_artifact", _fake_reader(frozenset(invalid)))
            if present & invalid:
                with pytest.raises(LoadError):
                    gather(Path(tmp))
                return
            got = gather(Path(tmp))
        finally:
            mp.undo()
    assert set(got.artifacts) == {"titck", "openfda_ndc", "wikidata", *present}
    assert set(missing_sources(got)) == set(load_module.OPTIONAL) - present
    assert set(got.cadences) == set(got.artifacts)
    assert got.cadences.get(FR_BDPM, 30) == 30 and got.cadences.get(ES_CIMA, 7) == 7
