"""Exact discrete Laplace noise (privacy design §6.2, DP15, DP16). Pure: no I/O.

Sampler: Canonne, Kamath and Steinke, "The Discrete Gaussian for Differential Privacy"
(arXiv:2004.00010), Algorithm 1 (Bernoulli(exp(-gamma)) for rational gamma) and
Algorithm 2 (discrete Laplace with rational scale).
All arithmetic is on `int` and `Fraction`; no floats.
Randomness comes only from `rng.randbelow`, so tests can pass a seeded generator and
production a keyed deterministic one (`KeyedRandom`).
"""

from __future__ import annotations

import hashlib
import hmac
from fractions import Fraction
from typing import Protocol


class RandomSource(Protocol):
    def randbelow(self, n: int) -> int:
        """Uniform integer in [0, n)."""
        ...


def bernoulli(p: Fraction, rng: RandomSource) -> bool:
    """True with probability p (0 <= p <= 1), exactly."""
    if not (0 <= p <= 1):
        raise ValueError("p must be in [0, 1]")
    return rng.randbelow(p.denominator) < p.numerator


def bernoulli_exp_neg(gamma: Fraction, rng: RandomSource) -> bool:
    """True with probability exp(-gamma), gamma >= 0 rational (CKS20 Algorithm 1)."""
    if gamma < 0:
        raise ValueError("gamma must be >= 0")
    while gamma > 1:
        if not bernoulli_exp_neg(Fraction(1), rng):
            return False
        gamma -= 1
    # 0 <= gamma <= 1: K = first k with A_k = 0, where A_k ~ Bernoulli(gamma / k).
    k = 1
    while bernoulli(gamma / k, rng):
        k += 1
    return k % 2 == 1


def discrete_laplace(scale: Fraction, rng: RandomSource) -> int:
    """Sample Z with P(Z = z) proportional to exp(-|z| / scale) (CKS20 Algorithm 2)."""
    if scale <= 0:
        raise ValueError("scale must be > 0")
    # CKS20 Algorithm 2 samples Lap_Z(t/s): U is uniform over t and Y = floor(X / s).
    t, s = scale.numerator, scale.denominator
    while True:
        u = rng.randbelow(t)
        if not bernoulli_exp_neg(Fraction(u, t), rng):
            continue
        v = 0
        while bernoulli_exp_neg(Fraction(1), rng):
            v += 1
        x = u + t * v
        y = x // s
        negative = bernoulli(Fraction(1, 2), rng)
        if negative and y == 0:
            continue
        return -y if negative else y


class KeyedRandom:
    """Deterministic uniform integers from HMAC-SHA256(key, seed || counter).

    The same key and seed always give the same sequence, so a repeated query for the same cell
    and data version returns the same noisy value (DP16). `randbelow` uses rejection sampling,
    so it has no modulo bias.
    """

    def __init__(self, key: bytes, seed: bytes) -> None:
        if len(key) < 32:
            raise ValueError("key must be at least 32 bytes")
        self._key = key
        self._seed = seed
        self._counter = 0
        self._buffer = b""

    def _bytes(self, n: int) -> bytes:
        while len(self._buffer) < n:
            block = hmac.new(
                self._key,
                self._seed + self._counter.to_bytes(8, "big"),
                hashlib.sha256,
            ).digest()
            self._counter += 1
            self._buffer += block
        out, self._buffer = self._buffer[:n], self._buffer[n:]
        return out

    def randbelow(self, n: int) -> int:
        if n <= 0:
            raise ValueError("n must be > 0")
        if n == 1:
            return 0
        bits = (n - 1).bit_length()
        nbytes = (bits + 7) // 8
        mask = (1 << bits) - 1
        while True:
            value = int.from_bytes(self._bytes(nbytes), "big") & mask
            if value < n:
                return value


def cell_seed(cell_key: tuple[str, ...], data_version: str) -> bytes:
    """Unambiguous seed for one cell of one data version (length-prefixed parts)."""
    parts = [data_version, *cell_key]
    out = bytearray()
    for part in parts:
        raw = part.encode("utf-8")
        out += len(raw).to_bytes(4, "big") + raw
    return bytes(out)
