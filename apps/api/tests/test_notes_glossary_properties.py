"""Glossary loader and use: P19 (pure part), P20 and the committed files (doctor-loop §5)."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.memory.messages import MEDDRA_NOTICE_LONG
from janus.notes import glossary as gl
from janus.notes.templates import CATALOGUE, SPECS
from tests.notes_strategies import (
    GLOSSARY_LANGS,
    SYNTHETIC_PIPC,
    cascade_rows,
    csv_text,
    ingredient_row,
    sentence_rows,
    synthetic_glossary,
)

WEB_MESSAGES = Path(__file__).resolve().parents[2] / "web" / "messages"
PIPC_CSV = Path(__file__).resolve().parents[3] / "data" / "pipc.csv"

ING = [
    ingredient_row("Q100", {"en": "alfazin", "tr": "alfazin", "de": "Alfazin", "fr": "alfazine"}),
    ingredient_row("Q200", {"en": "betarol", "en_alt": "betarolum"}),
    ingredient_row("Q300", {"en": "gammacil", "tr": "gamasil"}, status="proposed"),
    ingredient_row("J7", {"en": "deltamid", "es": "deltamida"}, status="rejected"),
]


def parse_with(
    ingredients: list[dict[str, str]] | None = None,
    cascades: list[dict[str, str]] | None = None,
    sentences: list[dict[str, str]] | None = None,
) -> gl.Glossary:
    return gl.parse(
        csv_text(gl.INGREDIENT_HEADER, ING if ingredients is None else ingredients),
        csv_text(gl.CASCADE_HEADER, cascade_rows() if cascades is None else cascades),
        csv_text(gl.SENTENCE_HEADER, sentence_rows() if sentences is None else sentences),
    )


# --- P20 --------------------------------------------------------------------------------------


def test_p20_valid_synthetic_glossary_loads() -> None:
    g = parse_with()
    assert g.available_languages() == frozenset(GLOSSARY_LANGS)
    assert len(g.sentences) == len(CATALOGUE) and len(g.cascades) == 65


def _mutations() -> list[tuple[str, str, str]]:
    """(file, mutation name, expected error code)."""
    return [
        ("ingredients", "duplicate_key", "duplicate_key"),
        ("ingredients", "bad_key", "bad_key"),
        ("ingredients", "not_nfc", "not_nfc"),
        ("ingredients", "forbidden", "forbidden_phrase"),
        ("ingredients", "reassurance", "reassurance_word"),
        ("ingredients", "bad_status", "bad_status"),
        ("ingredients", "accepted_no_en", "accepted_without_english"),
        ("cascades", "duplicate_position", "duplicate_position"),
        ("cascades", "bad_position", "bad_position"),
        ("cascades", "bad_hash", "bad_hash"),
        ("cascades", "forbidden", "forbidden_phrase"),
        ("sentences", "unknown_template", "unknown_template"),
        ("sentences", "duplicate_template", "duplicate_template"),
        ("sentences", "placeholder", "placeholder_mismatch"),
        ("sentences", "digit_in_claim", "digit_in_claim"),
        ("sentences", "kind", "kind_mismatch"),
        ("sentences", "evidence", "evidence_mismatch"),
        ("sentences", "unknown_role", "unknown_role"),
        ("sentences", "params", "params_mismatch"),
        ("sentences", "unknown_param_type", "unknown_param_type"),
        ("sentences", "shared", "shared_mismatch"),
        ("sentences", "forbidden_tr", "forbidden_phrase"),
        ("sentences", "reassurance_es", "reassurance_word"),
        ("sentences", "stray_brace", "stray_brace"),
        ("sentences", "accepted_empty", "accepted_with_empty_text"),
        ("sentences", "bad_header", "bad_header"),
    ]


@pytest.mark.parametrize(("file", "mutation", "code"), _mutations())
def test_p20_each_defect_is_named(file: str, mutation: str, code: str) -> None:
    """Feature: doctor-loop, Property P20. Validates Req 7.5."""
    ing = [dict(r) for r in ING]
    cas = cascade_rows()
    sen = sentence_rows()
    claim = next(r for r in sen if r["kind"] == "claim" and r["params"])
    match mutation:
        case "duplicate_key":
            ing.append(dict(ing[0]))
        case "bad_key":
            ing[0]["key"] = "Q0"
        case "not_nfc":
            ing[0]["fr"] = "alfazine\u0301"
        case "forbidden":
            if file == "ingredients":
                ing[0]["es"] = "cura"
            else:
                cas[3]["drug_a_de"] = "Diagnose"
        case "reassurance":
            ing[0]["en"] = "safe alfazin"
        case "bad_status":
            ing[0]["status"] = "approved"
        case "accepted_no_en":
            ing[0]["en"] = ""
        case "duplicate_position":
            cas.append(dict(cas[0]))
        case "bad_position":
            cas[0]["position"] = "66"
        case "bad_hash":
            cas[0]["en_sha256"] = "XYZ"
        case "unknown_template":
            sen.append({**sen[0], "id": "made.up"})
        case "duplicate_template":
            sen.append(dict(sen[0]))
        case "placeholder":
            claim["de"] = claim["de"].replace("{", "{x", 1)
        case "digit_in_claim":
            claim["fr"] += " 3"
        case "kind":
            claim["kind"] = "fixed"
        case "evidence":
            claim["evidence"] = "faers"
        case "unknown_role":
            claim["evidence"] = "rumour"
        case "params":
            claim["params"] += ";extra:int"
        case "unknown_param_type":
            claim["params"] = claim["params"].rsplit(":", 1)[0] + ":color"
        case "shared":
            claim["shared"] = "Memory.codes.weak"
        case "forbidden_tr":
            sen[0]["tr"] += " tanı"
        case "reassurance_es":
            sen[0]["es"] += " sin problemas"
        case "stray_brace":
            sen[0]["en"] += " }"
        case "accepted_empty":
            sen[0]["fr"] = ""
        case "bad_header":
            with pytest.raises(gl.GlossaryError) as info:
                gl.parse_sentences("id,kind\n")
            assert info.value.code == code
            return
        case _:
            raise AssertionError(mutation)
    with pytest.raises(gl.GlossaryError) as info:
        parse_with(ing, cas, sen)
    assert info.value.code == code
    assert info.value.file == f"{file}.csv"
    assert str(info.value).startswith(f"{file}.csv: row ")


# --- P19 (pure part) --------------------------------------------------------------------------


def test_p19_only_accepted_rows_are_used() -> None:
    """Feature: doctor-loop, Property P19. Validates Req 1.5, 7.3, 7.4."""
    g = parse_with()
    assert g.name("Q100", "de") == gl.Name("Alfazin", "glossary")
    assert g.name("Q100", "es") == gl.Name("alfazin", "english_fallback")
    assert g.name("Q200", "en") == gl.Name("betarol (betarolum)", "glossary")
    assert g.name("Q200", "tr") == gl.Name("betarol", "english_fallback")
    assert g.name("Q300", "tr", "gammacil-label") == gl.Name("gammacil-label", "not_reviewed")
    assert g.name("J7", "es") == gl.Name(None, "code_only")
    assert g.name("Q999", "fr", None) == gl.Name(None, "code_only")


@given(
    statuses=st.lists(st.sampled_from(gl.STATUSES), min_size=len(SPECS), max_size=len(SPECS)),
    cascade_status=st.sampled_from(gl.STATUSES),
    drop=st.sets(st.sampled_from(GLOSSARY_LANGS)),
)
def test_p19_language_availability(
    statuses: list[str], cascade_status: str, drop: set[str]
) -> None:
    """Feature: doctor-loop, Property P19 (availability). Validates Req 1.5."""
    sen = sentence_rows()
    for r, s in zip(sen, statuses, strict=True):
        r["status"] = s
        if s != "accepted":
            for lang in drop:
                r[lang] = ""
    g = parse_with(cascades=cascade_rows(cascade_status), sentences=sen)
    all_sentences = all(s == "accepted" for s in statuses)
    expected: set[str] = set()
    if all_sentences:
        expected.add("en")
        if cascade_status == "accepted":
            expected |= set(GLOSSARY_LANGS[1:])
    assert g.available_languages() == frozenset(expected)
    for r in sen:
        for lang in GLOSSARY_LANGS:
            if r["status"] != "accepted":
                with pytest.raises(KeyError):
                    g.text(r["id"], lang)


def test_p19_proposed_glossary_offers_no_language() -> None:
    assert synthetic_glossary(status="proposed").available_languages() == frozenset()


def test_cascade_names_need_the_current_english_text() -> None:
    g = parse_with()
    a, e, b = SYNTHETIC_PIPC[5]
    assert g.cascade(5, "de", (a, e, b)) == (f"{a} de", f"{e} de", f"{b} de")
    assert g.cascade(5, "en", (a, e, b)) == (a, e, b)
    assert g.cascade(5, "de", (a, e, b + " changed")) is None


# --- the committed files ----------------------------------------------------------------------


def test_committed_glossary_loads() -> None:
    """The real files parse; their status decides which languages exist (task 16 checks five)."""
    g = gl.load()
    assert g.available_languages() <= frozenset(GLOSSARY_LANGS)


def _message(lang: str, key: str) -> str:
    node = json.loads((WEB_MESSAGES / f"{lang}.json").read_text(encoding="utf-8"))
    for part in key.split("."):
        node = node[part]
    assert isinstance(node, str)
    return node


def test_p23_shared_rows_equal_the_message_files() -> None:
    """Feature: doctor-loop, Property P23 (shared rows). Validates Req 14.1."""
    for row in gl.load().sentences.values():
        if row.shared:
            for lang in GLOSSARY_LANGS:
                if row.texts[lang]:
                    assert row.texts[lang] == _message(lang, row.shared), (row.id, lang)
        if row.id == "stat.meddra_long":
            assert all(t in ("", MEDDRA_NOTICE_LONG) for t in row.texts.values())


def test_committed_cascade_hashes_match_pipc_csv() -> None:
    rows = list(csv.DictReader(io.StringIO(PIPC_CSV.read_text(encoding="utf-8"))))
    english = {int(r["position"]): (r["drug_a"], r["adverse_event"], r["drug_b"]) for r in rows}
    for position, row in gl.load().cascades.items():
        assert row.en_sha256 == gl.cascade_hash(*english[position]), position
