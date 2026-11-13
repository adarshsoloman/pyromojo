"""Pin bitarray==3.12.3 mutation semantics the Mojo port must match.

Phase 1C oracle: append, extend, insert, delete (via ``del``), concat
(``+``/``+=``), equality and ordering. The native Mojo tests mirror
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


def test_no_delete_method() -> None:
    # Deletion is spelled ``del a[i]`` / ``del a[i:j]`` in the reference;
    # there is no ``.delete`` method. The Mojo port therefore exposes a
    # ``delete(i)`` method carrying the ``__delitem__`` semantics below.
    assert not hasattr(bitarray, "delete")


@pytest.mark.parametrize("endian", ENDIANS)
def test_append(endian: str) -> None:
    c = bitarray(endian=endian)
    c.append(1)
    assert c.to01() == "1"
    c.append(0)
    c.append(True)
    c.append(False)
    assert c.to01() == "1010"
    assert len(c) == 4
    assert c.endian == endian


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize("n", [0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65])
def test_append_boundaries(endian: str, n: int) -> None:
    c = bitarray("0" * n, endian=endian)
    c.append(1)
    assert len(c) == n + 1
    assert c.nbytes == (n + 8) // 8
    assert c[-1] == 1
    assert c.to01() == "0" * n + "1"


@pytest.mark.parametrize("bad", [2, -1, 9])
def test_append_rejects(bad: int) -> None:
    c = bitarray("10")
    with pytest.raises(ValueError, match="bit must be 0 or 1"):
        c.append(bad)
    assert c.to01() == "10"


@pytest.mark.parametrize("bad", [1.0, "1", None, [1]])
def test_append_rejects_type(bad: object) -> None:
    with pytest.raises(TypeError):
        bitarray("10").append(bad)


@pytest.mark.parametrize("endian", ENDIANS)
def test_extend(endian: str) -> None:
    c = bitarray("10", endian=endian)
    c.extend("11")
    assert c.to01() == "1011"
    c.extend([0, True])
    assert c.to01() == "101101"
    c.extend(bitarray("00"))
    assert c.to01() == "10110100"
    c.extend([])
    c.extend("")
    c.extend(bitarray(""))
    assert c.to01() == "10110100"
    assert c.endian == endian


def test_extend_cross_endian_keeps_target() -> None:
    c = bitarray("10", endian="big")
    c.extend(bitarray("11", endian="little"))
    assert c.to01() == "1011"
    assert c.endian == "big"


def test_extend_self() -> None:
    c = bitarray("101")
    c.extend(c)
    assert c.to01() == "101101"


def test_extend_rejects_atomically() -> None:
    c = bitarray("10")
    with pytest.raises(ValueError, match="bit must be 0 or 1"):
        c.extend([1, 2, 1])
    assert c.to01() == "10"
    with pytest.raises(TypeError):
        c.extend(5)
    assert c.to01() == "10"


INSERT_CASES = [
    ("", 0, 1, "1"),
    ("", 5, 1, "1"),
    ("", -5, 1, "1"),
    ("101", 0, 0, "0101"),
    ("101", 3, 1, "1011"),
    ("101", 100, 1, "1011"),
    ("101", -100, 1, "1101"),
    ("101", -1, 1, "1011"),
    ("101", -3, 0, "0101"),
    ("101", 1, True, "1101"),
]


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize(("setup", "index", "value", "expected"), INSERT_CASES)
def test_insert(endian: str, setup: str, index: int, value: int, expected: str) -> None:
    c = bitarray(setup, endian=endian)
    c.insert(index, value)
    assert c.to01() == expected
    assert c.endian == endian


def test_insert_rejects_atomically() -> None:
    c = bitarray("101")
    with pytest.raises(ValueError, match="bit must be 0 or 1"):
        c.insert(1, 2)
    assert c.to01() == "101"
    with pytest.raises(TypeError):
        c.insert(1, "1")
    assert c.to01() == "101"
    with pytest.raises(TypeError):
        c.insert(1.0, 1)


DELETE_CASES = [
    ("101", 0, "01"),
    ("101", 2, "10"),
    ("101", 1, "11"),
    ("101", -1, "10"),
    ("101", -3, "01"),
    ("1", 0, ""),
    ("10110011", 7, "1011001"),
    ("10110011", 0, "0110011"),
]


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize(("setup", "index", "expected"), DELETE_CASES)
def test_delete(endian: str, setup: str, index: int, expected: str) -> None:
    c = bitarray(setup, endian=endian)
    del c[index]
    assert c.to01() == expected
    assert c.endian == endian


@pytest.mark.parametrize("index", [3, -4, 100, -100])
def test_delete_rejects(index: int) -> None:
    c = bitarray("101")
    with pytest.raises(IndexError, match="bitarray assignment index out of range"):
        del c[index]
    assert c.to01() == "101"
    with pytest.raises(IndexError):
        del bitarray("")[0]


CONCAT_CASES = [
    # (left, left_endian, right, right_endian, expected, result_endian)
    ("", "big", "", "little", "", "big"),
    ("", "big", "101", "big", "101", "big"),
    ("101", "little", "", "big", "101", "little"),
    ("10", "big", "11", "little", "1011", "big"),
    ("11", "little", "10", "big", "1110", "little"),
    ("101", "big", "01010", "big", "10101010", "big"),
    ("1111111", "little", "0", "little", "11111110", "little"),
]


@pytest.mark.parametrize(
    ("left", "left_endian", "right", "right_endian", "expected", "result_endian"),
    CONCAT_CASES,
)
def test_concat(
    left: str,
    left_endian: str,
    right: str,
    right_endian: str,
    expected: str,
    result_endian: str,
) -> None:
    a = bitarray(left, endian=left_endian)
    b = bitarray(right, endian=right_endian)
    c = a + b
    assert c.to01() == expected
    assert c.endian == result_endian
    # Operands are untouched and storage is independent.
    assert a.to01() == left
    assert b.to01() == right
    if len(c):
        c[0] = 1 - c[0]
        assert a.to01() == left


def test_concat_self() -> None:
    a = bitarray("101")
    assert (a + a).to01() == "101101"
    assert a.to01() == "101"


def test_iadd() -> None:
    a = bitarray("10", endian="big")
    a += bitarray("11", endian="little")
    assert a.to01() == "1011"
    assert a.endian == "big"
    a += a
    assert a.to01() == "10111011"


def test_equality() -> None:
    assert bitarray("101") == bitarray("101")
    assert bitarray("101", endian="big") == bitarray("101", endian="little")
    assert (bitarray("101") != bitarray("101")) is False
    assert bitarray("") == bitarray("")
    assert bitarray("10") != bitarray("101")
    assert bitarray("10") != bitarray("11")
    assert bitarray("") != bitarray("0")
    # Non-bitarray operands compare False/True, never raise.
    assert (bitarray("101") == "101") is False
    assert (bitarray("101") != "101") is True
    assert (bitarray("101") == 5) is False
    assert (bitarray("") == "") is False


def test_ordering() -> None:
    assert bitarray("10") < bitarray("11")
    assert not (bitarray("11") < bitarray("10"))
    assert bitarray("") < bitarray("0")
    assert bitarray("101") < bitarray("1010")
    assert not (bitarray("1010") < bitarray("101"))
    assert bitarray("10") <= bitarray("10")
    assert bitarray("10") >= bitarray("10")
    assert bitarray("11") > bitarray("10")
    assert bitarray("10", endian="big") < bitarray("11", endian="little")
    assert bitarray("101", endian="big") <= bitarray("101", endian="little")
    with pytest.raises(TypeError):
        assert bitarray("10") < "11"
    with pytest.raises(TypeError):
        assert bitarray("10") < 5


def test_mutation_fuzz_against_list_model() -> None:
    rng = random.Random(20260601)
    for trial in range(200):
        for endian in ENDIANS:
            model = [rng.choice((0, 1)) for _ in range(rng.randrange(10))]
            a = bitarray(model, endian=endian)
            for _ in range(rng.randrange(1, 15)):
                op = rng.choice(["append", "insert", "delete", "extend", "concat"])
                if op == "append":
                    v = rng.choice((0, 1))
                    model.append(v)
                    a.append(v)
                elif op == "insert":
                    pos = rng.randint(-len(model) - 3, len(model) + 3)
                    v = rng.choice((0, 1))
                    model.insert(max(0, min(len(model), pos + len(model) if pos < 0 else pos)), v)
                    a.insert(pos, v)
                elif op == "delete" and model:
                    pos = rng.randrange(-len(model), len(model))
                    del model[pos]
                    del a[pos]
                elif op == "extend":
                    add = [rng.choice((0, 1)) for _ in range(rng.randrange(5))]
                    model.extend(add)
                    a.extend(add)
                else:
                    add = [rng.choice((0, 1)) for _ in range(rng.randrange(5))]
                    model = model + add
                    a = a + bitarray(add)
                assert a.tolist() == model, (trial, endian, op)
                assert a.endian == endian
