"""Transparent pure-Python bitarray baseline (the honest floor).

Representation: a Python ``list`` of ``bool`` in logical order, one
element per bit. No NumPy, Cython, Numba, or other compiled
acceleration. Every operation preserves the logical length with
zero-fill shifts, matching the reference semantics probed for
``bitarray==3.12.3``.

Negative shift counts raise ``ValueError`` (reference parity); the
benchmarked domain uses non-negative counts only.
"""

from __future__ import annotations


def from_bits(s: str) -> list[bool]:
    return [c == "1" for c in s]


def to_bits(xs: list[bool]) -> str:
    return "".join("1" if x else "0" for x in xs)


def band(a: list[bool], b: list[bool]) -> list[bool]:
    return [x and y for x, y in zip(a, b, strict=True)]


def bor(a: list[bool], b: list[bool]) -> list[bool]:
    return [x or y for x, y in zip(a, b, strict=True)]


def bxor(a: list[bool], b: list[bool]) -> list[bool]:
    return [bool(x != y) for x, y in zip(a, b, strict=True)]


def count(xs: list[bool]) -> int:
    return sum(xs)


def _check_shift(k: int) -> None:
    if k < 0:
        raise ValueError("negative shift count")


def shl(xs: list[bool], k: int) -> list[bool]:
    _check_shift(k)
    n = len(xs)
    if k >= n:
        return [False] * n
    return xs[k:] + [False] * k


def shr(xs: list[bool], k: int) -> list[bool]:
    _check_shift(k)
    n = len(xs)
    if k >= n:
        return [False] * n
    return [False] * k + xs[: n - k]
