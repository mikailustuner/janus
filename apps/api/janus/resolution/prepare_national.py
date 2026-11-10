"""Products and ingredient lists of the Canadian and Italian sources (national-products design
§4, Req 3-5). Pure.

Health Canada DPD (`ca_dpd`): one product per marketed human DIN; ingredients in file order with
the strength as published (`STRENGTH STRENGTH_UNIT`, then ` / DOSAGE_VALUE DOSAGE_UNIT` when the
source states a reference quantity). AIFA open data (`eu_it_aifa`): one product per authorised
pack (AIC); ingredients are the rows of `PA_confezioni.csv`. Homeopathic registrations and
suspended packs are left out, and a pack with an unnamed ingredient row (`N.D.`) keeps an unnamed
ingredient, so it is never an exact match.

Names are mapped by the same ladder as every other source (neutral rules; no Italian word list
exists, so none is used). Two deterministic additions, both of which can only leave a name
unmapped or ambiguous, never choose between keys:

* DPD names of the form `A (B)` ("NORTRIPTYLINE (NORTRIPTYLINE HYDROCHLORIDE)": the ingredient and
  the form supplied): the name maps when `A` maps to one key and `B` maps to the same key or to
  none; two different keys are `ambiguous`.
* the national ATC bridge (the TİTCK rule of drug-resolution §5.3 step 6, per source): the name of
  a single-ingredient product whose published 7-character code belongs to exactly one eligible
  item maps to that item; a name bridged to two items is `ambiguous`.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from janus.resolution.canonical import canonical_line
from janus.resolution.matching import NO_MATCH, Match, NameIndex, Step, map_name
from janus.resolution.names import fold

CA_DPD = "ca_dpd"
IT_AIFA = "eu_it_aifa"
UNNAMED = "(unnamed ingredient)"
DPD_HUMAN_CLASS = "Human"
AIFA_HOMEOPATHIC = "Omeopatico"
AIFA_AUTHORISED = "Autorizzata"
AIFA_NOT_STATED = frozenset({"", "N.D."})  # the source's own "not available" spellings
AIFA_FORM_NOT_KNOWN = frozenset({"", "Non nota"})
AIFA_NO_UNIT = frozenset({"", "N.D.", "Q.TA E UM NON PRESENTI SU ET"})
BRIDGE_STEP: Step = "national_atc_bridge"

_PAREN = re.compile(r"^(?P<outer>[^()]+?)\s*\((?P<inner>[^()]+)\)$")
_ZERO = re.compile(r"^0*(\.0*)?$")
_THOUSANDS = re.compile(r"^[1-9][0-9]*\.[0-9]{3}$")


@dataclass(frozen=True)
class NationalProduct:
    """A Canadian or Italian product before ingredient decisions (the shape of `EuProduct`)."""

    product: dict[str, Any]
    names: tuple[tuple[str, str | None], ...]


@dataclass(frozen=True)
class LeftOut:
    """Source rows that did not become a product (coverage report)."""

    counts: Mapping[str, int] = field(default_factory=dict[str, int])


def _opt(value: Any) -> str | None:
    return None if value is None else str(value)


def _ordered(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Rows in canonical order, so product ids do not depend on file row order."""
    return sorted(rows, key=lambda r: canonical_line(r).encode("utf-8"))


# --- Health Canada DPD -------------------------------------------------------------------------


def dpd_strength(ingredient: Mapping[str, Any]) -> str | None:
    """`STRENGTH STRENGTH_UNIT[ / [DOSAGE_VALUE ]DOSAGE_UNIT]` from the published cells (trimmed),
    or `None` when the source gives no strength."""
    amount = str(ingredient.get("strength") or "").strip()
    unit = str(ingredient.get("strength_unit") or "").strip()
    if not amount or not unit:
        return None
    # Expressed as the base (BASE = Y) or as an equivalent / calculated amount: not comparable
    # with a strength of the salt, so no strength is shown for comparison.
    if str(ingredient.get("base") or "").strip() == "Y":
        return None
    if str(ingredient.get("strength_type") or "").strip():
        return None
    per = " ".join(
        x
        for x in (
            str(ingredient.get("dosage_value") or "").strip(),
            str(ingredient.get("dosage_unit") or "").strip(),
        )
        if x
    )
    return f"{amount} {unit} / {per}" if per else f"{amount} {unit}"


