"""Chains A→B→C over reported findings (cascade-engine design §4.5, Req 2.6). Pure."""

from __future__ import annotations

import itertools
from collections.abc import Sequence

from janus.cascades.model import Chain, ChainLink, Finding

MAX_PATHS = 10_000
MAX_CHAINS = 100


def _contains(longer: tuple[str, ...], shorter: tuple[str, ...]) -> bool:
    n = len(shorter)
    return any(longer[i : i + n] == shorter for i in range(len(longer) - n + 1))


def chains(findings: Sequence[Finding]) -> tuple[tuple[Chain, ...], bool]:
    """Maximal simple paths with two or more links; returns (chains, truncated)."""
    edges: dict[tuple[str, str], list[Finding]] = {}
    for f in findings:
        edges.setdefault((f.index.key, f.marker.key), []).append(f)
    succ: dict[str, list[str]] = {}
    for a, b in sorted(edges):
        succ.setdefault(a, []).append(b)

    paths: list[tuple[str, ...]] = []
    truncated = False

    def walk(path: list[str]) -> None:
        nonlocal truncated
        if truncated:
            return
        if len(path) >= 3:
            if len(paths) >= MAX_PATHS:
                truncated = True
                return
            paths.append(tuple(path))
        for nxt in succ.get(path[-1], []):
            if nxt not in path:
                path.append(nxt)
                walk(path)
                path.pop()

    for start in sorted(succ):
        walk([start])
    maximal = [p for p in paths if not any(len(q) > len(p) and _contains(q, p) for q in paths)]
    maximal.sort(key=lambda p: (-len(p), p))
    if len(maximal) > MAX_CHAINS:
        truncated = True
        maximal = maximal[:MAX_CHAINS]
    out: list[Chain] = []
    for p in maximal:
        links: list[ChainLink] = []
        probable = True
        for a, b in itertools.pairwise(p):
            fs = edges[(a, b)]
            links.append(ChainLink(a, b, tuple(sorted(f.finding_id for f in fs))))
            probable = probable and any(f.status == "probable" for f in fs)
        out.append(Chain(">".join(p), p, tuple(links), "probable" if probable else "possible"))
    return tuple(out), truncated
