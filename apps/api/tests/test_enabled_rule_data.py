"""The accepted Phase 2 rule data is valid and does what the review sheet says (task 21).

Checks on the committed files only; the measured coverage is in the sheet (Section 9) and in the
task 24 report.
"""

from __future__ import annotations

import csv
from pathlib import Path

from janus.resolution.atc import ATC_PREFIX, DATA_DIR, RouteMap
from janus.resolution.load import LOCAL_SYNONYMS, read_local_synonyms, read_synonyms
from janus.resolution.matching import IndexItem, NameIndex, map_name
from janus.resolution.name_lists import BASE_SALT_WORDS, EXTRA_SALT_WORDS
from janus.resolution.names import fold, strip_salts

FRENCH_ROUTES = {
    "orale", "intraveineuse", "sous-cutanée", "intramusculaire", "cutanée", "inhalée",
    "ophtalmique", "sublinguale", "intraartérielle", "voie buccale autre", "rectale",
    "transdermique", "intrathécale", "péridurale", "vaginale", "nasale", "périneurale",
    "intraarticulaire", "infiltration", "intra-utérine", "dentaire", "gingivale",
    "intravitréenne", "périarticulaire",
}  # fmt: skip


def test_french_route_rows_are_in_the_map_and_valid() -> None:
    """Appendix C: 24 French rows, exact strings, ATC prefixes of 1-5 characters."""
    route_map = RouteMap.load()
    assert FRENCH_ROUTES <= set(route_map.allow)
    for route in FRENCH_ROUTES:
        assert all(ATC_PREFIX.match(p) and len(p) <= 5 for p in route_map.allow[route])
    # a topical corticosteroid code is allowed on the skin and not by mouth (as for the US rows)
    assert route_map.allowed("D07AC16", ["cutanée"]) and not route_map.allowed(
        "H02AB09", ["cutanée"]
    )
    assert route_map.allowed("H02AB09", ["orale"]) and not route_map.allowed("D07AC16", ["orale"])
    assert route_map.allowed("S01BA01", ["ophtalmique"])
    # every English row survived
    assert {"ORAL", "TOPICAL", "INTRAVENOUS"} <= set(route_map.allow)


def test_synonym_file_holds_the_confirmed_rows_and_no_turkish_row() -> None:
    rows = list(csv.DictReader((DATA_DIR / "ingredient_synonyms.csv").open(encoding="utf-8")))
    names = {r["name"] for r in rows}
    assert len(rows) == 134 and "FENOFIBRIC ACID" in names and "SODIUM (BICARBONATE DE)" in names
    # the Turkish row never enters the repository: the one item has only its English-label row
    assert {r["name"] for r in rows if r["qid"] == "Q27259379"} == {"FENOFIBRIC ACID"}
    assert "PANCRELIPASE AMYLASE" not in names  # owner decision 4: leave unmapped
    assert len(read_synonyms()) == 134


def test_local_synonyms_are_read_from_the_data_directory_only(tmp_path: Path) -> None:
    assert read_local_synonyms(tmp_path) == ()
    folder = tmp_path / "resolution"
    folder.mkdir()
    (folder / LOCAL_SYNONYMS).write_text(
        "name,qid,note\nlocal name,Q1,evidence\n", encoding="utf-8"
    )
    assert read_local_synonyms(tmp_path) == (("local name", "Q1"),)


def test_accepted_examples_of_the_review_sheet() -> None:
    items = [
        IndexItem("Q1", {"en": "tramadol"}),
        IndexItem("Q2", {"en": "amlodipine", "es": "amlodipino"}),
        IndexItem("Q3", {"en": "mycophenolic acid"}),
        IndexItem("Q4", {"en": "infliximab"}),
        IndexItem("Q5", {"en": "calcium chloride"}),
    ]
    from janus.resolution.anion_acid import AnionAcidTable

    index = NameIndex.build(items, acid=AnionAcidTable.load())
    assert map_name("CHLORHYDRATE DE TRAMADOL", index, lang="fr").keys == ("Q1",)
    assert map_name("TRAMADOL HIDROCLORURO", index, lang="es").keys == ("Q1",)
    assert map_name("AMLODIPINO BESILATO", index, lang="es").keys == ("Q2",)
    assert map_name("MYCOPHENOLATE MOFETIL", index, lang="en").step == "anion_acid"
    assert map_name("INFLIXIMAB-DYYB", index, lang="en").step == "biologic_suffix"
    # prodrug esters with their own INN stay unmapped; so does a salicylate salt
    assert map_name("ARIPIPRAZOLE LAUROXIL", index, lang="en").status == "none"
    assert "lauroxil" not in EXTRA_SALT_WORDS["en"] | BASE_SALT_WORDS
    # a counter-ion that is a substance is not stripped away to nothing
    assert strip_salts(fold("calcium chloride"), "en") == "calcium chloride"
    assert strip_salts(fold("chlorure de calcium anhydre"), "fr") == "chlorure de calcium"
