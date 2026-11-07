"""Checks on the real pipeline artifacts (drug-resolution design §7). Local only: skipped in CI
and when `JANUS_DATA_DIR` has no current artifacts. Prints counts only, no TİTCK names."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import pytest

from janus.resolution.load import LoadError, gather, prepare_inputs
from janus.resolution.names import fold

DATA_DIR = Path(os.environ.get("JANUS_DATA_DIR") or Path(__file__).resolve().parents[3] / ".data")

pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true" or not (DATA_DIR / "artifacts" / "titck" / "current").exists(),
    reason="real artifacts are local only",
)


def test_real_artifacts() -> None:
    try:
        inputs = gather(DATA_DIR)
    except LoadError as exc:  # pragma: no cover - local setup
        pytest.skip(str(exc))
    for a in inputs.artifacts.values():
        a.verify()
    ds = prepare_inputs(inputs)
    tr = [p for p in ds.products if p.source_id == "titck"]

    amlipin = [p for p in tr if p.codes and p.codes[0][1] == "8680199094206"]
    assert len(amlipin) == 1
    assert [(i.qid, i.rule_input()) for i in amlipin[0].ingredients] == [
        ("Q411347", ("C08CA01",)),
        ("Q412208", ("C09AA03",)),
    ]

    barcodes = Counter(p.codes[0][1] for p in tr if p.codes)
    dups = {b: n for b, n in barcodes.items() if n > 1}
    assert (len(dups), sum(dups.values())) == (52, 104)

    name_only = [p for p in tr if p.name_only]
    assert len(name_only) == 155
    product_keys = {(n.name_key, n.ref) for n in ds.names if n.kind == "product"}
    assert all((fold(p.product_name or ""), p.candidate_id) in product_keys for p in name_only)

    cov = ds.coverage
    rx = cov["openfda_ndc"]["rx"]["products_fully_mapped_share"]
    print(  # local report, counts only
        "titck occurrences mapped", cov["titck"]["occurrences_mapped_share"],
        "| openFDA Rx products fully mapped", rx,
        "| group agreement", cov["titck"]["wikidata_group_agreement"]["share"],
    )  # fmt: skip
