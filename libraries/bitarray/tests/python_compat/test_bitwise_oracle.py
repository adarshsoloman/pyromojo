"""Pin bitarray==3.12.3 bitwise/shift semantics the Mojo port must match.

Phase 1D1 oracle: AND/OR/XOR/NOT, in-place variants, left/right shifts
and in-place shifts. The native Mojo tests mirror these exact
expectations.
"""

from __future__ import annotations

import random

import pytest

from bitarray import bitarray

ENDIANS = ["big", "little"]


def test_pinned_version() -> None:
    import bitarray as mod

    assert mod.__version__ == "3.12.3"


def truth_table(op: str, x: str, y: str, endian: str) -> str:
    a, b = bitarray(x, endian=endian), bitarray(y, endian=endian)
    if op == "and":
        return (a & b).to01()
    if op == "or":
        return (a | b).to01()
    return (a ^ b).to01()


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize(
    ("x", "y"),
    [
        ("0000", "0000"),
        ("1111", "1111"),
        ("1010", "0101"),
        ("1010", "1100"),
        ("1010", "1010"),
        ("", ""),
        ("0", "1"),
        ("1010101", "0101010"),
    ],
)
def test_bitwise_truth(endian: str, x: str, y: str) -> None:
    assert truth_table("and", x, y, endian) == "".join(
        "1" if a == "1" and b == "1" else "0" for a, b in zip(x, y, strict=True)
    )
    assert truth_table("or", x, y, endian) == "".join(
        "1" if a == "1" or b == "1" else "0" for a, b in zip(x, y, strict=True)
    )
    assert truth_table("xor", x, y, endian) == "".join(
        "1" if a != b else "0" for a, b in zip(x, y, strict=True)
    )


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize("text", ["", "0", "1", "1010", "1010101", "11111111", "00000000"])
def test_invert(endian: str, text: str) -> None:
    a = bitarray(text, endian=endian)
    assert (~a).to01() == "".join("0" if c == "1" else "1" for c in text)
    assert (~a).endian == endian
    assert len(~a) == len(a)


def test_bitwise_length_rule() -> None:
    with pytest.raises(ValueError, match="equal length"):
        bitarray("1010") & bitarray("110")
    with pytest.raises(ValueError, match="equal length"):
        bitarray("1010") | bitarray("")
    with pytest.raises(ValueError, match="equal length"):
        bitarray("") ^ bitarray("1")
    # Empty & empty is legal.
    assert (bitarray("") & bitarray("")).to01() == ""


def test_bitwise_endianness_rule() -> None:
    with pytest.raises(ValueError, match="equal bit-endianness"):
        bitarray("1010", endian="big") & bitarray("1010", endian="little")
    with pytest.raises(ValueError, match="equal bit-endianness"):
        bitarray("1010", endian="big") | bitarray("1010", endian="little")
    with pytest.raises(ValueError, match="equal bit-endianness"):
        bitarray("1010", endian="big") ^ bitarray("1010", endian="little")
    # Length is reported before endianness.
    with pytest.raises(ValueError, match="equal length"):
        bitarray("1010", endian="big") & bitarray("11", endian="little")
    # Result keeps the (shared) operand endianness.
    r = bitarray("1010", endian="little") & bitarray("1100", endian="little")
    assert r.endian == "little"
    r = bitarray("1010", endian="big") | bitarray("1100", endian="big")
    assert r.endian == "big"


def test_bitwise_bad_operand() -> None:
    with pytest.raises(TypeError):
        bitarray("1010") & "1100"
    with pytest.raises(TypeError):
        bitarray("1010") | 5


@pytest.mark.parametrize("op", ["and", "or", "xor"])
def test_inplace(op: str) -> None:
    a = bitarray("1010", endian="big")
    b = bitarray("1100", endian="big")
    before = id(a)
    if op == "and":
        a &= b
        assert a.to01() == "1000"
    elif op == "or":
        a |= b
        assert a.to01() == "1110"
    else:
        a ^= b
        assert a.to01() == "0110"
    assert id(a) == before
    assert a.endian == "big"
    assert b.to01() == "1100"


