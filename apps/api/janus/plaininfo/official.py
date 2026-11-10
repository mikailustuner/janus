"""Official texts and pages for a product (plain-medicine-info design §5). Read-only.

United States: the "Indications and Usage" section of the product's label, from the current
`us_labels` run. The run's product NDCs are indexed in memory by product key; the text of one
label is read from the Parquet file when it is asked for. A product code that more than one
label names gets no text: Janus does not choose between labels.

France and Spain: the address of the product's page in the national database (BDPM, CIMA),
found by the product name exactly as the source publishes it, and only when one CIS code or one
registration number carries that name in the current run.

Each holder reloads when `current` points to another run, like the recall check (no restart).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import duckdb

from janus.integrity.freshness import parse_snapshot_date
from janus.resolution.ndc import canonical_product

LABEL_URL = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={}"
FR_URL = "https://base-donnees-publique.medicaments.gouv.fr/medicament/{}/extrait"
ES_URL = "https://cima.aemps.es/cima/publico/detalle.html?nregistro={}"
_SET_ID = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
_FR_CODE = re.compile(r"^[0-9]{8}$")
_ES_CODE = re.compile(r"^[0-9]{4,10}$")


@dataclass(frozen=True)
class Run:
    path: Path
    run_id: str
    snapshot_date: dt.date
    license: str


def read_manifest(run: Path, source_id: str, schema_version: str) -> Run:
    """The manifest of a usable run. Raises `OSError`, `ValueError` or `KeyError` otherwise."""
    manifest: dict[str, Any] = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    outcome = manifest.get("outcome")
    if outcome == "needs_review" and not (run / "promotion.json").exists():
        raise ValueError("needs_review run was not promoted")
    if outcome not in ("succeeded", "needs_review"):
        raise ValueError("run did not succeed")
    if manifest.get("source_id") != source_id or manifest.get("schema_version") != schema_version:
        raise ValueError("not the expected source and schema")
    return Run(
        path=run / "rows.parquet",
        run_id=str(manifest["run_id"]),
        snapshot_date=parse_snapshot_date(str(manifest["snapshot_date"])),
        license=str(manifest["license"]),
    )


def _query(path: Path, sql: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    con = duckdb.connect()
    try:
        return con.execute(sql, [str(path), *(params or [])]).fetchall()
    except duckdb.Error as exc:
        raise ValueError("rows cannot be read") from exc
    finally:
        con.close()


class Holder[T]:
    """`value` is what `read` makes of the current run of `pipeline`, or None when there is no
    usable run."""

    def __init__(self, data_dir: Path | None, pipeline: str, read: Callable[[Path], T]) -> None:
        self._link = None if data_dir is None else data_dir / "artifacts" / pipeline / "current"
        self._read = read
        self._lock = threading.Lock()
        self._target: str | None = None
        self._value: T | None = None

    @property
    def value(self) -> T | None:
        if self._link is None:
            return None
        try:
            target = os.path.realpath(self._link, strict=True)
        except OSError:
            return None
        with self._lock:
            if target != self._target:
                try:
                    self._value = self._read(Path(target))
                except (OSError, ValueError, KeyError):
                    self._value = None
                self._target = target
            return self._value


# --- United States: label text ----------------------------------------------------------------


@dataclass(frozen=True)
class LabelText:
    set_id: str
    version: str | None
    effective_date: dt.date | None
    paragraphs: tuple[str, ...]  # as published


@dataclass(frozen=True)
class Labels:
    run: Run
    by_product: dict[str, tuple[str, ...]]  # 9-digit product key -> set ids
    labels: int

    def set_ids(self, product: str) -> tuple[str, ...]:
        return self.by_product.get(product, ())

    def text(self, set_id: str) -> LabelText | None:
        rows = _query(
            self.run.path,
            "SELECT set_id, version, effective_date, indications FROM read_parquet(?) "
            "WHERE set_id = ?",
            [set_id],
        )
        if len(rows) != 1:
            return None
        sid, version, effective, indications = rows[0]
        return LabelText(
            set_id=str(sid),
            version=None if version is None else str(version),
            effective_date=None if effective is None else dt.date.fromisoformat(str(effective)),
            paragraphs=tuple(str(p) for p in indications),
        )


def read_labels(run_dir: Path) -> Labels:
    run = read_manifest(run_dir, "openfda_label_indications", "us_labels-1")
    by_product: dict[str, set[str]] = {}
    labels: set[str] = set()
    for set_id, ndc in _query(run.path, "SELECT set_id, unnest(product_ndcs) FROM read_parquet(?)"):
        key = canonical_product(str(ndc))
        if key is None or not _SET_ID.match(str(set_id)):
            continue
        labels.add(str(set_id))
        by_product.setdefault(key, set()).add(str(set_id))
    return Labels(run, {k: tuple(sorted(v)) for k, v in by_product.items()}, len(labels))


def labels_holder(data_dir: Path | None) -> Holder[Labels]:
    return Holder(data_dir, "us_labels", read_labels)


# --- France and Spain: the product's page -----------------------------------------------------

Country = Literal["FR", "ES"]


@dataclass(frozen=True)
class Pages:
    run: Run
    country: Country
    by_name: dict[str, str]  # published product name -> code, names with one code only

    def url(self, name: str) -> str | None:
        code = self.by_name.get(name)
        if code is None:
            return None
        return (FR_URL if self.country == "FR" else ES_URL).format(code)


def unique_names(pairs: list[tuple[Any, ...]], code: re.Pattern[str]) -> dict[str, str]:
    """Names that exactly one well-formed code carries. A name with two codes is left out."""
    seen: dict[str, set[str]] = {}
    for name, value in pairs:
        if isinstance(name, str) and name and isinstance(value, str):
            seen.setdefault(name, set()).add(value)
    return {
        name: next(iter(codes))
        for name, codes in seen.items()
        if len(codes) == 1 and code.match(next(iter(codes)))
    }


def read_fr(run_dir: Path) -> Pages:
    run = read_manifest(run_dir, "bdpm", "eu_fr_bdpm-1")
    pairs = _query(
        run.path,
        "SELECT DISTINCT denomination, cis FROM read_parquet(?) "
        "WHERE NOT name_only AND NOT specialty_missing",
    )
    return Pages(run, "FR", unique_names(pairs, _FR_CODE))


def read_es(run_dir: Path) -> Pages:
    run = read_manifest(run_dir, "cima", "eu_es_cima-1")
    pairs = _query(run.path, "SELECT DISTINCT name, registration_number FROM read_parquet(?)")
    return Pages(run, "ES", unique_names(pairs, _ES_CODE))


def pages_holders(data_dir: Path | None) -> dict[Country, Holder[Pages]]:
    return {
        "FR": Holder(data_dir, "eu_fr_bdpm", read_fr),
        "ES": Holder(data_dir, "eu_es_cima", read_es),
    }
