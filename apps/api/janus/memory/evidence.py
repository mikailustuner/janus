"""Citation of FAERS statistics (collective-memory design §6; owner decision 2026-11-08, DP12).

There is one dataset-level evidence record per FAERS snapshot, `dataset:faers`, written by the
evidence-integrity loader from the `faers` artifact. A statistic cites it with a deterministic
locator naming the ingredient(s), the event, the region and the scope:

    faers:ingredient=Q1,Q2;event=cough;region=ALL;scope=suspect
    faers:ingredient=Q18216;event=pt:Oedema%20peripheral;region=US;scope=any
    faers:ingredient=Q18216;event=;region=ALL;scope=suspect          (no event: ingredient counts)

The locator holds no run id, build id or date, so an issued note's citation stays valid after a
rebuild. Pure: no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final
from urllib.parse import quote, unquote

from janus.memory.model import (
    EVENT_KEY_PATTERN,
    INGREDIENT_KEY_PATTERN,
    RESPONSE_REGIONS,
)

FAERS_EVIDENCE_ID: Final = "dataset:faers"
PREFIX: Final = "faers:"
_KEY = re.compile(INGREDIENT_KEY_PATTERN)
_EVENT_KEY = re.compile(EVENT_KEY_PATTERN)
SCOPES: Final = ("suspect", "any")


class LocatorError(ValueError):
    """A locator is malformed. The message never carries the locator."""


@dataclass(frozen=True)
class EventRef:
    """Exactly one of `key` (a Janus event key) and `pt` (a MedDRA PT); both None = no event."""

    key: str | None = None
    pt: str | None = None


@dataclass(frozen=True)
class Locator:
    ingredients: tuple[str, ...]
    event: EventRef
    region: str
    scope: str


def faers_locator(
    ingredients: tuple[str, ...] | list[str], event: EventRef, region: str, scope: str
) -> str:
    keys = sorted(set(ingredients))
    if not keys or not all(_KEY.fullmatch(k) for k in keys):
        raise LocatorError("bad ingredient key")
    if region not in RESPONSE_REGIONS or scope not in SCOPES:
        raise LocatorError("bad region or scope")
    if event.key is not None and event.pt is not None:
        raise LocatorError("both key and pt")
    if event.key is not None:
        if not _EVENT_KEY.fullmatch(event.key):
            raise LocatorError("bad event key")
        ev = event.key
    elif event.pt is not None:
        if not event.pt:
            raise LocatorError("empty pt")
        ev = "pt:" + quote(event.pt, safe="")
    else:
        ev = ""
    return f"{PREFIX}ingredient={','.join(keys)};event={ev};region={region};scope={scope}"


def parse_locator(text: str) -> Locator:
    if not text.startswith(PREFIX):
        raise LocatorError("not a FAERS locator")
    parts = text[len(PREFIX) :].split(";")
    if len(parts) != 4:
        raise LocatorError("wrong number of parts")
    fields: dict[str, str] = {}
    for name, part in zip(("ingredient", "event", "region", "scope"), parts, strict=True):
        label, sep, value = part.partition("=")
        if label != name or not sep:
            raise LocatorError("wrong part")
        fields[name] = value
    keys = tuple(fields["ingredient"].split(","))
    if keys != tuple(sorted(set(keys))) or not all(_KEY.fullmatch(k) for k in keys):
        raise LocatorError("bad ingredient key")
    ev = fields["event"]
    if ev == "":
        event = EventRef()
    elif ev.startswith("pt:"):
        pt = unquote(ev[3:])
        if not pt or quote(pt, safe="") != ev[3:]:
            raise LocatorError("bad pt")
        event = EventRef(pt=pt)
    elif _EVENT_KEY.fullmatch(ev):
        event = EventRef(key=ev)
    else:
        raise LocatorError("bad event")
    if fields["region"] not in RESPONSE_REGIONS or fields["scope"] not in SCOPES:
        raise LocatorError("bad region or scope")
    return Locator(keys, event, fields["region"], fields["scope"])
