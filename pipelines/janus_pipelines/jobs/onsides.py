"""`onsides` pipeline: the pinned OnSIDES v3.1.1 release → one row per drug label (light-face design §3.1).

OnSIDES (Tatonetti lab; Tanaka et al., Med 2025, doi:10.1016/j.medj.2025.100642) extracts adverse
effects from drug labels of the US (DailyMed), EU (EMA), UK (EMC) and Japan (KEGG) with a language
model. Data: CC BY 4.0 (LICENSE-DATA, checked 2026-11-08); code: MIT. The release asset is pinned by
its SHA-256: a new release is a reviewed code change, never picked up silently.

Output rows: `label_id, source, product_name, source_product_id, url, ingredient_ids, effects`
(`effects` = distinct `(meddra_id, section)` pairs of the label). Side tables: `meddra`
(id, name, term type as published: PT or LLT) and `ingredients` (RxNorm or OMOP id, name).
The extraction can be wrong or incomplete (README "Limitations"); the light face says so.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Final

import polars as pl

from janus_pipelines.core.canonical import sha256_bytes
from janus_pipelines.core.http import BULK_READ_TIMEOUT, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import (
    ExpectedSchema,
    Field,
    SchemaMismatchError,
    SchemaReport,
)

RELEASE: Final = "v3.1.1"
RELEASE_DATE: Final = "2026-04-22"  # data release date of v3.1.1 (GitHub release, README)
URL: Final = f"https://github.com/tatonetti-lab/onsides/releases/download/{RELEASE}/onsides-{RELEASE}.zip"
SHA256: Final = "7739c73336786c92e73ca383af92d3f2814caf5e94206e08475b86d5a5ec22b9"
SOURCES: Final = ("US", "EU", "UK", "JP")
SECTIONS: Final = ("AR", "BW", "WP", "NA")

# Columns read from each CSV of the release (all read as text, then cast).
TABLES: Final[Mapping[str, tuple[str, ...]]] = {
    "product_label": (
        "label_id",
        "source",
        "source_product_name",
        "source_product_id",
        "source_label_url",
    ),
    "product_adverse_effect": ("product_label_id", "label_section", "effect_meddra_id"),
    "product_to_rxnorm": ("label_id", "rxnorm_product_id"),
    "vocab_rxnorm_ingredient_to_product": ("ingredient_id", "product_id"),
    "vocab_rxnorm_ingredient": ("rxnorm_id", "rxnorm_name", "rxnorm_term_type"),
    "vocab_meddra_adverse_effect": ("meddra_id", "meddra_name", "meddra_term_type"),
}

ONSIDES_SCHEMA = ExpectedSchema(
    version="onsides-1",
    fields=(
        Field("label_id", frozenset({"int"})),
        Field("source", frozenset({"str"})),
    ),
)

EFFECT_STRUCT = pl.Struct({"meddra_id": pl.Int64(), "section": pl.String()})
ROW_SCHEMA: Mapping[str, pl.DataType] = {
    "label_id": pl.Int64(),
    "source": pl.String(),
    "product_name": pl.String(),
    "source_product_id": pl.String(),
    "url": pl.String(),
    "ingredient_ids": pl.List(pl.String()),
    "effects": pl.List(EFFECT_STRUCT),
}


class ReleaseHashError(ValueError):
    """The downloaded archive is not the pinned release."""


@dataclass(frozen=True)
class Payload:
    archive: bytes
    scratch: Path


def _csv(zf: zipfile.ZipFile, table: str, out: Path) -> pl.LazyFrame:
    """Extract `csv/<table>.csv` to the scratch directory and scan it as text."""
    name = f"csv/{table}.csv"
    if name not in zf.namelist():
        raise SchemaMismatchError(SchemaReport(missing=(f"{name} in the release",)))
    path = out / f"{table}.csv"
    with zf.open(name) as src, path.open("wb") as dst:
        while chunk := src.read(1 << 20):
            dst.write(chunk)
    frame = pl.scan_csv(path, infer_schema=False, quote_char='"')
    present = frame.collect_schema().names()
    missing = [c for c in TABLES[table] if c not in present]
    if missing:
        raise SchemaMismatchError(SchemaReport(missing=tuple(f"{table}.{c}" for c in missing)))
    return frame.select(list(TABLES[table]))


def parse_release(archive: bytes, scratch: Path) -> ParseResult:
    """Pure in its inputs: the archive bytes and a scratch directory for the extracted CSVs."""
    scratch.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        t = {name: _csv(zf, name, scratch) for name in TABLES}
    labels = t["product_label"].with_columns(pl.col("label_id").cast(pl.Int64)).collect()
    bad_source = labels.filter(~pl.col("source").is_in(SOURCES)).height
    if bad_source:
        raise SchemaMismatchError(
            SchemaReport(wrong_type=(("product_label.source", ("unknown region",)),))
        )
    label_ingredients = (
        t["product_to_rxnorm"]
        .join(
            t["vocab_rxnorm_ingredient_to_product"],
            left_on="rxnorm_product_id",
            right_on="product_id",
        )
        .select(pl.col("label_id").cast(pl.Int64), pl.col("ingredient_id"))
        .unique()
        .group_by("label_id")
        .agg(pl.col("ingredient_id").sort().alias("ingredient_ids"))
        .collect()
    )
    effects = (
        t["product_adverse_effect"]
        .filter(pl.col("effect_meddra_id").is_not_null() & (pl.col("effect_meddra_id") != ""))
        .select(
            pl.col("product_label_id").cast(pl.Int64).alias("label_id"),
            pl.struct(
                pl.col("effect_meddra_id").cast(pl.Int64).alias("meddra_id"),
                pl.col("label_section").alias("section"),
            ).alias("effect"),
        )
        .unique()
        .sort("label_id", "effect")
        .group_by("label_id", maintain_order=True)
        .agg(pl.col("effect").alias("effects"))
        .collect()
    )
    sections = (
        effects.select(pl.col("effects").explode().struct.field("section"))
        .unique()
        .to_series()
        .to_list()
    )
    unknown = sorted(str(s) for s in sections if s not in SECTIONS)
    if unknown:
        raise SchemaMismatchError(
            SchemaReport(wrong_type=(("product_adverse_effect.label_section", tuple(unknown)),))
        )
    joined = labels.join(label_ingredients, on="label_id", how="left").join(
        effects, on="label_id", how="left"
    )
    no_ingredient = joined.filter(pl.col("ingredient_ids").is_null()).height
    kept = joined.filter(pl.col("ingredient_ids").is_not_null())
    no_effect = kept.filter(pl.col("effects").is_null()).height
    kept = kept.filter(pl.col("effects").is_not_null())
    rows = (
        kept.select(
            "label_id",
            "source",
            pl.col("source_product_name").alias("product_name"),
            "source_product_id",
            pl.col("source_label_url").fill_null("").alias("url"),
            "ingredient_ids",
            "effects",
        )
        .sort("label_id")
        .cast(dict(ROW_SCHEMA))  # pyright: ignore[reportArgumentType]
    )
    rows_file = scratch / "rows.parquet"
    rows.write_parquet(rows_file, row_group_size=10_000)
    meddra = (
        t["vocab_meddra_adverse_effect"]
        .select(
            pl.col("meddra_id").cast(pl.Int64),
            pl.col("meddra_name").alias("name"),
            pl.col("meddra_term_type").alias("term_type"),
        )
        .sort("meddra_id")
        .collect()
    )
    ingredients = (
        t["vocab_rxnorm_ingredient"]
        .select(pl.col("rxnorm_id"), pl.col("rxnorm_name").alias("name"))
        .sort("rxnorm_id")
        .collect()
    )
    meddra_file, ingredients_file = scratch / "meddra.parquet", scratch / "ingredients.parquet"
    meddra.write_parquet(meddra_file)
    ingredients.write_parquet(ingredients_file)
    by_source = rows.group_by("source").len().sort("source")
    excluded = {k: v for k, v in {"no_ingredient": no_ingredient, "no_effect": no_effect}.items() if v}
    return ParseResult(
        rows=[],
        rows_file=rows_file,
        output_rows=rows.height,
        side_tables={"meddra": meddra_file, "ingredients": ingredients_file},
        input_rows=labels.height,
        excluded=excluded,
        schema=SchemaReport(),
        metrics={
            "release": RELEASE,
            "release_date": RELEASE_DATE,
            "labels_by_source": dict(
                zip(by_source["source"].to_list(), by_source["len"].to_list(), strict=True)
            ),
            "effect_pairs": int(rows.select(pl.col("effects").list.len().sum()).item()),
            "multi_ingredient_labels": int(
                rows.filter(pl.col("ingredient_ids").list.len() > 1).height
            ),
            "meddra_terms": meddra.height,
            "ingredients": ingredients.height,
            "limits": "Extracted by a language model from labels; some effects are missed or wrong.",
        },
    )


def check_release(body: bytes, expected: str = SHA256) -> None:
    got = sha256_bytes(body)
    if got != expected:
        raise ReleaseHashError(f"release archive hash {got[:12]}… is not the pinned {expected[:12]}…")


class OnsidesJob(Job[Payload]):
    name = "onsides"
    source_id = "onsides"
    schema = ONSIDES_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = ROW_SCHEMA

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        retrieved = ctx.now()
        fetcher = make_fetcher(require_contact=False)
        body = fetcher.get(URL, read_timeout=BULK_READ_TIMEOUT).content
        check_release(body)
        return RawInput(
            payload=Payload(body, ctx.scratch_dir(self.name)),
            source_urls=(URL,),
            source_sha256=sha256_bytes(body),
            retrieved_at=retrieved,
            snapshot_date=RELEASE_DATE,
            raw_files={f"onsides-{RELEASE}.zip": body},
        )

    def parse(self, raw: RawInput[Payload]) -> ParseResult:
        return parse_release(raw.payload.archive, raw.payload.scratch)

