"""Products and ingredient lists of the French and Spanish sources (drug-resolution design
§14.2, §14.3). Pure.

BDPM: the composition lines of a presentation are grouped by link number; per link the `FT` names
(therapeutic fraction) stand for the ingredient, and only a link without an `FT` line uses its `SA`
names (substance as formulated). Nomenclátor: the ingredients in `orden_colacion` order.
Both keep names and strengths exactly as published (licence: data are not altered).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from janus.resolution.canonical import canonical_line
from janus.resolution.names import fold

UNNAMED = "(unnamed ingredient)"
HOMEOPATHIC_MARKER = "pour preparations homeopathiques"


@dataclass(frozen=True)
class SourceIngredient:
    """One ingredient of a presentation: the published name and the dosage it was named from."""

    name: str
    strength: str | None


@dataclass(frozen=True)
class LinkStats:
    """Composition lines that did not become an ingredient of their own (coverage report)."""

    links: int = 0
    superseded_sa_lines: int = 0  # SA lines of a link that has an FT line
    multi_ft_links: int = 0  # links with two or more FT lines (each is an ingredient)


def _opt(value: Any) -> str | None:
    return None if value is None else str(value)


def bdpm_ingredients(
    composition: Sequence[Mapping[str, Any]],
) -> tuple[tuple[SourceIngredient, ...], LinkStats]:
    """Ingredients of a BDPM presentation from its composition lines (Req 5.8).

    Links are taken in the order of their first line; a line without a link number is a link of
    its own. Per link: every `FT` line is an ingredient; if there is none, every `SA` line is.
    """
    order: list[str] = []
    ft: dict[str, list[Mapping[str, Any]]] = {}
    sa: dict[str, list[Mapping[str, Any]]] = {}
    for i, line in enumerate(composition):
        link = _opt(line.get("link")) or f"\x00{i}"
        if link not in ft:
            order.append(link)
            ft[link], sa[link] = [], []
        (ft if line.get("nature") == "FT" else sa)[link].append(line)
    out: list[SourceIngredient] = []
    superseded = multi_ft = 0
    for link in order:
        chosen = ft[link] or sa[link]
        if ft[link]:
            superseded += len(sa[link])
            multi_ft += len(ft[link]) > 1
        out.extend(
            SourceIngredient(str(c.get("substance_name") or UNNAMED), _opt(c.get("dosage")))
            for c in chosen
        )
    return tuple(out), LinkStats(len(order), superseded, multi_ft)


def cima_ingredients(ingredients: Sequence[Mapping[str, Any]]) -> tuple[SourceIngredient, ...]:
    """Ingredients of a Nomenclátor presentation in `orden_colacion` order (file order breaks ties
    and puts a missing order last)."""
    indexed = list(enumerate(ingredients))
    indexed.sort(key=lambda p: (p[1].get("order") is None, p[1].get("order") or 0, p[0]))
    out: list[SourceIngredient] = []
    for _, ing in indexed:
        dose = _opt(ing.get("dose"))
        unit = _opt(ing.get("dose_unit"))
        strength = " ".join(x for x in (dose, unit) if x) or None
        out.append(SourceIngredient(str(ing.get("name") or UNNAMED), strength))
    return tuple(out)


def is_homeopathic_name(name: str) -> bool:
    """A BDPM substance name that carries the homeopathic marker (Req 12.10)."""
    return HOMEOPATHIC_MARKER in fold(name)


# --- products (design §14.2, §14.3) -----------------------------------------------------------

FR_BDPM = "eu_fr_bdpm"
ES_CIMA = "eu_es_cima"
_DMY = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_DIGITS = re.compile(r"^[0-9]+$")


@dataclass(frozen=True)
class EuProduct:
    """A French or Spanish presentation before ingredient decisions: the product fields in the
    shape of `PreparedProduct` (without ingredients), the published ingredient names with their
    strengths, the language of the ladder and the homeopathic flag (BDPM names only)."""

    product: dict[str, Any]
    names: tuple[tuple[str, str | None], ...]
    lang: Literal["fr", "es"]
    homeopathic: bool = False
    stats: LinkStats = LinkStats()


def _ordered(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Rows in canonical order, so product ids do not depend on file row order (design §4.3)."""
    return sorted(rows, key=lambda r: canonical_line(r).encode("utf-8"))


def _routes(text: Any) -> tuple[str, ...]:
    """The BDPM `routes` text split at `;` (Req 5.9): pieces trimmed, empty pieces dropped."""
    return tuple(p.strip() for p in str(text or "").split(";") if p.strip())


