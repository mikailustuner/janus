"""`eu_es_cima` pipeline: AEMPS Nomenclátor de prescripción → national code, ingredients, ATC,
NTIN and GTIN of every Spanish presentation.

Design §13.2, Req 12. Bulk file (about 190 MB of XML inside a 16 MB archive), read as a stream.
The CIMA REST API is not used here (Req 12.6). The Nomenclátor's duplicate-therapy,
interaction, geriatric-advice and similar elements are never read (Req 12.5, DP25).
Data: reuse with attribution (cite AEMPS and the date of the last update).
"""

from __future__ import annotations

import io
import zipfile
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import polars as pl
from defusedxml import ElementTree as SafeET

from janus_pipelines.core.canonical import Json, Row, sha256_bytes
from janus_pipelines.core.http import BULK_READ_TIMEOUT, FetchError, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

from janus_pipelines.core.validation import (
    ExpectedSchema,
    Field,
    SchemaMismatchError,
    SchemaReport,
)

ARCHIVE_URL = "https://listadomedicamentos.aemps.gob.es/prescripcion.zip"
PRESCRIPTION_XML = "Prescripcion.xml"
INGREDIENT_XML = "DICCIONARIO_PRINCIPIOS_ACTIVOS.xml"
NTIN_PREFIX = "0847000"

CIMA_SCHEMA = ExpectedSchema(
    version="eu_es_cima-1",
    fields=(Field("cn", frozenset({"str", "null"})),),
)

# Direct children of <prescription> that the job reads. Everything else is ignored; names
# outside READ and ADVICE are reported as extra columns (Req 2.1).
READ = frozenset(
    {
        "cod_nacion",
        "nro_definitivo",
        "des_nomco",
        "des_prese",
        "atc",
        "ntin",
        "gtin",
        "formasfarmaceuticas",
        "sw_comercializado",
        "cod_sitreg",
        "fecha_situacion_registro",
        "cod_sitreg_presen",
        "fec_sitreg_presen",
        "serializacion",
    }
)
# Known elements that are deliberately not ingested (DP25) or not needed.
IGNORED = frozenset(
    {
        "duplicidades",
        "interacciones_atc",
        "recomendacion_geriatria",
        "riesgo_pacience_geriatria",
        "desaconsejados_geriatria",
        "alerta_geriatria",
        "teratogenia",
        "notaseguridad",
        "excipientes",
        "imagenes",
        "biomarcadores",
        "problemassuministro",
        "notas",
        "secciones_ft",
    }
)


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def is_valid_gs1(digits: str) -> bool:
    """GS1 code of 8, 12, 13 or 14 digits with a correct check digit (Req 12.3)."""
    if len(digits) not in (8, 12, 13, 14) or not digits.isascii() or not digits.isdigit():
        return False
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits[:-1])))
    return (10 - total % 10) % 10 == int(digits[-1])


def gs1_check_digit(body: str) -> str:
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return str((10 - total % 10) % 10)


def make_ntin(cn6: str) -> str:
    """`0847000` + national code + check digit (design; GS1 Spain NTIN structure)."""
    body = NTIN_PREFIX + cn6
    return body + gs1_check_digit(body)


def ntin_is_standard(ntin: str) -> bool:
    return len(ntin) == 14 and ntin.startswith(NTIN_PREFIX)


def read_ingredient_dictionary(data: bytes) -> dict[str, str]:
    """`nroprincipioactivo` → `principioactivo` (names as published)."""
    names: dict[str, str] = {}
    number = None
    name = None
    for _event, el in SafeET.iterparse(io.BytesIO(data), events=("end",)):
        tag = local(el.tag)
        if tag == "nroprincipioactivo":
            number = (el.text or "").strip()
        elif tag == "principioactivo":
            name = el.text or ""
        elif tag == "principiosactivos":
            if number is not None and name is not None:
                names[number] = name
            number = name = None
            el.clear()
    return names


def _text(el: Element, tag: str) -> str | None:
    """Text of the first direct child `tag`, or None."""
    for child in el:
        if local(child.tag) == tag:
            return (child.text or "").strip()
    return None


def _children(el: Element, tag: str) -> list[Element]:
    return [c for c in el if local(c.tag) == tag]


def _codes(el: Element, wrapper: str) -> list[str]:
    out: list[str] = []
    for w in _children(el, wrapper):
        value = _text(w, "codigo")
        if value:
            out.append(value)
    return out


