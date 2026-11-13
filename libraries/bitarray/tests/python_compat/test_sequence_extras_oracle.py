"""Pin bitarray==3.12.3 reverse/fill/copy/rotate/find/index semantics.

Phase 1D3 oracle: in-place reversal, byte-boundary fill with counts,
independent copies, in-place rotation, first/rightmost search with -1 on
miss, and index with ValueError on miss. The native Mojo tests mirror
these exact expectations.
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
    ("text", "expected"),
    [("", ""), ("1", "1"), ("10110011", "11001101"), ("10000", "00001")],
)
def test_reverse(endian: str, text: str, expected: str) -> None:
    c = bitarray(text, endian=endian)
    assert c.reverse() is None
    assert c.to01() == expected
    assert c.endian == endian
    assert len(c) == len(text)


def test_reverse_double_is_identity() -> None:
    rng = random.Random(20260604)
    for endian in ENDIANS:
        for _ in range(50):
            n = rng.randrange(66)
            text = "".join(rng.choice("01") for _ in range(n))
            c = bitarray(text, endian=endian)
            c.reverse()
            c.reverse()
            assert c.to01() == text


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize(
    ("text", "m", "expected", "added"),
    [
        ("", 8, "", 0),
        ("10110011", 8, "10110011", 0),
        ("10110", 8, "10110000", 3),
        ("1", 8, "10000000", 7),
        ("10110", 1, "10110", 0),
        ("10110", 16, "1011000000000000", 11),
        ("101", 3, "101", 0),
        ("1011", 3, "101100", 2),
    ],
)
def test_fill(endian: str, text: str, m: int, expected: str, added: int) -> None:
    c = bitarray(text, endian=endian)
    assert c.fill(m) == added
    assert c.to01() == expected
    assert c.endian == endian
    assert len(c) == len(expected)
    assert c.nbytes == (len(expected) + 7) // 8


def test_fill_bad_m() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        bitarray("101").fill(0)
    with pytest.raises(ValueError, match="positive integer"):
        bitarray("101").fill(-3)
    with pytest.raises(TypeError):
        bitarray("101").fill("8")
    with pytest.raises(TypeError):
        bitarray("101").fill(m=8)


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize("text", ["", "1", "10110", "10110011", "1" * 65])
def test_copy(endian: str, text: str) -> None:
    c = bitarray(text, endian=endian)
    d = c.copy()
    assert type(d) is bitarray
    assert d is not c
    assert d.to01() == text
    assert d.endian == endian
    if len(d):
        d[0] = 1 - d[0]
        assert c.to01() == text


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize(
    ("text", "k", "expected"),
    [
        ("10110011", 1, "11011001"),
        ("10110011", 0, "10110011"),
        ("10110011", 2, "11101100"),
        ("10110011", -2, "11001110"),
        ("10110011", 8, "10110011"),
        ("10110011", 10, "11101100"),
        ("10110011", -10, "11001110"),
        ("", 3, ""),
        ("1", 5, "1"),
        ("10110", 3, "11010"),
        ("10110", -7, "11010"),
    ],
)
def test_rotate(endian: str, text: str, k: int, expected: str) -> None:
    c = bitarray(text, endian=endian)
    assert c.rotate(k) is None
    assert c.to01() == expected
    assert c.endian == endian
    assert len(c) == len(text)


def test_rotate_bad_k() -> None:
    with pytest.raises(TypeError):
        bitarray("101").rotate("2")
    with pytest.raises(TypeError):
        bitarray("101").rotate(2.0)
    with pytest.raises(TypeError):
        bitarray("101").rotate(k=2)


def test_rotate_roundtrip() -> None:
    rng = random.Random(20260605)
    for endian in ENDIANS:
        for _ in range(50):
            n = rng.randrange(1, 66)
            text = "".join(rng.choice("01") for _ in range(n))
            k = rng.randrange(-3 * n - 5, 3 * n + 5)
            c = bitarray(text, endian=endian)
            c.rotate(k)
            c.rotate(-k)
            assert c.to01() == text


def test_find() -> None:
    a = bitarray("10101")
    assert a.find(bitarray("101")) == 0
    assert a.find(bitarray("1")) == 0
    assert a.find(bitarray("0")) == 1
    assert a.find(bitarray("1111")) == -1
    assert bitarray("10").find(bitarray("10101")) == -1
    assert bitarray("101").find(bitarray("")) == 0
    assert bitarray("").find(bitarray("")) == 0
    assert bitarray("").find(bitarray("1")) == -1
    assert a.find(1) == 0
    assert a.find(True) == 0
    assert a.find(False) == 1
    with pytest.raises(ValueError, match="bit must be 0 or 1"):
        a.find(9)
    with pytest.raises(TypeError):
        a.find("101")


def test_find_bounds() -> None:
    a = bitarray("10101")
    assert a.find(bitarray("101"), 1, 5) == 2
    assert a.find(bitarray("1"), -4, -1) == 2
    assert a.find(bitarray("1"), -100, 100) == 0
    assert a.find(bitarray("1"), 4, 1) == -1
    assert a.find(bitarray(""), 1, 5) == 1
    assert a.find(bitarray(""), 4, 1) == -1


def test_find_right() -> None:
    a = bitarray("10101")
    assert a.find(bitarray("101"), right=True) == 2
    assert a.find(bitarray("1"), right=True) == 4
    assert a.find(bitarray("1111"), right=True) == -1
    assert a.find(bitarray("1"), 1, 4, right=True) == 2
    assert a.find(bitarray(""), 1, 5, right=True) == 5
    b = bitarray("10101", endian="little")
    assert b.find(bitarray("101", endian="big")) == 0
    assert b.find(bitarray("101", endian="big"), right=True) == 2


def test_index() -> None:
    a = bitarray("10101")
    assert a.index(bitarray("101")) == 0
    assert a.index(0) == 1
    assert a.index(True) == 0
    assert a.index(bitarray(""), 1, 5) == 1
    with pytest.raises(ValueError, match=r"bitarray\('1111'\) not in bitarray"):
        a.index(bitarray("1111"))
    with pytest.raises(ValueError, match="0 not in bitarray"):
        bitarray("111").index(0)
    with pytest.raises(ValueError, match="bit must be 0 or 1"):
        a.index(9)
    with pytest.raises(TypeError):
        a.index("101")
    assert a.index(bitarray("1"), right=True) == 4


def test_find_index_fuzz() -> None:
    rng = random.Random(20260606)
    for _trial in range(200):
        for endian in ENDIANS:
            n = rng.choice([0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65])
            bits = [rng.choice((0, 1)) for _ in range(n)]
            a = bitarray(bits, endian=endian)
            m = rng.randrange(min(n + 2, 6))
            pat = [rng.choice((0, 1)) for _ in range(m)]
            sub = bitarray(pat, endian="little" if endian == "big" else "big")
            lo = rng.randint(-n - 3, n + 3)
            hi = rng.randint(-n - 3, n + 3)
            # Slice-clamped window for search ...
            sloc = max(0, min(n, lo + n if lo < 0 else lo))
            shoc = max(0, min(n, hi + n if hi < 0 else hi))
            # ... but find/index/sub-count do NOT clamp start above.
            lloc = max(0, lo + n if lo < 0 else lo)
            hloc = max(0, min(n, hi + n if hi < 0 else hi))
            if hloc < lloc:
                model, model_r = [], []
            elif m == 0:
                model, model_r = list(range(lloc, hloc + 1)), list(range(hloc, lloc - 1, -1))
            else:
                model = [p for p in range(lloc, hloc - m + 1) if bits[p : p + m] == pat]
                model_r = model[::-1]
            if shoc < sloc:
                smodel = []
            elif m == 0:
                smodel = list(range(sloc, shoc + 1))
            else:
                smodel = [p for p in range(sloc, shoc - m + 1) if bits[p : p + m] == pat]
            assert list(a.search(sub, lo, hi)) == smodel
            assert a.find(sub, lo, hi) == (model[0] if model else -1)
            assert a.find(sub, lo, hi, right=True) == (model_r[0] if model_r else -1)
            if m == 0:
                expect_c = hloc - lloc + 1 if hloc >= lloc else 0
            else:
                expect_c, last_end = 0, lloc
                for p in model:
                    if p >= last_end:
                        expect_c += 1
                        last_end = p + m
            assert a.count(sub, lo, hi) == expect_c
            if model:
                assert a.index(sub, lo, hi) == model[0]
            else:
                with pytest.raises(ValueError):
                    a.index(sub, lo, hi)
