"""Dose-form groups (medication-passport design §5.2, DP7, owner decision 6 of 2026-11-08). Pure.

`data/dose_form_groups.csv` (Janus, Apache-2.0) maps a source's published dose form, exactly as
published, to one coarse Janus group or to nothing. openFDA and the BDPM publish some forms that do
not name the route (`SOLUTION`, `GEL`, `solution`, `crème`), so a row may be limited to one
published route set: `route` is `*` (any route set), an empty string (no route published) or the
product's routes sorted and joined with `|` exactly as published. A product takes the row of its own
route set first, then the `*` row; anything else, or an empty group, is unknown.

`other` collects real forms that fit none of the groups (sublingual and buccal forms, dental
products, kits); it is shown but never compared, because two products in `other` need not share a
form. Modified-release forms outside the oral solid groups have no group of their own and stay
unknown (Req 6.5: never in the same group as an immediate-release form).

The table is drafted by `forms_draft.py` and reviewed row by row. A row's note starts with
`proposed` until the owner accepts it (`accepted`); `FormTable.reviewed` is true only when every row
is accepted, and no user-facing answer may use an unreviewed table (task 4 review stop).
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from janus.resolution.atc import DATA_DIR

FORMS_FILE = DATA_DIR / "dose_form_groups.csv"
HEADER = ["source_id", "published_form", "route", "group", "note"]
SOURCES: frozenset[str] = frozenset({"titck", "openfda_ndc", "eu_fr_bdpm", "eu_es_cima"})
ANY_ROUTE = "*"

GROUPS: tuple[str, ...] = (
    "oral_solid",
    "oral_solid_modified_release",
    "oral_liquid",
    "injection",
    "inhaled",
    "nasal",
    "ophthalmic",
    "otic",
    "cutaneous",
    "transdermal",
    "rectal",
    "vaginal",
    "other",
)
# Countable unit forms: a BDPM strength without its reference quantity is per unit only here (§5.1).
COUNTABLE_GROUPS: frozenset[str] = frozenset({"oral_solid", "oral_solid_modified_release"})
# Shown, never compared (two products in `other` need not share a form).
NOT_COMPARED_GROUPS: frozenset[str] = frozenset({"other"})
STATUSES = ("proposed", "accepted")


class FormTableError(ValueError):
    """The table file is malformed. The message names the row and the defect."""


def route_key(routes: Iterable[str]) -> str:
    """The `route` value of a product's published route set (sorted, distinct, `|`-joined)."""
    return "|".join(sorted(set(routes)))


@dataclass(frozen=True)
class FormTable:
    rows: Mapping[tuple[str, str, str], str | None]
    version: str  # SHA-256 of the file
    reviewed: bool  # every row accepted by the owner

    def group(
        self, source_id: str, published_form: str | None, routes: Iterable[str] = ()
    ) -> str | None:
        """Total: an unknown source, form or route set gives `None`; never raises."""
        if not published_form:
            return None
        exact = (source_id, published_form, route_key(routes))
        if exact in self.rows:
            return self.rows[exact]
        return self.rows.get((source_id, published_form, ANY_ROUTE))


def _valid_route(route: str) -> bool:
    if route in (ANY_ROUTE, ""):
        return True
    parts = route.split("|")
    return all(p.strip() == p and p for p in parts) and parts == sorted(set(parts))


def parse(text: str) -> FormTable:
    """Pure. Refuses a bad header, an unknown source, an empty form, a bad route value, a group
    outside the closed set, a repeated key and a note that does not start with a status."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != HEADER:
        raise FormTableError("dose_form_groups.csv: header is not the expected one")
    rows: dict[tuple[str, str, str], str | None] = {}
    reviewed = True
    for n, r in enumerate(reader, start=2):
        if None in r or any(r[h] is None for h in HEADER):  # pyright: ignore[reportUnnecessaryComparison]
            raise FormTableError(f"dose_form_groups.csv row {n}: wrong number of fields")
        source, form, route, group, note = (r[h] for h in HEADER)
        if source not in SOURCES:
            raise FormTableError(f"dose_form_groups.csv row {n}: unknown source")
        if not form.strip():
            raise FormTableError(f"dose_form_groups.csv row {n}: empty published form")
        if not _valid_route(route):
            raise FormTableError(f"dose_form_groups.csv row {n}: route is not a sorted route set")
        if group and group not in GROUPS:
            raise FormTableError(f"dose_form_groups.csv row {n}: unknown group")
        status = note.split(";", 1)[0].strip()
        if status not in STATUSES:
            raise FormTableError(f"dose_form_groups.csv row {n}: note must start with a status")
        key = (source, form, route)
        if key in rows:
            raise FormTableError(f"dose_form_groups.csv row {n}: repeated key")
        rows[key] = group or None
        reviewed = reviewed and status == "accepted"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return FormTable(rows, digest, reviewed and bool(rows))


def load(path: Path = FORMS_FILE) -> FormTable:
    """Read and validate the table (startup). A defect raises `FormTableError`."""
    return parse(path.read_bytes().decode("utf-8"))  # no newline translation: hash of the file
