"""Drugs@FDA review documents for the drug model kit (spec model-kit, milestone M5): locate and
fetch.

The Drugs@FDA data file (one zip from fda.gov) maps products to applications and applications to
documents. For every pool drug the NDAs whose products have a single active ingredient naming the
drug are taken; their review documents (type 3) of the original submission are read from the review
table-of-contents page, and the clinical pharmacology or biopharmaceutics review PDFs (priority 1)
or the multidiscipline or integrated review (priority 2) are chosen, at most three per drug.
Download: one request per second at most, timeouts, a generic User-Agent, resumable (a file that is
already on disk is not fetched again). Build-time code. Research use only. Not for clinical
decisions."""

from __future__ import annotations

import csv
import io
import json
import re
import time
import zipfile
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass
from html import unescape as html_unescape
from pathlib import Path
from typing import Final
from urllib.parse import urljoin

from janus_pipelines.modelkit.resolver import IdentityTable

DATA_FILE_URL: Final = "https://www.fda.gov/media/89850/download"
REVIEW_TYPE: Final = "3"
MAX_PER_DRUG: Final = 3
MAX_PDF_BYTES: Final = 100 * 1024**2
_PRIORITY: Final = (
    (re.compile(r"clin\w*[ _-]?pharm|biopharm", re.I), 1),
    (re.compile(r"multi[ _-]?discipline|integrated ?r", re.I), 2),
)
_PDF_IN_JS: Final = re.compile(r"""(["'])([^"'<>\s+]+\.pdf)\1""", re.I)
_FLAG: Final = re.compile(r"(\w+)\s*:\s*([01])")
_SUFFIX: Final = re.compile(r"pdfBaseName \+ '(\w+\.pdf)")


@dataclass(frozen=True)
class ReviewPdf:
    drug_key: str
    appl_no: str
    url: str
    priority: int
    submission: str  # ORIG or SUPPL


