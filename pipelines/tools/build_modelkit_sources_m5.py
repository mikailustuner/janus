"""Build `data/modelkit/sources_m5.json`: the source records (milestone M5) of the published rows of
the current `modelkit_documents` artifact: per PMC article its title, authors, journal, year, DOI,
licence and link; per review study the Drugs@FDA PDF it was read from. The exports cite them
(references.bib, LICENSES.txt). Only sources listed as published in precision_documents.json are
written. Research use only.

python tools/build_modelkit_sources_m5.py DOCS_ROWS_PARQUET DL_DIR PRECISION_JSON OUT_JSON
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import polars as pl

from janus_pipelines.modelkit.pmc_jats import parse_article


def main(rows_path: Path, dl: Path, precision: Path, out: Path) -> None:
    published = {
        k for k, v in json.loads(precision.read_text("utf-8")).items() if v.get("published") is True
    }
    rows = pl.read_parquet(rows_path).to_dicts()
    records: dict[str, dict[str, Any]] = {}
    arts = json.loads((dl / "pmc" / "articles.json").read_text("utf-8"))
    for r in sorted(rows, key=lambda r: (r["source_id"], r["study_id"], r["source_locator"])):
        key = f"{r['source_id']}:{r['study_id']}"
        if r["source_id"] not in published or key in records:
            continue
        if r["source_id"] == "pmc_oa":
            rec = arts[r["study_id"]]
            xml = (dl / "pmc" / "xml" / f"{rec['version']}.xml").read_bytes()
            a = parse_article(xml, r["study_id"], str(rec["xml_licence"]))
            records[key] = {
                "type": "article",
                "title": a.title,
                "authors": list(a.authors),
                "journal": a.journal,
                "year": a.year,
                "doi": a.doi,
                "pmcid": a.pmcid,
                "licence": a.licence,
                "url": f"https://pmc.ncbi.nlm.nih.gov/articles/{a.pmcid}/",
                "retrieved": r["extracted_at"],
            }
        elif r["source_id"] == "drugsatfda_review":
            url = str(r["source_locator"]).split("#", 1)[0]
            records[key] = {
                "type": "review",
                "title": f"Drugs@FDA review PDF {url.rsplit('/', 1)[-1]} ({r['study_id']})",
                "url": url,
                "retrieved": r["extracted_at"],
                "licence": "public domain unless noted (U.S. government work)",
            }
    out.write_text(json.dumps(records, indent=1, sort_keys=True, ensure_ascii=False) + "\n", "utf-8")
    print(f"{len(records)} source records")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