def prescription_row(el: Element, dictionary: Mapping[str, str]) -> dict[str, Json]:
    cn_raw = _text(el, "cod_nacion") or ""
    cn_ok = len(cn_raw) == 6 and cn_raw.isascii() and cn_raw.isdigit()
    ingredients: list[tuple[int, int, dict[str, Json]]] = []
    routes: list[str] = []
    for form in _children(el, "formasfarmaceuticas"):
        for via in _children(form, "viasadministracion"):
            code = _text(via, "cod_via_admin")
            if code:
                routes.append(code)
        for pa in _children(form, "composicion_pa"):
            code = _text(pa, "cod_principio_activo")
            if not code:
                continue
            order_text = _text(pa, "orden_colacion") or ""
            order = int(order_text) if order_text.isdigit() else 10**6
            ingredients.append(
                (
                    order,
                    len(ingredients),
                    {
                        "code": code,
                        "name": dictionary.get(code),
                        "dose": _text(pa, "dosis_pa"),
                        "dose_unit": _text(pa, "unidad_dosis_pa"),
                        "order": order if order_text.isdigit() else None,
                    },
                )
            )
    ingredients.sort(key=lambda t: (t[0], t[1]))
    atc_el = _children(el, "atc")
    return {
        "cn": cn_raw if cn_ok else None,
        "name_only": not cn_ok,
        "registration_number": _text(el, "nro_definitivo"),
        "name": _text(el, "des_nomco"),
        "presentation_name": _text(el, "des_prese"),
        "atc_code": _text(atc_el[0], "cod_atc") if atc_el else None,
        "ingredients": [t[2] for t in ingredients],
        "ntins": _codes(el, "ntin"),
        "gtins": _codes(el, "gtin"),
        "route_codes": routes,
        "commercialised": _text(el, "sw_comercializado") == "1",
        "registration_status": _text(el, "cod_sitreg"),
        "registration_status_date": _text(el, "fecha_situacion_registro"),
        "presentation_status": _text(el, "cod_sitreg_presen"),
        "presentation_status_date": _text(el, "fec_sitreg_presen"),
        "serialised": _text(el, "serializacion") == "1",
    }


def open_archive(archive: bytes) -> zipfile.ZipFile:
    try:
        zf = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile:
        raise SchemaMismatchError(SchemaReport(missing=("a zip archive",))) from None
    members = set(zf.namelist())
    absent = tuple(n for n in (PRESCRIPTION_XML, INGREDIENT_XML) if n not in members)
    if absent:
        raise SchemaMismatchError(SchemaReport(missing=absent))
    return zf


def read_list_date(archive: bytes) -> str:
    """The `listprescriptiondate` in the header of Prescripcion.xml (Req 12.1); reads only the
    first elements of the stream."""
    zf = open_archive(archive)
    with zf.open(PRESCRIPTION_XML) as stream:
        for _event, el in SafeET.iterparse(stream, events=("end",)):
            tag = local(el.tag)
            if tag == "listprescriptiondate" and (el.text or "").strip():
                return (el.text or "").strip()
            if tag == "prescription":
                break
    raise SchemaMismatchError(SchemaReport(missing=("listprescriptiondate in the header",)))


