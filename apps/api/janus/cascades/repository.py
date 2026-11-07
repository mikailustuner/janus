"""Read-only queries of the cascade engine (cascade-engine design §3.7, §6.1, §7). Parameterised."""

from __future__ import annotations

from typing import Any, cast

import psycopg

from janus.cascades.model import RuleBase
from janus.cascades.rulebase import rule_base_from_content

_CACHE: dict[str, RuleBase] = {}
_CACHE_SIZE = 4


def current_version(conn: psycopg.Connection) -> str | None:
    row = conn.execute("SELECT version FROM cascade_rule_base_current WHERE one").fetchone()
    return None if row is None else str(row[0])


def rule_base(conn: psycopg.Connection, version: str) -> RuleBase:
    """The stored rule base of `version`, parsed once per process (content is immutable)."""
    cached = _CACHE.get(version)
    if cached is not None:
        return cached
    row = conn.execute(
        "SELECT content FROM cascade_rule_base WHERE version = %s", (version,)
    ).fetchone()
    if row is None:
        raise LookupError("rule base version not stored")
    rb = rule_base_from_content(cast(dict[str, Any], row[0]), version)
    if len(_CACHE) >= _CACHE_SIZE:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[version] = rb
    return rb


def current_rule_base(conn: psycopg.Connection) -> RuleBase | None:
    v = current_version(conn)
    return None if v is None else rule_base(conn, v)
