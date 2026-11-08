"""Strength codes (medication-passport design §5.1, DP5, DP6). Pure.

`strength_code(source_id, published, form_group)` turns one published ingredient strength into a
normalised code (amount, unit, basis) or `None`. Exact rational arithmetic: mass in micrograms, IU
kept apart, no tolerance, no rounding. A value is given only where the source states (or, for the
BDPM, the form implies) what the amount refers to:

- `openfda_ndc`: `A U/1` (per unit), `A U/N mL` (per mL, A / N; `/mL` is `/1 mL`), `A U/N g`
  (per g).
- `eu_fr_bdpm`: `A U` with French decimals and space-grouped thousands; per unit only for the
  countable form groups, else `None` (the reference quantity is not loaded).
- `eu_es_cima`: `A U`, parsed for reports; the basis is not loaded, so always `None`.
- `titck`: no strength stored; always `None`.

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


def parse(source_id: str, published: str | None) -> Quantity | None:
    """The quantity a source's published strength states, or `None` (never raises)."""
    if not published:
        return None
    if source_id == "openfda_ndc":
        return _parse_us(published)
    if source_id in ("eu_fr_bdpm", "eu_es_cima"):
        return _parse_eu(published)
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
    elif source_id != "openfda_ndc":
        basis = None  # the Nomenclátor basis is not loaded (OD1, owner decision 3)
    if basis is None:
        return None
    amount = canonical(q.amount)
    return None if amount is None else StrengthCode(amount, q.unit, basis)


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
