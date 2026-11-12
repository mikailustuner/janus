# ruff: noqa: E501 - layout pages and article XML are kept as the sources print them
"""Milestone M5: review PDF and PMC table readers, the human-only filter, licence checks, study
identity."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

from janus_pipelines.modelkit import doc_a, doc_b, documents, fda_reviews, pmc_articles, review_text
from janus_pipelines.modelkit.formref import BrandTable
from janus_pipelines.modelkit.model import ReaderStats
from janus_pipelines.modelkit.pmc_jats import Article, Table, attribution, parse_article
from janus_pipelines.modelkit.resolver import IdentityTable
from janus_pipelines.modelkit.species import article_is_human, table_is_human
from janus_pipelines.modelkit.study_identity import groups, keys_text, norm_code

REPO = Path(__file__).resolve().parents[2]
TABLE = IdentityTable.from_csv(
    (REPO / "data" / "modelkit" / "identity_m2.csv").read_text(encoding="utf-8")
)
BRANDS = BrandTable.empty()

PAGE = """\
  4.2 Individual Study Reviews

  Study AB-1001: a single dose study in healthy subjects. Each subject received a single oral dose of
  50 mg amantadine tablets under fasted conditions.

          Table 3. Mean (CV%) Pharmacokinetic Parameters of Amantadine following a Single Oral
          Dose of 50-mg Amantadine Tablets in Healthy Subjects (Study AB-1001)

                                  Fasted                Fed
                                  n=12                  n=12

           Cmax (ng/mL)           120 (25)              110 (20)
           AUC0-inf (ng·h/mL)     2400 (30)             2350 (28)
           t1/2 (h)               15.2 (12)             15.0 (14)
          Source: Clinical study report AB-1001.

"""

SUMMARY_PAGE = """\
  1.3 Summary of Clinical Pharmacology Findings

          Table 1. Summary of Pharmacokinetic Parameters of Amantadine (Study AB-1001)

                                  Fasted
           Cmax (ng/mL)           999 (25)

  2 Question Based Review
"""


def _pages(*texts: str) -> list[review_text.Page]:
    pages = [t + "\n" * 2 + "x" * 320 for t in texts]
    return review_text.mark_pages(pages)


DOC = doc_a.ReviewDoc(
    "amantadine", "123456", "https://www.accessdata.fda.gov/drugsatfda_docs/nda/2020/123456Orig1s000ClinPharmR.pdf",
    "123456Orig1s000ClinPharmR.pdf", "Drugs@FDA review PDF",
)  # fmt: skip


def test_both_review_readers_read_the_same_cells_with_dose_from_the_title() -> None:
    counts: Counter[str] = Counter()
    stats = {"a": ReaderStats(), "b": ReaderStats()}
    pairs = documents.read_review(_pages(PAGE), DOC, TABLE, BRANDS, stats, counts)
    confirmed = {(p.a.parameter, p.a.value, p.a.dose_mg) for p in pairs if p.result.confirmed}
    assert ("cmax", 120.0, 50.0) in confirmed
    assert ("auc_inf", 2400.0, 50.0) in confirmed
    assert ("t_half", 15.2, None) in confirmed
    cmax = next(p for p in pairs if p.a.value == 120.0)
    assert cmax.a.study_id == cmax.b.study_id == "FDA study AB1001"  # type: ignore[union-attr]
    assert cmax.a.locator == cmax.b.locator  # type: ignore[union-attr]
    assert "#page=1&line=" in cmax.a.locator
    assert cmax.a.context.food == "fasted"
    fed = next(p for p in pairs if p.a.value == 110.0)
    assert fed.a.context.food == "fed"


def test_a_summary_section_is_never_read() -> None:
    stats = {"a": ReaderStats(), "b": ReaderStats()}
    pairs = documents.read_review(_pages(SUMMARY_PAGE), DOC, TABLE, BRANDS, stats, Counter())
    assert all(p.a.value != 999.0 for p in pairs)
    assert doc_b.read_review(_pages(SUMMARY_PAGE), DOC, TABLE, BRANDS, ReaderStats()) == []


def test_dispersion_columns_are_never_values() -> None:
    page = """\
          Table 8. Pharmacokinetic Parameters of Amantadine after a Single Oral Dose of 100 mg (Study CD-2002)

                                Group 1                     Group 2
           Parameter            Mean      (CV%)             Mean      (CV%)
           Cmax (ng/mL)         345       22.8              380       21.4
