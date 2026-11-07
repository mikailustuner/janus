"""Read-only queries over the resolution tables (drug-resolution design §4). Parameterised SQL.

Every function takes a connection inside `read_only_tx()` (REPEATABLE READ, READ ONLY), so one
request sees one dataset version.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, LiteralString

import psycopg

type ProductRef = tuple[str, int]  # (source id, product id)


@dataclass(frozen=True)
class SourceVersionRow:
    source_id: str
    run_id: str
    region: str | None
    snapshot_date: str
    cadence_days: int | None = None


@dataclass(frozen=True)
class Current:
    dataset_id: str
    sources: dict[str, SourceVersionRow]


def current(conn: psycopg.Connection) -> Current | None:
    row = conn.execute("SELECT dataset_id FROM res_current").fetchone()
    if row is None:
        return None
    dataset = str(row[0])
    rows = conn.execute(
        "SELECT source_id, run_id, region, snapshot_date, cadence_days FROM res_source_version "
        "WHERE dataset_id = %s ORDER BY source_id",
        (dataset,),
    ).fetchall()
    return Current(dataset, {r[0]: SourceVersionRow(r[0], r[1], r[2], r[3], r[4]) for r in rows})


def refs_by_codes(
    conn: psycopg.Connection, dataset: str, kind: str, codes: Sequence[str]
) -> list[ProductRef]:
    if not codes:
        return []
    rows = conn.execute(
        "SELECT DISTINCT source_id, product_id FROM res_product_code "
        "WHERE dataset_id = %s AND kind = %s AND code = ANY(%s) ORDER BY source_id, product_id",
        (dataset, kind, list(codes)),
    ).fetchall()
    return [(str(r[0]), int(r[1])) for r in rows]


@dataclass(frozen=True)
class ProductRow:
    source_id: str
    product_id: int
    fields: dict[str, Any]
    ingredients: list[dict[str, Any]]
    packages: list[tuple[str, str]]  # (published, ndc11)


_PRODUCT_COLS: tuple[LiteralString, ...] = (
    "region", "product_name", "brand_name", "generic_name", "ingredient_text", "published_atc",
    "product_type", "routes", "dosage_form", "marketing_end_date", "suspension_status",
    "name_only", "product_rxcuis",
)  # fmt: skip
_INGREDIENT_COLS: tuple[LiteralString, ...] = (
    "position", "published_name", "strength", "status", "reason", "qid", "key_candidates",
    "match_step", "atc", "atc_selection", "rxcuis", "rxcui_status",
)  # fmt: skip


def products(
    conn: psycopg.Connection, dataset: str, refs: Iterable[ProductRef]
) -> list[ProductRow]:
    """Products with ingredients and packages, in the order of `refs` (unknown refs skipped)."""
    wanted = list(dict.fromkeys(refs))
    if not wanted:
        return []
    sources = [s for s, _ in wanted]
    ids = [i for _, i in wanted]
    params = (dataset, sources, ids)
    keyed = (
        "dataset_id = %s AND (source_id, product_id) IN "
        "(SELECT * FROM unnest(%s::text[], %s::int[]))"
    )
    product_cols = ", ".join(_PRODUCT_COLS)
    base = conn.execute(
        f"SELECT source_id, product_id, {product_cols} FROM res_product WHERE {keyed}",  # noqa: S608 (fixed names)
        params,
    ).fetchall()
    ings: defaultdict[ProductRef, list[dict[str, Any]]] = defaultdict(list)
    for r in conn.execute(
        f"SELECT source_id, product_id, {', '.join(_INGREDIENT_COLS)} "  # noqa: S608 (fixed column names)
        f"FROM res_product_ingredient WHERE {keyed} ORDER BY source_id, product_id, position",
        params,
    ).fetchall():
        ings[(r[0], r[1])].append({str(k): v for k, v in zip(_INGREDIENT_COLS, r[2:], strict=True)})
    pkgs: defaultdict[ProductRef, list[tuple[str, str]]] = defaultdict(list)
    for r in conn.execute(
        f"SELECT source_id, product_id, code_published, code FROM res_product_code "  # noqa: S608 (fixed text)
        f"WHERE {keyed} AND kind = 'ndc_package11' ORDER BY code, code_published",
        params,
    ).fetchall():
        pkgs[(r[0], r[1])].append((str(r[2]), str(r[3])))
    found: dict[ProductRef, dict[str, Any]] = {
        (str(r[0]), int(r[1])): {str(k): v for k, v in zip(_PRODUCT_COLS, r[2:], strict=True)}
        for r in base
    }
    return [
        ProductRow(s, i, found[(s, i)], ings[(s, i)], pkgs[(s, i)])
        for s, i in wanted
        if (s, i) in found
    ]


def ingredients(
    conn: psycopg.Connection, dataset: str, qids: Iterable[str]
) -> dict[str, dict[str, Any]]:
    wanted = sorted(set(qids))
    if not wanted:
        return {}
    rows = conn.execute(
        "SELECT qid, labels, ingredient_atc, rxcuis FROM res_ingredient "
        "WHERE dataset_id = %s AND qid = ANY(%s)",
        (dataset, wanted),
    ).fetchall()
    return {str(r[0]): {"labels": r[1], "ingredient_atc": r[2], "rxcuis": list(r[3])} for r in rows}


@dataclass(frozen=True)
class NameHit:
    name_key: str
    kind: str
    region: str
    ref: str
    similarity: float


def search_names(
    conn: psycopg.Connection, dataset: str, key: str, regions: Sequence[str], limit: int = 200
) -> list[NameHit]:
    """Candidates by exact key, prefix or trigram similarity (pg_trgm), ingredients for all
    regions. Ranking is done by the caller (pure `rank`)."""
    rows = conn.execute(
        "SELECT name_key, kind, region, ref, similarity(name_key, %(k)s) AS sim "
        "FROM res_name WHERE dataset_id = %(d)s AND (region = '' OR region = ANY(%(r)s)) "
        "AND (name_key = %(k)s OR name_key LIKE %(p)s OR name_key %% %(k)s) "
        "ORDER BY (name_key = %(k)s) DESC, sim DESC, name_key, kind, region, ref LIMIT %(n)s",
        {"k": key, "d": dataset, "r": list(regions), "p": _like_prefix(key), "n": limit},
    ).fetchall()
    return [NameHit(str(r[0]), str(r[1]), str(r[2]), str(r[3]), float(r[4])) for r in rows]


def _like_prefix(key: str) -> str:
    return key.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def combination_codes(conn: psycopg.Connection, dataset_id: str) -> frozenset[str]:
    """Codes the loader classified as combination codes in this dataset (design §5.4)."""
    rows = conn.execute(
        "SELECT code FROM res_combination_atc WHERE dataset_id = %s", (dataset_id,)
    ).fetchall()
    return frozenset(str(r[0]) for r in rows)