def iso_date(dmy: str | None) -> str | None:
    """`dd/mm/yyyy` as published by the BDPM to ISO, else `None`."""
    m = _DMY.match(dmy or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def is_marketing_stop(status: str | None) -> bool:
    """`Déclaration d'arrêt de commercialisation` or `Arrêt de commercialisation …` (not a
    suspension)."""
    return status is not None and "arret de commercialisation" in fold(status)


def bdpm_products(rows: Iterable[Mapping[str, Any]]) -> list[EuProduct]:
    """One product per BDPM presentation row, ids in canonical row order from 1."""
    out: list[EuProduct] = []
    for i, r in enumerate(_ordered(rows), start=1):
        cip13 = None if r.get("name_only") else _opt(r.get("cip13"))
        ings, stats = bdpm_ingredients(r.get("composition") or [])
        commercial = _opt(r.get("presentation_commercialisation"))
        dated = " ".join(x for x in (commercial, _opt(r.get("presentation_declaration_date"))) if x)
        status = tuple(
            s
            for s in (
                _opt(r.get("authorisation_status")),
                _opt(r.get("procedure")),
                _opt(r.get("commercialisation_status")),
                _opt(r.get("presentation_status")),
                dated or None,
            )
            if s
        )
        product: dict[str, Any] = {
            "source_id": FR_BDPM,
            "product_id": i,
            "region": "EU",
            "product_name": _opt(r.get("denomination")),
            "brand_name": None,
            "generic_name": None,
            "ingredient_text": None,
            "published_atc": None,
            "product_type": None,
            "routes": _routes(r.get("routes")),
            "dosage_form": _opt(r.get("pharmaceutical_form")),
            "marketing_end_date": (
                iso_date(_opt(r.get("presentation_declaration_date")))
                if is_marketing_stop(commercial)
                else None
            ),
            "suspension_status": None,
            "name_only": cip13 is None,
            "product_rxcuis": (),
            "codes": () if cip13 is None else (("fr_cip13", cip13, cip13),),
            "status_published": status,
        }
        out.append(
            EuProduct(
                product,
                tuple((x.name, x.strength) for x in ings),
                "fr",
                any(is_homeopathic_name(x.name) for x in ings),
                stats,
            )
        )
    return out


def _gtin14(value: Any) -> tuple[str, str] | None:
    """(code padded to 14 digits, as published) for a digit string of at most 14 digits."""
    text = _opt(value)
    if text is None or not _DIGITS.match(text) or len(text) > 14:
        return None
    return text.zfill(14), text


def cima_products(rows: Iterable[Mapping[str, Any]]) -> list[EuProduct]:
    """One product per Nomenclátor presentation row, ids in canonical row order from 1."""
    out: list[EuProduct] = []
    for i, r in enumerate(_ordered(rows), start=1):
        cn = None if r.get("name_only") else _opt(r.get("cn"))
        codes: list[tuple[str, str, str]] = [] if cn is None else [("es_cn", cn, cn)]
        for kind, key in (("es_ntin", "ntins"), ("es_gtin", "gtins")):
            seen: set[str] = set()
            values: Sequence[Any] = r.get(key) or []
            for value in values:
                pair = _gtin14(value)
                if pair is not None and pair[0] not in seen:
                    seen.add(pair[0])
                    codes.append((kind, pair[0], pair[1]))
        ings = cima_ingredients(r.get("ingredients") or [])
        flag = r.get("commercialised")
        status = tuple(
            s
            for s in (
                None if flag is None else f"commercialised:{str(bool(flag)).lower()}",
                _status(
                    "registration_status",
                    r.get("registration_status"),
                    r.get("registration_status_date"),
                ),
                _status(
                    "presentation_status",
                    r.get("presentation_status"),
                    r.get("presentation_status_date"),
                ),
                None
                if r.get("serialised") is None
                else f"serialised:{str(bool(r['serialised'])).lower()}",
            )
            if s
        )
        name = _opt(r.get("name"))
        product: dict[str, Any] = {
            "source_id": ES_CIMA,
            "product_id": i,
            "region": "EU",
            "product_name": _opt(r.get("presentation_name")) or name,
            "brand_name": name,
            "generic_name": None,
            "ingredient_text": None,
            "published_atc": _opt(r.get("atc_code")),
            "product_type": None,
            "routes": (),
            "dosage_form": None,
            "marketing_end_date": None,
            "suspension_status": None,
            "name_only": cn is None,
            "product_rxcuis": (),
            "codes": tuple(codes),
            "status_published": status,
        }
        out.append(EuProduct(product, tuple((x.name, x.strength) for x in ings), "es"))
    return out


def _status(label: str, code: Any, date: Any) -> str | None:
    text = " ".join(x for x in (_opt(code), _opt(date)) if x)
    return f"{label}:{text}" if text else None
