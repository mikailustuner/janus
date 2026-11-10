"""Strength codes (medication-passport design §5.1, DP5, DP6). Pure.

`strength_code(source_id, published, form_group)` turns one published ingredient strength into a
normalised code (amount, unit, basis) or `None`. Exact rational arithmetic: mass in micrograms, IU
kept apart, no tolerance, no rounding. A value is given only where the source states (or, for the
BDPM, the form implies) what the amount refers to:

- `openfda_ndc`: `A U/1` (per unit, only for the countable form groups: elsewhere `/1` may be per
  spray or per actuation, owner decision R2), `A U/N mL` (per mL, A / N; `/mL` is `/1 mL`),
  `A U/N g` (per g).
- `eu_fr_bdpm`: `A U` with French decimals and space-grouped thousands; per unit only for the
  countable form groups, else `None` (the reference quantity is not loaded).
- `eu_es_cima`: `A U`, parsed for reports; the basis is not loaded, so always `None`.
- `titck`: no strength stored; always `None`.
- `ca_dpd`: `A U` (per unit only for the countable form groups, as for the BDPM), `A U / N ML` or
  `A U / ML` (per mL), `A U / N L` (per mL, A / (1000 N)), `A U / N G` (per g). Every other
  reference unit (vial, sachet, actuation, hour, `W/W` …) gives `None`. `UNIT` is not IU.
- `eu_it_aifa`: `A U` with AIFA's unit names (`AIFA_UNITS`): plain mass and international units
  (per unit only for the countable form groups) and mass per millilitre, litre or gram.

U is a mass unit (`kg`, `g`, `mg`, `ug`, `mcg`, `µg`, `microgramme(s)`, `microgramo(s)`) or IU
(`[iU]`, `[IU]`, `UI`). Homeopathic units, `[USP'U]`, `%`, mass-per-mass ratios and every other
spelling give `None`; so does a division that does not end within six decimals, and an amount that
does not fit the request pattern of §3.1.

`python -m janus.passport.strength` prints, per source of the current dataset, how many ingredient
rows have a strength, how many parse and how many get a code (counts only).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from typing import Literal

from janus.passport.forms import COUNTABLE_GROUPS

Unit = Literal["ug", "IU"]
Basis = Literal["unit", "mL", "g"]
AMOUNT = re.compile(r"^(0|[1-9][0-9]{0,8})(\.[0-9]{0,5}[1-9])?$")  # request pattern (§3.1)
SCALE = 10**6  # at most six decimals
# Sources for which `strength_code` can give a code at all (design §3.2 `can_compare.strength`).
CODED_SOURCES: frozenset[str] = frozenset({"openfda_ndc", "eu_fr_bdpm", "ca_dpd", "eu_it_aifa"})

MASS_UG: dict[str, int] = {
    "kg": 10**9,
    "g": 10**6,
    "mg": 10**3,
    "ug": 1,
    "mcg": 1,
    "µg": 1,  # micro sign U+00B5
    "μg": 1,  # Greek mu U+03BC
    "microgramme": 1,
    "microgrammes": 1,
    "microgramo": 1,
    "microgramos": 1,
}
IU_SPELLINGS = frozenset({"[iu]", "ui"})

_DEC = r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)"
_US = re.compile(
    rf"^(?P<a>{_DEC})\s*(?P<u>[a-z\[\]µμ]+)\s*/\s*(?:(?P<n>{_DEC})\s*)?(?P<du>[a-z]+)?$",
    re.IGNORECASE,
)
# French and Spanish: decimal comma, thousands grouped by a space (also a no-break space).
_EU = re.compile(
    r"^(?P<i>[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+|[0-9]+)"
    r"(?:,(?P<f>[0-9]+))?\s*(?P<u>[a-zµμ\[\]]+)$",
    re.IGNORECASE,
)


# Health Canada DPD: `A U` or `A U / [N ]DU`, as composed from the published cells by
# `resolution/prepare_national.dpd_strength`.
_CA = re.compile(
    rf"^(?P<a>{_DEC})\s*(?P<u>[a-zµμ]+)(?:\s*/\s*(?:(?P<n>{_DEC})\s*)?(?P<du>[a-z]+))?$",
    re.IGNORECASE,
)
# Reference units of the DPD that are a volume or a mass: (basis, how many of it one `DU` is).
_CA_PER: dict[str, tuple[Basis, int]] = {"ml": ("mL", 1), "l": ("mL", 1000), "g": ("g", 1)}
# AIFA unit names: (unit, micrograms or IU per one, basis, how many of the basis the name means).
AIFA_UNITS: dict[str, tuple[Unit, int, Basis | None, int]] = {
    "milligrammi": ("ug", 10**3, None, 1),
    "grammi": ("ug", 10**6, None, 1),
    "microgrammi": ("ug", 1, None, 1),
    "international unit(s)": ("IU", 1, None, 1),
    "milligram(s)/millilitre": ("ug", 10**3, "mL", 1),
    "microgram(s)/millilitre": ("ug", 1, "mL", 1),
    "gram(s)/millilitre": ("ug", 10**6, "mL", 1),
    "gram(s)/litre": ("ug", 10**6, "mL", 1000),
    "milligram(s)/litre": ("ug", 10**3, "mL", 1000),
    "milligram(s)/gram": ("ug", 10**3, "g", 1),
    "microgram(s)/gram": ("ug", 1, "g", 1),
}
_IT = re.compile(rf"^(?P<a>{_DEC}) (?P<u>.+)$")


@dataclass(frozen=True)
class StrengthCode:
    amount: str  # canonical decimal: no exponent, no trailing zeros, > 0
    unit: Unit
    basis: Basis


@dataclass(frozen=True)
class Quantity:
    """A parsed published strength: `amount` per one `basis` (`None` = not stated)."""

    amount: Fraction
    unit: Unit
    basis: Basis | None


def _unit(spelling: str) -> tuple[Unit, int] | None:
    s = spelling.lower()
    if s in IU_SPELLINGS:
        return ("IU", 1)
    factor = MASS_UG.get(s)
    return None if factor is None else ("ug", factor)


def canonical(value: Fraction) -> str | None:
    """The canonical decimal of `value`, or `None` when it is not positive, does not end within
    six decimals, or does not fit the request pattern."""
    if value <= 0:
        return None
    scaled = value * SCALE
    if scaled.denominator != 1:
        return None
    whole, frac = divmod(scaled.numerator, SCALE)
    text = str(whole) if frac == 0 else f"{whole}.{frac:06d}".rstrip("0")
    return text if AMOUNT.fullmatch(text) else None


def _parse_us(published: str) -> Quantity | None:
    m = _US.fullmatch(published.strip())
    if m is None:
        return None
    unit = _unit(m["u"])
    if unit is None:
        return None
    n = Fraction(m["n"]) if m["n"] else Fraction(1)
    if n <= 0:
        return None
    du = m["du"]
    if du is None:
        if m["n"] is None or n != 1:
            return None
        basis: Basis = "unit"
    elif du.lower() == "ml":
        basis = "mL"
    elif du == "g":
        basis = "g"
    else:
        return None
    return Quantity(Fraction(m["a"]) * unit[1] / n, unit[0], basis)


def _parse_eu(published: str) -> Quantity | None:
    m = _EU.fullmatch(published.strip())
    if m is None:
        return None
    unit = _unit(m["u"])
    if unit is None:
        return None
    whole = re.sub(r"[ \u00a0\u202f]", "", m["i"])
    value = Fraction(f"{whole}.{m['f']}") if m["f"] else Fraction(whole)
    return Quantity(value * unit[1], unit[0], None)


def _parse_ca(published: str) -> Quantity | None:
    m = _CA.fullmatch(published.strip())
    if m is None:
        return None
    unit = _unit(m["u"])
    if unit is None or unit[0] != "ug":
        return None  # `UNIT` is not an international unit; `%` and the like are not a mass
    amount = Fraction(m["a"]) * unit[1]
    if m["du"] is None:
        return Quantity(amount, unit[0], None)
    per = _CA_PER.get(m["du"].lower())
    n = Fraction(m["n"]) if m["n"] else Fraction(1)
    if per is None or n <= 0:
        return None
    return Quantity(amount / (n * per[1]), unit[0], per[0])


def _parse_it(published: str) -> Quantity | None:
    m = _IT.fullmatch(published.strip())
    spec = AIFA_UNITS.get(m["u"]) if m else None
    if m is None or spec is None:
        return None
    unit, factor, basis, per = spec
    return Quantity(Fraction(m["a"]) * factor / per, unit, basis)


def parse(source_id: str, published: str | None) -> Quantity | None:
    """The quantity a source's published strength states, or `None` (never raises)."""
    if not published:
        return None
    if source_id == "openfda_ndc":
        return _parse_us(published)
    if source_id in ("eu_fr_bdpm", "eu_es_cima"):
        return _parse_eu(published)
    if source_id == "ca_dpd":
        return _parse_ca(published)
    if source_id == "eu_it_aifa":
        return _parse_it(published)
    return None


