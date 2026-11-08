"""GS1 element-string parsing (drug-resolution design §4.5). Pure: no I/O, no clock.

The client sends only AI (01), (17) and, if present, (712) (owner decision DP19, extended
2026-11-08). The serial (21) identifies a single box and must never leave the device: an element
string that carries AI (21) is rejected with `gs1_serial_not_accepted` before any value is read
(Req 1.4). A lot (10) that still arrives is read only to find the end of the field and to detect
a repeated AI with a different value; it is never stored, returned or logged. AI (712) is the
Spanish national code (a product number) and is kept as `national_code` if it has 7 digits.
Errors carry a fixed code and never include any part of the input (Req 8.4).
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Literal

GS = "\x1d"
SYMBOLOGY_IDENTIFIERS = ("]d2", "]C1", "]Q3")

# Character set 82 (GS1 General Specifications, figure 7.11-1).
_CSET82 = re.compile(r"^[!\"%&'()*+,\-./0-9:;<=>?A-Z_a-z]*$")
_DIGITS = re.compile(r"^[0-9]*$")


@dataclass(frozen=True)
class AiSpec:
    length: int  # exact length if fixed, else maximum length
    fixed: bool
    numeric: bool


# Supported Application Identifiers. Fixed lengths follow the GS1 predefined-length table.
AI_TABLE: dict[str, AiSpec] = {
    "00": AiSpec(18, True, True),  # SSCC
    "01": AiSpec(14, True, True),  # GTIN
    "02": AiSpec(14, True, True),  # GTIN of contained trade items
    "10": AiSpec(20, False, False),  # batch / lot
    "11": AiSpec(6, True, True),  # production date
    "12": AiSpec(6, True, True),  # due date
    "13": AiSpec(6, True, True),  # packaging date
    "15": AiSpec(6, True, True),  # best before
    "16": AiSpec(6, True, True),  # sell by
    "17": AiSpec(6, True, True),  # expiry
    "20": AiSpec(2, True, True),  # internal product variant
    "21": AiSpec(20, False, False),  # serial number
    "22": AiSpec(20, False, False),  # consumer product variant
    "30": AiSpec(8, False, True),  # variable count
    "240": AiSpec(30, False, False),  # additional product identification
    "241": AiSpec(30, False, False),  # customer part number
    # National healthcare reimbursement numbers (710 DE PZN, 711 FR, 712 ES, 713 BR,
    # 714 PT, 715 US NDC, 716 IT AIC).
    **{str(ai): AiSpec(20, False, False) for ai in range(710, 717)},
}


class Gs1ErrorCode(StrEnum):
    EMPTY = "gs1_empty"
    MALFORMED = "gs1_malformed"
    UNKNOWN_AI = "gs1_unknown_ai"
    DUPLICATE_AI = "gs1_duplicate_ai"
    FIELD_LENGTH = "gs1_field_length"
    FIELD_CHARACTERS = "gs1_field_characters"
    GTIN_MISSING = "gtin_missing"
    GTIN_CHECK_DIGIT = "gtin_check_digit"
    SERIAL_NOT_ACCEPTED = "gs1_serial_not_accepted"


class Gs1Error(ValueError):
    """Invalid GS1 content. `code` is a fixed value; the message never contains input."""

    def __init__(self, code: Gs1ErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


ExpiryStatus = Literal["absent", "valid", "invalid"]


@dataclass(frozen=True)
class Gs1Data:
    """What resolution keeps from a scan. There is deliberately no serial or lot value.

    `serial_present` is always False (a serial is rejected, never parsed); it stays for contract
    compatibility. `national_code` is the AI (712) value of 7 digits, else None.
    """

    gtin14: str
    expiry: date | None
    expiry_status: ExpiryStatus
    serial_present: bool
    lot_present: bool
    national_code: str | None = None


def gtin_check_digit(body: str) -> int:
    """GS1 mod-10 check digit for the digits before the check digit (weights 3,1 from the right)."""
    if not body or not _DIGITS.match(body):
        raise ValueError("digits required")
    total = 0
    for i, ch in enumerate(reversed(body)):
        total += int(ch) * (3 if i % 2 == 0 else 1)
    return (10 - total % 10) % 10


def is_valid_gtin(digits: str) -> bool:
    if len(digits) not in (8, 12, 13, 14) or not _DIGITS.match(digits):
        return False
    return gtin_check_digit(digits[:-1]) == int(digits[-1])


def to_gtin14(digits: str) -> str:
    """Left-pad a GTIN-8/12/13/14 to 14 digits; raise `Gs1Error` if it is not a valid GTIN."""
    if not is_valid_gtin(digits):
        raise Gs1Error(Gs1ErrorCode.GTIN_CHECK_DIGIT)
    return digits.zfill(14)


def parse_expiry(yymmdd: str, today: date) -> date | None:
    """AI (17) value → date, or None if the month or day is impossible.

    Century by the GS1 rule (General Specifications §7.12): with d = YY - (current year mod 100),
    d ≥ 51 → previous century, d ≤ -50 → next century, else the current century.
    DD = 00 means the last day of the month.
    """
    if len(yymmdd) != 6 or not _DIGITS.match(yymmdd):
        return None
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:])
    century = today.year // 100
    diff = yy - today.year % 100
    if diff >= 51:
        century -= 1
    elif diff <= -50:
        century += 1
    year = century * 100 + yy
    if not 1 <= mm <= 12 or not 1 <= year <= 9999:
        return None
    last = calendar.monthrange(year, mm)[1]
    if dd == 0:
        return date(year, mm, last)
    if dd > last:
        return None
    return date(year, mm, dd)


def _strip_identifier(content: str) -> str:
    for ident in SYMBOLOGY_IDENTIFIERS:
        if content.startswith(ident):
            return content[len(ident) :]
    return content


def _check_value(spec: AiSpec, value: str) -> None:
    if (spec.fixed and len(value) != spec.length) or not 1 <= len(value) <= spec.length:
        raise Gs1Error(Gs1ErrorCode.FIELD_LENGTH)
    pattern = _DIGITS if spec.numeric else _CSET82
    if not pattern.match(value):
        raise Gs1Error(Gs1ErrorCode.FIELD_CHARACTERS)


SERIAL_AI = "21"
NATIONAL_CODE_AI = "712"
_NATIONAL_CODE = re.compile(r"^[0-9]{7}$")


def _match_ai(text: str, pos: int) -> str:
    for size in (2, 3, 4):
        ai = text[pos : pos + size]
        if len(ai) == size and ai in AI_TABLE:
            if ai == SERIAL_AI:
                raise Gs1Error(Gs1ErrorCode.SERIAL_NOT_ACCEPTED)
            return ai
    raise Gs1Error(Gs1ErrorCode.UNKNOWN_AI)


def _fields_fnc1(text: str) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    pos = 0
    n = len(text)
    while pos < n:
        if text[pos] == GS:
            pos += 1
            continue
        ai = _match_ai(text, pos)
        spec = AI_TABLE[ai]
        start = pos + len(ai)
        if spec.fixed:
            end = start + spec.length
            if end > n:
                raise Gs1Error(Gs1ErrorCode.FIELD_LENGTH)
        else:
            gs = text.find(GS, start)
            end = n if gs == -1 else gs
        value = text[start:end]
        if GS in value:
            raise Gs1Error(Gs1ErrorCode.MALFORMED)
        _check_value(spec, value)
        fields.append((ai, value))
        pos = end
    return fields


_PAREN_AI = re.compile(r"\(([0-9]{2,4})\)")


def _fields_parenthesised(text: str) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    pos = 0
    n = len(text)
    while pos < n:
        m = _PAREN_AI.match(text, pos)
        if m is None:
            raise Gs1Error(Gs1ErrorCode.MALFORMED)
        ai = m.group(1)
        if ai not in AI_TABLE:
            raise Gs1Error(Gs1ErrorCode.UNKNOWN_AI)
        if ai == SERIAL_AI:
            raise Gs1Error(Gs1ErrorCode.SERIAL_NOT_ACCEPTED)
        start = m.end()
        nxt = text.find("(", start)
        end = n if nxt == -1 else nxt
        value = text[start:end]
        if ")" in value:
            raise Gs1Error(Gs1ErrorCode.MALFORMED)
        _check_value(AI_TABLE[ai], value)
        fields.append((ai, value))
        pos = end
    return fields


def parse_element_string(content: str, today: date) -> Gs1Data:
    """Parse a GS1 element string (FNC1 or parenthesised form) or bare GTIN digits."""
    text = _strip_identifier(content.strip())
    if not text.strip(GS):
        raise Gs1Error(Gs1ErrorCode.EMPTY)

    if _DIGITS.match(text) and len(text) in (8, 12, 13, 14):
        return Gs1Data(to_gtin14(text), None, "absent", False, False)

    fields = _fields_parenthesised(text) if text.startswith("(") else _fields_fnc1(text)

    seen: dict[str, str] = {}
    for ai, value in fields:
        if ai in seen and seen[ai] != value:
            raise Gs1Error(Gs1ErrorCode.DUPLICATE_AI)
        seen[ai] = value

    gtin = seen.get("01")
    if gtin is None:
        raise Gs1Error(Gs1ErrorCode.GTIN_MISSING)
    gtin14 = to_gtin14(gtin)

    expiry: date | None = None
    status: ExpiryStatus = "absent"
    if "17" in seen:
        expiry = parse_expiry(seen["17"], today)
        status = "valid" if expiry is not None else "invalid"

    national = seen.get(NATIONAL_CODE_AI)
    return Gs1Data(
        gtin14=gtin14,
        expiry=expiry,
        expiry_status=status,
        serial_present=False,
        lot_present="10" in seen,
        national_code=national if national and _NATIONAL_CODE.match(national) else None,
    )