"""
    pairs = documents.read_review(
        _pages(page), DOC, TABLE, BRANDS, {"a": ReaderStats(), "b": ReaderStats()}, Counter()
    )
    values = {p.a.value for p in pairs if p.result.confirmed}
    assert values == {345.0, 380.0}


def test_studies_must_agree() -> None:
    a = doc_a.study_code("Table 2 (Study XY-12345)")
    assert a == "XY12345"
    assert doc_a.study_code("in this study 2 subjects") is None


def test_reader_b_imports_nothing_of_reader_a_or_the_pairing() -> None:
    path = REPO / "pipelines" / "janus_pipelines" / "modelkit" / "doc_b.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module)
        elif isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
    banned = {"reader_a", "doc_a", "pairing", "documents", "confirm.confirm", "formulation_a"}
    assert not {m for m in mods if any(m.endswith("." + b) for b in banned)}


# --- human-only filter --------------------------------------------------------------------------


def test_the_pilot_horse_case_is_dropped() -> None:
    assert not article_is_human(
        "Canagliflozin treatment of a horse with hyperinsulinemia, including pharmacokinetic analysis of different "
        "dosing protocols: a case report.",
        "Frontiers in veterinary science",
        "equine metabolic syndrome; SGLT2",
        "A 14-year-old gelding was treated with canagliflozin; plasma concentrations were measured.",
        "The patient received 300 mg once daily.",
    )
    assert not table_is_human(
        "Pharmacokinetic parameters for 300 mg canagliflozin in a 450 kg horse after a single dose",
        "",
        "",
    )


def test_a_human_study_passes_and_a_rat_study_does_not() -> None:
    assert article_is_human(
        "Pharmacokinetics of canagliflozin in healthy Chinese volunteers", "Clin Pharmacol Drug Dev", "",
        "Twenty-four healthy subjects received a single oral dose.", "",
    )  # fmt: skip
    assert not article_is_human(
        "Pharmacokinetic interactions between canagliflozin and sorafenib in rats",
        "Pharmaceutics",
        "",
        "",
        "",
    )
    assert not article_is_human(
        "Bioavailability of a new tablet", "J Pharm", "", "Dissolution was tested.", ""
    )


def test_an_article_of_another_species_reaches_no_reader() -> None:
    art = Article(
        "PMC1", "Canagliflozin in a horse", "Frontiers in veterinary science", "2026", "", ("A B",), "", "", "",
        (Table("t1", "Table 1", "PK of canagliflozin in a 450 kg horse", (("Parameter", "Value"), ("Cmax (ng/mL)", "283")), 1, ""),),
        (), "CC BY 4.0",
    )  # fmt: skip
    counts: Counter[str] = Counter()
    out = documents.read_article(
        art, "canagliflozin", TABLE, BRANDS, {"a": ReaderStats(), "b": ReaderStats()}, counts, "v"
    )
    assert out == [] and counts["articles_not_human"] == 1


# --- PMC tables and licences ---------------------------------------------------------------------

JATS = b"""<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><journal-meta><journal-title-group><journal-title>Clin Pharmacol
</journal-title></journal-title-group></journal-meta><article-meta><article-id pub-id-type="doi">10.1/x</article-id>
<title-group><article-title>Pharmacokinetics of canagliflozin in healthy volunteers</article-title></title-group>
<contrib-group><contrib contrib-type="author"><name><surname>Doe</surname><given-names>Jane</given-names></name></contrib>
</contrib-group><pub-date><year>2024</year></pub-date><permissions><license license-type="open-access"
xlink:href="https://creativecommons.org/licenses/by/4.0/"><license-p>CC BY 4.0</license-p></license></permissions>
<abstract><p>Healthy subjects received canagliflozin (trial NCT01234567).</p></abstract></article-meta></front>
<body><sec sec-type="methods"><title>Methods</title><p>Twelve healthy subjects received a single oral dose of 300 mg
canagliflozin tablets.</p></sec>
<table-wrap id="tab2"><label>Table 2</label><caption><p>Pharmacokinetic parameters of canagliflozin (mean, CV%)</p></caption>
<table><thead><tr><th>Parameter</th><th>Fasted (n = 12)</th></tr></thead><tbody>
<tr><td>Cmax (ng/mL)</td><td>2,800 (25)</td></tr><tr><td>AUCinf (ng*h/mL)</td><td>21000 (30)</td></tr>
<tr><td>t1/2 (h)</td><td>11.5 (20)</td></tr></tbody></table>
<table-wrap-foot><p>Data are mean (CV%).</p></table-wrap-foot></table-wrap></body></article>"""


def test_pmc_readers_agree_and_dose_comes_from_the_methods() -> None:
    import xml.etree.ElementTree as ET

    lic = pmc_articles.xml_licence(ET.fromstring(JATS))  # noqa: S314
    assert lic == "CC BY 4.0"
    art = parse_article(JATS, "PMC999", lic)
    assert art.nct_ids == ("NCT01234567",)
    pairs = documents.read_article(
        art,
        "canagliflozin",
        TABLE,
        BRANDS,
        {"a": ReaderStats(), "b": ReaderStats()},
        Counter(),
        "v",
    )
    got = {
        (p.a.parameter, p.a.value, p.a.dose_mg, p.a.locator) for p in pairs if p.result.confirmed
    }
    assert ("cmax", 2800.0, 300.0, "PMC999#tab2/r1c1") in got
    assert ("t_half", 11.5, None, "PMC999#tab2/r3c1") in got
    assert "Licence CC BY 4.0" in attribution(art) and "Jane Doe" in attribution(art)


def test_pmc_dose_is_never_taken_from_the_abstract() -> None:
    xml = JATS.replace(
        b"a single oral dose of 300 mg\ncanagliflozin tablets.", b"tablets."
    ).replace(
        b"Healthy subjects received canagliflozin",
        b"Healthy subjects received 100 mg canagliflozin",
    )
    art = parse_article(xml, "PMC999", "CC BY 4.0")
    pairs = documents.read_article(
        art,
        "canagliflozin",
        TABLE,
        BRANDS,
        {"a": ReaderStats(), "b": ReaderStats()},
        Counter(),
        "v",
    )
    assert all(p.a.dose_mg is None for p in pairs)


@pytest.mark.parametrize(
    ("href", "ok"),
    [
        ("https://creativecommons.org/licenses/by/4.0/", "CC BY 4.0"),
        ("https://creativecommons.org/publicdomain/zero/1.0/", "CC0"),
        ("https://creativecommons.org/licenses/by-nc/4.0/", None),
        ("https://creativecommons.org/licenses/by-nc-nd/4.0/", None),
        ("https://creativecommons.org/licenses/by-sa/4.0/", None),
    ],
)
def test_xml_licence(href: str, ok: str | None) -> None:
    import xml.etree.ElementTree as ET

    x = (
        '<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta><permissions>'
        f'<license xlink:href="{href}"><license-p>text</license-p></license></permissions></article-meta></front></article>'
    )
    assert pmc_articles.xml_licence(ET.fromstring(x)) == ok  # noqa: S314


def test_three_licence_checks() -> None:
    assert pmc_articles.search_licence_ok({"license": "cc by"})
    assert not pmc_articles.search_licence_ok({"license": "cc by-nc"})
    assert pmc_articles.metadata_licence_ok(
        {"license_code": "CC BY", "is_retracted": "no", "is_manuscript": "no"}
    )
    assert not pmc_articles.metadata_licence_ok({"license_code": "CC BY-NC"})
    assert not pmc_articles.metadata_licence_ok({"license_code": "CC BY", "is_retracted": "yes"})
    assert not pmc_articles.metadata_licence_ok({"license_code": "TDM"})


# --- Drugs@FDA table of contents --------------------------------------------------------------


def test_toc_links_follow_the_flags_of_the_page() -> None:
    html = """<script>var pdfBaseName = "204114Orig1s000";
