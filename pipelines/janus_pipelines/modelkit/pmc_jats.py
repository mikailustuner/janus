"""JATS article XML -> the shared input of both PMC table readers (spec model-kit, milestone M5).

Tables become grids (row and column spans expanded: a spanned cell repeats its text); the header
rows are the rows of `<thead>` (or, without one, the rows above the first row with a number, decided
by each reader). The methods text is the text of the sections whose title or type names methods,
design, subjects or materials. Nothing here reads a value. Research use only. Not for clinical
decisions."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Final

_METHODS: Final = re.compile(
    r"method|design|subjects|participants|patients and|materials|study population|protocol|procedures",
    re.I,
)
_NCT: Final = re.compile(r"\bNCT\s?0?\d{7,8}\b")


@dataclass(frozen=True)
class Table:
    table_id: str  # the table-wrap id, or t<index>
    label: str  # "Table 2"
    caption: str
    grid: tuple[tuple[str, ...], ...]
    head_rows: int  # rows of <thead>; 0 when the table has none
    footnotes: str


@dataclass(frozen=True)
class Article:
    pmcid: str
    title: str
    journal: str
    year: str
    doi: str
    authors: tuple[str, ...]
    keywords: str
    abstract: str
    methods: str
    tables: tuple[Table, ...]
    nct_ids: tuple[str, ...]
    licence: str


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def _grid(table: ET.Element) -> tuple[list[list[str]], int]:
    rows: list[ET.Element] = []
    head = 0
    thead = table.find(".//thead")
    if thead is not None:
        hr = thead.findall(".//tr")
        rows += hr
        head = len(hr)
    for tb in table.findall(".//tbody"):
        rows += tb.findall(".//tr")
    if not rows:
        rows = table.findall(".//tr")
        head = 0
    grid: list[list[str | None]] = []
    for r, tr in enumerate(rows):
        while len(grid) <= r:
            grid.append([])
        c = 0
        for cell in tr:
            if cell.tag not in ("td", "th"):
                continue
            while c < len(grid[r]) and grid[r][c] is not None:
                c += 1
            rs = max(1, min(50, int(cell.get("rowspan", "1") or 1)))
            cs = max(1, min(50, int(cell.get("colspan", "1") or 1)))
            text = _text(cell)
            for dr in range(rs):
                while len(grid) <= r + dr:
                    grid.append([])
                row = grid[r + dr]
                for dc in range(cs):
                    while len(row) <= c + dc:
                        row.append(None)
                    row[c + dc] = text
            c += cs
    width = max((len(r) for r in grid), default=0)
    return [[x if x is not None else "" for x in r] + [""] * (width - len(r)) for r in grid], head


def parse_article(xml: bytes, pmcid: str, licence: str) -> Article:
    root = ET.fromstring(xml)  # noqa: S314 - public archive file
    meta = root.find(".//article-meta")
    title = _text(meta.find(".//article-title") if meta is not None else None)
    journal = _text(root.find(".//journal-title"))
    year = _text(meta.find(".//pub-date/year")) if meta is not None else ""
    doi = ""
    for aid in root.iter("article-id"):
        if aid.get("pub-id-type") == "doi":
            doi = _text(aid)
    authors: list[str] = []
    for c in root.iterfind(".//contrib-group/contrib"):
        if c.get("contrib-type", "author") != "author":
            continue
        name = c.find("name")
        if name is not None:
            authors.append(
                " ".join(
                    x for x in (_text(name.find("given-names")), _text(name.find("surname"))) if x
                )
            )
        elif (collab := c.find("collab")) is not None:
            authors.append(_text(collab))
    keywords = " ; ".join(_text(k) for k in root.iterfind(".//kwd"))
    abstract = " ".join(_text(a) for a in root.iterfind(".//abstract"))
    body = root.find(".//body")
    methods_parts: list[str] = []
    if body is not None:
        for sec in body.iter("sec"):
            st = sec.get("sec-type", "") + " " + _text(sec.find("title"))
            if _METHODS.search(st):
                methods_parts += [_text(p) for p in sec.findall("p")]
    tables: list[Table] = []
    for i, tw in enumerate(root.iter("table-wrap")):
        tbl = tw.find(".//table")
        if tbl is None:
            continue
        grid, head = _grid(tbl)
        if not grid:
            continue
        tables.append(
            Table(
                tw.get("id") or f"t{i}",
                _text(tw.find("label")),
                _text(tw.find("caption")),
                tuple(tuple(r) for r in grid),
                head,
                " ".join(_text(f) for f in tw.iterfind(".//table-wrap-foot")),
            )
        )
    full = _text(root)
    ncts = sorted({re.sub(r"\s", "", m.group(0)).upper() for m in _NCT.finditer(full)})
    return Article(
        pmcid, title, journal, year, doi, tuple(authors), keywords, abstract, " ".join(methods_parts),
        tuple(tables), tuple(n if len(n) == 11 else "NCT" + n[3:].zfill(8) for n in ncts), licence,
    )  # fmt: skip


def attribution(a: Article) -> str:
    """The per-article credit shown with every value: authors, title, journal, year, DOI, licence,
    changes."""
    names = ", ".join(a.authors[:3]) + (" et al." if len(a.authors) > 3 else "")
    doi = f" https://doi.org/{a.doi}" if a.doi else ""
    lic_url = (
        "https://creativecommons.org/publicdomain/zero/1.0/"
        if a.licence == "CC0"
        else "https://creativecommons.org/licenses/by/"
        + (a.licence.split()[-1] if a.licence[-1].isdigit() else "4.0")
        + "/"
    )
    return (
        f"{a.pmcid}; {names or 'authors not stated'}. {a.title}. {a.journal} {a.year}.{doi} "
        f"Licence {a.licence} ({lic_url}). Changes: values transcribed from a table, units converted, short parts quoted."
    )
