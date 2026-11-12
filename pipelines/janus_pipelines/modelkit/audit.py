"""Expert sample audit of the model kit (plan sections 6.4 and 12.3; milestone M6).

A reviewer answers each item of a stratified random sample of the published confirmed values with
`correct`, `incorrect` or `cannot_judge`. This module scores filled answer sheets (precision with
Wilson 95 % intervals per stratum, per margin and overall; the release criterion) and checks the
`expert_audit` record that the evidence job reads from `data/modelkit/expert_audit.json`. The record
holds counts, dates and reviewer roles only, never a name. Research use only. Not for clinical
decisions.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

VERDICTS: Final = frozenset({"correct", "incorrect", "cannot_judge"})
ERROR_CLASSES: Final = frozenset(
    {
        "value", "unit", "parameter", "analyte", "dose", "arm_context", "population",
        "formulation_route", "regimen", "statistic", "source_mismatch", "sp_class_grade",
        "sp_measure", "sp_magnitude_direction", "sp_reference", "other",
    }
)  # fmt: skip
ROLES: Final = frozenset({"pharmacometrician", "clinical_pharmacologist", "pharmacist"})
# plan section 12.3: precision >= 0.95, Wilson lower bound >= 0.90, n >= 300
PRECISION_MIN: Final = 0.95
WILSON_LOW_MIN: Final = 0.90
N_MIN: Final = 300
RECORD_SCHEMA: Final = "modelkit_expert_audit-1"
_DATE = re.compile(r"^20[0-9]{2}-[01][0-9]-[0-3][0-9]$")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson score interval of k successes in n trials; None for n = 0."""
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (0.0 if k == 0 else max(0.0, c - h)), (1.0 if k == n else min(1.0, c + h))


@dataclass(frozen=True)
class Share:
    correct: int
    incorrect: int
    cannot_judge: int
    blank: int

    @property
    def n(self) -> int:
        return self.correct + self.incorrect

    @property
    def precision(self) -> float | None:
        return self.correct / self.n if self.n else None

    @property
    def interval(self) -> tuple[float, float] | None:
        return wilson(self.correct, self.n)

    @property
    def conservative(self) -> float | None:
        answered = self.n + self.cannot_judge
        return self.correct / answered if answered else None

    def as_dict(self) -> dict[str, object]:
        iv = self.interval
        return {
            "correct": self.correct,
            "incorrect": self.incorrect,
            "cannot_judge": self.cannot_judge,
            "blank": self.blank,
            "n": self.n,
            "precision": self.precision,
            "wilson_low": iv[0] if iv else None,
            "wilson_high": iv[1] if iv else None,
            "conservative": self.conservative,
        }


def share(verdicts: Sequence[str]) -> Share:
    c = Counter(verdicts)
    return Share(c["correct"], c["incorrect"], c["cannot_judge"], c[""])


def read_answers(rows: Sequence[Mapping[str, str]], where: str) -> dict[str, str]:
    """item id -> verdict ("" when not answered) of one filled sheet. Raises ValueError on an
    unknown verdict, an incorrect item without an error class from the fixed list, or a repeat."""
    out: dict[str, str] = {}
    for i, r in enumerate(rows, start=2):
        item = (r.get("item_id") or "").strip()
        if not item:
            raise ValueError(f"{where}:{i}: no item_id")
        if item in out:
            raise ValueError(f"{where}:{i}: item {item} answered twice")
        v = (r.get("verdict") or "").strip().lower().replace(" ", "_").replace("-", "_")
        if v and v not in VERDICTS:
            raise ValueError(f"{where}:{i}: verdict must be correct, incorrect or cannot_judge")
        if v == "incorrect":
            classes = {
                c.strip() for c in (r.get("error_class") or "").replace(";", ",").split(",")
            } - {""}
            if not classes or not classes <= ERROR_CLASSES:
                raise ValueError(f"{where}:{i}: an incorrect item needs an error class of the list")
        out[item] = v
    return out


def consensus(sheets: Sequence[Mapping[str, str]]) -> dict[str, str]:
    """Strict consensus of several reviewers (pre-registered): incorrect if any reviewer says
    incorrect; correct if none does and at least one says correct; cannot_judge if every answer is
    cannot_judge; blank if nobody answered."""
    items = sorted({k for s in sheets for k in s})
    out: dict[str, str] = {}
    for k in items:
        vs = {s.get(k, "") for s in sheets} - {""}
        if "incorrect" in vs:
            out[k] = "incorrect"
        elif "correct" in vs:
            out[k] = "correct"
        elif vs:
            out[k] = "cannot_judge"
        else:
            out[k] = ""
    return out


def kappa(a: Mapping[str, str], b: Mapping[str, str]) -> float | None:
    """Cohen's kappa on the items both reviewers judged correct or incorrect."""
    both = [
        k for k in a if a[k] in ("correct", "incorrect") and b.get(k) in ("correct", "incorrect")
    ]
    if not both:
        return None
    n = len(both)
    po = sum(a[k] == b[k] for k in both) / n
    pa = sum(a[k] == "correct" for k in both) / n
    pb = sum(b[k] == "correct" for k in both) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def criterion_met(s: Share) -> bool:
    iv = s.interval
    return bool(
        s.n >= N_MIN and s.precision is not None and s.precision >= PRECISION_MIN
        and iv is not None and iv[0] >= WILSON_LOW_MIN
    )  # fmt: skip


