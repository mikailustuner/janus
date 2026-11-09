"""Builders of CDS Hooks requests and FHIR resources for the cds-hooks tests."""

from __future__ import annotations

from typing import Any

from janus.cds.mapping import ATC, NDC, RXNORM

PATIENT = "pat-1"


def coding(system: str, code: str) -> dict[str, str]:
    return {"system": system, "code": code}


def med_request(
    rid: str,
    codings: list[dict[str, str]],
    status: str = "active",
    patient: str | None = PATIENT,
) -> dict[str, Any]:
    r: dict[str, Any] = {
        "resourceType": "MedicationRequest",
        "id": rid,
        "status": status,
        "intent": "order",
        "medicationCodeableConcept": {"coding": codings, "text": "free text"},
        "authoredOn": "2026-10-01",
    }
    if patient is not None:
        r["subject"] = {"reference": f"Patient/{patient}"}
    return r


def med_statement(
    rid: str, codings: list[dict[str, str]], status: str = "active"
) -> dict[str, Any]:
    return {
        "resourceType": "MedicationStatement",
        "id": rid,
        "status": status,
        "medicationCodeableConcept": {"coding": codings},
        "subject": {"reference": f"Patient/{PATIENT}"},
        "effectiveDateTime": "2020-01-01",
    }


def bundle(resources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": r} for r in resources],
    }


def request(
    hook: str,
    drafts: list[dict[str, Any]],
    active: list[dict[str, Any]] | None = None,
    statements: list[dict[str, Any]] | None = None,
    selections: list[str] | None = None,
    prefetch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "userId": "Practitioner/example",
        "patientId": PATIENT,
        "draftOrders": bundle(drafts),
    }
    if hook == "order-select":
        context["selections"] = (
            selections
            if selections is not None
            else [f"MedicationRequest/{d['id']}" for d in drafts]
        )
    body: dict[str, Any] = {
        "hook": hook,
        "hookInstance": "d1577c69-dfbe-44ad-ba6d-3e05e953b2ea",
        "context": context,
    }
    if prefetch is not None:
        body["prefetch"] = prefetch
    else:
        body["prefetch"] = {
            "medicationRequests": bundle(active or []),
            "medicationStatements": bundle(statements or []),
        }
    return body


__all__ = ["ATC", "NDC", "PATIENT", "RXNORM"]
