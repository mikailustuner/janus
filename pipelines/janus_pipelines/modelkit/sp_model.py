"""Special populations from US labels (spec model-kit, milestone M4, design DP-M26): what a reader returns.

One candidate is one numeric statement of a label: the exposure (AUC or Cmax) of a special population as a ratio to the
reference population, with the population class and grade, the reference population if the sentence names one, and
the quote. Two readers (`sp_a`, pattern based on sentences; `sp_b`, structure first, then clauses and token windows)
read the same label independently and share only this module (the result type and the vocabulary). Pure data.
Research use only. Not for clinical decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

POP_CLASSES: Final = ("geriatric", "renal", "hepatic")
MEASURES: Final = ("auc", "cmax")
# One vocabulary for the population grade. "" = the statement names none.
GRADES: Final = (
    "",
    "mild",
    "moderate",
    "severe",
    "esrd",
    "dialysis",
    "cp_a",
    "cp_b",
    "cp_c",
    "age65",
    "age75",
    "age80",
    "pooled",  # several grades together ("mild and moderate"): one statement for all of them
)
# Fields of the openFDA label that can carry a statement (US sections 8.5, 8.6, 8.7 and 12.3), in the order read.
SECTION_FIELDS: Final = (
    "geriatric_use",
    "use_in_specific_populations",
    "pharmacokinetics",
    "clinical_pharmacology",
)
TABLE_FIELDS: Final = (
    "pharmacokinetics_table",
    "clinical_pharmacology_table",
    "use_in_specific_populations_table",
    "geriatric_use_table",
)
RATIO_MIN: Final = 0.0
RATIO_MAX: Final = 50.0
# Context that makes a statement not a plain "population versus reference" statement of the parent drug.
FLAGS: Final = (
    "metabolite",
    "enantiomer",
    "unbound",
    "pediatric",
    "interaction",
    "animal",
    "pregnancy",
    "dose_change",
)


@dataclass(frozen=True)
class SpLabel:
    """One label as the readers get it: the text of the sections read, by field name."""

    set_id: str
    version: str
    effective_date: str
    drug_key: str
    sections: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: dict[str, tuple[str, ...]]()
    )
    tables: dict[str, tuple[str, ...]] = field(default_factory=lambda: dict[str, tuple[str, ...]]())


@dataclass(frozen=True)
class SpCandidate:
    reader: str  # "a" or "b"
    drug_key: str
    set_id: str
    version: str
    section: str  # field name the statement was read in
    pop_class: str
    grade: str
    measure: str
    ratio: float  # exposure of the population / exposure of the reference population
    ratio_text: str  # how the label states it ("30 % higher", "2-fold increase")
    definition: str  # the text of the population definition as written ("CLcr 30 to 50 mL/min", "Child-Pugh B")
    reference: str  # the reference population if the sentence names one, else ""
    quote: str  # the sentence (or the table row with its header)
    flags: tuple[str, ...] = ()
    from_table: bool = False

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.set_id, self.pop_class, self.measure)


@dataclass
class SpStats:
    """Counts a reader keeps while reading; reported, never used to decide anything."""

    counts: dict[str, int] = field(default_factory=lambda: dict[str, int]())

    def add(self, what: str, n: int = 1) -> None:
        self.counts[what] = self.counts.get(what, 0) + n
