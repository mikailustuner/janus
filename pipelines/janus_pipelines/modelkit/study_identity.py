"""Cross-source study identity, the leakage guard of the held-out rule (spec model-kit, milestone
M5, pre-registered).

A review study, a registry record and an article can describe the same study. Two studies of one
drug (any source, different study ids) are the same study if (1) they share an NCT number, (2) they
share a sponsor study code, (3) they duplicate a result numerically (same parameter other than Tmax,
both doses stated and equal within 1 %, values within 1 %, numbers of subjects equal or at least one
missing), or (4) one is the document-level study of a review PDF and the other a coded study of the
same PDF (both carry the key `DOC:<pdf>`). Links are closed transitively. The group of a study is
the first study id of its group in sorted order. Pure functions. Research use only. Not for clinical
decisions."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Final

TOLERANCE: Final = 0.01
_NO_DUPLICATE_RULE: Final = frozenset({"tmax"})
StudyKey = tuple[str, str, str]  # (drug_key, source_id, study_id)


def norm_code(text: str) -> str | None:
    """A sponsor study code as a key: upper case letters and digits, at least 5 characters, at least
    2 digits."""
    code = re.sub(r"[^A-Z0-9]", "", text.upper())
    if len(code) < 5 or sum(ch.isdigit() for ch in code) < 2:
        return None
    if re.fullmatch(r"NCT\d{8}", code):
        return None  # an NCT number is its own key
    return code


def keys_text(nct: Iterable[str] = (), codes: Iterable[str] = (), docs: Iterable[str] = ()) -> str:
    """The `study_keys` cell: NCT:..., CODE:..., DOC:... joined by '|', sorted."""
    out = {f"NCT:{n.upper()}" for n in nct if re.fullmatch(r"NCT\d{8}", n.upper())}
    out |= {f"CODE:{c}" for c in (norm_code(x) for x in codes) if c}
    out |= {f"DOC:{d}" for d in docs if d}
    return "|".join(sorted(out))


class _Union:
    def __init__(self) -> None:
        self.parent: dict[StudyKey, StudyKey] = {}

    def find(self, x: StudyKey) -> StudyKey:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def join(self, a: StudyKey, b: StudyKey) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            if rb < ra:
                ra, rb = rb, ra
            self.parent[rb] = ra


def _close(a: float, b: float) -> bool:
    return a > 0 and b > 0 and abs(a - b) <= TOLERANCE * max(a, b)


def groups(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[StudyKey, str], dict[str, int]]:
    """(group id of every study, counts of links by rule). Rows need drug_key, source_id, study_id,
    study_keys, parameter, value_si, dose, n_subjects, analyte_class, origin."""
    u = _Union()
    by_key: dict[tuple[str, str], set[StudyKey]] = defaultdict(set)
    studies: set[StudyKey] = set()
    for r in rows:
        s: StudyKey = (str(r["drug_key"]), str(r["source_id"]), str(r["study_id"]))
        studies.add(s)
        u.find(s)
        for k in str(r.get("study_keys") or "").split("|"):
            if k:
                by_key[(s[0], k)].add(s)
        if r["source_id"] == "clinicaltrials_gov" and re.fullmatch(r"NCT\d{8}", str(r["study_id"])):
            by_key[(s[0], f"NCT:{r['study_id']}")].add(s)
    counts: dict[str, int] = defaultdict(int)
    for (_, k), members in sorted(by_key.items()):
        ms = sorted(members)
        for m in ms[1:]:
            if u.find(m) != u.find(ms[0]):
                counts[k.split(":", 1)[0].lower()] += 1
            u.join(ms[0], m)
    # numerical duplicates
    cells: dict[tuple[str, str], list[tuple[float, float, int | None, StudyKey]]] = defaultdict(
        list
    )
    for r in rows:
        if (
            r["parameter"] in _NO_DUPLICATE_RULE
            or r.get("origin") == "derived"
            or r["dose"] is None
        ):
            continue
        if r.get("analyte_class") != "parent":
            continue
        s = (str(r["drug_key"]), str(r["source_id"]), str(r["study_id"]))
        cells[(s[0], str(r["parameter"]))].append(
            (
                float(r["value_si"]),
                float(r["dose"]),
                None if r["n_subjects"] is None else int(r["n_subjects"]),
                s,
            )
        )
    for vals in cells.values():
        vals.sort(key=lambda x: (x[0], x[1], x[3]))
        for i, (v, d, n, s) in enumerate(vals):
            for v2, d2, n2, s2 in vals[i + 1 :]:
                if v2 > v * (1 + TOLERANCE) + 1e-12:
                    break
                if s2 == s or not _close(v, v2) or not _close(d, d2):
                    continue
                if n is not None and n2 is not None and n != n2:
                    continue
                if u.find(s) != u.find(s2):
                    counts["numeric_duplicate"] += 1
                u.join(s, s2)
    out = {s: f"{u.find(s)[1]}:{u.find(s)[2]}" for s in studies}
    return out, dict(counts)
