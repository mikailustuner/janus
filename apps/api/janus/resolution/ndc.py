"""US National Drug Code handling (drug-resolution design §4.4). Pure.

A 10-digit NDC has three segments in one of three layouts (4-4-2, 5-3-2, 5-4-1). The canonical
package key is the 11-digit 5-4-2 form (the short segment padded with one zero); the canonical
product key is the 9-digit 5-4 form. Ten digits without hyphens do not say which layout they
use, so they give up to three keys and every match is returned (Req 3.1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Layout = Literal["4-4-2", "5-3-2", "5-4-1"]
LAYOUTS: dict[Layout, tuple[int, int, int]] = {
    "4-4-2": (4, 4, 2),
    "5-3-2": (5, 3, 2),
    "5-4-1": (5, 4, 1),
}
PRODUCT_LAYOUTS = {(4, 4), (5, 3), (5, 4)}
LABEL_PREFIXES = ("NDC:", "NDC", "N")  # longest first

KeyKind = Literal["ndc_package11", "ndc_product9"]

_NDC_GTIN = re.compile(r"^[0-8]03([0-9]{10})[0-9]$")
_WS = re.compile(r"\s+")


class NdcError(ValueError):
    """Malformed NDC input. The message is a fixed code and never contains input."""

    code = "ndc_malformed"

    def __init__(self) -> None:
        super().__init__(self.code)


@dataclass(frozen=True, order=True)
class NdcKey:
    kind: KeyKind
    code: str


def package11(labeler: str, product: str, package: str) -> str:
    return labeler.zfill(5) + product.zfill(4) + package.zfill(2)


def product9(labeler: str, product: str) -> str:
    return labeler.zfill(5) + product.zfill(4)


def split_ndc10(digits: str, layout: Layout) -> tuple[str, str, str]:
    a, b, _ = LAYOUTS[layout]
    return digits[:a], digits[a : a + b], digits[a + b :]


def layouts_of_ndc10(digits: str) -> dict[Layout, str]:
    """Every layout's canonical 11-digit key for 10 plain digits."""
    if len(digits) != 10 or not digits.isascii() or not digits.isdigit():
        raise NdcError()
    return {layout: package11(*split_ndc10(digits, layout)) for layout in LAYOUTS}


def canonical_package(published: str) -> str | None:
    """Canonical 11-digit key of a published hyphenated package NDC, or None if malformed."""
    parts = published.split("-")
    if len(parts) != 3 or not all(p.isascii() and p.isdigit() for p in parts):
        return None
    lengths = tuple(len(p) for p in parts)
    if lengths not in LAYOUTS.values() and lengths != (5, 4, 2):
        return None
    return package11(*parts)


def canonical_product(published: str) -> str | None:
    """Canonical 9-digit key of a published hyphenated product NDC, or None if malformed."""
    parts = published.split("-")
    if len(parts) != 2 or not all(p.isascii() and p.isdigit() for p in parts):
        return None
    if (len(parts[0]), len(parts[1])) not in PRODUCT_LAYOUTS:
        return None
    return product9(*parts)


def ndc_from_gtin(gtin14: str) -> str | None:
    """The 10 NDC digits of an NDC GTIN (indicator, `03`, NDC, check digit), else None.

    A UPC-A `3` + NDC + check digit padded to GTIN-14 is `003…`, so it is covered too.
    """
    m = _NDC_GTIN.match(gtin14)
    return m.group(1) if m else None


def _strip_prefix(text: str) -> str:
    upper = text.upper()
    for prefix in LABEL_PREFIXES:
        if upper.startswith(prefix):
            return text[len(prefix) :]
    return text


def parse_ndc_input(raw: str) -> frozenset[NdcKey]:
    """NDC as typed or read from a label → lookup keys. Raise `NdcError` if malformed."""
    text = _strip_prefix(_WS.sub("", raw))
    if not text or not all(ch.isascii() and (ch.isdigit() or ch == "-") for ch in text):
        raise NdcError()
    if "-" in text:
        parts = text.split("-")
        if not all(parts):
            raise NdcError()
        lengths = tuple(len(p) for p in parts)
        if len(parts) == 3 and (lengths in LAYOUTS.values() or lengths == (5, 4, 2)):
            return frozenset({NdcKey("ndc_package11", package11(*parts))})
        if len(parts) == 2 and lengths in PRODUCT_LAYOUTS:
            return frozenset({NdcKey("ndc_product9", product9(*parts))})
        raise NdcError()
    if len(text) == 11:
        return frozenset({NdcKey("ndc_package11", text)})
    if len(text) == 10:
        return frozenset(NdcKey("ndc_package11", k) for k in layouts_of_ndc10(text).values())
    raise NdcError()
