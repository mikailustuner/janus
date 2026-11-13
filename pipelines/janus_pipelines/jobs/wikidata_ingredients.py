"""`wikidata_ingredients` pipeline: items with an ATC code (P267), their RxNorm CUIs (P3345)
and labels/aliases in en, tr, de, fr, es, pt (design §5.3, Req 7). Data CC0.

Portuguese: `label_pt`/`aliases_pt` come from the `pt` labels. Where an item has no `pt` label
but has a `pt-br` one, that label is used (checked on 2026-11-13: the 299 `pt-br` labels of
ATC items are drug names in Brazilian spelling, 292 of them also have a `pt` label and 7 do
not, so the fallback adds 7 names). A `pt-br` label or alias that differs from the `pt` label
is kept as an alias (for example xenônio next to xenón). Nothing else is derived from `pt-br`."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any, ClassVar, cast

import polars as pl

from janus_pipelines.core.canonical import Row, sha256_bytes
from janus_pipelines.core.http import Fetcher, FetchError, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import (
    KIND_NULL,
    ExpectedSchema,
    Field,
    SchemaReport,
    check_schema,
)

ENDPOINT = "https://query.wikidata.org/sparql"
LANGS = ("en", "tr", "de", "fr", "es", "pt")
PT_FALLBACK = "pt-br"  # fetched with the other languages, merged into `pt` only
FETCH_LANGS = (*LANGS, PT_FALLBACK)
ATC_FIRST_LETTERS = tuple("ABCDGHJLMNPRSV")
ENTITY_PREFIX = "http://www.wikidata.org/entity/"
_QID = re.compile(r"Q[1-9][0-9]*")
READ_TIMEOUT = 90.0


def codes_query(letter: str | None = None) -> str:
    restrict = f' FILTER(STRSTARTS(?atc, "{letter}"))' if letter else ""
    return (
        "SELECT ?item ?atc ?rxcui WHERE { ?item wdt:P267 ?atc ."
        f"{restrict} OPTIONAL {{ ?item wdt:P3345 ?rxcui }} }}"
    )


def labels_query(lang: str, letter: str | None = None) -> str:
    if lang not in FETCH_LANGS:
        raise ValueError(f"unsupported language {lang!r}")
    restrict = f' FILTER(STRSTARTS(?a, "{letter}"))' if letter else ""
    return (
        "SELECT DISTINCT ?item ?label ?alias WHERE { ?item wdt:P267 ?a ."
        f"{restrict}"
        f' OPTIONAL {{ ?item rdfs:label ?label . FILTER(LANG(?label) = "{lang}") }}'
        f' OPTIONAL {{ ?item skos:altLabel ?alias . FILTER(LANG(?alias) = "{lang}") }} }}'
    )


def _labels_for(lang: str, letter: str | None) -> str:
    return labels_query(lang, letter)


CODES_SCHEMA = ExpectedSchema(
    version="wikidata-codes-1",
    fields=(Field("item", frozenset({"uri"})), Field("atc", frozenset({"literal"}))),
)
LABELS_SCHEMA = ExpectedSchema(
    version="wikidata-labels-1",
    fields=(
        Field("item", frozenset({"uri"})),
        Field("label", frozenset({"literal", KIND_NULL})),
        Field("alias", frozenset({"literal", KIND_NULL})),
    ),
)
OUTPUT_SCHEMA = ExpectedSchema(version="wikidata_ingredients-1", fields=CODES_SCHEMA.fields)

type Binding = Mapping[str, Mapping[str, str]]


@dataclass(frozen=True)
class SparqlResult:
    vars: tuple[str, ...]
    bindings: tuple[Binding, ...]


def parse_sparql_json(data: bytes) -> SparqlResult:
    doc = cast(dict[str, Any], json.loads(data))
    head = cast(dict[str, Any], doc.get("head", {}))
    results = cast(dict[str, Any], doc.get("results", {}))
    return SparqlResult(
        vars=tuple(cast(list[str], head.get("vars", []))),
        bindings=tuple(cast(list[Binding], results.get("bindings", []))),
    )


def observe_bindings(result: SparqlResult) -> dict[str, frozenset[str]]:
    kinds: dict[str, set[str]] = {v: set() for v in result.vars}
    for b in result.bindings:
        for v in result.vars:
            cell = b.get(v)
            kinds[v].add(cell.get("type", "?") if cell is not None else KIND_NULL)
    return {k: frozenset(v) for k, v in kinds.items()}


def qid(uri: str) -> str | None:
    if not uri.startswith(ENTITY_PREFIX):
        return None
    value = uri[len(ENTITY_PREFIX) :]
    return value if _QID.fullmatch(value) else None


@dataclass(frozen=True)
class Merged:
    rows: list[Row]
    input_items: int
    excluded: dict[str, int]


def merge(
    code_bindings: Iterable[Binding], label_bindings: Mapping[str, Iterable[Binding]]
) -> Merged:
    """Group by QID. Independent of binding order and of how bindings were split into
    queries; each QID appears once with at least one ATC code (Req 7.3, 7.4). Pure."""
    atc: dict[str, set[str]] = {}
    rxcui: dict[str, set[str]] = {}
    invalid: set[str] = set()
    for b in code_bindings:
        uri = b["item"]["value"]
        q = qid(uri)
        if q is None:
            invalid.add(uri)
            continue
        atc.setdefault(q, set()).add(b["atc"]["value"].strip())
        if "rxcui" in b:
            rxcui.setdefault(q, set()).add(b["rxcui"]["value"].strip())
    labels: dict[tuple[str, str], set[str]] = {}
    aliases: dict[tuple[str, str], set[str]] = {}
    for lang, bindings in label_bindings.items():
        for b in bindings:
            q = qid(b["item"]["value"])
            if q is None or q not in atc:
                continue  # labels only describe items that have an ATC code
            if "label" in b:
                labels.setdefault((q, lang), set()).add(b["label"]["value"])
            if "alias" in b:
                aliases.setdefault((q, lang), set()).add(b["alias"]["value"])
    for q in sorted({q for q, lang in (*labels, *aliases) if lang == PT_FALLBACK}):
        br_labels = labels.pop((q, PT_FALLBACK), set())
        br_aliases = aliases.pop((q, PT_FALLBACK), set())
        if not labels.get((q, "pt")) and br_labels:
            labels[(q, "pt")] = {min(br_labels)}  # no `pt` label: a `pt-br` label stands in
        extra = (br_labels | br_aliases) - labels.get((q, "pt"), set())
        aliases.setdefault((q, "pt"), set()).update(extra)
    rows: list[Row] = []
    for q in sorted(atc, key=lambda x: int(x[1:])):
        row: dict[str, Any] = {
            "qid": q,
            "atc_codes": sorted(c for c in atc[q] if c),
            "rxcuis": sorted(rxcui.get(q, set())),
        }
        for lang in LANGS:
            found = labels.get((q, lang))
            row[f"label_{lang}"] = min(found) if found else None
            row[f"aliases_{lang}"] = sorted(aliases.get((q, lang), set()))
        rows.append(row)
    rows = [r for r in rows if r["atc_codes"]]
    excluded = {"invalid_qid": len(invalid)} if invalid else {}
    empty = len(atc) - len(rows)
    if empty:
        excluded["empty_atc"] = empty
    return Merged(rows=rows, input_items=len(atc) + len(invalid), excluded=excluded)


# Payload: query name -> list of response bodies (one, or one per ATC letter after a split).
type Payload = dict[str, list[bytes]]


class WikidataIngredientsJob(Job[Payload]):
    name = "wikidata_ingredients"
    source_id = "wikidata"
    schema = OUTPUT_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "qid": pl.String(),
        "atc_codes": pl.List(pl.String()),
        "rxcuis": pl.List(pl.String()),
        **{f"label_{lang}": pl.String() for lang in LANGS},
        **{f"aliases_{lang}": pl.List(pl.String()) for lang in LANGS},
    }

    def _run_query(
        self,
        fetcher: Fetcher,
        name: str,
        build: Callable[[str | None], str],
        hashes: dict[str, str],
    ) -> list[bytes]:
        """Run one query; if it fails (e.g. the service's time limit), split it by ATC letter."""
        try:
            text = build(None)
            hashes[name] = sha256_bytes(text.encode())
            return [self._get(fetcher, text)]
        except FetchError:
            parts: list[bytes] = []
            for letter in ATC_FIRST_LETTERS:
                text = build(letter)
                hashes[f"{name}:{letter}"] = sha256_bytes(text.encode())
                parts.append(self._get(fetcher, text))
            return parts

    @staticmethod
    def _get(fetcher: Fetcher, query: str) -> bytes:
        return fetcher.get(
            ENDPOINT,
            params={"query": query, "format": "json"},
            headers={"Accept": "application/sparql-results+json"},
            read_timeout=READ_TIMEOUT,
        ).content

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        fetcher = make_fetcher(require_contact=True)
        retrieved = ctx.now()
        hashes: dict[str, str] = {}
        payload: Payload = {"codes": self._run_query(fetcher, "codes", codes_query, hashes)}
        for lang in FETCH_LANGS:
            payload[f"labels_{lang}"] = self._run_query(
                fetcher,
                f"labels_{lang}",
                partial(_labels_for, lang),
                hashes,
            )
        files = {
            f"{name}-{i}.json": body
            for name, parts in payload.items()
            for i, body in enumerate(parts)
        }
        digest = sha256_bytes(b"".join(files[k] for k in sorted(files)))
        return RawInput(
            payload=payload,
            source_urls=(ENDPOINT,),
            source_sha256=digest,
            retrieved_at=retrieved,
            snapshot_date=retrieved.isoformat(),
            snapshot_date_is_retrieval_time=True,
            raw_files=files,
            query_sha256=hashes,
        )

    def parse(self, raw: RawInput[Payload]) -> ParseResult:
        codes: list[Binding] = []
        report = SchemaReport()
        for body in raw.payload.get("codes", []):
            result = parse_sparql_json(body)
            report = check_schema(CODES_SCHEMA, observe_bindings(result))
            codes.extend(result.bindings)
        labels: dict[str, Sequence[Binding]] = {}
        for lang in FETCH_LANGS:
            collected: list[Binding] = []
            for body in raw.payload.get(f"labels_{lang}", []):
                result = parse_sparql_json(body)
                check_schema(LABELS_SCHEMA, observe_bindings(result))
                collected.extend(result.bindings)
            labels[lang] = collected
        merged = merge(codes, labels)
        rows = merged.rows
        return ParseResult(
            rows=rows,
            input_rows=merged.input_items,
            excluded=merged.excluded,
            schema=report,
            metrics={
                "items": len(rows),
                "items_with_rxcui": sum(1 for r in rows if r["rxcuis"]),
                **{
                    f"items_with_label_{lang}": sum(1 for r in rows if r[f"label_{lang}"])
                    for lang in LANGS
                },
            },
        )
