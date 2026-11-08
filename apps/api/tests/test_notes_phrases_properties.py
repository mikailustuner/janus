"""Phrase lists and the disclaimer: P23 and the P31 baseline (doctor-loop design §5.4, §13)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from janus.cascades import schemas as cascade_schemas
from janus.integrity import schemas as integrity_schemas
from janus.memory import messages
from janus.notes import phrases
from janus.resolution.model import ResolutionResult

WEB = Path(__file__).resolve().parents[2] / "web"
RULE_9 = (
    "Janus provides information, not medical advice. Research prototype — not a medical device."
)


def ts_lists() -> dict[str, list[str]]:
    text = (WEB / "src" / "i18n" / "forbidden-phrases.ts").read_text(encoding="utf-8")
    body = text[text.index("forbiddenPhrases") : text.index("} as const")]
    out: dict[str, list[str]] = {}
    for lang, block in re.findall(r"(\w\w): \[(.*?)\]", body, re.DOTALL):
        out[lang] = re.findall(r'"([^"]+)"', block)
    return out


def test_p23_forbidden_lists_equal_the_web_lists() -> None:
    """Feature: doctor-loop, Property P23 (phrase parity). Validates Req 14.2."""
    assert {k: list(v) for k, v in phrases.FORBIDDEN.items()} == ts_lists()
    assert set(phrases.REASSURANCE) == set(phrases.FORBIDDEN) == set(phrases.LANGUAGES)


def test_p23_disclaimers_equal_the_message_files() -> None:
    """Feature: doctor-loop, Property P23 (disclaimer). Validates Req 14.1, 14.3."""
    assert messages.DISCLAIMER == RULE_9
    for lang in phrases.LANGUAGES:
        text = json.loads((WEB / "messages" / f"{lang}.json").read_text(encoding="utf-8"))
        disclaimer = text["Disclaimer"]["text"]
        assert disclaimer.strip() == disclaimer and disclaimer
        assert phrases.violations(disclaimer, lang) == ([], [])
    en = json.loads((WEB / "messages" / "en.json").read_text(encoding="utf-8"))
    assert en["Disclaimer"]["text"] == RULE_9


def test_p31_api_responses_use_the_rule_9_constant() -> None:
    """Feature: doctor-loop, Property P31 (baseline). Validates Req 14.3.

    The three API constants used an ASCII hyphen before DP18; they now equal rule 9 and differ from
    the old text only in that character."""
    old = RULE_9.replace("—", "-")
    for value in (
        cascade_schemas.DISCLAIMER,
        integrity_schemas.DISCLAIMER,
        ResolutionResult.model_fields["disclaimer"].default,
    ):
        assert value == RULE_9
        assert value.replace("—", "-") == old


words = st.text(alphabet=st.characters(categories=["L"]), min_size=1, max_size=6)


@given(lang=st.sampled_from(phrases.LANGUAGES), data=st.data())
def test_matching_is_whole_word_and_case_insensitive(lang: str, data: st.DataObject) -> None:
    phrase = data.draw(st.sampled_from(phrases.FORBIDDEN[lang]))
    sep = data.draw(st.sampled_from([" ", ", ", ". ", "\n", "(", " — "]))
    assert phrase in phrases.find_phrases(f"x{sep}{phrase.upper()}{sep}y", [phrase])
    glued = data.draw(words) + phrase + data.draw(words)
    assert phrases.find_phrases(glued, [phrase]) == []


def test_examples() -> None:
    assert phrases.find_phrases("Ne pas arrêtez de prendre", phrases.FORBIDDEN["fr"]) == [
        "arrêtez de prendre"
    ]
    assert (
        phrases.find_phrases("N'arrêtez pas ce médicament brutalement.", phrases.FORBIDDEN["fr"])
        == []
    )
    assert phrases.find_phrases("No deje de tomar este medicamento", phrases.FORBIDDEN["es"]) == [
        "deje de tomar"
    ]
    assert (
        phrases.find_phrases(
            "No suspenda este medicamento de forma brusca.", phrases.FORBIDDEN["es"]
        )
        == []
    )
    assert phrases.find_phrases("Procuration", ["cura"]) == []
    assert phrases.find_phrases("tanısı", ["tanı"]) == []
    assert phrases.violations("Unsicherheit", "de") == ([], [])
    assert phrases.violations("Das ist sicher.", "de") == ([], ["sicher"])
