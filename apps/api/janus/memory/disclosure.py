"""k-suppression and noisy release of user-data counts (privacy design §6, Req 4). Pure.

Shared with the collective-memory spec. Never used for FAERS counts, which are public.

- A cell is released only if its true contributor count is at least k (k >= 20), decided
  before any noise.
- A released value is the true count plus discrete Laplace noise with scale 1/ε, clamped at 0.
- Totals are sums of released noisy values only, so no output depends on a suppressed cell.
- Noise is deterministic per (cell key, data version) under a secret key.

Product wording: "hidden under 20, noise added". Because suppression uses true counts, the
release as a whole is not claimed to be formally ε-differentially private (DP14).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from fractions import Fraction
from typing import Final

from janus.memory.noise import KeyedRandom, RandomSource, cell_seed, discrete_laplace

K_MIN: Final = 20


@dataclass(frozen=True)
class Cell:
    key: tuple[str, ...]
    count: int  # true contributor count (donations, not people: DP13)


@dataclass(frozen=True)
class Released:
    key: tuple[str, ...]
    value: int  # noisy, non-negative


@dataclass(frozen=True)
class Release:
    cells: tuple[Released, ...]  # only cells with count >= k, sorted by key
    suppressed: int  # number of withheld cells
    total_of_released: int | None  # sum of released values; None if nothing released


def check_parameters(k: int, epsilon: Fraction) -> None:
    if k < K_MIN:
        raise ValueError("k must be at least 20")
    if not (0 < epsilon <= 10):
        raise ValueError("epsilon must be in (0, 10]")


def noisy_count(true_count: int, *, epsilon: Fraction, rng: RandomSource) -> int:
    if true_count < 0:
        raise ValueError("count must be >= 0")
    if epsilon <= 0:
        raise ValueError("epsilon must be > 0")
    return max(0, true_count + discrete_laplace(1 / epsilon, rng))


NoiseSource = Callable[[tuple[str, ...], str], RandomSource]


def keyed_noise_source(key: bytes) -> NoiseSource:
    """Production noise source: one deterministic generator per (cell key, data version)."""

    def source(cell_key: tuple[str, ...], data_version: str) -> RandomSource:
        return KeyedRandom(key, cell_seed(cell_key, data_version))

    return source


def release_table(
    cells: Iterable[Cell],
    *,
    k: int,
    epsilon: Fraction,
    noise_source: NoiseSource,
    data_version: str,
) -> Release:
    check_parameters(k, epsilon)
    by_key: dict[tuple[str, ...], int] = {}
    for cell in cells:
        if cell.count < 0:
            raise ValueError("count must be >= 0")
        if cell.key in by_key:
            raise ValueError("duplicate cell key")
        by_key[cell.key] = cell.count
    released: list[Released] = []
    suppressed = 0
    for key in sorted(by_key):
        count = by_key[key]
        if count < k:
            suppressed += 1
            continue
        rng = noise_source(key, data_version)
        released.append(Released(key, noisy_count(count, epsilon=epsilon, rng=rng)))
    total = sum(r.value for r in released) if released else None
    return Release(tuple(released), suppressed, total)
