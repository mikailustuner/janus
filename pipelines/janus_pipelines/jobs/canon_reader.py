"""The LLM half of the reader step (séance design §3.4, Req 1.3c).

`read_spans` turns theme spans (with their rule tags) into reader rows through a `Reader`. The
only real reader is `AnthropicReader`, used when `ANTHROPIC_API_KEY` is set; tests use a fake.
Without a key the reading is done offline by the reader agent and stored as `reader_ai.csv`
(design DP6); this module then only validates that file's rows.

The LLM is used for language only: it reads and translates; whether a claim is kept is decided
by the review passes and the deterministic assembly. Output is validated field by field and a
row that does not validate is refused, never repaired. Nothing is logged.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Protocol

MODEL: Final = "claude-opus-5-5"  # tech.md: Opus for hard Arabic extraction
CONDITION_VALUES: Final = ("wound", "burn", "ulcer", "infection", "out_of_scope")
AGREE: Final = ("yes", "partial", "no")
FORBIDDEN_EN: Final = ("cure", "cures", "treatment for", "diagnosis")
READER_COLUMNS: Final = (
    "span_id",
    "substance_id",
    "conditions",
    "body_site",
    "use_en",
    "machine_translation_en",
    "rule_theme_agrees",
    "rule_use_agrees",
    "reader_note",
)
SYSTEM: Final = (
    "You read clauses of Ibn Sina's Canon of Medicine, Book 2 (Arabic, OpenITI text with known "
    "typos). For each clause return: the conditions it names among wound, burn, ulcer "
    "(skin or mucosa only), infection (whitlow, carbuncle, abscess, foul, putrid, malignant, "
    "creeping or spreading ulcers, gangrene) or out_of_scope (internal organs, scars, general "
    "properties, garbled text); the body site; the use in one short English line; a faithful "
    "English translation that marks doubtful readings in brackets and keeps reported views "
    "('it is said') as reported; and whether the rule tags agree. Describe the text only: never "
    "advise, never use the words cure, cures, treatment for or diagnosis."
)
SCHEMA: Final[Mapping[str, Any]] = {
    "type": "object",
    "properties": {
        "conditions": {"type": "array", "items": {"enum": list(CONDITION_VALUES)}},
        "body_site": {"type": "string"},
        "use_en": {"type": "string"},
        "machine_translation_en": {"type": "string"},
        "rule_theme_agrees": {"enum": list(AGREE)},
        "rule_use_agrees": {"enum": list(AGREE)},
        "reader_note": {"type": "string"},
    },
    "required": [
        "conditions",
        "body_site",
        "use_en",
        "machine_translation_en",
        "rule_theme_agrees",
        "rule_use_agrees",
        "reader_note",
    ],
    "additionalProperties": False,
}


class ReaderError(ValueError):
    """The reader's output for a span is invalid. The message names the field, not the text."""


class Reader(Protocol):
    def read(self, span: Mapping[str, str]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class SpanInput:
    span_id: str
    substance_id: str
    row: Mapping[str, str]  # a theme_spans.csv row


def prompt(span: Mapping[str, str]) -> str:
    return json.dumps(
        {
            "arabic_span": span["arabic_span"],
            "rule_conditions": span["conditions_en"],
            "rule_forms": span["rule_forms"],
            "rule_vehicles": span["rule_vehicles"],
            "rule_parts": span["rule_parts"],
            "rule_actions": span["rule_actions"],
        },
        ensure_ascii=False,
    )


def validate(out: Mapping[str, Any], span_id: str, substance_id: str) -> dict[str, str]:
    """One reader row from the reader's JSON. Raises `ReaderError` naming the bad field."""
    if set(out) != set(SCHEMA["required"]):
        raise ReaderError("reader output has missing or extra fields")
    conds = out["conditions"]
    if not isinstance(conds, list) or not conds:
        raise ReaderError("conditions")
    values = [str(c) for c in conds]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    if any(v not in CONDITION_VALUES for v in values) or len(set(values)) != len(values):
        raise ReaderError("conditions")
    if "out_of_scope" in values and len(values) > 1:
        raise ReaderError("conditions")
    for field in ("rule_theme_agrees", "rule_use_agrees"):
        if out[field] not in AGREE:
            raise ReaderError(field)
    texts = {k: out[k] for k in ("body_site", "use_en", "machine_translation_en", "reader_note")}
    for k, v in texts.items():
        if not isinstance(v, str):
            raise ReaderError(k)
    if not str(texts["machine_translation_en"]).strip():
        raise ReaderError("machine_translation_en")
    for k in ("use_en", "machine_translation_en", "reader_note"):
        low = str(texts[k]).lower()
        if any(f in low.split() or (" " in f and f in low) for f in FORBIDDEN_EN):
            raise ReaderError(k)
    ordered = [c for c in CONDITION_VALUES if c in values]
    return {
        "span_id": span_id,
        "substance_id": substance_id,
        "conditions": "|".join(ordered),
        "body_site": str(texts["body_site"]),
        "use_en": str(texts["use_en"]),
        "machine_translation_en": str(texts["machine_translation_en"]),
        "rule_theme_agrees": str(out["rule_theme_agrees"]),
        "rule_use_agrees": str(out["rule_use_agrees"]),
        "reader_note": str(texts["reader_note"]),
    }


def read_spans(spans: Sequence[SpanInput], reader: Reader) -> list[dict[str, str]]:
    return [validate(reader.read(s.row), s.span_id, s.substance_id) for s in spans]


class AnthropicReader:
    """Claude through the Anthropic SDK: structured JSON output, a timeout, fallbacks on a
    refusal. `client` is an `anthropic.Anthropic`; it is passed in so tests never need one."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def read(self, span: Mapping[str, str]) -> Mapping[str, Any]:
        response = self._client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": prompt(span)}],
            timeout=120.0,
        )
        if response.stop_reason == "refusal":
            raise ReaderError("the model declined this span")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise ReaderError("no text block")
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise ReaderError("not JSON") from exc
        if not isinstance(data, dict):
            raise ReaderError("not an object")
        return data  # pyright: ignore[reportUnknownVariableType]


def configured() -> bool:
    """True when an API key is set. The key itself is never read here or logged."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