def test_inplace_errors_atomic() -> None:
    a = bitarray("1010")
    with pytest.raises(ValueError, match="equal length"):
        a &= bitarray("11")
    assert a.to01() == "1010"
    with pytest.raises(ValueError, match="equal bit-endianness"):
        a |= bitarray("1010", endian="little")
    assert a.to01() == "1010"


def test_inplace_self() -> None:
    a = bitarray("1010")
    a &= a
    assert a.to01() == "1010"
    a |= a
    assert a.to01() == "1010"
    a ^= a
    assert a.to01() == "0000"


SHIFT_CASES = [
    # (text, count, left_expected, right_expected)
    ("101100", 0, "101100", "101100"),
    ("101100", 1, "011000", "010110"),
    ("101100", 2, "110000", "001011"),
    ("101100", 5, "000000", "000001"),
    ("101100", 6, "000000", "000000"),
    ("101100", 100, "000000", "000000"),
    ("", 3, "", ""),
    ("1", 0, "1", "1"),
    ("1", 1, "0", "0"),
    ("0", 5, "0", "0"),
    ("10110011", 2, "11001100", "00101100"),
    ("10110011", 3, "10011000", "00010110"),
    ("10110011", 7, "10000000", "00000001"),
    ("10110011", 8, "00000000", "00000000"),
    ("1111111", 3, "1111000", "0001111"),
    ("10000001", 1, "00000010", "01000000"),
]


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize(("text", "count", "want_left", "want_right"), SHIFT_CASES)
def test_shifts(endian: str, text: str, count: int, want_left: str, want_right: str) -> None:
    assert (bitarray(text, endian=endian) << count).to01() == want_left
    assert (bitarray(text, endian=endian) >> count).to01() == want_right


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize("count", [-1, -100])
def test_shift_negative(endian: str, count: int) -> None:
    with pytest.raises(ValueError, match="negative shift count"):
        bitarray("101100", endian=endian) << count
    with pytest.raises(ValueError, match="negative shift count"):
        bitarray("101100", endian=endian) >> count


def test_shift_bad_type() -> None:
    with pytest.raises(TypeError):
        bitarray("101100") << 1.5
    with pytest.raises(TypeError):
        bitarray("101100") >> "2"


def test_shift_inplace() -> None:
    a = bitarray("101100", endian="big")
    before = id(a)
    a <<= 2
    assert a.to01() == "110000"
    assert id(a) == before
    a >>= 1
    assert a.to01() == "011000"
    assert a.endian == "big"
    with pytest.raises(ValueError, match="negative shift count"):
        a <<= -1
    assert a.to01() == "011000"


def test_shift_returns_new_object() -> None:
    a = bitarray("101100")
    b = a << 2
    assert b.to01() == "110000"
    assert a.to01() == "101100"
    assert b is not a


def test_bitwise_fuzz_against_model() -> None:
    rng = random.Random(20260602)
    for _trial in range(200):
        for endian in ENDIANS:
            n = rng.choice([0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65])
            xs = "".join(rng.choice("01") for _ in range(n))
            ys = "".join(rng.choice("01") for _ in range(n))
            a, b = bitarray(xs, endian=endian), bitarray(ys, endian=endian)
            assert (a & b).tolist() == [x & y for x, y in zip(a.tolist(), b.tolist(), strict=True)]
            assert (a | b).tolist() == [x | y for x, y in zip(a.tolist(), b.tolist(), strict=True)]
            assert (a ^ b).tolist() == [x ^ y for x, y in zip(a.tolist(), b.tolist(), strict=True)]
            assert (~a).tolist() == [1 - x for x in a.tolist()]
            k = rng.choice([0, 1, 2, 7, 8, 9, 15, 16, 63, 64, 65, 100])
            # Exact model: drop-first-k, zero-fill, truncate to n.
            assert (a << k).tolist() == (a.tolist()[k:] + [0] * k)[:n]
            assert (a >> k).tolist() == ([0] * k + a.tolist())[:n]


def test_bitwise_result_independence() -> None:
    a = bitarray("1010")
    b = bitarray("1100")
    c = a & b
    c[0] = 1 - c[0]
    assert a.to01() == "1010"
    assert b.to01() == "1100"
    d = ~a
    d[0] = 1 - d[0]
    assert a.to01() == "1010"
