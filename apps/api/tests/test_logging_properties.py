"""Property tests for the allowlist formatter (privacy design §8, P2)."""

from __future__ import annotations

import io
import json
import logging
import sys
import uuid

from hypothesis import given
from hypothesis import strategies as st

from janus.observability.logging import (
    LEVELS,
    AllowlistFormatter,
    LogEvent,
    configure_logging,
    log_event,
    register_route_templates,
    registered_route_templates,
)
from tests.sentinels import leaked, sentinels

ALLOWED_KEYS = {
    "ts",
    "level",
    "logger",
    "event",
    "request_id",
    "route",
    "status",
    "latency_ms",
    "error_class",
    "count",
}
TEMPLATES = ["/health", "/test/resolve/{code}", "/contributions"]


class SentinelError(Exception):
    pass


def _value(s: str) -> st.SearchStrategy[object]:
    return st.sampled_from([s, [s], {"k": s}, {s: 1}, (s,), 1.5, -3, True, None])


@st.composite
def records(draw: st.DrawFn) -> tuple[logging.LogRecord, list[str]]:
    secrets: list[str] = draw(st.lists(sentinels(), min_size=8, max_size=8))
    name = draw(
        st.one_of(
            st.sampled_from(["janus", "janus.x", "uvicorn.error", "httpx2", "root", "multipart"]),
            st.just("janus." + secrets[0]),
            st.just(secrets[0]),
        )
    )
    level = draw(st.sampled_from([logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, 50]))
    msg = draw(st.sampled_from([secrets[1], "value %s", "%(x)s", "", "HTTP Request: GET %s"]))
    args = (secrets[2],) if "%s" in msg else None
    exc_info = None
    if draw(st.booleans()):
        try:
            raise SentinelError(secrets[3])
        except SentinelError:
            exc_info = sys.exc_info()
    record = logging.LogRecord(name, level, secrets[4] + ".py", 1, msg, args, exc_info)
    if draw(st.booleans()):
        record.stack_info = secrets[5]
    extra_names = draw(st.lists(st.sampled_from(["body", "code", "ingredient", "x"]), max_size=3))
    for extra in extra_names:
        setattr(record, extra, secrets[6])
    if draw(st.booleans()):
        record.janus_event = draw(st.sampled_from([*LogEvent, secrets[7]]))
    if draw(st.booleans()):
        record.janus_fields = draw(
            st.fixed_dictionaries(
                {},
                optional={
                    "request_id": st.one_of(_value(secrets[0]), st.uuids(version=4).map(str)),
                    "route": st.one_of(_value(secrets[1]), st.sampled_from(TEMPLATES)),
                    "status": st.one_of(_value(secrets[2]), st.integers(0, 1000)),
                    "latency_ms": st.one_of(
                        _value(secrets[3]), st.floats(allow_nan=True, allow_infinity=True)
                    ),
                    "error_class": st.one_of(_value(secrets[4]), st.just(ValueError)),
                    "count": st.one_of(_value(secrets[5]), st.integers(-5, 5)),
                    secrets[6]: _value(secrets[6]),
                },
            )
        )
    if draw(st.booleans()):
        record.levelname = secrets[7]
    return record, secrets


@given(records())
def test_formatter_emits_only_allowlisted_validated_keys(
    item: tuple[logging.LogRecord, list[str]],
) -> None:
    """Feature: privacy, Property P2. Validates Req 2.2."""
    register_route_templates(TEMPLATES)
    record, secrets = item
    out = AllowlistFormatter().format(record)
    assert "\n" not in out
    line = json.loads(out)
    assert set(line) <= ALLOWED_KEYS
    assert line["level"] in LEVELS | {"UNKNOWN"}
    assert line["event"] in {e.value for e in LogEvent} | {"suppressed"}
    if "request_id" in line:
        assert uuid.UUID(line["request_id"]).version == 4
    if "route" in line:
        assert line["route"] in registered_route_templates()
    if "status" in line:
        assert 100 <= line["status"] <= 599
    if "latency_ms" in line:
        assert line["latency_ms"] >= 0
    if "error_class" in line:
        assert line["error_class"] == "ValueError"
    if "count" in line:
        assert line["count"] >= 0
    assert leaked(out, secrets) == []


def test_library_logger_messages_are_suppressed() -> None:
    stream = io.StringIO()
    configure_logging(stream)
    planted = "HTTP Request: GET https://api.fda.gov/x?search=zzndczz"
    logging.getLogger("httpx2").info(planted)  # log-guard: ignore (planted library leak)
    logging.getLogger("uvicorn.error").exception("boom zzbodyzz")
    access_record = '127.0.0.1:5555 - "GET /resolve/zzcodezz HTTP/1.1" 404'
    logging.getLogger("uvicorn.access").info(access_record)  # log-guard: ignore (planted)
    log_event(LogEvent.purge, count=3)
    lines = [json.loads(x) for x in stream.getvalue().splitlines()]
    assert len(lines) == 3  # the uvicorn.access record is not emitted at all
    assert lines[0] == {**lines[0], "event": "suppressed", "logger": "httpx2"}
    assert lines[1]["event"] == "suppressed"
    assert lines[2]["event"] == "purge" and lines[2]["count"] == 3
    assert "zz" not in stream.getvalue()
