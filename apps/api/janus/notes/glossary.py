"""Clinical glossary: ingredient names, cascade names and note sentences (doctor-loop design §5.1).

Three CSV files in `glossary/` (in the package: the API image is built from `apps/api` only). Every
row has a status; only `accepted` rows are used, so a proposed glossary changes nothing (P19). The
loader validates everything at startup and fails loudly, naming file, row and column (P20).
English cascade names are the PIPC text of the rule base; the file holds the translations and the
hash of the English text they translate. Pure apart from `load()`, which reads the three files.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from janus.notes import phrases
from janus.notes.templates import CATALOGUE, KINDS, PARAM_TYPES, ROLES, Spec

GLOSSARY_DIR: Final = Path(__file__).parent / "glossary"
LANGUAGES: Final = ("en", "tr", "de", "fr", "es", "pt")
STATUSES: Final = ("proposed", "accepted", "rejected")
PIPC_ROWS: Final = 65
KEY_RE: Final = re.compile(r"^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$")
_PLACEHOLDER: Final = re.compile(r"\{([a-z_]+)\}")
_SHARED_RE: Final = re.compile(r"^[A-Za-z]+(\.[A-Za-z_]+)+$")
MAX_NAME: Final = 120
MAX_CASCADE: Final = 200  # PIPC class texts with examples run long in French and German
MAX_TEXT: Final = 600

INGREDIENT_HEADER: Final = ("key", *LANGUAGES, "en_alt", "status", "edited", "source", "note")
CASCADE_FIELDS: Final = tuple(
    f"{part}_{lang}" for lang in LANGUAGES[1:] for part in ("drug_a", "adverse_event", "drug_b")
)
CASCADE_HEADER: Final = ("position", "en_sha256", *CASCADE_FIELDS, "status", "note")
SENTENCE_HEADER: Final = (
    "id", "kind", "evidence", "params", *LANGUAGES, "status", "shared", "note",
)  # fmt: skip

Status = Literal["proposed", "accepted", "rejected"]
NameBasis = Literal["glossary", "english_fallback", "not_reviewed", "code_only"]


class GlossaryError(ValueError):
    """A defect in a glossary file. The message names file, row and column only."""

    def __init__(self, file: str, row: int, column: str, code: str) -> None:
        super().__init__(f"{file}: row {row}, column {column}: {code}")
        self.file, self.row, self.column, self.code = file, row, column, code


@dataclass(frozen=True)
class IngredientRow:
    key: str
    names: Mapping[str, str]  # language -> name ("" = none)
    en_alt: str
    status: Status


@dataclass(frozen=True)
class CascadeRow:
    position: int
    en_sha256: str
    names: Mapping[str, tuple[str, str, str]]  # tr, de, fr, es -> (drug_a, adverse_event, drug_b)
    status: Status


@dataclass(frozen=True)
class SentenceRow:
    id: str
    texts: Mapping[str, str]
    status: Status
    shared: str


@dataclass(frozen=True)
class Name:
    text: str | None
    basis: NameBasis


@dataclass(frozen=True)
class Glossary:
    ingredients: Mapping[str, IngredientRow]
    cascades: Mapping[int, CascadeRow]
    sentences: Mapping[str, SentenceRow]
    version: str

    def available_languages(self) -> frozenset[str]:
        """Design §5.6: every template accepted with a text; other than English, every PIPC row."""
        out: set[str] = set()
        for lang in LANGUAGES:
            ok = all(
                (row := self.sentences.get(tid)) is not None
                and row.status == "accepted"
                and row.texts[lang] != ""
                for tid in CATALOGUE
            )
            if ok and lang != "en":
                ok = len(self.cascades) == PIPC_ROWS and all(
                    r.status == "accepted" and all(r.names[lang]) for r in self.cascades.values()
                )
            if ok:
                out.add(lang)
        return frozenset(out)

    def text(self, template_id: str, lang: str) -> str:
        row = self.sentences[template_id]
        if row.status != "accepted" or not row.texts[lang]:
            raise KeyError(template_id)
        return row.texts[lang]

    def name(self, key: str, lang: str, label_en: str | None = None) -> Name:
        """Design §5.7: accepted name, else accepted English INN, else the unreviewed label."""
        row = self.ingredients.get(key)
        if row is not None and row.status == "accepted":
            if row.names[lang]:
                text = row.names[lang]
                if lang == "en" and row.en_alt:
                    text = f"{text} ({row.en_alt})"
                return Name(text, "glossary")
            if row.names["en"]:
                return Name(row.names["en"], "english_fallback")
        if label_en:
            return Name(label_en, "not_reviewed")
        return Name(None, "code_only")

    def cascade(
        self, position: int, lang: str, english: tuple[str, str, str]
    ) -> tuple[str, str, str] | None:
        """Cascade names in `lang`; English is the PIPC text. None if not accepted or stale."""
        if lang == "en":
            return english
        row = self.cascades.get(position)
        if row is None or row.status != "accepted" or row.en_sha256 != cascade_hash(*english):
            return None
        return row.names[lang]


def cascade_hash(drug_a: str, adverse_event: str, drug_b: str) -> str:
    return hashlib.sha256("\x1f".join((drug_a, adverse_event, drug_b)).encode("utf-8")).hexdigest()


# --- parsing ----------------------------------------------------------------------------------


def _rows(text: str, header: Sequence[str], file: str) -> list[tuple[int, dict[str, str]]]:
    reader = csv.reader(io.StringIO(text))
    try:
        first = next(reader)
    except StopIteration:
        raise GlossaryError(file, 1, "header", "missing_header") from None
    if tuple(first) != tuple(header):
        raise GlossaryError(file, 1, "header", "bad_header")
    out: list[tuple[int, dict[str, str]]] = []
    for n, raw in enumerate(reader, start=2):
        if len(raw) != len(header):
            raise GlossaryError(file, n, "row", "bad_row")
        out.append((n, dict(zip(header, raw, strict=True))))
    return out


def _cell(file: str, n: int, column: str, value: str, lang: str | None, limit: int) -> str:
    if unicodedata.normalize("NFC", value) != value:
        raise GlossaryError(file, n, column, "not_nfc")
    if value != value.strip() or "\n" in value or len(value) > limit:
        raise GlossaryError(file, n, column, "bad_text")
    if lang is not None and value:
        forbidden, reassurance = phrases.violations(value, lang)
        if forbidden:
            raise GlossaryError(file, n, column, "forbidden_phrase")
        if reassurance:
            raise GlossaryError(file, n, column, "reassurance_word")
    return value


def _status(file: str, n: int, value: str) -> Status:
    if value not in STATUSES:
        raise GlossaryError(file, n, "status", "bad_status")
    return value  # pyright: ignore[reportReturnType]


def parse_ingredients(text: str) -> dict[str, IngredientRow]:
    file = "ingredients.csv"
    out: dict[str, IngredientRow] = {}
    for n, r in _rows(text, INGREDIENT_HEADER, file):
        key = r["key"]
        if not KEY_RE.fullmatch(key):
            raise GlossaryError(file, n, "key", "bad_key")
        if key in out:
            raise GlossaryError(file, n, "key", "duplicate_key")
        names = {lang: _cell(file, n, lang, r[lang], lang, MAX_NAME) for lang in LANGUAGES}
        en_alt = _cell(file, n, "en_alt", r["en_alt"], "en", MAX_NAME)
        status = _status(file, n, r["status"])
        for lang, name in names.items():
            if name and not any(ch.isalpha() for ch in name):
                raise GlossaryError(file, n, lang, "bad_text")
        if status == "accepted" and not names["en"]:
            raise GlossaryError(file, n, "en", "accepted_without_english")
        edited = [e for e in r["edited"].split(";") if e]
        if any(e not in LANGUAGES for e in edited):
            raise GlossaryError(file, n, "edited", "bad_language")
        _cell(file, n, "source", r["source"], None, 80)
        _cell(file, n, "note", r["note"], None, 2000)
        out[key] = IngredientRow(key, names, en_alt, status)
    return out


def parse_cascades(text: str) -> dict[int, CascadeRow]:
    file = "cascades.csv"
    out: dict[int, CascadeRow] = {}
    for n, r in _rows(text, CASCADE_HEADER, file):
        if not re.fullmatch(r"[1-9][0-9]?", r["position"]) or not 1 <= int(r["position"]) <= 65:
            raise GlossaryError(file, n, "position", "bad_position")
        position = int(r["position"])
        if position in out:
            raise GlossaryError(file, n, "position", "duplicate_position")
        if not re.fullmatch(r"[0-9a-f]{64}", r["en_sha256"]):
            raise GlossaryError(file, n, "en_sha256", "bad_hash")
        names: dict[str, tuple[str, str, str]] = {}
        for lang in LANGUAGES[1:]:
            a, e, b = (
                _cell(file, n, f"{part}_{lang}", r[f"{part}_{lang}"], lang, MAX_CASCADE)
                for part in ("drug_a", "adverse_event", "drug_b")
            )
            names[lang] = (a, e, b)
        status = _status(file, n, r["status"])
        _cell(file, n, "note", r["note"], None, 2000)
        out[position] = CascadeRow(position, r["en_sha256"], names, status)
    return out


def _spec_params(raw: str) -> tuple[tuple[str, str], ...]:
    out: list[tuple[str, str]] = []
    for part in raw.split(";") if raw else []:
        name, _, typ = part.partition(":")
        out.append((name, typ))
    return tuple(out)


def _check_spec(file: str, n: int, r: Mapping[str, str], spec: Spec) -> None:
    if r["kind"] not in KINDS or r["kind"] != spec.kind:
        raise GlossaryError(file, n, "kind", "kind_mismatch")
    roles = tuple(x for x in r["evidence"].split(";") if x)
    if any(x not in ROLES for x in roles):
        raise GlossaryError(file, n, "evidence", "unknown_role")
    if roles != spec.evidence:
        raise GlossaryError(file, n, "evidence", "evidence_mismatch")
    params = _spec_params(r["params"])
    if any(t not in PARAM_TYPES for _, t in params):
        raise GlossaryError(file, n, "params", "unknown_param_type")
    if params != spec.params:
        raise GlossaryError(file, n, "params", "params_mismatch")
    if r["shared"] != (spec.shared or ""):
        raise GlossaryError(file, n, "shared", "shared_mismatch")


def parse_sentences(text: str) -> dict[str, SentenceRow]:
    file = "sentences.csv"
    out: dict[str, SentenceRow] = {}
    for n, r in _rows(text, SENTENCE_HEADER, file):
        tid = r["id"]
        spec = CATALOGUE.get(tid)
        if spec is None:
            raise GlossaryError(file, n, "id", "unknown_template")
        if tid in out:
            raise GlossaryError(file, n, "id", "duplicate_template")
        _check_spec(file, n, r, spec)
        if r["shared"] and not _SHARED_RE.fullmatch(r["shared"]):
            raise GlossaryError(file, n, "shared", "bad_shared_key")
        names = {p for p, _ in spec.params}
        texts: dict[str, str] = {}
        for lang in LANGUAGES:
            value = _cell(file, n, lang, r[lang], lang, MAX_TEXT)
            if value:
                if set(_PLACEHOLDER.findall(value)) != names:
                    raise GlossaryError(file, n, lang, "placeholder_mismatch")
                if _PLACEHOLDER.sub("", value).count("{") or _PLACEHOLDER.sub("", value).count("}"):
                    raise GlossaryError(file, n, lang, "stray_brace")
                if spec.kind == "claim" and any(ch.isdigit() for ch in value):
                    raise GlossaryError(file, n, lang, "digit_in_claim")
            texts[lang] = value
        status = _status(file, n, r["status"])
        if status == "accepted" and not all(texts.values()):
            raise GlossaryError(file, n, "status", "accepted_with_empty_text")
        _cell(file, n, "note", r["note"], None, 2000)
        out[tid] = SentenceRow(tid, texts, status, r["shared"])
    return out


def version_of(ingredients: str, cascades: str, sentences: str, extra: str = "") -> str:
    blob = json.dumps([ingredients, cascades, sentences, extra], ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def parse(ingredients: str, cascades: str, sentences: str, extra: str = "") -> Glossary:
    return Glossary(
        parse_ingredients(ingredients),
        parse_cascades(cascades),
        parse_sentences(sentences),
        version_of(ingredients, cascades, sentences, extra),
    )


def load(directory: Path = GLOSSARY_DIR, extra: str = "") -> Glossary:
    """Read and validate the three files; `extra` joins the version (event vocabulary labels)."""

    def read(name: str) -> str:
        return (directory / name).read_text(encoding="utf-8")

    return parse(read("ingredients.csv"), read("cascades.csv"), read("sentences.csv"), extra)


def vocabulary_digest(labels: Mapping[str, Mapping[str, str]], lines: Mapping[str, str]) -> str:
    """The part of the event vocabulary the note prints (labels, safety lines), for the version."""
    return json.dumps({"labels": labels, "lines": lines}, ensure_ascii=False, sort_keys=True)