def score(
    answers: Mapping[str, str],
    key: Sequence[Mapping[str, str]],
    frame_sizes: Mapping[str, int] | None = None,
) -> dict[str, object]:
    """Precision per stratum, per margin (frame, source group, parameter group, population) and
    overall for one sheet (or the consensus). `key` rows have item_id, frame and stratum
    ("source|parameter group|population" for frame E, "S|class|measure" for frame S). With
    `frame_sizes` (stratum -> N_h) a frame-weighted point estimate is added for information."""
    unknown = set(answers) - {k["item_id"] for k in key}
    if unknown:
        raise ValueError(f"answers for items not in the key: {sorted(unknown)[:5]}")
    by: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    every: list[str] = []
    for k in key:
        v = answers.get(k["item_id"], "")
        every.append(v)
        parts = k["stratum"].split("|")
        by["stratum"][k["stratum"]].append(v)
        by["frame"][k["frame"]].append(v)
        by["source"][parts[0]].append(v)
        if k["frame"] == "E":
            by["parameter_group"][parts[1]].append(v)
            by["population"][parts[2]].append(v)
        else:
            by["sp_class"][parts[1]].append(v)
            by["sp_measure"][parts[2]].append(v)
    overall = share(every)
    out: dict[str, object] = {
        "overall": overall.as_dict(),
        "criterion": {
            "precision_min": PRECISION_MIN,
            "wilson_low_min": WILSON_LOW_MIN,
            "n_min": N_MIN,
            "met": criterion_met(overall),
        },
        **{
            m: {g: share(vs).as_dict() for g, vs in sorted(groups.items())}
            for m, groups in sorted(by.items())
        },
    }
    if frame_sizes:
        weighted: dict[str, float | None] = {}
        for frame in sorted({k["frame"] for k in key}):
            strata = {
                s: vs for s, vs in by["stratum"].items()
                if any(k["stratum"] == s and k["frame"] == frame for k in key)
            }  # fmt: skip
            total = sum(frame_sizes.get(s, 0) for s, vs in strata.items() if share(vs).n)
            est = sum(
                frame_sizes.get(s, 0) * (share(vs).precision or 0.0)
                for s, vs in strata.items() if share(vs).n
            )  # fmt: skip
            weighted[frame] = est / total if total else None
        out["frame_weighted_precision"] = weighted
    return out


def make_record(
    result: Mapping[str, object],
    *,
    date: str,
    release: str,
    roles: Sequence[str],
    n_items: int,
    reviewers_met: bool,
) -> dict[str, object]:
    """The `expert_audit` record of the consensus result (what the product shows). The criterion
    is met only if the consensus and every reviewer meet it (`reviewers_met`)."""
    o = cast(dict[str, object], result["overall"])  # made by score()
    c = cast(dict[str, object], result["criterion"])
    record: dict[str, object] = {
        "schema": RECORD_SCHEMA,
        "date": date,
        "release_audited": release,
        "n_items": n_items,
        "n": o["n"],
        "correct": o["correct"],
        "cannot_judge": o["cannot_judge"],
        "precision": o["precision"],
        "wilson_low": o["wilson_low"],
        "wilson_high": o["wilson_high"],
        "criterion_met": bool(c["met"]) and reviewers_met,
        "reviewer_roles": sorted(set(roles)),
    }
    check_record(record)
    return record


RECORD_KEYS: Final = frozenset(
    {
        "schema", "date", "release_audited", "n_items", "n", "correct", "cannot_judge",
        "precision", "wilson_low", "wilson_high", "criterion_met", "reviewer_roles",
    }
)  # fmt: skip


def check_record(record: Mapping[str, object]) -> None:
    """Fail loudly unless the record is exactly the documented shape (no other field, so no name
    can enter it), its counts agree and its numbers recompute."""
    if frozenset(record) != RECORD_KEYS:
        raise ValueError(f"expert_audit: fields must be exactly {sorted(RECORD_KEYS)}")
    if record["schema"] != RECORD_SCHEMA:
        raise ValueError("expert_audit: unknown schema")
    date = record["date"]
    if not isinstance(date, str) or not _DATE.match(date):
        raise ValueError("expert_audit: date must be YYYY-MM-DD")
    ints = {k: record[k] for k in ("n_items", "n", "correct", "cannot_judge")}
    if not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in ints.values()):
        raise ValueError("expert_audit: counts must be non-negative integers")
    n, correct = int(ints["n"]), int(ints["correct"])  # type: ignore[arg-type]
    if correct > n or n + int(ints["cannot_judge"]) > int(ints["n_items"]) or n == 0:  # type: ignore[arg-type]
        raise ValueError("expert_audit: counts do not add up")
    iv = wilson(correct, n)
    assert iv is not None  # noqa: S101 - n > 0
    for field, want in (("precision", correct / n), ("wilson_low", iv[0]), ("wilson_high", iv[1])):
        got = record[field]
        if not isinstance(got, (int, float)) or abs(float(got) - want) > 5e-4:
            raise ValueError(f"expert_audit: {field} does not match the counts")
    met = record["criterion_met"]
    if not isinstance(met, bool) or (met and not criterion_met(Share(correct, n - correct, 0, 0))):
        raise ValueError("expert_audit: criterion_met does not match the counts")
    roles = record["reviewer_roles"]
    if not isinstance(roles, list) or not roles or not set(roles) <= ROLES:  # type: ignore[arg-type]
        raise ValueError(
            f"expert_audit: reviewer_roles must be a non-empty list of {sorted(ROLES)}"
        )
    release = record["release_audited"]
    if not isinstance(release, str) or not release:
        raise ValueError("expert_audit: release_audited is required")
