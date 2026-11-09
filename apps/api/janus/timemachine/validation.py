"""PBPK credibility rule (design §8.2, DP-T10). Pure.

The rule is fixed before the numbers are seen: a drug is `credible` when the predicted Cmax
*and* AUC are both within `FOLD_LIMIT` of the published observed value, `borderline` when both
are within `FOLD_BORDERLINE`, and `failed` otherwise. A drug that is not `credible` may not
carry an exposure-versus-potency statement; its card says the model is not validated for it
(Req 5.4).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

FOLD_LIMIT = 2.0
FOLD_BORDERLINE = 3.0


class Credibility(StrEnum):
    credible = "credible"
    borderline = "borderline"
    failed = "failed"


def fold_error(predicted: float, observed: float) -> float:
    """Ratio >= 1 between predicted and observed, whichever way round."""
    if predicted <= 0 or observed <= 0:
        raise ValueError("predicted and observed must be positive")
    return max(predicted / observed, observed / predicted)


@dataclass(frozen=True)
class DrugValidation:
    drug: str
    reference: str
    observed_cmax: float
    observed_auc: float
    predicted_cmax: float
    predicted_auc: float
    note: str = ""

    @property
    def cmax_fold(self) -> float:
        return fold_error(self.predicted_cmax, self.observed_cmax)

    @property
    def auc_fold(self) -> float:
        return fold_error(self.predicted_auc, self.observed_auc)

    @property
    def credibility(self) -> Credibility:
        worst = max(self.cmax_fold, self.auc_fold)
        if worst <= FOLD_LIMIT:
            return Credibility.credible
        if worst <= FOLD_BORDERLINE:
            return Credibility.borderline
        return Credibility.failed

    @property
    def may_carry_exposure_statement(self) -> bool:
        return self.credibility is Credibility.credible


def summary(rows: list[DrugValidation]) -> dict[str, int]:
    out = dict.fromkeys([c.value for c in Credibility], 0)
    for r in rows:
        out[r.credibility.value] += 1
    return out