def dpd_products(rows: Iterable[Mapping[str, Any]]) -> tuple[list[NationalProduct], LeftOut]:
    """One product per marketed human DPD row, ids in canonical row order from 1. Veterinary,
    disinfectant and radiopharmaceutical rows are left out (counted)."""
    out: list[NationalProduct] = []
    left: defaultdict[str, int] = defaultdict(int)
    n = 0
    for r in _ordered(rows):
        if r.get("product_class") != DPD_HUMAN_CLASS:
            left["not_human_class"] += 1
            continue
        n += 1
        din = None if r.get("name_only") else _opt(r.get("din"))
        forms: list[str] = [str(f) for f in cast("list[Any]", r.get("forms") or []) if f]
        atc_rows = cast("list[Mapping[str, Any]]", r.get("atc") or [])
        codes = [str(a.get("code") or "") for a in atc_rows]
        status = _opt(r.get("status"))
        ingredients: Sequence[Mapping[str, Any]] = r.get("ingredients") or []
        product: dict[str, Any] = {
            "source_id": CA_DPD,
            "product_id": n,
            "region": "CA",
            "product_name": _opt(r.get("brand_name")),
            "brand_name": None,
            "generic_name": None,
            "ingredient_text": None,
            # One published code only: several codes do not say which one names the product.
            "published_atc": codes[0] if len(codes) == 1 and codes[0] else None,
            "product_type": None,
            "routes": tuple(str(x) for x in cast("list[Any]", r.get("routes") or []) if x),
            # Several published forms (kits) are shown together and have no form group.
            "dosage_form": "; ".join(forms) if forms else None,
            "marketing_end_date": None,
            "suspension_status": None,
            "name_only": din is None,
            "product_rxcuis": (),
            "codes": () if din is None else (("ca_din", din, din),),
            "status_published": (status,) if status else (),
        }
        names = tuple((str(i.get("name") or UNNAMED), dpd_strength(i)) for i in ingredients)
        declared = str(r.get("number_of_ais") or "").strip()
        if declared.isdigit() and int(declared) != len(ingredients):
            # The source counts another number of ingredients than it lists: never an exact match.
            names = (*names, (UNNAMED, None))
        out.append(NationalProduct(product, names))
    return out, LeftOut(dict(left))


def _names_form_of(outer: str, inner: str) -> bool:
    """The parenthesis starts with the outer name's first word: a salt or form of that substance
    ("DOXEPIN (DOXEPIN HYDROCHLORIDE)"), not another substance."""
    words = fold(outer).split()
    return bool(words) and fold(inner).startswith(words[0])


def map_dpd_name(name: str, mapper: Callable[[str], Match]) -> Match:
    """The DPD `A (B)` rule (module docstring). `mapper` is the ordinary ladder for one name."""
    whole = mapper(name)
    m = _PAREN.fullmatch(name.strip())
    if whole.status == "mapped" or m is None:
        return whole
    outer, inner = mapper(m["outer"]), mapper(m["inner"])
    if outer.status != "mapped":
        return whole
    if inner.status == "mapped" and inner.keys == outer.keys:
        return outer
    if inner.status == "none":
        return outer if _names_form_of(m["outer"], m["inner"]) else whole
    keys = tuple(sorted({*outer.keys, *inner.keys}))
    return Match("ambiguous", None, keys)


# --- AIFA open data ----------------------------------------------------------------------------


