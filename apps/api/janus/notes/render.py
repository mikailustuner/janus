"""Number, date and placeholder rendering per language (doctor-loop design §5.3, DP26). Pure.

Fixed rules for six languages, no locale library. The auditor (design §5.5) checks that every
numeral of a claim sentence comes from these functions, so the builder and the auditor share them.

| | en | tr | de | fr | es | pt |
| decimal | . | , | , | , | , | , |
| grouping | , | . | . | U+202F | . from 5 digits | NBSP from 5 digits |
| month | 03/2026 | 03.2026 | 03.2026 | 03/2026 | 03/2026 | 03/2026 |
| date | 2026-11-08 | 08.11.2026 | 08.11.2026 | 08/11/2026 | 08/11/2026 | 08/11/2026 |
| percent | 11.9% | %11,9 | 11,9 % (NBSP) | 11,9 % (U+202F) | 11,9 % (NBSP) | 11,9% |
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Final

from janus.notes.templates import Spec

DECIMAL: Final = {"en": ".", "tr": ",", "de": ",", "fr": ",", "es": ",", "pt": ","}
GROUP: Final = {"en": ",", "tr": ".", "de": ".", "fr": "\u202f", "es": ".", "pt": "\u00a0"}
# CLDR minimumGroupingDigits
MIN_GROUPING: Final = {"en": 1, "tr": 1, "de": 1, "fr": 1, "es": 2, "pt": 2}
NBSP: Final = "\u00a0"
RATIO_LOW: Final = Decimal("0.01")
RATIO_HIGH: Final = 1000
# A numeral as the renderers write it: digits with grouping or decimal separators between them.
NUMERAL: Final = re.compile(r"\d+(?:[.,\u202f\u00a0]\d+)*")
_PLACEHOLDER: Final = re.compile(r"\{([a-z_]+)\}")

Value = int | float | Decimal | str | dt.date | tuple[str, ...]


def _group(digits: str, lang: str) -> str:
    if len(digits) < 4 + (MIN_GROUPING[lang] - 1):
        return digits
    parts: list[str] = []
    while len(digits) > 3:
        parts.insert(0, digits[-3:])
        digits = digits[:-3]
    parts.insert(0, digits)
    return GROUP[lang].join(parts)


def format_decimal(value: Decimal, lang: str) -> str:
    """A finite decimal with the digits it has (published values keep their decimals)."""
    if not value.is_finite():
        raise ValueError("finite decimals only")
    sign = "-" if value < 0 else ""
    text = format(abs(value), "f")
    whole, _, frac = text.partition(".")
    out = _group(whole, lang)
    return sign + (out + DECIMAL[lang] + frac if frac else out)


def format_int(value: int, lang: str) -> str:
    return format_decimal(Decimal(value), lang)


def _rounded(value: Decimal) -> Decimal:
    """2 decimals below 10, 1 below 100, else 0, judged on the rounded value."""
    for places, limit in ((2, 10), (1, 100)):
        q = value.quantize(Decimal(1).scaleb(-places), ROUND_HALF_EVEN)
        if q < limit:
            return q
    return value.quantize(Decimal(1), ROUND_HALF_EVEN)


def format_ratio(value: float, lang: str) -> str:
    """PRR/ROR and its range: 2, 1 or 0 decimals; below 0.01 and from 1,000 as bounds."""
    d = Decimal(repr(value))
    if not d.is_finite() or d < 0:
        raise ValueError("ratios are finite and non-negative")
    if d >= RATIO_HIGH:
        return ">" + format_int(RATIO_HIGH, lang)
    q = _rounded(d)
    if q == 0:  # would print as 0.00
        return "<" + format_decimal(RATIO_LOW, lang)
    return format_decimal(q, lang)


def format_percent(value: Decimal, lang: str) -> str:
    number = format_decimal(value, lang)
    if lang == "tr":
        return "%" + number
    if lang in ("en", "pt"):
        return number + "%"
    if lang == "fr":
        return number + "\u202f%"
    return number + NBSP + "%"


def format_month(value: str, lang: str) -> str:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise ValueError("month must be YYYY-MM")
    year, month = value.split("-")
    return f"{month}.{year}" if lang in ("tr", "de") else f"{month}/{year}"


def format_date(value: dt.date, lang: str) -> str:
    if lang == "en":
        return value.isoformat()
    sep = "." if lang in ("tr", "de") else "/"
    return f"{value.day:02d}{sep}{value.month:02d}{sep}{value.year:04d}"


def render_value(typ: str, value: Value, lang: str) -> str:
    match typ:
        case "int":
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(typ)
            return format_int(value, lang)
        case "ratio":
            if not isinstance(value, float | int) or isinstance(value, bool):
                raise TypeError(typ)
            return format_ratio(float(value), lang)
        case "percent":
            if not isinstance(value, Decimal):
                raise TypeError(typ)
            return format_percent(value, lang)
        case "decimal_text":
            if not isinstance(value, Decimal):
                raise TypeError(typ)
            return format_decimal(value, lang)
        case "month":
            if not isinstance(value, str):
                raise TypeError(typ)
            return format_month(value, lang)
        case "date":
            if not isinstance(value, dt.date):
                raise TypeError(typ)
            return format_date(value, lang)
        case "quarter" | "term":
            if not isinstance(value, str):
                raise TypeError(typ)
            return value
        case "code":
            if not isinstance(value, tuple):
                raise TypeError(typ)
            return ", ".join(value)
        case "version":
            if not isinstance(value, str):
                raise TypeError(typ)
            return value[:8]
        case _:
            raise ValueError(typ)


def numerals(text: str) -> list[str]:
    return NUMERAL.findall(text)


def fill(
    spec: Spec, template: str, values: Mapping[str, Value], lang: str
) -> tuple[str, list[str]]:
    """Fill `template`; return the text and the rendered parameters that contain digits."""
    if set(values) != {name for name, _ in spec.params}:
        raise ValueError(f"values of {spec.id} do not match its parameters")
    types = dict(spec.params)
    rendered = {name: render_value(types[name], v, lang) for name, v in values.items()}
    text = _PLACEHOLDER.sub(lambda m: rendered[m.group(1)], template)
    numbers = [
        rendered[m.group(1)]
        for m in _PLACEHOLDER.finditer(template)
        if any(ch.isdigit() for ch in rendered[m.group(1)])
    ]
    return text, numbers


def residue(text: str, numbers: Sequence[str]) -> str:
    """`text` without one occurrence of each rendered parameter; any digit left is foreign."""
    for n in numbers:
        text = text.replace(n, "", 1)
    return text


def join_names(names: Sequence[str], lang: str) -> str:
    """Ingredient names as a chain: A → B → C (the arrow is language-neutral)."""
    del lang
    return " → ".join(names)
