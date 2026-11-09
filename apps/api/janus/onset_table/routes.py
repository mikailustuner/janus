"""Route groups of FAERS drug lines for the onset table (faers-onset-table DP-O3). Pure.

FAERS `DRUG.route` is free text as reported ("Topical", "Oral use", "Intravenous drip",
"Ophthalmic", ...). The onset table counts a class member's suspect line only when its route
group is allowed for the class: by default systemic or unknown routes. Local routes (skin, eye,
ear, nose, airways, vagina and uterus, mouth and teeth, joints and lesions, bladder) would bring
in uses the PIPC row does not ask about (pharmacologist review O1-O6). Exposure that is not the
patient's own (transplacental, through breast milk or semen) is never counted.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Final


class RouteGroup(StrEnum):
    systemic_or_unknown = "systemic_or_unknown"
    eye = "eye"
    rectal = "rectal"
    nasal_inhaled = "nasal_inhaled"
    joint_lesion = "joint_lesion"
    local = "local"
    not_patient = "not_patient"


ENTERAL_TUBES: Final = (
    "nasogastric",
    "nasojejunal",
    "nasoduodenal",
    "nasal j",
    "nasal tube",
    "ng-tube",
    "ng tube",
)
SYSTEMIC_LOOKALIKES: Final = ("transdermal", "transmucosal", "subdermal", "subcut", "sub-q", "subq")
NOT_PATIENT: Final = ("transplacental", "transmammary", "intraplacent", "semen", "amnio")
EYE: Final = (
    "ophthalm",
    "opthalm",
    "ocular",
    "intravitreal",
    "conjunctival",
    "sunconjunctival",
    "intracameral",
    "retrobulbar",
    "tenon",
    "subretinal",
    "suprachoroidal",
    "intracorneal",
)
LOCAL: Final = (
    "topical",
    "cutaneous",
    "dermal",  # "transdermal", "subdermal" and "subcutaneous" are systemic: checked first
    "otic",
    "auricular",
    "ear canal",
    "vaginal",
    "uterine",
    "cervical",
    "dental",
    "gingival",
    "periodontal",
    "alveolar",
    "oropharyn",
    "oropharing",
    "pharynx",
    "intravesical",
    "urethral",
    "cavernos",
    "occlusive dressing",
    "iontophoresis",
    "infiltration",
    "local",
    "on hands",
    "endosinusial",
)
NASAL_INHALED: Final = ("nasal", "intranasal", "inhal", "respiratory", "nebuli")
JOINT_LESION: Final = ("articular", "intrasynovial", "intrabursal", "lesional")
# Class id -> extra route groups counted for it (besides systemic_or_unknown).
EXTRA_GROUPS: Final[Mapping[str, frozenset[RouteGroup]]] = {
    # PIPC row 3 names ophthalmic beta-blockers (Vander Zanden 2001; cascade-engine DP8).
    "beta_blocker_index_eye": frozenset({RouteGroup.eye}),
    # A rectal laxative (suppository, enema) is still the laxative the row asks about.
    "laxative": frozenset({RouteGroup.rectal}),
    # Systemic exposure by nose or airway: butorphanol and fentanyl nasal, inhaled levodopa,
    # inhaled loxapine, diazepam nasal (pharmacologist second pass P3).
    "opioid": frozenset({RouteGroup.nasal_inhaled}),
    "dopaminergic_antiparkinsonian": frozenset({RouteGroup.nasal_inhaled}),
    "antipsychotic": frozenset({RouteGroup.nasal_inhaled}),
    "benzodiazepine": frozenset({RouteGroup.nasal_inhaled}),
    # Joint and lesion injections give systemic exposure; the H02AB class note includes them
    # (pharmacologist second pass P2).
    "corticosteroid_systemic": frozenset({RouteGroup.joint_lesion}),
}


# Classes whose form-extension patterns (cascade_classes.csv) count in the onset table: the
# eye-drop extension of PIPC row 3, so that S01ED-only keys (levobunolol, metipranolol) count
# with timolol and the others (pharmacologist review O5).
FORM_EXTENSIONS_ON: Final = frozenset({"beta_blocker_index_eye"})


def route_group(route: str | None) -> RouteGroup:
    text = " ".join((route or "").casefold().split())
    if not text:
        return RouteGroup.systemic_or_unknown
    if any(t in text for t in NOT_PATIENT):
        return RouteGroup.not_patient
    if any(t in text for t in ENTERAL_TUBES) or "ng" in re.split(r"[^a-z]+", text):
        return RouteGroup.systemic_or_unknown
    if any(t in text for t in EYE):
        return RouteGroup.eye
    if "rect" in text:
        return RouteGroup.rectal
    if any(t in text for t in SYSTEMIC_LOOKALIKES):
        return RouteGroup.systemic_or_unknown
    if any(t in text for t in NASAL_INHALED):
        return RouteGroup.nasal_inhaled
    if any(t in text for t in JOINT_LESION):
        return RouteGroup.joint_lesion
    if any(t in text for t in LOCAL):
        return RouteGroup.local
    return RouteGroup.systemic_or_unknown


def allowed_groups(class_id: str) -> frozenset[RouteGroup]:
    return frozenset({RouteGroup.systemic_or_unknown}) | EXTRA_GROUPS.get(class_id, frozenset())
