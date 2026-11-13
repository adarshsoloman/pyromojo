"""Pin bitarray==3.12.3 sequence semantics the Mojo port must match.

Phase 1B oracle: construction (strings/iterables/endian), introspection,
indexing/assignment, iteration, slicing, slice assignment, ``to01`` and
``tolist``. Every behavior asserted here was observed by direct probing;
the native Mojo tests mirror these exact expectations.
"""

from __future__ import annotations

import random

import pytest

from bitarray import bitarray


def test_pinned_version() -> None:
    import bitarray as mod

    assert mod.__version__ == "3.12.3"


def test_string_construction() -> None:
    assert bitarray("101100").to01() == "101100"
    assert bitarray("").to01() == ""
    assert bitarray("0").to01() == "0"
    assert bitarray("00001111").to01() == "00001111"
    assert bitarray("1" * 65).to01() == "1" * 65
    # Whitespace and underscores are silently skipped.
    assert bitarray("1 0_1\t\r\n\x0b\x0c1").to01() == "1011"
    assert bitarray("_").to01() == ""
    assert bitarray("   ").to01() == ""


def test_string_construction_rejects() -> None:
    for bad in ("102", "abc", "1,0", "1.0", "1a"):
        with pytest.raises(ValueError):
            bitarray(bad)


def test_iterable_construction() -> None:
    assert bitarray([1, 0, 1, 1]).to01() == "1011"
    assert bitarray([True, False, True]).to01() == "101"
    assert bitarray([1, True, 0]).to01() == "110"
    assert bitarray((1, 0)).to01() == "10"
    assert bitarray(x for x in [1, 0, 1]).to01() == "101"
    assert bitarray([]).to01() == ""
    # Only 0/1 ints (bools coerce); everything else raises.
    for bad in ([2], [-1], [5]):
        with pytest.raises(ValueError):
            bitarray(bad)
    for bad in ([1.0], ["1"], [None]):
        with pytest.raises(TypeError):
            bitarray(bad)


@pytest.mark.parametrize("endian", ["big", "little"])
def test_construction_endianness(endian: str) -> None:
    a = bitarray("10000000", endian=endian)
    b = bitarray([1, 0, 0, 0, 0, 0, 0, 0], endian=endian)
    assert a.to01() == b.to01() == "10000000"
    assert a.endian == b.endian == endian
    # Same logical sequence, mirrored physical byte.
    raw = a.tobytes()
    other = bitarray("10000000", endian="little" if endian == "big" else "big")
    assert raw != other.tobytes()


def test_construction_endianness_rejects() -> None:
    with pytest.raises(ValueError):
        bitarray("101", endian="mid")


@pytest.mark.parametrize("endian", ["big", "little"])
@pytest.mark.parametrize("n", [0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65])
def test_introspection_boundaries(endian: str, n: int) -> None:
    a = bitarray("1" * n, endian=endian)
    assert len(a) == n
    assert a.nbytes == (n + 7) // 8
    assert a.padbits == (8 - n % 8) % 8
    assert a.endian == endian


def test_indexing() -> None:
    a = bitarray("101100")
    assert a[0] == 1
    assert a[2] == 1
    assert a[5] == 0
    assert a[-1] == 0
    assert a[-6] == 1
    assert type(a[0]) is int
    with pytest.raises(IndexError):
        a[6]
    with pytest.raises(IndexError):
        a[-7]
    with pytest.raises(IndexError):
        bitarray("")[0]


def test_assignment() -> None:
    b = bitarray("101100")
    b[0] = 0
    b[-1] = 1
    b[2] = 0
    assert b.to01() == "000101"
    b[0] = True
    b[1] = False
    assert b.to01() == "100101"
    assert len(b) == 6
    for bad in (2, -1, 9):
        with pytest.raises(ValueError):
            b.__setitem__(0, bad)
    for bad in (1.0, "1", None):
        with pytest.raises(TypeError):
            b.__setitem__(0, bad)
    with pytest.raises(IndexError):
        b.__setitem__(6, 1)
    with pytest.raises(IndexError):
        b.__setitem__(-7, 1)


def test_iteration_matches_conversions() -> None:
    for text in ("", "1", "10110"):
        for endian in ("big", "little"):
            a = bitarray(text, endian=endian)
            assert [x for x in a] == a.tolist()
            assert "".join(str(x) for x in a) == a.to01() == text
    assert bitarray("101").tolist() == [1, 0, 1]
    assert all(type(x) is int for x in bitarray("101").tolist())
    assert bitarray("").tolist() == []


