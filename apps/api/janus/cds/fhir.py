"""CDS Hooks request model and medicine extraction (cds-hooks design §3, §4). Pure.

The CDS Hooks fields are strict (an unknown top-level or context field is rejected); the FHIR
resources inside them are read leniently, because FHIR resources carry many fields Janus does not
need. Only the fields read here are type-checked. Errors name field paths, never values. Start
dates are never read (design DP4).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, StrictStr, StringConstraints

Hook = Literal["order-select", "order-sign"]
Origin = Literal["selected", "draft", "active", "statement"]
PrefetchKey = Literal["medicationRequests", "medicationStatements"]

MAX_ENTRIES: Final = 200
MAX_CODINGS: Final = 20
DRAFT_STATUSES: Final = frozenset({"draft", "active", "on-hold", "unknown"})
PREFETCH_STATUSES: Final = frozenset({"active", "on-hold"})
PREFETCH_KEYS: Final[tuple[PrefetchKey, ...]] = ("medicationRequests", "medicationStatements")
PREFETCH_TYPES: Final[Mapping[PrefetchKey, str]] = {
    "medicationRequests": "MedicationRequest",
    "medicationStatements": "MedicationStatement",
}

Id = Annotated[StrictStr, StringConstraints(min_length=1, max_length=128)]
Selection = Annotated[StrictStr, StringConstraints(min_length=1, max_length=256)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Context(_Strict):
    user_id: Id = Field(alias="userId")
    patient_id: Id = Field(alias="patientId")
    encounter_id: Id | None = Field(default=None, alias="encounterId")
    selections: Annotated[list[Selection], Field(max_length=MAX_ENTRIES)] | None = None
    draft_orders: dict[str, Any] = Field(alias="draftOrders")


class Prefetch(_Strict):
    medication_requests: dict[str, Any] | None = Field(default=None, alias="medicationRequests")
    medication_statements: dict[str, Any] | None = Field(default=None, alias="medicationStatements")


class HookRequest(_Strict):
    hook: Hook
    hook_instance: Id = Field(alias="hookInstance")
    # Accepted because the specification defines them; never read and never used (Req 2.6).
    fhir_server: StrictStr | None = Field(default=None, alias="fhirServer")
    fhir_authorization: dict[str, Any] | None = Field(default=None, alias="fhirAuthorization")
    context: Context
    prefetch: Prefetch | None = None
    extension: dict[str, Any] | None = None


class FieldError(ValueError):
    """A structural problem; carries field paths only."""

    def __init__(self, fields: Sequence[str]) -> None:
        super().__init__("invalid request")
        self.fields = sorted(set(fields))


class PrefetchMissingError(ValueError):
    """Neither prefetch key was sent (CDS Hooks: 412 Precondition Failed)."""


@dataclass(frozen=True)
class Coding:
    system: str
    code: str


@dataclass(frozen=True)
class Medicine:
    origin: Origin
    codings: tuple[Coding, ...]


@dataclass(frozen=True)
class Extracted:
    medicines: tuple[Medicine, ...]
    focus: frozenset[Origin]
    not_provided: tuple[
        PrefetchKey, ...
    ]  # prefetch keys absent, or answered by an OperationOutcome
    ignored: int  # resources left out: other patient or excluded status


def focus_of(hook: Hook) -> frozenset[Origin]:
    return frozenset({"selected"}) if hook == "order-select" else frozenset({"draft"})


def _resources(bundle: Mapping[str, Any], path: str) -> list[dict[str, Any]]:
    if bundle.get("resourceType") != "Bundle":
        raise FieldError([f"{path}.resourceType"])
    entry = bundle.get("entry", [])
    if not isinstance(entry, list) or len(entry) > MAX_ENTRIES:  # pyright: ignore[reportUnknownArgumentType]
        raise FieldError([f"{path}.entry"])
    out: list[dict[str, Any]] = []
    for i, e in enumerate(entry):  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        resource = e.get("resource") if isinstance(e, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not isinstance(resource, dict) or not isinstance(resource.get("resourceType"), str):  # pyright: ignore[reportUnknownMemberType]
            raise FieldError([f"{path}.entry.{i}.resource"])
        out.append(resource)  # pyright: ignore[reportUnknownArgumentType]
    return out


def _reference(value: Any) -> str | None:
    if isinstance(value, dict):
        ref = value.get("reference")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(ref, str):
            return ref
    return None


def _for_patient(resource: Mapping[str, Any], patient_id: str) -> bool:
    """False when the resource names another patient; a resource without a subject is kept."""
    ref = _reference(resource.get("subject")) or _reference(resource.get("patient"))
    if ref is None:
        return True
    want = f"Patient/{patient_id}"
    return ref == want or ref.endswith("/" + want)


def _key(resource: Mapping[str, Any]) -> str | None:
    rid = resource.get("id")
    return f"{resource['resourceType']}/{rid}" if isinstance(rid, str) else None


def _concept_codings(concept: Any, path: str) -> tuple[Coding, ...]:
    if not isinstance(concept, dict):
        return ()
    coding = concept.get("coding")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if not isinstance(coding, list):
        return ()
    if len(coding) > MAX_CODINGS:  # pyright: ignore[reportUnknownArgumentType]
        raise FieldError([f"{path}.coding"])
    out: list[Coding] = []
    for c in coding:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(c, dict):
            continue
        system, code = c.get("system"), c.get("code")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(system, str) and isinstance(code, str):
            out.append(Coding(system.strip(), code.strip()))
    return tuple(out)


def codings_of(
    resource: Mapping[str, Any], medications: Mapping[str, Mapping[str, Any]], path: str
) -> tuple[Coding, ...]:
    """Codings of `medicationCodeableConcept`, else of the referenced `Medication.code`."""
    concept = resource.get("medicationCodeableConcept")
    if concept is not None:
        return _concept_codings(concept, f"{path}.medicationCodeableConcept")
    ref = _reference(resource.get("medicationReference"))
    if ref is None:
        return ()
    med: Any = None
    if ref.startswith("#"):
        contained = resource.get("contained")
        if isinstance(contained, list):
            for c in contained:  # pyright: ignore[reportUnknownVariableType]
                if (
                    isinstance(c, dict)
                    and c.get("resourceType") == "Medication"  # pyright: ignore[reportUnknownMemberType]
                    and c.get("id") == ref[1:]  # pyright: ignore[reportUnknownMemberType]
                ):
                    med = cast(dict[str, Any], c)
                    break
    else:
        med = medications.get(ref)
    code = med.get("code") if isinstance(med, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return _concept_codings(code, f"{path}.medicationReference")


def _medications(resources: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for r in resources:
        key = _key(r)
        if r.get("resourceType") == "Medication" and key is not None:
            out[key] = r
    return out


def extract(request: HookRequest, sent_prefetch: frozenset[str]) -> Extracted:
    """Medicines of the draft orders and the prefetch, with their origin.

    `sent_prefetch` names the prefetch keys present in the body (a key sent as `null` means "no
    data"; an absent key means "not provided"). Raises `PrefetchMissingError` when neither key was
    sent, `FieldError` on a structural problem.
    """
    ctx = request.context
    if request.hook == "order-select" and ctx.selections is None:
        raise FieldError(["context.selections"])
    if not sent_prefetch & set(PREFETCH_KEYS):
        raise PrefetchMissingError
    patient = ctx.patient_id
    selected = set(ctx.selections or [])
    medicines: list[Medicine] = []
    ignored = 0

    drafts = _resources(ctx.draft_orders, "context.draftOrders")
    draft_meds = _medications(drafts)
    for i, r in enumerate(drafts):
        if r["resourceType"] != "MedicationRequest":
            continue
        if not _for_patient(r, patient) or r.get("status") not in DRAFT_STATUSES:
            ignored += 1
            continue
        key = _key(r)
        origin: Origin = (
            "selected" if request.hook == "order-select" and key in selected else "draft"
        )
        path = f"context.draftOrders.entry.{i}.resource"
        medicines.append(Medicine(origin, codings_of(r, draft_meds, path)))

    not_provided: list[PrefetchKey] = []
    values: dict[PrefetchKey, dict[str, Any] | None] = {}
    if request.prefetch is not None:
        values = {
            "medicationRequests": request.prefetch.medication_requests,
            "medicationStatements": request.prefetch.medication_statements,
        }
    for name in PREFETCH_KEYS:
        if name not in sent_prefetch:
            not_provided.append(name)
            continue
        value = values.get(name)
        if value is None:
            continue  # sent as null: the client has no data for this template
        path = f"prefetch.{name}"
        kind = value.get("resourceType")
        if kind == "OperationOutcome":
            not_provided.append(name)
            continue
        resources = _resources(value, path) if kind == "Bundle" else [value]
        if kind != "Bundle" and kind != PREFETCH_TYPES[name]:
            raise FieldError([f"{path}.resourceType"])
        meds = _medications(resources)
        for j, r in enumerate(resources):
            if r["resourceType"] == "OperationOutcome":
                not_provided.append(name)
                continue
            if r["resourceType"] != PREFETCH_TYPES[name]:
                continue
            if not _for_patient(r, patient) or r.get("status") not in PREFETCH_STATUSES:
                ignored += 1
                continue
            entry_path = f"{path}.entry.{j}.resource" if kind == "Bundle" else path
            origin_p: Origin = "active" if name == "medicationRequests" else "statement"
            medicines.append(Medicine(origin_p, codings_of(r, meds, entry_path)))
    return Extracted(
        tuple(medicines),
        focus_of(request.hook),
        tuple(dict.fromkeys(not_provided)),
        ignored,
    )