def _rows(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    text = zf.read(name).decode("latin-1")
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


def drug_applications(zip_path: Path, table: IdentityTable) -> dict[str, list[str]]:
    """NDAs per pool drug: every product of the application has one active ingredient, naming only
    this drug."""
    with zipfile.ZipFile(zip_path) as zf:
        apps = {r["ApplNo"]: r for r in _rows(zf, "Applications.txt")}
        products = _rows(zf, "Products.txt")
    per_app: dict[str, set[str | None]] = defaultdict(set)
    for p in products:
        ingredient = p["ActiveIngredient"]
        if ";" in ingredient:
            per_app[p["ApplNo"]].add(None)
            continue
        drugs = table.drugs_in(ingredient)
        per_app[p["ApplNo"]].add(drugs[0] if len(drugs) == 1 else None)
    out: dict[str, list[str]] = defaultdict(list)
    for appl, keys in sorted(per_app.items()):
        if apps.get(appl, {}).get("ApplType") != "NDA" or len(keys) != 1 or None in keys:
            continue
        key = next(iter(keys))
        assert key is not None  # noqa: S101 - excluded above
        out[key].append(appl)
    return dict(out)


def review_entries(zip_path: Path, appls: set[str]) -> list[dict[str, str]]:
    """Review documents (type 3) of these applications, original submission first."""
    with zipfile.ZipFile(zip_path) as zf:
        docs = _rows(zf, "ApplicationDocs.txt")
    out = [
        d
        for d in docs
        if d["ApplicationDocsTypeID"] == REVIEW_TYPE
        and d["ApplNo"] in appls
        and d["ApplicationDocsURL"].strip()
    ]
    return sorted(
        out,
        key=lambda d: (d["ApplNo"], d["SubmissionType"].strip() != "ORIG", d["ApplicationDocsURL"]),
    )


def priority(name: str) -> int | None:
    for rx, p in _PRIORITY:
        if rx.search(name):
            return p
    return None


def toc_pdf_links(html: str, toc_url: str) -> list[str]:
    """The PDF links of a review table-of-contents page: plain links, the file names of the page's
    script, and the names built from the base name and the flags set to 1 (the newer pages build the
    links in a script)."""
    names: list[str] = []
    names += re.findall(r'href="([^"\']+\.pdf)"', html, re.I)
    if block := re.search(r"var pdfFilenames\s*=\s*\{([^}]*)\}", html, re.S):
        names += [n for _, n in _PDF_IN_JS.findall(block.group(1))]
    base = re.search(r'var pdfBaseName\s*=\s*"([^"]+)"', html)
    flags = {}
    if m := re.search(r"var pdfFiles\s*=\s*\{([^}]*)\}", html, re.S):
        flags = {k.lower(): v == "1" for k, v in _FLAG.findall(m.group(1))}
    if base:
        for m in _SUFFIX.finditer(html):
            if flags.get(m.group(1).removesuffix(".pdf").lower(), False):
                names.append(base.group(1) + m.group(1))
    out: list[str] = []
    for n in names:
        url = urljoin(toc_url, html_unescape(n.strip())).replace("http://", "https://")
        if url not in out:
            out.append(url)
    return out


def choose(drug_key: str, candidates: list[tuple[str, str, str]]) -> list[ReviewPdf]:
    """(appl, submission, url) -> at most MAX_PER_DRUG PDFs by priority, original first,
    application, URL."""
    seen: set[str] = set()
    ranked: list[ReviewPdf] = []
    for appl, sub, url in candidates:
        p = priority(url.rsplit("/", 1)[-1])
        if p is None or url in seen:
            continue
        seen.add(url)
        ranked.append(ReviewPdf(drug_key, appl, url, p, sub))
    ranked.sort(key=lambda r: (r.priority, r.submission != "ORIG", r.appl_no, r.url))
    return ranked[:MAX_PER_DRUG]


def pdf_name(r: ReviewPdf) -> str:
    return f"{r.drug_key}__{r.appl_no}__" + re.sub(
        r"[^A-Za-z0-9._-]", "_", r.url.rsplit("/", 1)[-1]
    )


Get = Callable[[str], bytes | None]  # GET with rate limit; None for a missing page


def locate_and_fetch(
    zip_path: Path,
    table: IdentityTable,
    out_dir: Path,
    get: Get,
    log: Callable[[str], None] = print,
) -> dict[str, object]:
    """Locate the review PDFs of every pool drug and download them into `out_dir/pdf`. Resumable:
    the table of contents pages are cached in `out_dir/toc`, the choice in `out_dir/choice.json`,
    files on disk are kept."""
    (out_dir / "toc").mkdir(parents=True, exist_ok=True)
    (out_dir / "pdf").mkdir(parents=True, exist_ok=True)
    apps = drug_applications(zip_path, table)
    entries = review_entries(zip_path, {a for v in apps.values() for a in v})
    by_app: dict[str, list[dict[str, str]]] = defaultdict(list)
    for e in entries:
        by_app[e["ApplNo"]].append(e)
    choice: dict[str, list[dict[str, object]]] = {}
    counts: dict[str, int] = defaultdict(int)
    t0 = time.monotonic()
    for i, key in enumerate(sorted(apps), 1):
        cands: list[tuple[str, str, str]] = []
        for appl in apps[key]:
            for e in by_app.get(appl, []):
                url = (
                    e["ApplicationDocsURL"]
                    .strip()
                    .replace("http://", "https://")
                    .replace(" ", "%20")
                )
                sub = e["SubmissionType"].strip()
                if url.lower().endswith(".pdf"):
                    cands.append((appl, sub, url))
                elif sub == "ORIG" and re.search(r"\.(?:html?|cfm)$", url, re.I):
                    cache = (
                        out_dir / "toc" / re.sub(r"[^A-Za-z0-9._-]", "_", url.rsplit("/", 1)[-1])
                    )
                    if cache.exists():
                        html = cache.read_text("latin-1")
                    else:
                        body = get(url)
                        counts["toc_requests"] += 1
                        html = (body or b"").decode("latin-1")
                        cache.write_text(html, "latin-1")
                    cands += [(appl, sub, u) for u in toc_pdf_links(html, url)]
        chosen = choose(key, cands)
        choice[key] = [asdict(c) for c in chosen]
        for c in chosen:
            target = out_dir / "pdf" / pdf_name(c)
            if target.exists():
                continue
            body = get(c.url)
            counts["pdf_requests"] += 1
            if body is None or len(body) > MAX_PDF_BYTES or not body.startswith(b"%PDF"):
                counts["pdf_missing_or_too_big"] += 1
                continue
            target.write_bytes(body)
        if i % 25 == 0:
            log(f"fda {i}/{len(apps)} drugs, {dict(counts)}, {time.monotonic() - t0:.0f}s")
            (out_dir / "choice.json").write_text(json.dumps(choice, indent=1))
    (out_dir / "choice.json").write_text(json.dumps(choice, indent=1))
    return {
        "drugs_with_nda": len(apps),
        "drugs_with_review_entry": sum(1 for k in apps if any(by_app.get(a) for a in apps[k])),
        "drugs_with_chosen_pdf": sum(1 for v in choice.values() if v),
        "pdfs_chosen": sum(len(v) for v in choice.values()),
        **counts,
    }
