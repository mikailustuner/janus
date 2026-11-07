"""Property tests for the donation model, report week and retention (P7, P8, P16 pure parts)."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from janus.contributions.models import ContributionIn
from janus.contributions.retention import is_expired, retention_cutoff
from janus.contributions.tokens import new_token, token_hash
from janus.contributions.vocabulary import VocabularyError, parse_vocabulary
from janus.contributions.week import report_week
from tests.donation_strategies import CONTEXT, invalid_payloads, valid_payloads


@given(st.datetimes(timezones=st.timezones()))
def test_report_week_is_monday_of_utc_iso_week(now: dt.datetime) -> None:
    """Feature: privacy, Property P8 (pure part). Validates Req 3.2."""
    week = report_week(now)
    utc_day = now.astimezone(dt.UTC).date()
    assert week.isoweekday() == 1
    assert 0 <= (utc_day - week).days <= 6
    assert week.isocalendar()[:2] == utc_day.isocalendar()[:2]


def test_report_week_rejects_naive_time() -> None:
    with pytest.raises(ValueError):
        report_week(dt.datetime(2026, 11, 7, 12, 0))


@given(valid_payloads())
def test_valid_payloads_are_accepted(payload: dict[str, Any]) -> None:
    model = ContributionIn.model_validate(payload, context=CONTEXT)
    assert model.ingredients == sorted(payload["ingredients"])


@given(invalid_payloads())
def test_invalid_payloads_are_rejected(payload: dict[str, Any]) -> None:
    """Feature: privacy, Property P7 (model part). Validates Req 3.1, 3.2."""
    with pytest.raises(ValidationError):
        ContributionIn.model_validate(payload, context=CONTEXT)


@given(valid_payloads())
def test_validation_without_context_fails_closed(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ContributionIn.model_validate(payload)


def _reference_cutoff(day: dt.date) -> dt.date:
    """24 months = 2 years; 29 February falls back to 28 February."""
    try:
        return day.replace(year=day.year - 2)
    except ValueError:
        return day.replace(year=day.year - 2, day=28)


@given(st.dates(min_value=dt.date(2003, 1, 1), max_value=dt.date(2200, 12, 31)))
def test_retention_cutoff_is_24_months_earlier(day: dt.date) -> None:
    """Feature: privacy, Property P16 (pure part). Validates Req 3.6."""
    assert retention_cutoff(day) == _reference_cutoff(day)


@given(
    week=st.dates(min_value=dt.date(2020, 1, 1), max_value=dt.date(2030, 12, 31)).map(
        lambda d: d - dt.timedelta(days=d.weekday())
    ),
    received_offset=st.integers(0, 6),
    today=st.dates(min_value=dt.date(2020, 1, 1), max_value=dt.date(2033, 12, 31)),
)
def test_expired_never_keeps_longer_than_24_months(
    week: dt.date, received_offset: int, today: dt.date
) -> None:
    """A donation received in `week` is purged once 24 months have passed since receipt."""
    received = week + dt.timedelta(days=received_offset)
    if received <= retention_cutoff(today):
        assert is_expired(week, today)


@given(st.integers(0, 50))
def test_tokens_are_unique_and_well_formed(_n: int) -> None:
    a, b = new_token(), new_token()
    assert a != b
    assert len(token_hash(a)) == 32
    assert a.startswith("jdt_") and len(a) == 47


def test_vocabulary_rejects_bad_keys() -> None:
    assert parse_vocabulary("# c\ncough\n\ndizziness\n") == frozenset({"cough", "dizziness"})
    with pytest.raises(VocabularyError):
        parse_vocabulary("Free Text\n")
    with pytest.raises(VocabularyError):
        parse_vocabulary("# only comments\n")
