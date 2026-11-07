"""Sentinel strategies for log-leak tests (privacy design §7).

A sentinel is "zz" + text + "zz" over letters that cannot occur in a UUID, a route template, a
status code, a latency or a timestamp, so finding one in log output means a value leaked.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from hypothesis import strategies as st

ALPHABET = "ghjkmnpqrstuvwxyGHJKMNPQRSTUVWXYçğışöüÇĞİŞÖÜ"  # noqa: RUF001 (Turkish letters on purpose)


def sentinels(min_size: int = 3, max_size: int = 10) -> st.SearchStrategy[str]:
    return st.text(alphabet=ALPHABET, min_size=min_size, max_size=max_size).map(
        lambda t: f"zz{t}zz"
    )


def ascii_sentinels(min_size: int = 3, max_size: int = 10) -> st.SearchStrategy[str]:
    """For places that only take ASCII (header values, URL path segments)."""
    return st.text(alphabet="ghjkmnpqrstuvwxy", min_size=min_size, max_size=max_size).map(
        lambda t: f"zz{t}zz"
    )


def _strings_in(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():  # pyright: ignore[reportUnknownVariableType]
            yield str(k)  # pyright: ignore[reportUnknownArgumentType]
            yield from _strings_in(v)
    elif isinstance(value, list):
        for v in value:  # pyright: ignore[reportUnknownVariableType]
            yield from _strings_in(v)


def leaked(output: str, secrets: Iterable[str]) -> list[str]:
    """Secrets found in raw output or in any decoded JSON string value of any output line."""
    texts = [output]
    for line in output.splitlines():
        try:
            texts.extend(_strings_in(json.loads(line)))
        except ValueError:
            continue
    found: list[str] = []
    for secret in secrets:
        if secret and any(secret in t for t in texts):
            found.append(secret)
    return found