var pdfFiles = { clinPharmR: 1, integratedR: 0, multidisciplineR: 0 };
reviewHtml += '<li><a href="' + pdfBaseName + 'ClinPharmR.pdf" title="x">';
reviewHtml += '<li><a href="' + pdfBaseName + 'IntegratedR.pdf" title="x">';
</script>"""
    links = fda_reviews.toc_pdf_links(
        html, "https://www.accessdata.fda.gov/drugsatfda_docs/nda/2013/204114Orig1s000TOC.html"
    )
    assert links == [
        "https://www.accessdata.fda.gov/drugsatfda_docs/nda/2013/204114Orig1s000ClinPharmR.pdf"
    ]
    assert fda_reviews.priority("021938_S000_Sutent_BioPharmR.pdf") == 1
    assert fda_reviews.priority("x_MultidisciplineR.pdf") == 2
    assert fda_reviews.priority("x_MedR.pdf") is None


# --- study identity -------------------------------------------------------------------------------


def _row(src: str, study: str, keys: str = "", **kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "drug_key": "d", "source_id": src, "study_id": study, "study_keys": keys, "parameter": "cmax",
        "value_si": 100.0, "dose": 50.0, "n_subjects": 12, "analyte_class": "parent", "origin": "reader_pair",
    }  # fmt: skip
    return {**base, **kw}


def test_shared_nct_or_code_links_studies() -> None:
    rows = [
        _row(
            "clinicaltrials_gov",
            "NCT01234567",
            keys_text(["NCT01234567"], ["AB-1001"]),
            value_si=1.0,
        ),
        _row("pmc_oa", "PMC1", keys_text(["NCT01234567"]), value_si=2.0),
        _row("drugsatfda_review", "FDA study AB1001", keys_text([], ["AB1001"]), value_si=3.0),
        _row("pmc_oa", "PMC2", "", value_si=4.0),
    ]
    g, links = groups(rows)
    assert (
        len(
            {
                g[("d", "clinicaltrials_gov", "NCT01234567")],
                g[("d", "pmc_oa", "PMC1")],
                g[("d", "drugsatfda_review", "FDA study AB1001")],
            }
        )
        == 1
    )
    assert g[("d", "pmc_oa", "PMC2")] == "pmc_oa:PMC2"
    assert links["nct"] == 1 and links["code"] == 1


def test_numeric_duplicates_link_but_not_tmax_and_not_other_doses() -> None:
    rows = [
        _row("clinicaltrials_gov", "NCT00000001", value_si=100.0),
        _row("pmc_oa", "PMC1", value_si=100.5, n_subjects=None),
        _row("pmc_oa", "PMC2", value_si=100.0, dose=100.0),
        _row("pmc_oa", "PMC3", value_si=100.0, n_subjects=13),
        _row("pmc_oa", "PMC4", parameter="tmax", value_si=2.0),
        _row("pmc_oa", "PMC5", parameter="tmax", value_si=2.0),
    ]
    g, _ = groups(rows)
    assert g[("d", "pmc_oa", "PMC1")] == g[("d", "clinicaltrials_gov", "NCT00000001")]
    assert g[("d", "pmc_oa", "PMC2")] == "pmc_oa:PMC2"
    # PMC3 states another n than the registry, but PMC1 (no n) matches both: the closure joins them (conservative)
    assert g[("d", "pmc_oa", "PMC3")] == g[("d", "pmc_oa", "PMC1")]
    assert g[("d", "pmc_oa", "PMC4")] != g[("d", "pmc_oa", "PMC5")]
    g2, _ = groups([rows[0], rows[3]])
    assert (
        g2[("d", "pmc_oa", "PMC3")] == "pmc_oa:PMC3"
    )  # different numbers of subjects: not the same study


def test_document_level_review_study_joins_the_coded_studies_of_its_pdf() -> None:
    rows = [
        _row("drugsatfda_review", "FDA NDA 1 x", keys_text(docs=["u"]), value_si=1.0),
        _row(
            "drugsatfda_review", "FDA study AB1001", keys_text([], ["AB1001"], ["u"]), value_si=2.0
        ),
    ]
    g, _ = groups(rows)
    assert (
        g[("d", "drugsatfda_review", "FDA NDA 1 x")]
        == g[("d", "drugsatfda_review", "FDA study AB1001")]
    )


def test_norm_code() -> None:
    assert norm_code("OS320-PKP07") == "OS320PKP07"
    assert norm_code("101") is None
    assert norm_code("NCT01234567") is None


def test_pmc_spread_columns_are_never_values() -> None:
    grid = (
        ("", "Fasted", "Fasted", "Fasted", "Fasted"),
        ("Parameter", "Mean", "SD", "Min", "Max"),
        ("Cmax (ng/ml)", "253.46", "139.12", "73.20", "485.00"),
    )
    art = Article(
        "PMC2", "Pharmacokinetics of telmisartan in healthy volunteers", "J", "2024", "", ("A B",), "",
        "Healthy subjects took part.", "Twelve healthy subjects received a single oral dose of 40 mg telmisartan tablets.",
        (Table("t1", "Table 1", "PK parameters of telmisartan", grid, 2, ""),), (), "CC BY 4.0",
    )  # fmt: skip
    pairs = documents.read_article(
        art, "telmisartan", TABLE, BRANDS, {"a": ReaderStats(), "b": ReaderStats()}, Counter(), "v"
    )
    assert {p.a.value for p in pairs} == {253.46}
    assert all(p.b is None or p.b.value == 253.46 for p in pairs)


# --- iteration 2 (addendum 6): rules from the first blinded review sample ----------------------


def _pmc_one(caption: str, grid: tuple[tuple[str, ...], ...]) -> list[tuple[str, float, bool]]:
    art = Article(
        "PMC3", "Pharmacokinetics of telmisartan in healthy volunteers", "J", "2024", "", ("A B",), "",
        "Healthy subjects took part.", "Twelve healthy subjects received a single oral dose of 40 mg telmisartan tablets.",
        (Table("t1", "Table 1", caption, grid, 1, ""),), (), "CC BY 4.0",
    )  # fmt: skip
    pairs = documents.read_article(art, "telmisartan", TABLE, BRANDS, {"a": ReaderStats(), "b": ReaderStats()}, Counter(), "v")
    return [(p.a.parameter, p.a.value, p.result.confirmed) for p in pairs]


def test_a_count_column_is_never_a_value() -> None:
    grid = (("Parameter", "N", "Mean"), ("Cmax (ng/mL)", "24", "300"), ("t1/2 (h)", "24", "20.5"))
    got = _pmc_one("PK parameters of telmisartan", grid)
    assert {v for _, v, ok in got if ok} == {300.0, 20.5}


def test_tables_of_models_special_populations_and_animals_are_not_read() -> None:
    grid = (("Parameter", "Mean"), ("CL/F (L/h)", "30"))
    for caption in (
        "Population pharmacokinetic model parameter estimates of telmisartan",
        "PK of telmisartan in subjects with hepatic impairment",
        "Toxicokinetics of telmisartan in dogs",
    ):
        assert _pmc_one(caption, grid) == []


def test_a_title_naming_a_metabolite_is_never_the_parent() -> None:
    grid = (("Parameter", "Mean"), ("t1/2 (h)", "30"))
    got = _pmc_one("PK parameters of telmisartan and its metabolite M2", grid)
    assert not any(ok for _, _, ok in got)
    got = _pmc_one("PK parameters of telmisartan (Study AB-1001)", grid)
    assert any(ok for _, _, ok in got)


def test_equal_values_with_and_without_n_do_not_break_the_grouping() -> None:
    rows = [_row("pmc_oa", "PMC1", n_subjects=None), _row("pmc_oa", "PMC2", n_subjects=12)]
    g, _ = groups(rows)
    assert g[("d", "pmc_oa", "PMC1")] == g[("d", "pmc_oa", "PMC2")]
