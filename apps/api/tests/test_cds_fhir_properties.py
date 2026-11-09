"""CDS Hooks request model and extraction: P7 and examples (cds-hooks task 1). Pure."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from janus.cds import fhir
from tests.cds_strategies import (
    ATC,
    PATIENT,
    RXNORM,
    bundle,
    coding,
    med_request,
    med_statement,
    request,
)

STATUSES = ["draft", "active", "on-hold", "unknown", "cancelled", "completed", "stopped",
            "entered-in-error", "revoked", "intended", "not-taken"]  # fmt: skip


def parse(body: dict[str, Any]) -> fhir.Extracted:
    req = fhir.HookRequest.model_validate(body)
    prefetch: dict[str, Any] = body.get("prefetch") or {}
    return fhir.extract(req, frozenset(prefetch))


def rx(code: str = "17767") -> list[dict[str, str]]:
    return [coding(RXNORM, code)]


def test_order_select_origins_and_focus() -> None:
    body = request(
        "order-select",
        [med_request("a", rx("1"), "draft"), med_request("b", rx("2"), "draft")],
        active=[med_request("c", rx("3"))],
        statements=[med_statement("d", rx("4"))],
        selections=["MedicationRequest/a", "NutritionOrder/x"],
    )
    ex = parse(body)
    assert [m.origin for m in ex.medicines] == ["selected", "draft", "active", "statement"]
    assert ex.focus == frozenset({"selected"})
    assert ex.medicines[0].codings == (fhir.Coding(RXNORM, "1"),)


def test_order_sign_focus_is_every_draft() -> None:
    ex = parse(request("order-sign", [med_request("a", rx(), "draft")]))
    assert [m.origin for m in ex.medicines] == ["draft"]
    assert ex.focus == frozenset({"draft"})


@given(
    st.lists(
        st.tuples(st.sampled_from(STATUSES), st.sampled_from([PATIENT, "other", None])),
        max_size=12,
    ),
    st.sampled_from(["order-select", "order-sign"]),
)
def test_p7_other_patient_and_excluded_status_never_count(
    specs: list[tuple[str, str | None]], hook: str
) -> None:
    """P7: a resource for another patient or with an excluded status gives no medicine."""
    drafts = [med_request(f"d{i}", rx(), s, p) for i, (s, p) in enumerate(specs)]
    active = [med_request(f"a{i}", rx(), s, p) for i, (s, p) in enumerate(specs)]
    ex = parse(request(hook, drafts, active=active))
    want_drafts = sum(1 for s, p in specs if s in fhir.DRAFT_STATUSES and p != "other")
    want_active = sum(1 for s, p in specs if s in fhir.PREFETCH_STATUSES and p != "other")
    assert sum(1 for m in ex.medicines if m.origin in ("selected", "draft")) == want_drafts
    assert sum(1 for m in ex.medicines if m.origin == "active") == want_active
    assert ex.ignored == 2 * len(specs) - want_drafts - want_active


def test_absolute_subject_reference_is_the_same_patient() -> None:
    r = med_request("a", rx(), "draft")
    r["subject"] = {"reference": f"https://fhir.example.org/r4/Patient/{PATIENT}"}
    assert len(parse(request("order-sign", [r])).medicines) == 1


def test_medication_reference_contained_and_in_bundle() -> None:
    contained = med_request("a", [], "draft")
    del contained["medicationCodeableConcept"]
    contained["medicationReference"] = {"reference": "#m1"}
    contained["contained"] = [
        {"resourceType": "Medication", "id": "m1", "code": {"coding": [coding(ATC, "C08CA01")]}}
    ]
    referenced = med_request("c", [])
    del referenced["medicationCodeableConcept"]
    referenced["medicationReference"] = {"reference": "Medication/m2"}
    medication = {"resourceType": "Medication", "id": "m2", "code": {"coding": rx("5")}}
    body = request("order-sign", [contained], active=[referenced, medication])
    ex = parse(body)
    assert [m.codings for m in ex.medicines] == [
        (fhir.Coding(ATC, "C08CA01"),),
        (fhir.Coding(RXNORM, "5"),),
    ]


def test_prefetch_absent_null_and_operation_outcome() -> None:
    drafts = [med_request("a", rx(), "draft")]
    body = request("order-sign", drafts, prefetch={})
    with pytest.raises(fhir.PrefetchMissingError):
        parse(body)
    body = request("order-sign", drafts, prefetch={"medicationRequests": None})
    ex = parse(body)
    assert ex.not_provided == ("medicationStatements",)
    outcome: dict[str, Any] = {"resourceType": "OperationOutcome", "issue": []}
    body = request(
        "order-sign",
        drafts,
        prefetch={"medicationRequests": outcome, "medicationStatements": None},
    )
    assert parse(body).not_provided == ("medicationRequests",)


def test_dates_are_not_read() -> None:
    """DP4: the extracted medicine carries origin and codings only."""
    ex = parse(request("order-sign", [med_request("a", rx(), "draft")]))
    assert set(vars(ex.medicines[0])) == {"origin", "codings"}


def _extra(b: dict[str, Any]) -> None:
    b["extra"] = 1


def _context_extra(b: dict[str, Any]) -> None:
    b["context"]["extra"] = 1


def _hook(b: dict[str, Any]) -> None:
    b["hook"] = "patient-view"


def _prefetch_extra(b: dict[str, Any]) -> None:
    b["prefetch"]["patient"] = {}


def _no_instance(b: dict[str, Any]) -> None:
    del b["hookInstance"]


Mutation = Callable[[dict[str, Any]], None]


@pytest.mark.parametrize(
    ("mutate", "field"),
    [
        (_extra, "extra"),
        (_context_extra, "context.extra"),
        (_hook, "hook"),
        (_prefetch_extra, "prefetch.patient"),
        (_no_instance, "hookInstance"),
    ],
)
def test_strict_fields_are_rejected_by_name(mutate: Mutation, field: str) -> None:
    body = request("order-sign", [med_request("a", rx(), "draft")])
    mutate(body)
    with pytest.raises(ValidationError) as exc:
        fhir.HookRequest.model_validate(body)
    assert field in {".".join(str(p) for p in e["loc"]) for e in exc.value.errors()}


def test_order_select_needs_selections() -> None:
    body = request("order-select", [med_request("a", rx(), "draft")])
    del body["context"]["selections"]
    with pytest.raises(fhir.FieldError) as exc:
        parse(body)
    assert exc.value.fields == ["context.selections"]


def test_limits_name_fields() -> None:
    many = [med_request(f"a{i}", rx(), "draft") for i in range(fhir.MAX_ENTRIES + 1)]
    with pytest.raises(fhir.FieldError) as exc:
        parse(request("order-sign", many))
    assert exc.value.fields == ["context.draftOrders.entry"]
    codings = [coding(RXNORM, str(i + 1)) for i in range(fhir.MAX_CODINGS + 1)]
    with pytest.raises(fhir.FieldError) as exc:
        parse(request("order-sign", [med_request("a", codings, "draft")]))
    assert exc.value.fields == [
        "context.draftOrders.entry.0.resource.medicationCodeableConcept.coding"
    ]
    body = request("order-sign", [])
    body["context"]["draftOrders"] = bundle([])
    body["context"]["draftOrders"]["resourceType"] = "List"
    with pytest.raises(fhir.FieldError):
        parse(body)
