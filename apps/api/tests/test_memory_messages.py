"""The closed set of codes and their English sentences (design §7, §10: P25 Python side).

The web test (`memory-words.test.ts`) checks the five message files; this one checks the API's
English canonical sentences and that both sides agree.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from janus.memory import messages

WEB = Path(__file__).resolve().parents[3] / "apps" / "web" / "messages"
LOCALES = ("en", "tr", "de", "fr", "es")

# Same English lists as apps/web/src/i18n/{forbidden-phrases,memory-words}.ts.
FORBIDDEN = [
    "stop taking", "you should stop", "discontinue", "unnecessary medicine", "cure", "cures",
    "treatment for", "diagnosis", "you have", "safe to stop", "your medicines are safe",
]  # fmt: skip
PEOPLE = [
    "people", "person", "persons", "patient", "patients", "individual", "individuals", "humans",
    "someone", "anyone", "like you",
]  # fmt: skip
CAUSAL = [
    "cause", "causes", "caused", "causing", "because of", "due to", "risk", "risks", "chance",
    "chances", "probability", "likely", "unlikely", "safe", "unsafe", "dangerous", "harmless",
    "normal", "unusual", "interact", "interacts", "interaction", "interactions", "side effect",
    "side effects", "reaction", "reactions",
]  # fmt: skip


def found(text: str, words: list[str]) -> list[str]:
    return [w for w in words if re.search(rf"(?<![^\W\d_]){re.escape(w)}(?![^\W\d_])", text, re.I)]


def violations(code: str, text: str) -> list[str]:
    exempt = code == "screening_statistic" and text == messages.SCREENING_SENTENCE
    return found(text, FORBIDDEN) + found(text, PEOPLE) + ([] if exempt else found(text, CAUSAL))


@pytest.mark.parametrize("code", messages.CODES)
def test_every_sentence_is_clean(code: str) -> None:
    """Feature: collective-memory, Property P25 (API sentences) — Validates: Req 8.2-8.4."""
    assert violations(code, messages.SENTENCES[code]) == []


def test_only_the_screening_sentence_is_exempt() -> None:
    s = messages.SCREENING_SENTENCE
    assert found(s, CAUSAL)  # the exception is real
    assert violations("screening_statistic", s) == []
    for code, text in (
        ("weak", s),
        ("screening_statistic", s + " "),
        ("screening_statistic", "Note. " + s),
        ("screening_statistic", s.replace("causes", "makes")[:-1] + " cause."),
        ("screening_statistic", s + " " + s),
    ):
        assert violations(code, text), (code, text[-20:])
    assert s.endswith("is not evidence that the medicine causes the event.")


def test_fixed_sentences() -> None:
    assert messages.DISCLAIMER == (
        "Janus provides information, not medical advice. Research prototype — not a medical device."
    )
    assert messages.MEDDRA_NOTICE == "MedDRA® is a registered trademark of ICH"
    assert messages.SENTENCES["weak"] == "Few reports; treat as a weak pattern."
    assert messages.BASE_NOTICES[-1] == "screening_statistic"
    assert set(messages.BASE_NOTICES) <= set(messages.CODES)


def test_all_five_message_files_carry_every_code() -> None:
    """Feature: collective-memory, Property P25 — Validates: Req 8.1."""
    expected = {c for c in messages.CODES if c != "screening_statistic"}
    for locale in LOCALES:
        memory = json.loads((WEB / f"{locale}.json").read_text(encoding="utf-8"))["Memory"]
        assert set(memory["codes"]) == expected, locale
        assert all(v.strip() for v in memory["codes"].values()), locale
        assert memory["meddra"] == messages.MEDDRA_NOTICE
        assert "{date}" in memory["attribution"]
    en = json.loads((WEB / "en.json").read_text(encoding="utf-8"))
    assert en["Memory"]["screening"] == messages.SCREENING_SENTENCE
    assert en["Memory"]["codes"] == {c: messages.SENTENCES[c] for c in expected}
    assert en["Memory"]["attribution"] == messages.ATTRIBUTION
    assert en["Disclaimer"]["text"] == messages.DISCLAIMER


def test_safety_lines_exist_for_every_vocabulary_line() -> None:
    from janus.memory.vocabulary import SAFETY_LINES

    assert set(SAFETY_LINES) <= set(messages.CODES)
