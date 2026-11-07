"""In-memory TİTCK-shaped workbooks for tests. No TİTCK data is stored in the repository:
every workbook is built from generated values when a test runs."""

from __future__ import annotations

import io
from dataclasses import dataclass

from hypothesis import strategies as st
from openpyxl import Workbook

from janus_pipelines.jobs.titck import SHEET

HEADER = [
    "SIRA NO",
    "BARKOD",
    "ÜRÜN ADI",
    "ETKİN MADDE",
    "ATC KODU",
    "RUHSAT SAHİBİ",
    "RUHSATI ASKIDA OLMAYAN ÜRÜN: 0\nMADDE-23 GEREKÇELİ ASKIDA OLAN ÜRÜN: 1",
]


def ean13(first12: str) -> str:
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(first12))
    return first12 + str((10 - total % 10) % 10)


@dataclass(frozen=True)
class SpecRow:
    """One generated sheet row and what the pipeline should do with it."""

    kind: str  # "product" | "blank" | "invalid_barcode"
    barcode: int | str | None = None
    name: str | None = None
    ingredients: tuple[str, ...] = ()
    separator: str = ", "
    atc: str | None = None
    suspension: int | None = 0

    @property
    def ingredient_text(self) -> str | None:
        return self.separator.join(self.ingredients) if self.ingredients else None


NAME_PART = st.text(
    alphabet=st.sampled_from(list("abcçdefgğhıijklmnoöprsştuüvyz")), min_size=2, max_size=10
).filter(lambda s: s != "ve")
INGREDIENT = st.lists(NAME_PART, min_size=1, max_size=3).map(" ".join)
SEPARATOR = st.sampled_from([", ", ",", "/", " / ", " ve ", " + ", "+", "; "])
ATC = st.one_of(st.none(), st.from_regex(r"[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}", fullmatch=True))
BARCODE12 = st.from_regex(r"869[0-9]{9}", fullmatch=True)


@st.composite
def spec_rows(draw: st.DrawFn, max_rows: int = 40) -> list[SpecRow]:
    pool = draw(st.lists(BARCODE12.map(ean13), min_size=1, max_size=15, unique=True))
    rows: list[SpecRow] = []
    for _ in range(draw(st.integers(1, max_rows))):
        kind = draw(st.sampled_from(["product"] * 6 + ["blank", "invalid_barcode"]))
        if kind == "blank":
            rows.append(SpecRow("blank"))
            continue
        if kind == "invalid_barcode":
            bad = draw(
                st.one_of(
                    BARCODE12,  # 12 digits
                    BARCODE12.map(lambda s: s + str((int(ean13(s)[-1]) + 1) % 10)),  # bad check
                    st.just("ABC"),
                )
            )
            rows.append(SpecRow("invalid_barcode", barcode=bad, name="X", ingredients=("y",)))
            continue
        code = draw(st.sampled_from(pool))
        as_int = draw(st.booleans())
        rows.append(
            SpecRow(
                "product",
                barcode=int(code) if as_int else code,
                name=draw(NAME_PART).upper(),
                ingredients=tuple(draw(st.lists(INGREDIENT, min_size=0, max_size=4))),
                separator=draw(SEPARATOR),
                atc=draw(ATC),
                suspension=draw(st.sampled_from([0, 1, 2, 3, None])),
            )
        )
    return rows


def build_workbook(
    rows: list[SpecRow], header: list[str] | None = None, sheet: str = SHEET
) -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = sheet
    ws.append(["RUHSATLI BEŞERİ TIBBİ ÜRÜNLER LİSTESİ", None, None, None, None, None, None])
    ws.append(header or HEADER)
    for i, r in enumerate(rows, start=1):
        if r.kind == "blank":
            ws.append([None] * len(HEADER))
            continue
        ws.append([i, r.barcode, r.name, r.ingredient_text, r.atc, "FİRMA A.Ş.", r.suspension])
    ws2 = wb.create_sheet("Geçici İzinli Alerjenler")
    ws2.append(["BARKOD", "ÜRÜN ADI"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
