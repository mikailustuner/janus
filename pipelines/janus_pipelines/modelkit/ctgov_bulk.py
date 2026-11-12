"""ClinicalTrials.gov bulk download -> evidence candidates (spec model-kit, milestone M2).

Reads the official bulk file (`ctg-studies.json.zip`: one JSON record per study, the same record
format as the study endpoint of the data API) from disk, keeps the studies with posted results that
have a PK outcome measure and name a drug of the pool, and reads each (study, drug) pair with the
two independent readers. Build-time code, no network. Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import json
import pickle
import zipfile
from collections import Counter
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from janus_pipelines.modelkit import formulation, reader_a, reader_b, strict_ctgov
from janus_pipelines.modelkit.formref import BrandTable
from janus_pipelines.modelkit.model import Candidate, ReaderStats
from janus_pipelines.modelkit.pairing import Paired, pair
from janus_pipelines.modelkit.resolver import IdentityTable

_RESULTS = b'"resultsSection"'
_MAX_MEMBER = 200_000_000  # bytes; a single study record is far smaller


def iter_result_studies(
    zf: zipfile.ZipFile, names: list[str], counts: Counter[str]
) -> Iterator[dict[str, Any]]:
    """Every listed study record of the bulk file that has posted results with outcome measures."""
    for name in names:
        info = zf.getinfo(name)
        if info.file_size > _MAX_MEMBER:
            continue
        counts["studies"] += 1
        raw = zf.read(info)
        if _RESULTS not in raw:
            continue
        counts["studies_with_results"] += 1
        study = json.loads(raw)
        if "outcomeMeasuresModule" not in study.get("resultsSection", {}):
            continue
        yield study


def has_pk_outcome(study: dict[str, Any]) -> bool:
    measures = study["resultsSection"]["outcomeMeasuresModule"].get("outcomeMeasures", [])
    return any(reader_a.parameter_of(m.get("title", "")) is not None for m in measures)


def study_drugs(study: dict[str, Any], table: IdentityTable) -> list[str]:
    """Pool drugs named by the interventions, the arm groups or the titles of the record."""
    proto = study["protocolSection"]
    parts: list[str] = []
    ident = proto.get("identificationModule", {})
    parts += [ident.get("briefTitle", ""), ident.get("officialTitle", "")]
    arms = proto.get("armsInterventionsModule", {})
    for i in arms.get("interventions", []):
        parts.append(i.get("name", ""))
        parts += i.get("otherNames", [])
    for g in arms.get("armGroups", []):
        parts += [g.get("label", ""), g.get("description", "")]
    return table.drugs_in(" . ".join(parts))


Shard = tuple[
    list[Paired], list[Candidate], dict[str, set[str]], Counter[str], dict[str, ReaderStats]
]
SHARDS = 256  # a fixed number: the result does not depend on how many workers run them

_G: dict[str, Any] = {}


def _read_shard(
    zip_path: Path, names: list[str], table: IdentityTable, brands: BrandTable
) -> Shard:
    pairs: list[Paired] = []
    only_b: list[Candidate] = []
    kept: dict[str, set[str]] = {}
    counts: Counter[str] = Counter()
    stats = {"a": ReaderStats(), "b": ReaderStats()}
    with zipfile.ZipFile(zip_path) as zf:
        for study in iter_result_studies(zf, names, counts):
            if not has_pk_outcome(study):
                continue
            counts["studies_with_pk_outcome"] += 1
            drugs = study_drugs(study, table)
            if not drugs:
                continue
            counts["studies_naming_a_pool_drug"] += 1
            nct = study["protocolSection"]["identificationModule"]["nctId"]
            for key in drugs:
                a_rows = reader_a.read_ctgov(study, key, table, stats["a"])
                b_rows = reader_b.read_ctgov(study, key, table, stats["b"])
                if not a_rows and not b_rows:
                    continue
                kept.setdefault(key, set()).add(nct)
                p, left = pair(a_rows, b_rows)
                p = formulation.resolve_pairs(p, study, table, brands, counts)
                p = strict_ctgov.apply(p, study, table, brands, counts)
                pairs += p
                only_b += left
    return pairs, only_b, kept, counts, stats


def _init_worker(identity_text: str, brands_text: str) -> None:
    _G["table"] = IdentityTable.from_csv(identity_text)
    _G["brands"] = BrandTable.from_csv(brands_text) if brands_text else BrandTable.empty()


def _work(args: tuple[Path, list[str], Path | None]) -> Shard:
    """One shard; with a checkpoint file the result is kept there and reused by a later run."""
    zip_path, names, checkpoint = args
    if checkpoint is not None and checkpoint.exists():
        return pickle.loads(checkpoint.read_bytes())  # noqa: S301 - our own earlier output
    shard = _read_shard(zip_path, names, _G["table"], _G["brands"])
    if checkpoint is not None:
        tmp = checkpoint.with_suffix(".tmp")
        tmp.write_bytes(pickle.dumps(shard))
        tmp.replace(checkpoint)
    return shard


def read_bulk(
    zip_path: Path,
    identity_text: str,
    stats: dict[str, ReaderStats],
    counts: Counter[str],
    workers: int = 1,
    checkpoint_dir: Path | None = None,
    brands_text: str = "",
) -> tuple[list[Paired], list[Candidate], dict[str, set[str]]]:
    """Pairs of the two readers for every (study, drug); candidates only reader B found; the studies
    kept per drug. The member list is cut into SHARDS contiguous parts that are read independently
    (in `workers` processes) and joined in order, so the result is the same for any worker count."""
    with zipfile.ZipFile(zip_path) as zf:
        names = [i.filename for i in zf.infolist() if i.filename.endswith(".json")]
    size = max(1, -(-len(names) // SHARDS))
    if checkpoint_dir is not None:
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
    tasks = [
        (
            zip_path,
            names[i : i + size],
            None if checkpoint_dir is None else checkpoint_dir / f"shard-{i // size:03d}.pkl",
        )
        for i in range(0, len(names), size)
    ]
    del names
    if workers <= 1:
        _init_worker(identity_text, brands_text)
        shards = [_work(t) for t in tasks]
    else:
        with ProcessPoolExecutor(
            max_workers=workers, initializer=_init_worker, initargs=(identity_text, brands_text)
        ) as pool:
            shards = list(pool.map(_work, tasks))
    pairs: list[Paired] = []
    only_b: list[Candidate] = []
    kept: dict[str, set[str]] = {}
    for p, ob, k, c, st in shards:
        pairs += p
        only_b += ob
        for key, ncts in k.items():
            kept.setdefault(key, set()).update(ncts)
        counts.update(c)
        for r in "ab":
            stats[r].seen += st[r].seen
            for why, n in st[r].skipped.items():
                stats[r].skipped[why] = stats[r].skipped.get(why, 0) + n
    return pairs, only_b, kept
