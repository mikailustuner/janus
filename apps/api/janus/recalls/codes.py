"""Reading NDCs and lot codes out of a record's own text (recall-check design §4). Pure.

Only what the record itself writes is read: hyphenated package NDCs anywhere, and hyphenated
product NDCs or 11-digit package NDCs after the word NDC. Ten digits without hyphens have three
possible layouts and are not read. openFDA's added `openfda` block is not used: it lists every
product of the same label, not the recalled ones (DP-R2).

A lot is compared by its ASCII letters and digits, upper-cased. The web app has the same rule in
`apps/web/src/recall/lot.ts`; `LOT_EXAMPLES` is the table both test suites check.
"""

from __future__ import annotations

import re
from typing import Final

from janus.resolution.ndc import canonical_package, canonical_product

MIN_LOT_CODE: Final = 3
MAX_LOT_CODE: Final = 20  # GS1 AI (10) holds at most 20 characters

_PACKAGE = re.compile(r"(?<![0-9-])([0-9]{4,5}-[0-9]{3,4}-[0-9]{1,2})(?![0-9-])")
_NDC_WORD = r"NDC[#:.\s]*(?:No\.?|Number|Code)?[#:.\s]*"
_PRODUCT = re.compile(_NDC_WORD + r"([0-9]{4,5}-[0-9]{3,4})(?![0-9-])", re.IGNORECASE)
_DIGITS11 = re.compile(_NDC_WORD + r"([0-9]{11})(?![0-9-])", re.IGNORECASE)
_NOT_LOT_CHAR = re.compile(r"[^0-9A-Za-z]")
_SEPARATORS = re.compile(r"[\s,;:()\[\]#&]+")
_DIGIT = re.compile(r"[0-9]")
# An expiry or use-by date as written next to a lot: 8/2025, 02/28/2026, 12-13-16.
_DATE = re.compile(r"^[0-9]{1,2}([/-])([0-9]{1,2}\1)?[0-9]{2,4}\.?$")

# (as written, normalised): shared with apps/web/src/recall/lot.test.ts.
LOT_EXAMPLES: Final[tuple[tuple[str, str], ...]] = (
    ("AB1234", "AB1234"),
    ("ab-1234", "AB1234"),
    (" 37-883948 ", "37883948"),
    ("07282026@2", "072820262"),
    ("CC/004/24-25", "CC0042425"),
    ("Lot#", "LOT"),
    ("é12ß", "12"),
    ("---", ""),
)


def ndc_keys(*texts: str | None) -> tuple[frozenset[str], frozenset[str]]:
    """(package keys, product keys) written in the texts.

    The product keys include the product part of every package key, so a record that names one
    package is also found by the product code.
    """
    packages: set[str] = set()
    products: set[str] = set()
    for text in texts:
        if not text:
            continue
        for m in _PACKAGE.finditer(text):
            key = canonical_package(m.group(1))
            if key is not None:
                packages.add(key)
        for m in _DIGITS11.finditer(text):
            packages.add(m.group(1))
        for m in _PRODUCT.finditer(text):
            key = canonical_product(m.group(1))
            if key is not None:
                products.add(key)
    products.update(p[:9] for p in packages)
    return frozenset(packages), frozenset(products)


def normalise_lot(lot: str) -> str:
    """The ASCII letters and digits of a lot, upper-cased."""
    return _NOT_LOT_CHAR.sub("", lot).upper()


def lot_codes(*texts: str | None) -> frozenset[str]:
    """The normalised tokens of a record's lot text that can be a lot code: 3-20 characters with
    a digit, not written as a date. Tokens are split at whitespace and at `, ; : ( ) [ ] # &`
    only, so a lot written with a hyphen, a slash or an `@` stays one code."""
    out: set[str] = set()
    for text in texts:
        if not text:
            continue
        for token in _SEPARATORS.split(text):
            if _DATE.match(token):
                continue
            code = normalise_lot(token)
            if MIN_LOT_CODE <= len(code) <= MAX_LOT_CODE and _DIGIT.search(code):
                out.add(code)
    return frozenset(out)
