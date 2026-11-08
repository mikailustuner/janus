"""Hypothesis strategies for drug resolution (drug-resolution design §7).

Synthetic only: no TİTCK data. Builders render the same field set in each GS1 form so that
properties can compare forms.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from hypothesis import strategies as st

from janus.resolution.atc import CombinationRules, RouteMap
from janus.resolution.gs1 import AI_TABLE, GS, gtin_check_digit

# GS1 character set 82 without "(" and ")", which the parenthesised form cannot carry.
CSET82_NO_PARENS = (
    "!\"%&'*+,-./0123456789:;<=>?ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"
)
CSET82 = CSET82_NO_PARENS + "()"


def with_check_digit(body: str) -> str:
    return body + str(gtin_check_digit(body))


def gtin14s() -> st.SearchStrategy[str]:
    return st.text(alphabet="0123456789", min_size=13, max_size=13).map(with_check_digit)


def short_gtins() -> st.SearchStrategy[str]:
    """Valid GTIN-8, GTIN-12 and GTIN-13."""
    return st.sampled_from([7, 11, 12]).flatmap(
        lambda n: st.text(alphabet="0123456789", min_size=n, max_size=n).map(with_check_digit)
    )


def yymmdd() -> st.SearchStrategy[str]:
    return st.integers(0, 999999).map(lambda n: f"{n:06d}")


def valid_yymmdd() -> st.SearchStrategy[str]:
    return st.tuples(st.integers(0, 99), st.integers(1, 12), st.integers(0, 28)).map(
        lambda t: f"{t[0]:02d}{t[1]:02d}{t[2]:02d}"
    )


def today_dates() -> st.SearchStrategy[date]:
    return st.dates(min_value=date(1951, 1, 1), max_value=date(9948, 12, 31))


@dataclass(frozen=True)
class Gs1Fields:
    """One field set: AI → value, in the order to render."""

    fields: tuple[tuple[str, str], ...]


def _value_for(ai: str, parens_allowed: bool) -> st.SearchStrategy[str]:
    spec = AI_TABLE[ai]
    if ai == "01":
        return gtin14s()
    if ai == "17":
        return yymmdd()
    alphabet = "0123456789" if spec.numeric else (CSET82 if parens_allowed else CSET82_NO_PARENS)
    if spec.fixed:
        return st.text(alphabet=alphabet, min_size=spec.length, max_size=spec.length)
    return st.text(alphabet=alphabet, min_size=1, max_size=spec.length)


# AI (21) is rejected by the API (drug-resolution DP19, P50), so general field sets never carry it.
OPTIONAL_AIS = [ai for ai in AI_TABLE if ai not in ("01", "21")]


@st.composite
def gs1_field_sets(draw: st.DrawFn, *, parens_allowed: bool = False) -> Gs1Fields:
    """(01) plus a random subset of other supported AIs, in random order."""
    others = draw(st.lists(st.sampled_from(OPTIONAL_AIS), unique=True, max_size=6))
    ais = draw(st.permutations(["01", *others]))
    return Gs1Fields(tuple((ai, draw(_value_for(ai, parens_allowed))) for ai in ais))


def render_parenthesised(f: Gs1Fields) -> str:
    return "".join(f"({ai}){value}" for ai, value in f.fields)


def render_fnc1(f: Gs1Fields, *, identifier: str = "", gs_after_fixed: bool = False) -> str:
    """FNC1 form: a GS ends every variable-length field except the last one."""
    out = [identifier]
    last = len(f.fields) - 1
    for i, (ai, value) in enumerate(f.fields):
        out.append(ai + value)
        variable = not AI_TABLE[ai].fixed
        if i != last and (variable or gs_after_fixed):
            out.append(GS)
    return "".join(out)


# --- NDC -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Ndc10:
    layout: str
    segments: tuple[str, str, str]

    @property
    def digits(self) -> str:
        return "".join(self.segments)

    @property
    def hyphenated(self) -> str:
        return "-".join(self.segments)

    @property
    def canonical11(self) -> str:
        a, b, c = self.segments
        return a.zfill(5) + b.zfill(4) + c.zfill(2)


@st.composite
def ndc10s(draw: st.DrawFn) -> Ndc10:
    layout = draw(st.sampled_from(["4-4-2", "5-3-2", "5-4-1"]))
    lengths = [int(x) for x in layout.split("-")]
    segs = tuple(draw(st.text(alphabet="0123456789", min_size=n, max_size=n)) for n in lengths)
    return Ndc10(layout, (segs[0], segs[1], segs[2]))


def label_prefixes() -> st.SearchStrategy[str]:
    return st.sampled_from(["", "NDC", "NDC:", "ndc ", "NDC: ", "N", "n"])


# --- synthetic sources (TİTCK-, openFDA- and Wikidata-shaped rows) ---------------------------

# Words that are not salt words and fold to themselves.
WORDS = ["alfazin", "betorol", "kavidin", "dumapril", "eslotan", "fenaxol", "gorvacin", "hilastin"]
SALTS = ["hidroklorur", "besilat", "sodyum", "monohidrat", "maleat"]
SYN_CODES = st.tuples(
    st.sampled_from("ACJN"),
    st.sampled_from(["01", "08", "09"]),
    st.sampled_from(["AA", "BB", "CA"]),
    st.sampled_from(["01", "02", "03", "51"]),
).map("".join)


def wikidata_row(
    qid: str, codes: list[str], labels: dict[str, str], aliases: dict[str, list[str]] | None = None
) -> dict[str, object]:
    row: dict[str, object] = {"qid": qid, "atc_codes": codes, "rxcuis": []}
    for lang in ("en", "tr", "de", "fr", "es"):
        row[f"label_{lang}"] = labels.get(lang)
        row[f"aliases_{lang}"] = (aliases or {}).get(lang, [])
    return row


def titck_row(
    barcode: str | None, name: str, ingredients: list[str], atc: str | None
) -> dict[str, object]:
    return {
        "barcode": barcode,
        "name_only": barcode is None,
        "product_name": name,
        "ingredient_text": ", ".join(ingredients) or None,
        "ingredients": ingredients,
        "atc_code": atc,
        "suspension_status": 0,
    }


def us_row(
    product_ndc: str,
    packages: list[str],
    ingredients: list[str],
    routes: list[str],
    product_type: str = "HUMAN PRESCRIPTION DRUG",
    brand: str | None = None,
) -> dict[str, object]:
    return {
        "product_ndc": product_ndc,
        "package_ndcs": packages,
        "product_type": product_type,
        "brand_name": brand,
        "generic_name": " and ".join(ingredients) or None,
        "active_ingredients": [{"name": n.upper(), "strength": "1 mg/1"} for n in ingredients],
        "rxcuis": [],
        "marketing_end_date": None,
        "route": routes,
        "dosage_form": "TABLET",
    }


RULES = CombinationRules(frozenset({"C09B", "A10BD"}), frozenset({"J01CA51"}), frozenset(), "t")
ROUTES = RouteMap(
    {
        "ORAL": ("A", "C", "J", "N"),
        "TOPICAL": ("D",),
        "orale": ("A", "C", "J", "N"),  # French BDPM route strings (Req 5.9)
        "cutanée": ("D",),
        "intraveineuse": ("J",),
    },
    "t",
)
COMBO_CODES = st.sampled_from(["C09BB03", "A10BD05", "J01CA51", "N01AA20", "C08CA51"])


def barcode13(i: int) -> str:
    return with_check_digit(f"869{i:09d}")


@st.composite
def sources(draw: st.DrawFn) -> tuple[list[Any], list[Any], list[Any]]:
    """Synthetic Wikidata items and TİTCK/openFDA products built from them."""
    n = draw(st.integers(2, len(WORDS)))
    words = WORDS[:n]
    wd: list[Any] = []
    for i, w in enumerate(words, start=1):
        codes = draw(st.lists(st.one_of(SYN_CODES, COMBO_CODES), min_size=1, max_size=3))
        lang = draw(st.sampled_from(["en", "tr"]))
        wd.append(wikidata_row(f"Q{i}", codes, {lang: w}))
    name = st.one_of(
        st.sampled_from(words),
        st.tuples(st.sampled_from(words), st.sampled_from(SALTS)).map(" ".join),
        st.just("bilinmeyen madde"),
        st.tuples(st.sampled_from(words), st.sampled_from(words)).map(" ".join),  # unsplit
    )
    published = st.one_of(st.none(), SYN_CODES, COMBO_CODES, st.sampled_from(["B05D", "S03CA0l"]))
    tr: list[Any] = []
    for i in range(draw(st.integers(1, 12))):
        ings = draw(st.lists(name, min_size=0, max_size=3))
        barcode = barcode13(draw(st.integers(1, 6))) if draw(st.integers(0, 5)) else None
        tr.append(titck_row(barcode, f"URUN {i}", ings, draw(published)))
    us: list[Any] = []
    for i in range(draw(st.integers(0, 6))):
        ings = draw(st.lists(st.sampled_from(words), min_size=1, max_size=2))
        routes = draw(st.lists(st.sampled_from(["ORAL", "TOPICAL", "NASAL"]), max_size=2))
        us.append(us_row(f"1234{i}-678", [f"1234{i}-678-90"], ings, routes))
    return tr, us, wd


# --- BDPM- and Nomenclátor-shaped rows (drug-resolution Phase 2) ----------------------------------


def bdpm_row(
    i: int,
    denomination: str,
    names: list[str],
    *,
    routes: str | None = "orale",
    sa: dict[int, str] | None = None,
    cip13: str | None = None,
    commercial: str = "Déclaration de commercialisation",
    declared: str = "16/03/2011",
) -> dict[str, object]:
    """A BDPM presentation: one FT line per name (links 1..n); `sa` adds an SA line (the
    substance as formulated) to link k, which the FT line supersedes."""
    lines: list[dict[str, object]] = []
    for k, name in enumerate(names, start=1):
        lines.append(_line(name, "FT", k))
        if sa and k in sa:
            lines.append(_line(sa[k], "SA", k))
    code = cip13 if cip13 is not None else f"3400{i:09d}"
    return {
        "cip13": code,
        "name_only": False,
        "cip7": code[6:],
        "cis": str(60000000 + i),
        "presentation_label": "plaquette(s) de 30 comprimé(s)",
        "presentation_status": "Présentation active",
        "presentation_commercialisation": commercial,
        "presentation_declaration_date": declared,
        "specialty_missing": False,
        "denomination": denomination,
        "pharmaceutical_form": "comprimé",
        "routes": routes,
        "authorisation_status": "Autorisation active",
        "procedure": "Procédure nationale",
        "commercialisation_status": "Commercialisée",
        "authorisation_date": "28/10/2010",
        "holder": " TITULAIRE",
        "composition": lines,
    }


def _line(name: str, nature: str, link: int) -> dict[str, object]:
    return {
        "form": "comprimé",
        "substance_code": str(link),
        "substance_name": name,
        "dosage": "1,00 mg",
        "reference": "un comprimé",
        "nature": nature,
        "link": str(link),
    }


def cima_row(
    i: int,
    name: str,
    names: list[str],
    atc: str | None,
    *,
    ntins: list[str] | None = None,
    gtins: list[str] | None = None,
) -> dict[str, object]:
    """A Nomenclátor presentation: ingredients in `orden_colacion` order 1..n."""
    cn = f"{600000 + i}"
    return {
        "cn": cn,
        "name_only": False,
        "registration_number": str(66000 + i),
        "name": name,
        "presentation_name": f"{name}, 30 comprimidos",
        "atc_code": atc,
        "ingredients": [
            {"code": str(k), "name": n, "dose": "500", "dose_unit": "mg", "order": k}
            for k, n in enumerate(names, start=1)
        ],
        "ntins": ntins if ntins is not None else [with_check_digit("0847000" + cn)],
        "gtins": gtins or [],
        "route_codes": ["49"],
        "commercialised": True,
        "registration_status": "1",
        "registration_status_date": "2020-08-11",
        "presentation_status": "1",
        "presentation_status_date": "2020-08-11",
        "serialised": True,
    }


HOMEOPATHIC_SUFFIX = " pour préparations homéopathiques"


@st.composite
def eu_rows(draw: st.DrawFn) -> tuple[list[Any], list[Any]]:
    """BDPM-like and Nomenclátor-like rows over the same words as `sources()`."""
    name = st.one_of(
        st.sampled_from(WORDS),
        st.tuples(st.sampled_from(WORDS), st.sampled_from(SALTS)).map(" ".join),
        st.just("substance inconnue"),
        st.tuples(st.sampled_from(WORDS), st.sampled_from(WORDS)).map(" ".join),  # unsplit
        st.sampled_from(WORDS).map(lambda w: w + HOMEOPATHIC_SUFFIX),
    )
    routes = st.one_of(
        st.none(),
        st.sampled_from(["orale", "cutanée", "orale;cutanée", "intraveineuse", "voie inconnue"]),
    )
    fr: list[Any] = []
    for i in range(draw(st.integers(0, 8))):
        names = draw(st.lists(name, min_size=0, max_size=3))
        fr.append(bdpm_row(i + 1, f"SPECIALITE {i}", names, routes=draw(routes)))
    published = st.one_of(st.none(), SYN_CODES, COMBO_CODES)
    es: list[Any] = []
    for i in range(draw(st.integers(0, 8))):
        names = draw(st.lists(name, min_size=0, max_size=3))
        es.append(cima_row(i + 1, f"MEDICAMENTO {i}", names, draw(published)))
    return fr, es
