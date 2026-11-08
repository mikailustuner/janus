# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""`openfda_label` pipeline: indications of US labels for the light-face cases (design §3.2).

Only the ingredients named in `data/light/validation_cases.csv` are queried, one request each
(`openfda.generic_name:"<name>"`, at most 1,000 labels). The light build uses the text to remove
a case drug's labels that already name the later indication (light-face DP9). openFDA is CC0;
not an FDA endorsement. Rows: `set_id, version, query, generic_names, indications`.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Final

import polars as pl

from janus_pipelines.core.canonical import Row, sha256_bytes
from janus_pipelines.core.http import make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import ExpectedSchema, Field, SchemaReport

API: Final = "https://api.fda.gov/drug/label.json"
LIMIT: Final = 1000
CASES_FILE: Final = Path("data") / "light" / "validation_cases.csv"

OPENFDA_LABEL_SCHEMA = ExpectedSchema(
    version="openfda_label-1",
    fields=(Field("set_id", frozenset({"str"})), Field("indications", frozenset({"str"}))),
)
ROW_SCHEMA: Mapping[str, pl.DataType] = {
    "set_id": pl.String(),
    "version": pl.String(),
    "query": pl.String(),
    "generic_names": pl.List(pl.String()),
    "indications": pl.String(),
}


@dataclass(frozen=True)
class Payload:
    responses: Mapping[str, bytes]  # query name -> response body (b"" for no match)


def case_ingredients(repo_root: Path) -> list[str]:
    """Distinct lower-case ingredient names of the validation cases, sorted."""
    path = repo_root / CASES_FILE
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or "ingredient_name" not in reader.fieldnames:
            raise ValueError("validation_cases.csv: header has no ingredient_name column")
        names = {(r.get("ingredient_name") or "").strip().lower() for r in reader}
    if "" in names:
        raise ValueError("validation_cases.csv: a row has no ingredient_name")
    return sorted(names)


def query_params(name: str) -> dict[str, str]:
    return {"search": f'openfda.generic_name:"{name}"', "limit": str(LIMIT)}


def _texts(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value if isinstance(x, str)]  # pyright: ignore[reportUnknownVariableType]
    return []


def names_ingredient(generic_name: str, name: str) -> bool:
    """The query name is a whole word of the label's generic name (salts and combinations count)."""
    return re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", generic_name) is not None


def parse_responses(responses: Mapping[str, bytes]) -> ParseResult:
    """One row per (query, set id) whose generic names contain the query name (case-folded)."""
    rows: list[Row] = []
    input_rows = 0
    excluded: dict[str, int] = {}
    per_query: dict[str, int] = {}
    for name in sorted(responses):
        body = responses[name]
        results: list[Any] = []
        if body:
            doc = json.loads(body)
            results = doc.get("results", []) if isinstance(doc, dict) else []
        seen: set[str] = set()
        for item in results:
            input_rows += 1
            if not isinstance(item, dict):
                excluded["malformed"] = excluded.get("malformed", 0) + 1
                continue
            set_id = item.get("set_id")
            raw_openfda = item.get("openfda")
            openfda: dict[str, Any] = raw_openfda if isinstance(raw_openfda, dict) else {}
            generic = sorted({g.strip().lower() for g in _texts(openfda.get("generic_name"))})
            if not isinstance(set_id, str) or not set_id:
                excluded["no_set_id"] = excluded.get("no_set_id", 0) + 1
                continue
            if not any(names_ingredient(g, name) for g in generic):
                excluded["other_generic_name"] = excluded.get("other_generic_name", 0) + 1
                continue
            if set_id in seen:
                excluded["duplicate_set_id"] = excluded.get("duplicate_set_id", 0) + 1
                continue
            seen.add(set_id)
            rows.append(
                {
                    "set_id": set_id,
                    "version": str(item.get("version") or ""),
                    "query": name,
                    "generic_names": generic,
                    "indications": "\n".join(_texts(item.get("indications_and_usage"))),
                }
            )
        per_query[name] = len(seen)
    rows.sort(key=lambda r: (str(r["query"]), str(r["set_id"])))
    return ParseResult(
        rows=rows,
        input_rows=input_rows,
        excluded=excluded,
        schema=SchemaReport(),
        metrics={"labels_per_query": dict(per_query), "limit": LIMIT},
    )


class OpenfdaLabelJob(Job[Payload]):
    name = "openfda_label"
    source_id = "openfda_label"
    schema = OPENFDA_LABEL_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = ROW_SCHEMA

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        retrieved = ctx.now()
        fetcher = make_fetcher(require_contact=False)
        names = case_ingredients(ctx.repo_root)
        responses: dict[str, bytes] = {}
        query_sha: dict[str, str] = {}
        for name in names:
            response = fetcher.get(API, params=query_params(name), allow_status=frozenset({404}))
            responses[name] = b"" if response.status_code == 404 else response.content
            query_sha[name] = sha256_bytes(responses[name])
        digest = sha256_bytes("".join(query_sha[n] for n in names).encode())
        return RawInput(
            payload=Payload(responses),
            source_urls=(API,),
            source_sha256=digest,
            retrieved_at=retrieved,
            snapshot_date=retrieved.date().isoformat(),
            snapshot_date_is_retrieval_time=True,
            query_sha256=query_sha,
        )

    def parse(self, raw: RawInput[Payload]) -> ParseResult:
        return parse_responses(raw.payload.responses)
