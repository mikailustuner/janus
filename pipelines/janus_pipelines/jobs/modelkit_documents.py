"""`modelkit_documents` pipeline: Drugs@FDA review PDFs and PMC Open Access articles (CC BY or CC0)
for the drug model kit (spec model-kit, milestone M5).

Input: a folder (`--input`) with the Drugs@FDA data file (`fda_meta/drugsatfda.zip`), the chosen
review PDFs (`fda/choice.json`, `fda/pdf/`) and the PMC articles (`pmc/articles.json`, `pmc/xml/`),
as `fda_reviews.locate_and_fetch` and `pmc_articles.fetch_articles` leave them; without `--input`
the job fetches them into its scratch folder first (at most one request per second per host, the
crawl delays of robots.txt respected, a generic User-Agent). Only the text layer of born-digital
PDFs is read; scanned PDFs are counted, not read. Tables only. Two independent readers, confirmation
by code, the human-only filter for articles, the study keys of every study (NCT numbers, sponsor
codes, review document) for the study identity rule of the evidence job. The rows have the evidence
schema; the `modelkit_evidence` job merges the rows of the sources whose measured precision allows
it (`data/modelkit/precision.json`). Research use only. Not for clinical decisions.

Sources: Drugs@FDA (public domain, U.S. government work; not an FDA endorsement) and PubMed Central
articles via the PMC Article Datasets of NLM (each article's own CC BY or CC0 licence; authors and
article are credited on every value; changes: values transcribed from a table, units converted,
short parts quoted)."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, ClassVar, Final

import polars as pl

from janus_pipelines.core.canonical import Json, Row
from janus_pipelines.core.http import RateLimiter, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import SchemaReport
from janus_pipelines.jobs.modelkit_evidence import EVIDENCE_ROW, EVIDENCE_SCHEMA, evidence_row
from janus_pipelines.modelkit import documents, fda_reviews, pmc_articles, review_text
from janus_pipelines.modelkit.doc_a import ReviewDoc, study_code
from janus_pipelines.modelkit.formref import BrandTable
from janus_pipelines.modelkit.model import ReaderStats
from janus_pipelines.modelkit.pairing import Paired
from janus_pipelines.modelkit.pilot import finalize_rows
from janus_pipelines.modelkit.pmc_jats import attribution, parse_article
from janus_pipelines.modelkit.resolver import IdentityTable
from janus_pipelines.modelkit.study_identity import keys_text

IDENTITY_PATH: Final = ("data", "modelkit", "identity_m2.csv")
PRODUCTS_PATH: Final = ("data", "modelkit", "product_forms.csv")
FDA_VERSION: Final = (
    "Drugs@FDA review PDF, born-digital text layer, retrieved {date}; "
    "public domain (U.S. government work), "
    "not an FDA endorsement"
)
PMC_VERSION: Final = (
    "{attribution} Retrieved {date} from the PMC Article Datasets (NLM); "
    "not an endorsement by the authors."
)
RATES: Final = {
    "www.fda.gov": 1 / 30,
    "www.accessdata.fda.gov": 1.0,
    "www.ebi.ac.uk": 0.1,
    "pmc-oa-opendata.s3.amazonaws.com": 1.0,
}

_G: dict[str, Any] = {}


def _init(identity: str, brands: str, forms: dict[str, frozenset[str]] | None = None) -> None:
    _G["table"] = IdentityTable.from_csv(identity)
    _G["brands"] = BrandTable.from_csv(brands) if brands else BrandTable.empty()
    _G["forms"] = forms or {}


def _pages(pdf: Path, cache: Path | None) -> list[str]:
    if cache is not None and cache.exists():
        return cache.read_text("utf-8").split("\f")
    pages = review_text.pdf_pages(pdf)
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text("\f".join(pages), "utf-8")
    return pages


def _read_pdf(
    args: tuple[dict[str, Any], Path, Path | None, str],
) -> tuple[str, list[Paired], list[str], Counter[str]]:
    choice, pdf, cache, date = args
    counts: Counter[str] = Counter()
    pages = _pages(pdf, cache)
    if not review_text.born_digital(pages):
        counts["review_pdfs_scanned"] += 1
        return pdf.name, [], [], counts
    counts["review_pdfs_born_digital"] += 1
    marked = review_text.mark_pages(pages)
    doc = ReviewDoc(
        choice["drug_key"], choice["appl_no"], choice["url"], choice["url"].rsplit("/", 1)[-1],
        FDA_VERSION.format(date=date),
    )  # fmt: skip
    stats = {"a": ReaderStats(), "b": ReaderStats()}
    forms = _G["forms"].get(choice["appl_no"], frozenset())
    pairs = documents.read_review(marked, doc, _G["table"], _G["brands"], stats, counts, forms)
    if pairs:
        counts["review_pdfs_with_candidates"] += 1
    return pdf.name, pairs, documents.review_study_keys(marked), counts


def read_folder(
    folder: Path, identity: str, brands: str, date: str, workers: int
) -> tuple[list[Row], dict[str, Json]]:
    """Every chosen review PDF and every licensed article of the folder -> checked evidence rows and
    metrics."""
    table = IdentityTable.from_csv(identity)
    counts: Counter[str] = Counter()
    rows: list[Row] = []
    choice_file = folder / "fda" / "choice.json"
    tasks: list[tuple[dict[str, Any], Path, Path | None, str]] = []
    if choice_file.exists():
        for chosen in json.loads(choice_file.read_text()).values():
            for c in chosen:
                pdf = folder / "fda" / "pdf" / fda_reviews.pdf_name(fda_reviews.ReviewPdf(**c))
                counts["review_pdfs_chosen"] += 1
                if pdf.exists():
                    counts["review_pdfs_downloaded"] += 1
                    tasks.append((c, pdf, folder / "fda" / "txt" / (pdf.name + ".txt"), date))
    data_file = folder / "fda_meta" / "drugsatfda.zip"
    forms = documents.application_forms(data_file) if data_file.exists() else {}
    if workers > 1:
        with ProcessPoolExecutor(
            max_workers=workers, initializer=_init, initargs=(identity, brands, forms)
        ) as pool:
            results = list(pool.map(_read_pdf, tasks, chunksize=4))
    else:
        _init(identity, brands, forms)
        results = [_read_pdf(t) for t in tasks]
    doc_level: set[str] = set()
    for _, pairs, _, _ in results:
        doc_level |= {
            p.a.locator.split("#", 1)[0] for p in pairs if p.a.study_id.startswith("FDA NDA ")
        }
    for _name, pairs, ncts, c in results:
        counts.update(c)
        made, dropped = finalize_rows(pairs, table)
        counts.update({f"dropped:{k}": v for k, v in dropped.items()})
        for r in made:
            r["extracted_at"] = date
            row = dict(evidence_row(r, "documents"))
            url = str(row["source_locator"]).split("#", 1)[0]
            code = (
                str(row["study_id"]).removeprefix("FDA study ")
                if str(row["study_id"]).startswith("FDA study ")
                else ""
            )
            row["study_keys"] = keys_text(
                ncts, [code] if code else [], [url] if url in doc_level else []
            )
            rows.append(row)
    _init(identity, brands)
    articles_file = folder / "pmc" / "articles.json"
    if articles_file.exists():
        for rec in json.loads(articles_file.read_text()).values():
            counts["pmc_articles_chosen"] += 1
            if rec.get("outcome") != "ok":
                counts[f"pmc_articles_{rec.get('outcome')}"] += 1
                continue
            xml = folder / "pmc" / "xml" / f"{rec['version']}.xml"
            art = parse_article(xml.read_bytes(), rec["pmcid"], str(rec["xml_licence"]))
            counts["pmc_articles_licensed"] += 1
            version = PMC_VERSION.format(attribution=attribution(art), date=date)
            stats = {"a": ReaderStats(), "b": ReaderStats()}
            codes = [x for x in (study_code(art.methods), study_code(art.abstract)) if x]
            for key in rec["drugs"]:
                pairs = documents.read_article(
                    art, key, _G["table"], _G["brands"], stats, counts, version
                )
                made, dropped = finalize_rows(pairs, table)
                counts.update({f"dropped:{k}": v for k, v in dropped.items()})
                for r in made:
                    r["extracted_at"] = date
                    row = dict(evidence_row(r, "documents"))
                    row["study_keys"] = keys_text(art.nct_ids, codes)
                    rows.append(row)
    confirmed = [r for r in rows if r["confirmed"]]
    metrics: dict[str, Json] = {
        **dict(sorted(counts.items())),
        "rows": len(rows),
        "confirmed_rows": len(confirmed),
        "by_source": {
            s: {
                "rows": sum(1 for r in rows if r["source_id"] == s),
                "confirmed": sum(1 for r in confirmed if r["source_id"] == s),
                "drugs_with_confirmed_row": len(
                    {str(r["drug_key"]) for r in confirmed if r["source_id"] == s}
                ),
                "documents_with_confirmed_row": len(
                    {
                        str(r["source_locator"]).split("#", 1)[0]
                        for r in confirmed
                        if r["source_id"] == s
                    }
                ),
            }
            for s in ("drugsatfda_review", "pmc_oa")
        },
        "processing_date": date,
    }
    return rows, metrics


def _fetch_all(target: Path, table: IdentityTable) -> None:
    """The network path: data file, review pages and PDFs, Europe PMC search, the articles."""
    fetcher = make_fetcher(require_contact=False)
    fetcher.limiter = RateLimiter(rates=RATES, default_rate=1.0)

    def get(url: str) -> bytes | None:
        r = fetcher.get(url, allow_status=frozenset({403, 404, 410}))
        return None if r.status_code in (403, 404, 410) else r.content

    meta = target / "fda_meta"
    meta.mkdir(parents=True, exist_ok=True)
    zip_path = meta / "drugsatfda.zip"
    if not zip_path.exists():
        body = get(fda_reviews.DATA_FILE_URL)
        if body is None:
            raise ValueError("Drugs@FDA data file not available")
        zip_path.write_bytes(body)
    fda_reviews.locate_and_fetch(zip_path, table, target / "fda", get)
    keys = sorted(table.by_key)
    hits = pmc_articles.run_search(
        [k.replace("_", " ") for k in keys], get, target / "pmc" / "search"
    )
    chosen = pmc_articles.assign(hits, table, set(keys))
    pmc_articles.fetch_articles(chosen, get, target / "pmc")


class ModelkitDocumentsJob(Job[Path]):
    name = "modelkit_documents"
    source_id = "modelkit_documents"
    schema = EVIDENCE_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {**EVIDENCE_ROW, "study_keys": pl.String()}

    def fetch(self, ctx: RunContext) -> RawInput[Path]:
        now = ctx.now()
        local = ctx.options.get("input")
        if local:
            folder = Path(local)
            urls: tuple[str, ...] = ()
        else:
            folder = ctx.scratch_dir(self.name)
            table = IdentityTable.from_csv(
                ctx.repo_root.joinpath(*IDENTITY_PATH).read_text("utf-8")
            )
            _fetch_all(folder, table)
            urls = (fda_reviews.DATA_FILE_URL, pmc_articles.SEARCH_URL, pmc_articles.BUCKET)
        digest = hashlib.sha256()
        for f in sorted(folder.glob("fda/choice.json")) + sorted(folder.glob("pmc/articles.json")):
            digest.update(f.read_bytes())
        date = ctx.options.get("snapshot_date") or now.date().isoformat()
        return RawInput(folder, urls, digest.hexdigest(), now, date)

    def parse(self, raw: RawInput[Path]) -> ParseResult:
        repo = Path(__file__).resolve().parents[3]
        identity = repo.joinpath(*IDENTITY_PATH).read_text("utf-8")
        brands = repo.joinpath(*PRODUCTS_PATH).read_text("utf-8")
        workers = max(1, min(2, int(os.environ.get("JANUS_MODELKIT_WORKERS", "1"))))
        date = raw.snapshot_date or raw.retrieved_at.date().isoformat()
        t0 = time.monotonic()
        rows, metrics = read_folder(raw.payload, identity, brands, date, workers)
        metrics["seconds"] = round(time.monotonic() - t0, 1)
        return ParseResult(
            rows=rows, input_rows=len(rows), excluded={}, schema=SchemaReport(), metrics=metrics
        )
