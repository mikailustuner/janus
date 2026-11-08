"""Tests for the `eu_es_cima` job (P24–P26, Req 12). Synthetic Nomenclátor files only."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

import httpx2
import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.canonical import Json
from janus_pipelines.core.http import FetchError, make_fetcher
from janus_pipelines.core.runner import RunContext
from janus_pipelines.core.validation import SchemaMismatchError
from janus_pipelines.jobs import eu_es_cima
from janus_pipelines.jobs.eu_es_cima import (
    INGREDIENT_XML,
    PRESCRIPTION_XML,
    EuEsCimaJob,
    gs1_check_digit,
    is_valid_gs1,
    make_ntin,
    parse_nomenclator,
    read_list_date,
)
from tests.stub_job import FIXED_NOW

NS = "http://schemas.aemps.es/prescripcion/aemps_prescripcion"
DIGITS = "0123456789"
CN6 = st.text(alphabet=DIGITS, min_size=6, max_size=6)


def reference_valid(code: str) -> bool:
    """Differential reference: pad to 14 digits and weight 3,1,3,1,... from the left."""
    if len(code) not in (8, 12, 13, 14) or not code.isdigit():
        return False
    padded = code.zfill(14)
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(padded[:13]))
    return (10 - total % 10) % 10 == int(padded[13])


@given(st.text(alphabet=DIGITS + "x -", max_size=16))
def test_is_valid_gs1_matches_reference(code: str) -> None:
    """Feature: data-pipelines, Property P24 — Validates: Req 12.3."""
    assert is_valid_gs1(code) == reference_valid(code)


@given(st.sampled_from([7, 11, 12, 13]), st.data())
def test_built_codes_are_valid_and_single_changes_are_not(length: int, data: st.DataObject) -> None:
    """Feature: data-pipelines, Property P24 (construction) — Validates: Req 12.3."""
    body = data.draw(st.text(alphabet=DIGITS, min_size=length, max_size=length))
    code = body + gs1_check_digit(body)
    assert is_valid_gs1(code)
    i = data.draw(st.integers(0, len(code) - 1))
    bump = data.draw(st.integers(1, 9))
    changed = code[:i] + str((int(code[i]) + bump) % 10) + code[i + 1 :]
    assert not is_valid_gs1(changed)


@given(CN6)
def test_ntin_embeds_the_national_code(cn: str) -> None:
    """Feature: data-pipelines, Property P24 (NTIN) — Validates: Req 12.3."""
    ntin = make_ntin(cn)
    assert len(ntin) == 14 and ntin.startswith("0847000") and ntin[7:13] == cn
    assert is_valid_gs1(ntin)


@dataclass
class Pres:
    cn: str
    regnum: str = "1"
    name: str = "MED"
    pres_name: str = "MED, 10 comprimidos"
    atc: str | None = "J01CR02"
    ingredients: list[tuple[str, int]] = field(default_factory=list[tuple[str, int]])
    ntins: list[str] = field(default_factory=list[str])
    gtins: list[str] = field(default_factory=list[str])
    routes: list[str] = field(default_factory=list[str])
    commercialised: bool = True
    extra: bool = False


DICTIONARY = {str(i): f"INGREDIENTE {i} ÁCIDO" for i in range(1, 8)}
UNKNOWN_CODE = "999"


def render_prescription(p: Pres, rng_order: list[int]) -> str:
    def el(tag: str, value: str) -> str:
        return f"<{tag}>{escape(value)}</{tag}>"

    pas = "".join(
        "<composicion_pa>"
        + el("cod_principio_activo", code)
        + el("orden_colacion", str(order))
        + el("dosis_pa", "500")
        + el("unidad_dosis_pa", "mg")
        + "</composicion_pa>"
        for code, order in [p.ingredients[i] for i in rng_order]
    )
    vias = "".join(
        f"<viasadministracion>{el('cod_via_admin', r)}</viasadministracion>" for r in p.routes
    )
    parts = [
        el("cod_nacion", p.cn),
        el("nro_definitivo", p.regnum),
        el("des_nomco", p.name),
        el("des_prese", p.pres_name),
        "<duplicidades>" + el("recomendacion_duplicidad", "ADVICE-SENTINEL") + "</duplicidades>",
        "<interacciones_atc>"
        + el("recomendacion_interaccion", "ADVICE-SENTINEL")
        + "</interacciones_atc>",
        el("sw_comercializado", "1" if p.commercialised else "0"),
        el("cod_sitreg", "1"),
        el("fecha_situacion_registro", "2020-01-02"),
        el("cod_sitreg_presen", "1"),
        el("fec_sitreg_presen", "2020-01-03"),
        el("serializacion", "1"),
    ]
    if p.atc:
        parts.append(f"<atc>{el('cod_atc', p.atc)}</atc>")
    parts += [f"<ntin>{el('codigo', n)}</ntin>" for n in p.ntins]
    parts += [f"<gtin>{el('codigo', g)}</gtin>" for g in p.gtins]
    parts.append(f"<formasfarmaceuticas>{pas}{vias}</formasfarmaceuticas>")
    if p.extra:
        parts.append(el("campo_nuevo", "x"))
    return "<prescription>" + "".join(parts) + "</prescription>"


def build_archive(
    presentations: list[Pres],
    orders: list[list[int]] | None = None,
    date: str | None = "2026-11-07",
    dictionary: dict[str, str] | None = None,
) -> bytes:
    header = f"<header><listprescriptiondate>{date}</listprescriptiondate></header>" if date else ""
    body = "".join(
        render_prescription(p, (orders[i] if orders else list(range(len(p.ingredients)))))
        for i, p in enumerate(presentations)
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<aemps_prescripcion xmlns="{NS}">{header}{body}</aemps_prescripcion>'
    )
    names = DICTIONARY if dictionary is None else dictionary
    dict_xml = (
        "<aemps_prescripcion_principios_activos>"
        + "".join(
            f"<principiosactivos><nroprincipioactivo>{n}</nroprincipioactivo>"
            f"<codigoprincipioactivo>C{n}</codigoprincipioactivo>"
            f"<principioactivo>{escape(v)}</principioactivo></principiosactivos>"
            for n, v in names.items()
        )
        + "</aemps_prescripcion_principios_activos>"
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr(PRESCRIPTION_XML, xml.encode("utf-8"))
        zf.writestr(INGREDIENT_XML, dict_xml.encode("utf-8"))
    return out.getvalue()


def gs1_code(draw: st.DrawFn, length: int, valid: bool) -> str:
    body = draw(st.text(alphabet=DIGITS, min_size=length - 1, max_size=length - 1))
    check = gs1_check_digit(body)
    return body + (check if valid else str((int(check) + 1) % 10))


@st.composite
def presentation_lists(draw: st.DrawFn) -> list[Pres]:
    cns = draw(st.lists(CN6, min_size=1, max_size=6, unique=True))
    out: list[Pres] = []
    for cn in cns:
        n_ing = draw(st.integers(0, 3))
        codes = draw(
            st.lists(st.sampled_from([*DICTIONARY, UNKNOWN_CODE]), min_size=n_ing, max_size=n_ing)
        )
        orders = draw(st.permutations(range(1, n_ing + 1)))
        ntins = draw(st.lists(st.sampled_from([make_ntin(cn), "0847000" + "1" * 7]), max_size=2))
        gtins = [
            draw(
                st.builds(gs1_code, st.just(draw), st.sampled_from([8, 12, 13, 14]), st.booleans())
            )
            for _ in range(draw(st.integers(0, 3)))
        ]
        out.append(
            Pres(
                cn=cn,
                name=draw(st.text(alphabet="abcXYZ áéñ&<>", max_size=8)),
                atc=draw(st.sampled_from([None, "J01CR02", "C09BB03"])),
                ingredients=list(zip(codes, orders, strict=True)),
                ntins=ntins,
                gtins=gtins,
                routes=draw(st.lists(st.sampled_from(["49", "48"]), max_size=2)),
                commercialised=draw(st.booleans()),
                extra=draw(st.booleans()),
            )
        )
    return out


def expected_row(p: Pres) -> dict[str, Json]:
    return {
        "cn": p.cn,
        "name_only": False,
        "name": p.name.strip(),
        "atc_code": p.atc,
        "ingredients": [
            {
                "code": code,
                "name": DICTIONARY.get(code),
                "dose": "500",
                "dose_unit": "mg",
                "order": order,
            }
            for code, order in sorted(p.ingredients, key=lambda t: t[1])
        ],
        "ntins": [n for n in p.ntins if is_valid_gs1(n)],
        "gtins": [g for g in p.gtins if is_valid_gs1(g)],
        "route_codes": p.routes,
        "commercialised": p.commercialised,
    }


@given(presentation_lists(), st.data())
def test_generated_nomenclator_parses_back(presentations: list[Pres], data: st.DataObject) -> None:
    """Feature: data-pipelines, Property P25 — Validates: Req 12.1, 12.2, 12.5.
    Parsed rows equal the generated presentations in any element order; ingredients are in
    `orden_colacion` order; advice and unknown elements never reach the output.
    """
    shuffled = data.draw(st.permutations(presentations))
    orders = [data.draw(st.permutations(range(len(p.ingredients)))) for p in shuffled]
    result = parse_nomenclator(build_archive(shuffled, orders))
    assert len(result.rows) == len(presentations)
    by_cn = {str(r["cn"]): r for r in result.rows}
    for p in presentations:
        row = by_cn[p.cn]
        for key, value in expected_row(p).items():
            assert row[key] == value, key
    assert "ADVICE-SENTINEL" not in repr(result.rows)
    assert ("campo_nuevo" in result.schema.extra) == any(p.extra for p in presentations)
    invalid = sum(
        len([g for g in p.gtins if not is_valid_gs1(g)])
        + len([n for n in p.ntins if not is_valid_gs1(n)])
        for p in presentations
    )
    assert result.metrics["invalid_gtin_values"] == invalid


def test_missing_header_date_or_member_fails() -> None:
    with pytest.raises(SchemaMismatchError, match="listprescriptiondate"):
        parse_nomenclator(build_archive([Pres(cn="123456")], date=None))
    with pytest.raises(SchemaMismatchError, match="listprescriptiondate"):
        read_list_date(build_archive([Pres(cn="123456")], date=None))
    assert read_list_date(build_archive([Pres(cn="123456")], date="2026-11-07")) == "2026-11-07"
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr(PRESCRIPTION_XML, "<x/>")
    with pytest.raises(SchemaMismatchError, match=INGREDIENT_XML):
        parse_nomenclator(bad.getvalue())


@given(st.lists(st.text(alphabet=DIGITS + "a ", max_size=9), min_size=1, max_size=5))
def test_national_code_is_six_digits_or_name_only(codes: list[str]) -> None:
    """Feature: data-pipelines, Property P26 — Validates: Req 12.3, 12.4."""
    presentations = [Pres(cn=c) for c in codes]
    result = parse_nomenclator(build_archive(presentations))
    for row, source in zip(result.rows, [c.strip() for c in codes], strict=True):
        is_cn = len(source) == 6 and source.isdigit()
        assert row["name_only"] is (not is_cn)
        assert row["cn"] == (source if is_cn else None)


@given(CN6, CN6, st.sampled_from(["ntin", "gtin"]))
def test_shared_codes_stay_on_every_presentation(a: str, b: str, kind: str) -> None:
    """Feature: data-pipelines, Property P26 (shared codes) — Validates: Req 12.3."""
    if a == b:
        return
    shared = make_ntin(a) if kind == "ntin" else "0" + "8435" + "000000" + "1"
    shared = shared if is_valid_gs1(shared) else shared[:-1] + gs1_check_digit(shared[:-1])
    p1, p2 = Pres(cn=a), Pres(cn=b)
    for p in (p1, p2):
        (p.ntins if kind == "ntin" else p.gtins).append(shared)
    result = parse_nomenclator(build_archive([p1, p2]))
    assert [r[kind + "s"] for r in result.rows] == [[shared], [shared]]
    assert result.metrics["shared_codes"] == 1


def test_ntin_anomalies_are_kept_and_counted() -> None:
    wrong_cn = make_ntin("111111")
    plain = "4150199715806"
    assert is_valid_gs1(plain)
    result = parse_nomenclator(
        build_archive([Pres(cn="222222", ntins=[wrong_cn, plain, make_ntin("222222")])])
    )
    (row,) = result.rows
    assert row["ntins"] == [wrong_cn, plain, make_ntin("222222")]
    assert result.metrics["ntin_cn_mismatch"] == 1 and result.metrics["ntin_nonstandard"] == 1


def test_ingredient_missing_from_dictionary_keeps_code_with_null_name() -> None:
    result = parse_nomenclator(build_archive([Pres(cn="333333", ingredients=[(UNKNOWN_CODE, 1)])]))
    (row,) = result.rows
    ing = row["ingredients"]
    assert isinstance(ing, list) and isinstance(ing[0], dict)
    assert ing[0]["code"] == UNKNOWN_CODE and ing[0]["name"] is None


def test_http_403_names_the_user_agent_policy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def handle(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(403, text="forbidden")

    real = make_fetcher

    def fake(*, require_contact: bool, transport: httpx2.BaseTransport | None = None):  # type: ignore[no-untyped-def]
        return real(require_contact=require_contact, transport=httpx2.MockTransport(handle))

    monkeypatch.setattr(eu_es_cima, "make_fetcher", fake)
    ctx = RunContext(
        data_dir=tmp_path,
        repo_root=tmp_path,
        registry=None,  # type: ignore[arg-type]
        code_version="t",
        now=lambda: FIXED_NOW,
    )
    with pytest.raises(FetchError, match="User-Agent"):
        EuEsCimaJob().fetch(ctx)