@lru_cache(maxsize=65536)
def strength_code(
    source_id: str, published: str | None, form_group: str | None
) -> StrengthCode | None:
    """The normalised strength of one published ingredient strength, or `None` (never raises)."""
    q = parse(source_id, published)
    if q is None:
        return None
    basis = q.basis
    if source_id == "eu_fr_bdpm":
        basis = "unit" if form_group in COUNTABLE_GROUPS else None
    elif source_id in ("ca_dpd", "eu_it_aifa"):
        # No reference quantity stated: per unit only for tablets and capsules, as for the BDPM.
        if basis is None and form_group in COUNTABLE_GROUPS:
            basis = "unit"
    elif source_id != "openfda_ndc":
        basis = None  # the Nomenclátor basis is not loaded (OD1, owner decision 3)
    elif basis == "unit" and form_group not in COUNTABLE_GROUPS:
        basis = None  # `/1` is per spray or per actuation outside tablets and capsules (R2)
    if basis is None:
        return None
    amount = canonical(q.amount)
    return None if amount is None else StrengthCode(amount, q.unit, basis)


# --- typed entry from the box (DP21, design §6.6, P21) ---------------------------------------

# The controlled inputs of the client: an amount with a decimal point or comma (at most six
# decimals), a unit and "per tablet, capsule or unit" / "per mL". `apps/web/src/passport/entry.ts`
# implements the same rule; a shared fixture of generated cases keeps the two equal (P21).
# A separator followed by exactly three digits after a non-zero whole part ("1,000", "1.000") is
# refused: it reads as a thousands group in English and as a decimal elsewhere (or the reverse in
# German), and a misread amount must never become a "same strength" answer.
ENTRY_UNITS: dict[str, tuple[Unit, int]] = {
    "mg": ("ug", 10**3),
    "g": ("ug", 10**6),
    "ug": ("ug", 1),
    "IU": ("IU", 1),
}
ENTRY_BASES: dict[str, Basis] = {"unit": "unit", "mL": "mL"}
_ENTRY = re.compile(r"^([0-9]{1,9})(?:[.,]([0-9]{1,6}))?$")


