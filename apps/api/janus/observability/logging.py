"""Allowlist logging (privacy design §4.2).

Every log record, from Janus code or any library, is formatted by `AllowlistFormatter`, which
emits one JSON object with a fixed set of keys and validated values. The formatter never reads
a record's message, arguments, exception or stack, so a record cannot carry health data into
the log, whatever its content. Janus code logs through `log_event()`.
"""

from __future__ import annotations

import json
import logging
import math
import re
import sys
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Final

UNMATCHED_ROUTE: Final = "<unmatched>"
SUPPRESSED: Final = "suppressed"

# Top-level packages whose name may appear in the `logger` key; anything else is "other".
KNOWN_LOGGERS: Final = (
    "janus",
    "uvicorn",
    "fastapi",
    "starlette",
    "httpx2",
    "httpx",
    "httpcore",
    "alembic",
    "psycopg",
    "sqlalchemy",
    "asyncio",
    "py.warnings",
)
LEVELS: Final = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
_UUID_RE: Final = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

# Loggers that libraries configure with their own handlers; they are reset to propagate to root.
_LIBRARY_LOGGERS: Final = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "fastapi",
    "starlette",
    "httpx2",
    "httpx",
    "httpcore",
    "alembic",
    "alembic.runtime.migration",
    "psycopg",
    "psycopg.pool",
    "sqlalchemy",
    "sqlalchemy.engine",
    "asyncio",
    "py.warnings",
)

_route_templates: frozenset[str] = frozenset()


class LogEvent(StrEnum):
    access = "access"
    unhandled_error = "unhandled_error"
    startup = "startup"
    shutdown = "shutdown"
    migration = "migration"
    donations_disabled = "donations_disabled"
    purge = "purge"


def register_route_templates(templates: Iterable[str]) -> None:
    """Record the app's route templates; only these (or `<unmatched>`) may be logged as route."""
    global _route_templates
    _route_templates = _route_templates | frozenset(templates) | {UNMATCHED_ROUTE}


def registered_route_templates() -> frozenset[str]:
    return _route_templates


def _logger_label(name: object) -> str:
    if not isinstance(name, str):
        return "other"
    if name == "root":
        return "root"
    for known in KNOWN_LOGGERS:
        if name == known or name.startswith(known + "."):
            return known
    return "other"


def _as_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _as_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _valid_fields(raw: object) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(raw, dict):
        return out
    fields: dict[Any, Any] = raw  # pyright: ignore[reportUnknownVariableType]
    rid = fields.get("request_id")
    if isinstance(rid, str) and _UUID_RE.fullmatch(rid):
        out["request_id"] = rid
    route = fields.get("route")
    if isinstance(route, str) and route in _route_templates:
        out["route"] = route
    status = _as_int(fields.get("status"))
    if status is not None and 100 <= status <= 599:
        out["status"] = status
    latency = _as_number(fields.get("latency_ms"))
    if latency is not None and latency >= 0:
        out["latency_ms"] = round(latency, 1)
    error_class = fields.get("error_class")
    if isinstance(error_class, type) and issubclass(error_class, BaseException):
        out["error_class"] = error_class.__qualname__
    count = _as_int(fields.get("count"))
    if count is not None and count >= 0:
        out["count"] = count
    return out


class AllowlistFormatter(logging.Formatter):
    """Formats any record as one JSON object with allowlisted keys only."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            return self._format(record)
        except Exception:  # never let formatting fall back to printing the record
            return json.dumps({"event": SUPPRESSED, "level": "UNKNOWN", "logger": "other"})

    def _format(self, record: logging.LogRecord) -> str:
        attrs = record.__dict__
        created = attrs.get("created")
        if not isinstance(created, float | int) or not math.isfinite(created):
            created = time.time()
        level = attrs.get("levelname")
        event = attrs.get("janus_event")
        line: dict[str, Any] = {
            "ts": datetime.fromtimestamp(created, UTC).isoformat(timespec="milliseconds"),
            "level": level if isinstance(level, str) and level in LEVELS else "UNKNOWN",
            "logger": _logger_label(attrs.get("name")),
            "event": event.value if isinstance(event, LogEvent) else SUPPRESSED,
        }
        if isinstance(event, LogEvent):
            line.update(_valid_fields(attrs.get("janus_fields")))
        return json.dumps(line, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


_janus_logger = logging.getLogger("janus")


def log_event(event: LogEvent, level: int = logging.INFO, **fields: object) -> None:
    """The only way Janus code writes a log line. The message is always empty."""
    # `event` is the LogEvent name, not a clinical event; fields are validated by the formatter.
    extra = {"janus_event": event, "janus_fields": fields}
    _janus_logger.log(level, "", extra=extra)


def make_handler(stream: Any = None) -> logging.Handler:
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(AllowlistFormatter())
    return handler


def configure_logging(stream: Any = None, level: int = logging.INFO) -> logging.Handler:
    """Route every logger through one allowlist handler on the root logger."""
    logging.raiseExceptions = False  # a failing handler must not print the record to stderr
    logging.captureWarnings(True)  # warnings carry source lines; send them through the formatter
    handler = make_handler(stream)
    root = logging.getLogger()
    for old in list(root.handlers):
        root.removeHandler(old)
    root.addHandler(handler)
    root.setLevel(level)
    existing = [
        n for n, lg in logging.Logger.manager.loggerDict.items() if isinstance(lg, logging.Logger)
    ]
    for name in {*_LIBRARY_LOGGERS, *existing}:
        lib = logging.getLogger(name)
        for old in list(lib.handlers):
            lib.removeHandler(old)
        lib.propagate = True
    return handler
