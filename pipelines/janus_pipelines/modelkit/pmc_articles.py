"""PMC Open Access articles (CC BY or CC0 only) for the drug model kit (spec model-kit, milestone
M5): find and fetch.

Search: Europe PMC (title names the drug and a PK word, open access, licence CC BY or CC0), drug
names in batches, hits assigned to drugs by the title, at most `MAX_PER_DRUG` newest articles per
drug. Full text: the PMC Article Datasets bucket of NLM (`pmc-oa-opendata`): the article version's
JSON metadata and its JATS XML. An article is used only if three licence checks pass (search result,
bucket metadata, the XML's own licence element) and it is neither retracted nor an author
manuscript. Build-time code; the caller supplies the rate-limited GET. Research use only. Not for
clinical decisions."""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlencode

from janus_pipelines.modelkit.resolver import IdentityTable

SEARCH_URL: Final = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
BUCKET: Final = "https://pmc-oa-opendata.s3.amazonaws.com"
MAX_PER_DRUG: Final = 10
BATCH: Final = 25
PK_TITLE: Final = "(TITLE:pharmacokinetic* OR TITLE:bioavailability OR TITLE:bioequivalence)"
LICENCE_QUERY: Final = 'OPEN_ACCESS:y AND (LICENSE:"cc by" OR LICENSE:"cc0")'
_BAD_TERMS: Final = re.compile(
    r"\b(?:nc|nd|sa)\b|non[- ]?commercial|no[- ]?deriv|share[- ]?alike", re.I
)


def search_queries(names: Sequence[str]) -> list[str]:
    """One query per batch of drug names (exact title phrases)."""
    out: list[str] = []
    for i in range(0, len(names), BATCH):
        part = " OR ".join(f'TITLE:"{n}"' for n in names[i : i + BATCH])
        out.append(f"({part}) AND {PK_TITLE} AND {LICENCE_QUERY}")
    return out


def search_licence_ok(hit: dict[str, Any]) -> bool:
    """Check 1: the licence of the search result is exactly CC BY or CC0."""
    return str(hit.get("license") or "").strip().lower() in ("cc by", "cc0")


def metadata_licence_ok(meta: dict[str, Any]) -> bool:
    """Check 3: the bucket's licence code is CC BY or CC0; not retracted, not an author manuscript."""
    code = re.sub(r"[\s_-]+", " ", str(meta.get("license_code") or "")).strip().lower()
    if code not in ("cc by", "cc0", "cc 0"):
        return False
    return str(meta.get("is_retracted", "no")).lower() not in ("yes", "true") and str(
        meta.get("is_manuscript", "no")
    ).lower() not in ("yes", "true")


def xml_licence(root: ET.Element) -> str | None:
    """Check 2: 'CC BY' or 'CC0' from the article's own <license> element, else None."""
    lic = root.find(".//permissions/license")
    if lic is None:
        return None
    href = " ".join(
        v for k, v in lic.attrib.items() if k.endswith("href") or k.endswith("license-type")
    )
    refs = [href] + [v for el in lic.iter() for k, v in el.attrib.items() if k.endswith("href")]
    text = " ".join(lic.itertext())
    blob = " ".join([*refs, text]).lower()
    if "creativecommons.org/publicdomain/zero" in blob or re.search(r"\bcc0\b", blob):
        return "CC0"
    by = re.search(r"creativecommons\.org/licenses/by/(\d\.\d)", blob)
    if by is None and not re.search(r"\bcc[ -]by\b(?![ -](?:nc|nd|sa))", blob):
        return None
    if re.search(r"licenses/by-(?:nc|nd|sa)", blob) or _BAD_TERMS.search(
        re.sub(r"creativecommons\.org/licenses/by/\S*", " ", blob)
    ):
        return None
    return f"CC BY {by.group(1)}" if by else "CC BY"


def assign(
    hits: list[dict[str, Any]], table: IdentityTable, pool: set[str]
) -> dict[str, list[dict[str, Any]]]:
    """Hits per pool drug named in the title, newest first, at most MAX_PER_DRUG, each passing check
    1."""
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for h in sorted(
        hits,
        key=lambda h: (str(h.get("firstPublicationDate") or ""), str(h.get("pmcid"))),
        reverse=True,
    ):
        if not h.get("pmcid") or not search_licence_ok(h):
            continue
        for key in table.drugs_in(re.sub(r"<[^>]+>", " ", str(h.get("title") or ""))):
            if key in pool and (key, h["pmcid"]) not in seen and len(out[key]) < MAX_PER_DRUG:
                seen.add((key, h["pmcid"]))
                out[key].append(h)
    return dict(out)


Get = Callable[[str], bytes | None]


