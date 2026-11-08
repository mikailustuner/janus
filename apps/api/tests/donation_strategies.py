"""Hypothesis strategies for donation payloads (privacy design §8, P6-P10)."""

from __future__ import annotations

from typing import Any

from hypothesis import strategies as st

from janus.contributions.models import AGE_BANDS
from janus.contributions.vocabulary import load_vocabulary
from janus.settings import EVENT_VOCABULARY

CONSENT_VERSIONS = frozenset({"2026-11-v1", "2026-12-v2"})
EVENTS = load_vocabulary(EVENT_VOCABULARY)
CONTEXT = {"consent_versions": CONSENT_VERSIONS, "events": EVENTS}

qids = st.integers(1, 9_999_999_999).map(lambda n: f"Q{n}")


@st.composite
def valid_payloads(draw: st.DrawFn) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "consent": {"version": draw(st.sampled_from(sorted(CONSENT_VERSIONS))), "explicit": True},
        "age_band": draw(st.sampled_from(AGE_BANDS)),
        "region": draw(st.sampled_from(["TR", "EU", "US"])),
        "ingredients": draw(st.lists(qids, min_size=1, max_size=20, unique=True)),
        "event": draw(st.sampled_from(sorted(EVENTS))),
        "direction": draw(st.sampled_from(["adverse", "benefit"])),
    }
    sex = draw(st.sampled_from(["female", "male", None, "absent"]))
    if sex != "absent":
        payload["sex"] = sex
    return payload


EXTRA_FIELD_NAMES = st.one_of(
    st.sampled_from(
        [
            "date",
            "created_at",
            "email",
            "name",
            "ip",
            "device_id",
            "notes",
            "city",
            "country",
            "postcode",
            "birth_date",
            "onset",
            "demo",
            "id",
            "deletion_token_hash",
            "report_week",
        ]
    ),
    st.text(min_size=1, max_size=12),
)

OUT_OF_DOMAIN: dict[str, list[Any]] = {
    "age_band": [0, 5, 10, 15, 17, 18, 19, 21, 95, 100, -5, "65", 65.0, None, True],
    "sex": ["other", "F", "", 1, "Female"],
    "region": ["DE", "tr", "Europe", "", None, "TR "],
    "ingredients": [
        [],
        ["aspirin"],
        ["Q0"],
        ["q1"],
        ["Q1", "Q1"],
        [f"Q{i}" for i in range(1, 22)],
        "Q1",
        [1],
        ["Q1 "],
    ],
    "event": ["Free text", "", "unknown_event_key", None, 3],
    "direction": ["neutral", "", None, "ADVERSE"],
}


@st.composite
def invalid_payloads(draw: st.DrawFn) -> dict[str, Any]:
    """A valid payload with exactly one defect."""
    payload = draw(valid_payloads())
    kind = draw(
        st.sampled_from(
            [
                "extra",
                "missing",
                "domain",
                "no_consent",
                "consent_false",
                "consent_unknown",
                "consent_extra",
                "demo_true",
            ]
        )
    )
    if kind == "extra":
        name = draw(EXTRA_FIELD_NAMES.filter(lambda n: n not in payload and n != "sex"))
        payload[name] = draw(st.one_of(st.text(max_size=8), st.integers(), st.booleans()))
    elif kind == "missing":
        name = draw(
            st.sampled_from(["consent", "age_band", "region", "ingredients", "event", "direction"])
        )
        del payload[name]
    elif kind == "domain":
        name = draw(st.sampled_from(sorted(OUT_OF_DOMAIN)))
        payload[name] = draw(st.sampled_from(OUT_OF_DOMAIN[name]))
    elif kind == "no_consent":
        del payload["consent"]
    elif kind == "consent_false":
        payload["consent"]["explicit"] = draw(st.sampled_from([False, None, "true", 1]))
    elif kind == "consent_unknown":
        payload["consent"]["version"] = draw(
            st.sampled_from(["2025-01-v0", "", "V1", "2026-11-v1 "])
        )
    elif kind == "consent_extra":
        payload["consent"]["accepted_at"] = "2026-11-07"
    else:
        payload["demo"] = True
    return payload
