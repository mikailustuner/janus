"""What a reader returns: one candidate value with its locator, quote, analyte and context."""

from __future__ import annotations

from dataclasses import dataclass, field

from janus_pipelines.modelkit.confirm import Context, Reading
from janus_pipelines.modelkit.resolver import AnalyteClass
from janus_pipelines.modelkit.units import Stat

PARAMETERS = (
    "cmax", "auc_inf", "auc_last", "auc_tau", "tmax", "t_half", "cl", "cl_f", "vss", "vd", "v_f", "f",
)  # fmt: skip
DOSE_PARAMS = frozenset({"cmax", "auc_inf", "auc_last", "auc_tau"})


@dataclass(frozen=True)
class Candidate:
    drug_key: str
    source_id: str  # clinicaltrials_gov, dailymed_spl
    study_id: str  # NCT id or label set id
    arm_id: str  # group id or table column; "" when none
    locator: str  # source locator, identical for both readers of the same cell or measurement
    parameter: str  # as stated; a per-kg unit moves cl and v to their per-kg parameter
    value: float
    unit: str  # as stated in the source
    stat: Stat
    analyte: AnalyteClass
    context: Context
    dose_mg: float | None
    n_subjects: int | None
    quote: str
    source_version: str
    interval_h: float | None = None
    notes: tuple[str, ...] = field(default=())

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.drug_key, self.locator, self.parameter)

    def reading(self) -> Reading:
        return Reading(
            self.value, self.unit, self.analyte, self.context, self.dose_mg, self.stat.center_type
        )


@dataclass
class ReaderStats:
    """Counts a reader keeps while reading; reported, never used to decide anything."""

    seen: int = 0
    skipped: dict[str, int] = field(default_factory=lambda: dict[str, int]())

    def skip(self, why: str) -> None:
        self.skipped[why] = self.skipped.get(why, 0) + 1