def run_search(
    names: Sequence[str], get: Get, cache: Path, log: Callable[[str], None] = print
) -> list[dict[str, Any]]:
    """Every hit of every batch query (cursor paging), cached per query and page."""
    cache.mkdir(parents=True, exist_ok=True)
    hits: list[dict[str, Any]] = []
    for qi, q in enumerate(search_queries(names)):
        cursor, page = "*", 0
        while True:
            f = cache / f"q{qi:03d}-p{page:02d}.json"
            if f.exists():
                body = f.read_bytes()
            else:
                url = (
                    SEARCH_URL
                    + "?"
                    + urlencode(
                        {
                            "query": q,
                            "format": "json",
                            "resultType": "core",
                            "pageSize": "1000",
                            "cursorMark": cursor,
                        }
                    )
                )
                got = get(url)
                if got is None:
                    log(f"search failed q{qi} p{page}")
                    break
                body = got
                f.write_bytes(body)
            d = json.loads(body)
            res = d.get("resultList", {}).get("result", [])
            hits += res
            nxt = d.get("nextCursorMark")
            if not res or not nxt or nxt == cursor:
                break
            cursor, page = nxt, page + 1
        log(f"search batch {qi + 1}: {len(hits)} hits so far")
    return hits


def version_keys(listing_xml: bytes, pmcid: str) -> list[str]:
    """Article version prefixes of a bucket listing (ListObjectsV2), e.g. PMC123.1, in version
    order."""
    keys = re.findall(rb"<Key>([^<]+)</Key>", listing_xml)
    vers = sorted(
        {int(m.group(1)) for k in keys if (m := re.match(rf"{pmcid}\.(\d+)/".encode(), k))}
    )
    return [f"{pmcid}.{v}" for v in vers]


def fetch_articles(
    chosen: dict[str, list[dict[str, Any]]],
    get: Get,
    out_dir: Path,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """For every chosen article: the newest version whose metadata passes check 3; its XML (kept if
    check 2 passes). Resumable: files on disk are reused. Writes `articles.json` (one record per
    article with the outcome)."""
    (out_dir / "xml").mkdir(parents=True, exist_ok=True)
    (out_dir / "meta").mkdir(parents=True, exist_ok=True)
    records: dict[str, dict[str, Any]] = {}
    pmcids = sorted({h["pmcid"] for hs in chosen.values() for h in hs})
    t0 = time.monotonic()
    for i, pmcid in enumerate(pmcids, 1):
        rec: dict[str, Any] = {
            "pmcid": pmcid,
            "drugs": sorted(k for k, hs in chosen.items() if any(h["pmcid"] == pmcid for h in hs)),
        }
        listing = out_dir / "meta" / f"{pmcid}.list.xml"
        if not listing.exists():
            body = get(f"{BUCKET}/?list-type=2&prefix={pmcid}.")
            listing.write_bytes(body or b"")
        versions = version_keys(listing.read_bytes(), pmcid)
        rec["outcome"] = "no_version_in_bucket"
        for v in reversed(versions):
            mfile = out_dir / "meta" / f"{v}.json"
            if not mfile.exists():
                body = get(f"{BUCKET}/metadata/{v}.json")
                mfile.write_bytes(body or b"{}")
            meta = json.loads(mfile.read_bytes() or b"{}")
            if not metadata_licence_ok(meta):
                rec["outcome"] = "metadata_licence_or_type_refused"
                rec["license_code"] = meta.get("license_code")
                continue
            xfile = out_dir / "xml" / f"{v}.xml"
            if not xfile.exists():
                body = get(f"{BUCKET}/{v}/{v}.xml")
                if body is None:
                    rec["outcome"] = "xml_missing"
                    break
                xfile.write_bytes(body)
            try:
                root = ET.fromstring(xfile.read_bytes())  # noqa: S314 - public archive file, parsed, never executed
            except ET.ParseError:
                rec["outcome"] = "xml_unreadable"
                break
            lic = xml_licence(root)
            rec.update(
                version=v,
                license_code=meta.get("license_code"),
                xml_licence=lic,
                citation=meta.get("citation"),
            )
            rec["outcome"] = "ok" if lic else "xml_licence_refused"
            if lic is None:
                xfile.unlink()
            break
        records[pmcid] = rec
        if i % 50 == 0:
            log(f"pmc {i}/{len(pmcids)} articles, {time.monotonic() - t0:.0f}s")
            (out_dir / "articles.json").write_text(json.dumps(records, indent=1))
    (out_dir / "articles.json").write_text(json.dumps(records, indent=1))
    outcomes: dict[str, int] = defaultdict(int)
    for r in records.values():
        outcomes[r["outcome"]] += 1
    return {"articles": len(records), "outcomes": dict(outcomes)}