def entry_code(amount: str, unit: str, basis: str) -> StrengthCode | None:
    """The strength code of a strength typed from the box, or `None` (never raises)."""
    m = _ENTRY.fullmatch(amount.strip(" "))
    spec = ENTRY_UNITS.get(unit)
    per = ENTRY_BASES.get(basis)
    if m is None or spec is None or per is None:
        return None
    if m[2] is not None and len(m[2]) == 3 and int(m[1]) != 0:
        return None  # "1,000" / "1.000": thousands group or decimal, ambiguous
    value = Fraction(f"{m[1]}.{m[2]}") if m[2] else Fraction(m[1])
    text = canonical(value * spec[1])
    return None if text is None else StrengthCode(text, spec[0], per)


# --- report (counts only) -------------------------------------------------------------------

_REPORT_SQL = """
SELECT i.source_id, i.strength, r.dosage_form, r.routes, count(*)
FROM res_product_ingredient i
JOIN res_product r USING (dataset_id, source_id, product_id)
WHERE i.dataset_id = (SELECT dataset_id FROM res_current)
GROUP BY 1, 2, 3, 4
"""


def main(argv: Sequence[str] | None = None) -> int:
    import psycopg

    from janus.passport import forms
    from janus.settings import Settings

    parser = argparse.ArgumentParser(prog="python -m janus.passport.strength")
    parser.parse_args(argv)
    settings = Settings.from_env()
    if not settings.database_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    table = forms.load()
    rows: Counter[tuple[str, str]] = Counter()
    with psycopg.connect(settings.database_url) as conn, conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        for source, published, form, routes, count in conn.execute(_REPORT_SQL):
            rows[(source, "rows")] += count
            if published:
                rows[(source, "with_strength")] += count
            if parse(source, published) is not None:
                rows[(source, "parsed")] += count
            if strength_code(source, published, table.group(source, form, routes)) is not None:
                rows[(source, "coded")] += count
    for source in sorted({s for s, _ in rows}):
        total = rows[(source, "rows")]
        parts = [f"{k} {rows[(source, k)]}" for k in ("with_strength", "parsed", "coded")]
        share = rows[(source, "coded")] / total if total else 0.0
        print(f"{source}: rows {total}, {', '.join(parts)} ({share:.1%} coded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
