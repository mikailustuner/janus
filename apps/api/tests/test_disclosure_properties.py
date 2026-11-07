"""Property and statistical tests for suppression and noise (design §8 P11-P14, S1)."""

from __future__ import annotations

import math
import random
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.memory.disclosure import (
    Cell,
    keyed_noise_source,
    noisy_count,
    release_table,
)
from janus.memory.noise import KeyedRandom, RandomSource, cell_seed, discrete_laplace

KEY = bytes(range(32))
EPSILONS = st.sampled_from(
    [Fraction(1, 10), Fraction(1, 2), Fraction(1), Fraction(2), Fraction(10)]
)


class SeededRandom:
    def __init__(self, seed: int) -> None:
        self._r = random.Random(seed)  # noqa: S311 (test-only, reproducible)

    def randbelow(self, n: int) -> int:
        return self._r.randrange(n)


def source_for_tests(key: bytes = KEY):  # type: ignore[no-untyped-def]
    return keyed_noise_source(key)


keys = st.tuples(st.sampled_from(["TR", "EU", "US"]), st.text(min_size=1, max_size=4))
cell_lists = st.lists(
    st.tuples(keys, st.integers(0, 60)), max_size=12, unique_by=lambda c: c[0]
).map(lambda xs: [Cell(k, n) for k, n in xs])


@given(cells=cell_lists, eps=EPSILONS, version=st.text(max_size=8), data=st.data())
def test_suppression_hides_small_cells_completely(
    cells: list[Cell], eps: Fraction, version: str, data: st.DataObject
) -> None:
    """Feature: privacy, Property P11. Validates Req 4.1."""
    src = source_for_tests()
    release = release_table(cells, k=20, epsilon=eps, noise_source=src, data_version=version)
    true = {c.key: c.count for c in cells}
    assert all(true[r.key] >= 20 for r in release.cells)
    assert {r.key for r in release.cells} == {c.key for c in cells if c.count >= 20}
    assert release.suppressed == sum(1 for c in cells if c.count < 20)
    # Change only suppressed cells (staying below k): nothing in the output may change.
    changed = [Cell(c.key, data.draw(st.integers(0, 19))) if c.count < 20 else c for c in cells]
    again = release_table(changed, k=20, epsilon=eps, noise_source=src, data_version=version)
    assert again == release


@given(count=st.integers(0, 10**6), eps=EPSILONS, seed=st.integers(0, 2**32))
def test_noisy_counts_are_non_negative_integers(count: int, eps: Fraction, seed: int) -> None:
    """Feature: privacy, Property P12. Validates Req 4.2."""
    value = noisy_count(count, epsilon=eps, rng=SeededRandom(seed))
    assert type(value) is int
    assert value >= 0


@given(cells=cell_lists, eps=EPSILONS, version=st.text(max_size=8), data=st.data())
def test_release_is_deterministic_and_order_independent(
    cells: list[Cell], eps: Fraction, version: str, data: st.DataObject
) -> None:
    """Feature: privacy, Property P13. Validates Req 4.2."""
    src = source_for_tests()
    first = release_table(cells, k=20, epsilon=eps, noise_source=src, data_version=version)
    shuffled = data.draw(st.permutations(cells))
    second = release_table(shuffled, k=20, epsilon=eps, noise_source=src, data_version=version)
    assert first == second
    total = sum(r.value for r in first.cells) if first.cells else None
    assert first.total_of_released == total


@given(k=st.integers(-100, 19))
def test_release_rejects_k_below_20(k: int) -> None:
    """Feature: privacy, Property P14 (module part). Validates Req 4.1."""
    with pytest.raises(ValueError):
        release_table(
            [Cell(("x",), 50)],
            k=k,
            epsilon=Fraction(1),
            noise_source=source_for_tests(),
            data_version="v",
        )


@given(n=st.integers(1, 10**12), seed=st.binary(max_size=16))
def test_keyed_randbelow_in_range(n: int, seed: bytes) -> None:
    value = KeyedRandom(KEY, seed).randbelow(n)
    assert 0 <= value < n


def test_cell_seed_is_unambiguous() -> None:
    assert cell_seed(("ab", "c"), "v") != cell_seed(("a", "bc"), "v")
    assert cell_seed(("a",), "bv") != cell_seed(("ba",), "v")


def _pmf(scale: Fraction, z: int) -> float:
    a = math.exp(-1 / float(scale))
    return (1 - a) / (1 + a) * a ** abs(z)


@pytest.mark.parametrize(
    ("eps", "keyed"),
    [
        (Fraction(1, 10), False),
        (Fraction(1, 2), False),
        (Fraction(1), False),
        (Fraction(2), False),
        (Fraction(1), True),
    ],
)
def test_sampler_matches_discrete_laplace(eps: Fraction, keyed: bool) -> None:
    """Statistical test S1: chi-square goodness of fit and mean, seeded. Validates Req 4.2."""
    scale = 1 / eps
    n = 200_000
    rng: RandomSource = KeyedRandom(KEY, b"s1") if keyed else SeededRandom(int(eps * 1000) + 7)
    draws = [discrete_laplace(scale, rng) for _ in range(n)]
    mean = sum(draws) / n
    var = 2 * math.exp(-1 / float(scale)) / (1 - math.exp(-1 / float(scale))) ** 2
    assert abs(mean) < 4 * math.sqrt(var / n)
    # Bins: every z with expected count >= 20 on its own; the two tails pooled.
    counts: dict[int, int] = {}
    for z in draws:
        counts[z] = counts.get(z, 0) + 1
    zmax = 0
    while n * _pmf(scale, zmax + 1) >= 20:
        zmax += 1
    chi2 = 0.0
    df = -1
    for z in range(-zmax, zmax + 1):
        expected = n * _pmf(scale, z)
        chi2 += (counts.get(z, 0) - expected) ** 2 / expected
        df += 1
    tail_expected = n - sum(n * _pmf(scale, z) for z in range(-zmax, zmax + 1))
    tail_observed = sum(c for z, c in counts.items() if abs(z) > zmax)
    if tail_expected > 0:
        chi2 += (tail_observed - tail_expected) ** 2 / tail_expected
        df += 1
    # Wilson-Hilferty upper 0.1% point of chi-square(df).
    zq = 3.090232
    critical = df * (1 - 2 / (9 * df) + zq * math.sqrt(2 / (9 * df))) ** 3
    assert chi2 < critical, f"chi2={chi2:.1f} df={df} critical={critical:.1f}"
