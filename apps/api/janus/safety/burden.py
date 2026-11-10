"""Anticholinergic burden in published scales (safety-check design §7, Req 5 and 6). Pure.

Three scales whose papers are published under CC BY and print the scored list: the German
anticholinergic burden score (Kiesel 2018), the CRIDECO scale (Ramos 2022) and the Brazilian scale
(Nery and Reis 2019). The lists are committed as `data/anticholinergic_<scale>.csv` with a
`.meta.json` that carries the citation and licence. Janus adds nothing to the scores: a
contribution is a published score of an ingredient on the list, a total is the sum of the
contributions of one scale. Scales are never added together or compared, and no total is graded.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from janus.cascades.model import EngineItem
from janus.resolution.atc import DATA_DIR

RULES_VERSION = "burden-1"
SCALE_IDS = ("kiesel2018", "crideco2022", "brazil2019")
_KEY = re.compile(r"^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$")
_HEADER = ["drug_as_published", "score", "locator", "ingredient_key", "mapping", "mapping_note"]
_MAPPINGS = ("name", "alias", "none")


@dataclass(frozen=True)
class Drug:
    published: str
    score: int
    locator: str
    key: str | None
    mapping: str
    note: str


@dataclass(frozen=True)
class Scale:
    scale_id: str
    title: str
    citation: str
    url: str
    license: str
    license_url: str
    snapshot_date: str
    drugs: tuple[Drug, ...]

    @property
    def by_key(self) -> dict[str, Drug]:
        return {d.key: d for d in self.drugs if d.key}


@dataclass(frozen=True)
class Contribution:
    key: str
    label_en: str | None
    items: tuple[int, ...]
    score: int
    drug: Drug


@dataclass(frozen=True)
class ScaleResult:
    scale: Scale
    contributions: tuple[Contribution, ...]  # by key

    @property
    def total(self) -> int:
        return sum(c.score for c in self.contributions)


def load_scale(scale_id: str, data_dir: Path = DATA_DIR) -> Scale:
    """Read one scale; a malformed file stops the import (a wrong score must never be shown)."""
    meta = json.loads((data_dir / f"anticholinergic_{scale_id}.meta.json").read_text("utf-8"))
    if meta["scale_id"] != scale_id or not str(meta["license"]).startswith("CC BY"):
        raise ValueError(f"{scale_id}: metadata must name the scale and a CC BY licence")
    with (data_dir / f"anticholinergic_{scale_id}.csv").open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != _HEADER:
            raise ValueError(f"{scale_id}: unexpected header")
        drugs: list[Drug] = []
        for r in reader:
            key = (r["ingredient_key"] or "").strip() or None
            if (
                not r["drug_as_published"].strip()
                or not r["score"].isdigit()
                or not 1 <= int(r["score"]) <= 3
                or not r["locator"].strip()
                or r["mapping"] not in _MAPPINGS
                or (key is None) != (r["mapping"] == "none")
                or (key is not None and not _KEY.match(key))
                or (r["mapping"] != "name" and not r["mapping_note"].strip())
            ):
                raise ValueError(f"{scale_id}: malformed row {r['drug_as_published']!r}")
            drugs.append(
                Drug(
                    r["drug_as_published"].strip(),
                    int(r["score"]),
                    r["locator"].strip(),
                    key,
                    r["mapping"],
                    r["mapping_note"].strip(),
                )
            )
    seen: dict[str, int] = {}
    for d in drugs:
        if d.key and seen.setdefault(d.key, d.score) != d.score:
            raise ValueError(f"{scale_id}: one key with two scores ({d.key})")
    return Scale(
        scale_id=scale_id,
        title=str(meta["title"]),
        citation=str(meta["attribution"]),
        url=f"https://doi.org/{meta['doi']}",
        license=str(meta["license"]),
        license_url=str(meta["license_url"]),
        snapshot_date=str(meta["snapshot_date"]),
        drugs=tuple(drugs),
    )


def load_scales(data_dir: Path = DATA_DIR) -> tuple[Scale, ...]:
    return tuple(load_scale(s, data_dir) for s in SCALE_IDS)


SCALES: tuple[Scale, ...] = load_scales()


def find(items: Sequence[EngineItem], scales: Sequence[Scale] = SCALES) -> tuple[ScaleResult, ...]:
    """For each scale (in the order given), the published scores of the list's checked ingredients,
    by ingredient key; a key that stands in several items is one contribution naming them all."""
    where: dict[str, set[int]] = {}
    labels: dict[str, str | None] = {}
    for item in items:
        for ing in item.ingredients:
            where.setdefault(ing.key, set()).add(item.index)
            labels[ing.key] = labels.get(ing.key) or ing.label_en
    out: list[ScaleResult] = []
    for scale in scales:
        listed: Mapping[str, Drug] = scale.by_key
        out.append(
            ScaleResult(
                scale,
                tuple(
                    Contribution(k, labels[k], tuple(sorted(where[k])), listed[k].score, listed[k])
                    for k in sorted(where)
                    if k in listed
                ),
            )
        )
    return tuple(out)