BASE = "10110011"
SLICE_CASES = {
    (1, 4, None): "011",
    (None, 3, None): "101",
    (2, None, None): "110011",
    (-3, None, None): "011",
    (None, None, None): "10110011",
    (None, None, 2): "1101",
    (None, None, -1): "11001101",
    (4, 1, None): "",
    (100, 200, None): "",
    (-100, 2, None): "10",
    (6, 2, -1): "1001",
}


@pytest.mark.parametrize("endian", ["big", "little"])
@pytest.mark.parametrize(("bounds", "expected"), list(SLICE_CASES.items()), ids=str)
def test_slices(endian: str, bounds: tuple, expected: str) -> None:
    a = bitarray(BASE, endian=endian)
    start, stop, step = bounds
    got = a[start:stop:step]
    assert got.to01() == expected
    assert got.endian == endian


def test_slice_independence() -> None:
    a = bitarray(BASE)
    s = a[:]
    s[0] = 0
    assert a.to01() == BASE
    assert s.to01() == "00110011"


def test_slice_step_zero() -> None:
    with pytest.raises(ValueError):
        bitarray(BASE)[::0]


def test_slice_assignment_resize() -> None:
    cases = [
        ("10110011", (1, 3, None), "111", "111110011"),
        ("10110011", (2, 5, None), "0", "100011"),
        ("10110011", (1, 1, None), "101", "11010110011"),
        ("10110011", (2, 4, None), "", "100011"),
        ("101", (None, None, None), "", ""),
    ]
    for setup, bounds, repl, expected in cases:
        c = bitarray(setup)
        c[bounds[0] : bounds[1] : bounds[2]] = bitarray(repl)
        assert c.to01() == expected


def test_slice_assignment_extended() -> None:
    c = bitarray("10101")
    c[::2] = bitarray("111")
    assert c.to01() == "10101"
    c[::-1] = bitarray("11111")
    assert c.to01() == "11111"
    c = bitarray("10101")
    c[1:4:2] = bitarray("00")
    assert c.to01() == "10101"
    # Mismatch fails atomically.
    c = bitarray("10101")
    with pytest.raises(ValueError):
        c[::2] = bitarray("11")
    assert c.to01() == "10101"
    # Operands are bitarray-or-int only.
    with pytest.raises(TypeError):
        c.__setitem__(slice(1, 3), "11")
    with pytest.raises(TypeError):
        c.__setitem__(slice(1, 3), [1, 1])


def test_slice_assignment_int_broadcast() -> None:
    c = bitarray("10101")
    c[1:3] = 1
    assert c.to01() == "11101"
    c = bitarray("10001")
    c[1:4] = True
    assert c.to01() == "11111"
    c = bitarray("10001")
    c[::2] = False
    assert c.to01() == "00000"
    # Empty selection: no-op, never resize.
    c = bitarray("10101")
    c[1:1] = 1
    assert c.to01() == "10101"
    # Bad value fails atomically.
    with pytest.raises(ValueError):
        c.__setitem__(slice(1, 3), 5)
    assert c.to01() == "10101"


def test_slice_assignment_cross_endian_and_self() -> None:
    c = bitarray("10101", endian="little")
    c[1:3] = bitarray("11", endian="big")
    assert c.to01() == "11101"
    assert c.endian == "little"
    c = bitarray("10101")
    c[::2] = c[::2]
    assert c.to01() == "10101"
    c = bitarray("10101")
    c[1:3] = c
    assert c.to01() == "11010101"


def test_slice_fuzz_against_list_model() -> None:
    rng = random.Random(20260501)
    for trial in range(300):
        n = rng.randrange(12)
        text = "".join(rng.choice("01") for _ in range(n))
        for endian in ("big", "little"):
            a = bitarray(text, endian=endian)
            lo = rng.randint(-n - 3, n + 3)
            hi = rng.randint(-n - 3, n + 3)
            step = rng.choice([1, 2, 3, -1, -2])
            model = list(text)[lo:hi:step]
            assert a[lo:hi:step].to01() == "".join(str(x) for x in model), (
                trial,
                text,
                endian,
                lo,
                hi,
                step,
            )