def parse_nomenclator(archive: bytes) -> ParseResult:
    """Parse the archive as a stream."""
    zf = open_archive(archive)
    dictionary = read_ingredient_dictionary(zf.read(INGREDIENT_XML))
    list_date: str | None = None
    rows: list[dict[str, Json]] = []
    child_names: set[str] = set()
    invalid_gtin_values = ntin_nonstandard = ntin_cn_mismatch = 0
    n_in = 0
    with zf.open(PRESCRIPTION_XML) as stream:
        root = None
        for event, el in SafeET.iterparse(stream, events=("start", "end")):
            if event == "start":
                if root is None:
                    root = el
                continue
            tag = local(el.tag)
            if tag == "listprescriptiondate":
                list_date = (el.text or "").strip()
            elif tag == "prescription":
                n_in += 1
                child_names.update(local(c.tag) for c in el)
                row = prescription_row(el, dictionary)
                cn = row["cn"]
                kept: dict[str, list[str]] = {}
                for key in ("ntins", "gtins"):
                    values = _strs(row[key])
                    valid = [v for v in values if is_valid_gs1(v)]
                    invalid_gtin_values += len(values) - len(valid)
                    kept[key] = valid
                row["ntins"], row["gtins"] = kept["ntins"], kept["gtins"]
                for ntin in kept["ntins"]:
                    if not ntin_is_standard(ntin):
                        ntin_nonstandard += 1
                    elif isinstance(cn, str) and ntin[7:13] != cn:
                        ntin_cn_mismatch += 1
                rows.append(row)
                el.clear()
                if root is not None:
                    root.clear()
    if not list_date:
        raise SchemaMismatchError(SchemaReport(missing=("listprescriptiondate in the header",)))
    if "cod_nacion" not in child_names and n_in:
        raise SchemaMismatchError(SchemaReport(missing=("cod_nacion",)))
    shared = Counter(v for r in rows for k in ("ntins", "gtins") for v in _strs(r[k]))
    extra = tuple(sorted(child_names - READ - IGNORED))
    has_ntin = sum(1 for r in rows if r["ntins"])
    has_gtin = sum(1 for r in rows if r["gtins"])
    return ParseResult(
        rows=list[Row](rows),
        input_rows=n_in,
        excluded={},
        schema=SchemaReport(extra=extra),
        metrics={
            "presentations": len(rows),
            "name_only_rows": sum(1 for r in rows if r["name_only"]),
            "rows_without_ingredient": sum(1 for r in rows if not r["ingredients"]),
            "rows_with_ntin": has_ntin,
            "rows_with_gtin": has_gtin,
            "rows_with_both": sum(1 for r in rows if r["ntins"] and r["gtins"]),
            "rows_with_neither": sum(1 for r in rows if not r["ntins"] and not r["gtins"]),
            "invalid_gtin_values": invalid_gtin_values,
            "ntin_nonstandard": ntin_nonstandard,
            "ntin_cn_mismatch": ntin_cn_mismatch,
            "shared_codes": sum(1 for n in shared.values() if n > 1),
            "list_date": list_date,
            "dictionary_entries": len(dictionary),
        },
    )


def _strs(value: Json) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str)]


class EuEsCimaJob(Job[bytes]):
    name = "eu_es_cima"
    source_id = "cima"
    schema = CIMA_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "cn": pl.String(),
        "name_only": pl.Boolean(),
        "registration_number": pl.String(),
        "name": pl.String(),
        "presentation_name": pl.String(),
        "atc_code": pl.String(),
        "ingredients": pl.List(
            pl.Struct(
                {
                    "code": pl.String(),
                    "name": pl.String(),
                    "dose": pl.String(),
                    "dose_unit": pl.String(),
                    "order": pl.Int64(),
                }
            )
        ),
        "ntins": pl.List(pl.String()),
        "gtins": pl.List(pl.String()),
        "route_codes": pl.List(pl.String()),
        "commercialised": pl.Boolean(),
        "registration_status": pl.String(),
        "registration_status_date": pl.String(),
        "presentation_status": pl.String(),
        "presentation_status_date": pl.String(),
        "serialised": pl.Boolean(),
    }

    def fetch(self, ctx: RunContext) -> RawInput[bytes]:
        retrieved = ctx.now()
        if "input" in ctx.options:
            path = Path(ctx.options["input"])
            data = path.read_bytes()
            urls: tuple[str, ...] = (ARCHIVE_URL, f"local file {path.name}")
        else:
            fetcher = make_fetcher(require_contact=False)
            response = fetcher.get(
                ARCHIVE_URL, read_timeout=BULK_READ_TIMEOUT, allow_status=frozenset({403})
            )
            if response.status_code == 403:
                raise FetchError(
                    "HTTP 403 from listadomedicamentos.aemps.gob.es: the host refused the "
                    "pipelines' User-Agent (it rejected a generic command-line agent on "
                    "2026-11-08); check the User-Agent policy before retrying"
                )
            data = response.content
            urls = (ARCHIVE_URL,)
        return RawInput(
            payload=data,
            source_urls=urls,
            source_sha256=sha256_bytes(data),
            retrieved_at=retrieved,
            snapshot_date=read_list_date(data),
            raw_files={"prescripcion.zip": data} if "input" not in ctx.options else {},
        )

    def parse(self, raw: RawInput[bytes]) -> ParseResult:
        return parse_nomenclator(raw.payload)
