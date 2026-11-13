"""Pin bitarray==3.12.3 count/search semantics the Mojo port must match.

Phase 1D2 oracle: ``count`` (default/bit/sub-bitarray values, bounds,
steps), ``search`` (patterns, bounds, ``right=``), return shapes and
error behavior. The native Mojo tests mirror these exact expectations,
except that Mojo ``search`` returns a materialized ``List[Int]`` instead
of a lazy iterator (documented in the implementation).
"""

from __future__ import annotations

import random

import pytest

from bitarray import bitarray

ENDIANS = ["big", "little"]


def test_pinned_version() -> None:
    import bitarray as mod

    assert mod.__version__ == "3.12.3"


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize(
    ("text", "ones"),
    [("", 0), ("0", 0), ("1", 1), ("10110", 3), ("0" * 65, 0), ("1" * 65, 65)],
)
def test_count_default(endian: str, text: str, ones: int) -> None:
    a = bitarray(text, endian=endian)
    assert a.count() == ones
    assert type(a.count()) is int


@pytest.mark.parametrize("endian", ENDIANS)
def test_count_values(endian: str) -> None:
    a = bitarray("10110", endian=endian)
    assert a.count(1) == 3
    assert a.count(0) == 2
    assert a.count(True) == 3
    assert a.count(False) == 2
    with pytest.raises(ValueError, match="bit must be 0 or 1"):
        a.count(2)
    with pytest.raises(TypeError):
        a.count("1")


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize("n", [0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65])
def test_count_boundaries(endian: str, n: int) -> None:
    # Alternating from 1: ceil(n/2) ones; padding bits never counted.
    a = bitarray("10" * ((n + 1) // 2), endian=endian)[:n]
    assert a.count() + a.count(0) == n
    assert a.count(1) == (n + 1) // 2
    assert a.count(0) == n // 2
    # Padding check: n ones in a non-aligned array.
    b = bitarray("1" * n, endian=endian)
    assert b.count() == n
    assert b.nbytes == (n + 7) // 8


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize(
    ("start", "stop", "step", "expected"),
    [
        (1, 4, 1, 2),
        (0, 5, 2, 2),
        (0, 5, 1, 3),
        (-4, -1, 1, 2),
        (-100, 100, 1, 3),
        (4, 1, 1, 0),
        (0, 5, 3, 2),
    ],
)
def test_count_bounds(endian: str, start: int, stop: int, step: int, expected: int) -> None:
    a = bitarray("10110", endian=endian)
    assert a.count(1, start, stop, step) == expected
    assert a.count(1, start, stop) == a.count(1, start, stop, 1)
    assert a[start:stop:step].count(1) == expected


def test_count_step_zero() -> None:
    with pytest.raises(ValueError, match="step cannot be zero"):
        bitarray("10110").count(1, 0, 5, 0)


def test_count_sub_pattern() -> None:
    assert bitarray("10101").count(bitarray("101")) == 1
    assert bitarray("1111").count(bitarray("11")) == 2  # non-overlapping
    assert bitarray("101").count(bitarray("")) == 4  # n + 1
    assert bitarray("").count(bitarray("")) == 1
    assert bitarray("10").count(bitarray("10101")) == 0
    assert bitarray("10101").count(bitarray("101"), 1, 5) == 1
    assert bitarray("10101").count(bitarray("101"), 0, 3) == 1
    assert bitarray("10101").count(bitarray("101"), 0, 2) == 0
    assert bitarray("10101", endian="big").count(bitarray("101", endian="little")) == 1
    with pytest.raises(ValueError, match="step must be 1"):
        bitarray("10101").count(bitarray("1"), 0, 5, 2)


def test_search_basic() -> None:
    assert list(bitarray("10101").search(bitarray("101"))) == [0, 2]
    assert list(bitarray("1111").search(bitarray("11"))) == [0, 1, 2]  # overlapping
    assert list(bitarray("10101").search(bitarray("1"))) == [0, 2, 4]
    assert list(bitarray("10101").search(1)) == [0, 2, 4]
    assert list(bitarray("10101").search(0)) == [1, 3]
    assert list(bitarray("10101").search(True)) == [0, 2, 4]
    assert list(bitarray("").search(bitarray("1"))) == []
    assert list(bitarray("000").search(bitarray("1111"))) == []
    assert list(bitarray("10").search(bitarray("10101"))) == []
    with pytest.raises(ValueError, match="bit must be 0 or 1"):
        list(bitarray("10101").search(2))
    with pytest.raises(TypeError):
        list(bitarray("10101").search("101"))


def test_search_empty_pattern() -> None:
    assert list(bitarray("101").search(bitarray(""))) == [0, 1, 2, 3]
    assert list(bitarray("").search(bitarray(""))) == [0]
    assert list(bitarray("101").search(bitarray(""), right=True)) == [3, 2, 1, 0]


def test_search_bounds() -> None:
    a = bitarray("10101")
    assert list(a.search(bitarray("101"), 1, 5)) == [2]
    assert list(a.search(bitarray("1"), -4, -1)) == [2]
    assert list(a.search(bitarray("1"), -100, 100)) == [0, 2, 4]
    assert list(a.search(bitarray("1"), 4, 1)) == []
    # Match must be fully contained in [start:stop).
    assert list(a.search(bitarray("101"), 0, 3)) == [0]
    assert list(a.search(bitarray("101"), 0, 2)) == []


def test_search_right() -> None:
    a = bitarray("10101")
    assert list(a.search(bitarray("101"), right=True)) == [2, 0]
    assert list(a.search(bitarray("1"), right=True)) == [4, 2, 0]
    assert list(a.search(bitarray("1"), 1, 4, right=True)) == [2]


def test_search_endianness() -> None:
    for endian in ENDIANS:
        a = bitarray("10101", endian=endian)
        assert list(a.search(bitarray("101", endian=endian))) == [0, 2]
    assert list(bitarray("10101", endian="big").search(bitarray("101", endian="little"))) == [0, 2]


def test_search_returns_iterator() -> None:
    it = bitarray("101").search(bitarray("1"))
    assert type(it).__name__ == "searchiterator"
    assert list(it) == [0, 2]


def test_count_search_fuzz_against_model() -> None:
    rng = random.Random(20260603)
    for trial in range(300):
        for endian in ENDIANS:
            n = rng.choice([0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65])
            bits = [rng.choice((0, 1)) for _ in range(n)]
            a = bitarray(bits, endian=endian)
            assert a.count() == sum(bits)
            assert a.count(0) == n - sum(bits)
            assert a.count() + a.count(0) == n
            m = rng.randrange(min(n + 2, 8))
            pat = [rng.choice((0, 1)) for _ in range(m)]
            sub = bitarray(pat, endian=endian)
            # Non-overlapping model for count.
            expect_c, p = 0, 0
            while p + m <= n:
                if bits[p : p + m] == pat:
                    expect_c += 1
                    p += max(m, 1)
                else:
                    p += 1
            if m == 0:
                expect_c = n + 1
            assert a.count(sub) == expect_c, (trial, bits, pat)
            # Overlapping model for search.
            if m:
                expect_s = [p for p in range(n - m + 1) if bits[p : p + m] == pat]
            else:
                expect_s = list(range(n + 1))
            assert list(a.search(sub)) == expect_s, (trial, bits, pat)
            assert list(a.search(sub, right=True)) == expect_s[::-1]
            lo = rng.randint(-n - 3, n + 3)
            hi = rng.randint(-n - 3, n + 3)
            lloc = max(0, min(n, lo + n if lo < 0 else lo))
            hloc = max(0, min(n, hi + n if hi < 0 else hi))
            if hloc < lloc:
                expect = []
            elif m == 0:
                # Empty pattern matches every position lloc..hloc inclusive.
                expect = list(range(lloc, hloc + 1))
            else:
                win = bits[lloc:hloc]
                expect = [p + lloc for p in range(len(win) - m + 1) if win[p : p + m] == pat]
            assert list(a.search(sub, lo, hi)) == expect