def aifa_strength(ingredient: Mapping[str, Any]) -> str | None:
    """`QUANTITA UNITA_MISURA` (trimmed) when the source gives both; a zero or absent quantity
    and the source's "not available" units give `None`."""
    amount = str(ingredient.get("quantity") or "").strip()
    unit = str(ingredient.get("unit") or "").strip()
    if not amount or _ZERO.fullmatch(amount) or unit in AIFA_NO_UNIT:
        return None
    if _THOUSANDS.fullmatch(amount):
        return None  # "1.000" reads as one thousand or as one: never guessed
    return f"{amount} {unit}"


def aifa_products(rows: Iterable[Mapping[str, Any]]) -> tuple[list[NationalProduct], LeftOut]:
    """One product per authorised, non-homeopathic AIFA pack, ids in canonical row order from 1."""
    out: list[NationalProduct] = []
    left: defaultdict[str, int] = defaultdict(int)
    n = 0
    for r in _ordered(rows):
        procedure = str(r.get("procedure") or "").strip()
        status = str(r.get("status") or "").strip()
        if procedure == AIFA_HOMEOPATHIC:
            left["homeopathic_registration"] += 1
            continue
        if status != AIFA_AUTHORISED:
            left["not_authorised"] += 1
            continue
        n += 1
        aic = None if r.get("name_only") else _opt(r.get("aic"))
        name = str(r.get("name") or "").strip()
        description = str(r.get("description") or "").strip()
        form = str(r.get("form") or "").strip()
        atc = str(r.get("atc_code") or "").strip()
        ingredients: Sequence[Mapping[str, Any]] = r.get("ingredients") or []
        product: dict[str, Any] = {
            "source_id": IT_AIFA,
            "product_id": n,
            "region": "EU",
            # The pack description tells the strengths and pack sizes of one medicine apart.
            "product_name": " ".join(x for x in (name, description) if x) or None,
            "brand_name": name or None,
            "generic_name": None,
            "ingredient_text": None,
            "published_atc": atc or None,
            "product_type": None,
            "routes": (),
            "dosage_form": None if form in AIFA_FORM_NOT_KNOWN else form,
            "marketing_end_date": None,
            "suspension_status": None,
            "name_only": aic is None,
            "product_rxcuis": (),
            "codes": () if aic is None else (("it_aic", aic, aic),),
            "status_published": tuple(s for s in (status, procedure) if s),
        }
        names: list[tuple[str, str | None]] = []
        for i in ingredients:
            published = str(i.get("name") or "").strip()
            if published in AIFA_NOT_STATED:
                names.append((UNNAMED, None))
            else:
                names.append((published, aifa_strength(i)))
        listed = "/".join(str(i.get("name") or "").strip() for i in ingredients)
        stated = str(r.get("ingredients_text") or "").split("/")
        if any(piece.strip() and piece.strip() not in listed for piece in stated):
            names.append((UNNAMED, None))  # the pack text names an ingredient the lines lack
        out.append(NationalProduct(product, tuple(names)))
    return out, LeftOut(dict(left))


# --- national ATC bridge -----------------------------------------------------------------------


def bridge_key(source_id: str, name: str) -> tuple[str, str]:
    return source_id, fold(name)


def bridged(bridge: Mapping[tuple[str, str], frozenset[str]], source_id: str, name: str) -> Match:
    """The bridge's answer for a name no earlier step maps: one key, several (ambiguous) or none."""
    keys = bridge.get(bridge_key(source_id, name))
    if not keys:
        return NO_MATCH
    return Match("mapped" if len(keys) == 1 else "ambiguous", BRIDGE_STEP, tuple(sorted(keys)))


def map_national_name(
    source_id: str,
    name: str,
    index: NameIndex,
    bridge: Mapping[tuple[str, str], frozenset[str]],
) -> Match:
    """The ladder (neutral rules), the DPD `A (B)` rule for Canada, then the national ATC bridge.
    A name that names two substances (`unsplit`) is never mapped through a product code."""
    if name == UNNAMED:
        return NO_MATCH

    def ladder(text: str) -> Match:
        return map_name(text, index, lang="en")

    hit = map_dpd_name(name, ladder) if source_id == CA_DPD else ladder(name)
    return bridged(bridge, source_id, name) if hit.status == "none" else hit
