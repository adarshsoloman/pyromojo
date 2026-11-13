"""Phase 1C native tests: append, extend, insert, delete, concat, compare.

Mirrors `tests/python_compat/test_mutation_oracle.py` case-for-case: every
expected value below was captured from `bitarray==3.12.3` probe runs.
Covers both endiannesses, boundary lengths
(0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65), storage invariants after every
mutation, and failure atomicity.
"""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises, assert_true

from mojo_bitarray import BitArray, ENDIAN_BIG, ENDIAN_LITTLE, bytes_for_bits


def assert_padding_zero(a: BitArray) raises:
    var pad = a.padbits()
    if pad == 0 or len(a.buffer) == 0:
        return
    var last = a.buffer[len(a.buffer) - 1]
    if a.big_endian:
        assert_equal(last & ((UInt8(1) << UInt8(pad)) - UInt8(1)), UInt8(0))
    else:
        assert_equal(last >> UInt8(8 - pad), UInt8(0))


def assert_invariants(a: BitArray, big_endian: Bool) raises:
    assert_equal(a.big_endian, big_endian)
    assert_equal(len(a.buffer), a.nbytes())
    assert_equal(a.nbytes(), bytes_for_bits(len(a)))
    assert_equal(a.padbits(), (8 - len(a) % 8) % 8)
    assert_padding_zero(a)


def test_append() raises:
    for big in [True, False]:
        var c = BitArray(String(""), big)
        c.append(1)
        assert_equal(c.to01(), String("1"))
        c.append(0)
        c.append(True)
        c.append(False)
        assert_equal(c.to01(), String("1010"))
        assert_equal(len(c), 4)
        assert_invariants(c, big)
    var d = BitArray(String("10"), ENDIAN_BIG)
    with assert_raises(contains="0 or 1"):
        d.append(2)
    with assert_raises(contains="0 or 1"):
        d.append(-1)
    assert_equal(d.to01(), String("10"))


def test_append_boundaries() raises:
    var sizes = List[Int]()
    for n in [0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65]:
        sizes.append(n)
    for i in range(len(sizes)):
        var n = sizes[i]
        for big in [True, False]:
            var text = String("")
            for _ in range(n):
                text += "0"
            var c = BitArray(text, big)
            var before = len(c.buffer)
            c.append(1)
            assert_equal(len(c), n + 1)
            assert_equal(c.nbytes(), (n + 8) // 8)
            assert_equal(c[-1], 1)
            assert_equal(c.to01(), text + String("1"))
            assert_invariants(c, big)
            # A new byte appears exactly at byte boundaries.
            assert_equal(len(c.buffer), before + (1 if n % 8 == 0 else 0))


def test_extend() raises:
    for big in [True, False]:
        var c = BitArray(String("10"), big)
        c.extend(String("11"))
        assert_equal(c.to01(), String("1011"))
        var two = List[Int]()
        two.append(0)
        two.append(1)
        c.extend(two)
        assert_equal(c.to01(), String("101101"))
        var tb = List[Bool]()
        tb.append(True)
        tb.append(False)
        c.extend(tb)
        assert_equal(c.to01(), String("10110110"))
        c.extend(BitArray(String("11"), not big))
        assert_equal(c.to01(), String("1011011011"))
        assert_equal(c.endian(), String("big") if big else String("little"))
        c.extend(List[Int]())
        c.extend(String(""))
        c.extend(BitArray(String(""), big))
        assert_equal(c.to01(), String("1011011011"))
        assert_invariants(c, big)


def test_extend_self_and_cross_endian() raises:
    var c = BitArray(String("101"), ENDIAN_BIG)
    c.extend(c.tolist())
    assert_equal(c.to01(), String("101101"))
    # Same-value extension. Mojo's borrow checker rejects `d.extend(d)`
    # (mut + imm alias), so the caller snapshots; the observable result
    # matches the reference `c.extend(c)`. The implementation snapshots
    # again internally as defense in depth.
    var d = BitArray(String("101"), ENDIAN_BIG)
    d.extend(d[:])
    assert_equal(d.to01(), String("101101"))
    assert_invariants(d, ENDIAN_BIG)
    var x = BitArray(String("10"), ENDIAN_BIG)
    x.extend(BitArray(String("11"), ENDIAN_LITTLE))
    assert_equal(x.to01(), String("1011"))
    assert_equal(x.endian(), String("big"))
    assert_invariants(x, ENDIAN_BIG)


def test_extend_rejects_atomically() raises:
    var c = BitArray(String("10"), ENDIAN_BIG)
    var bad = List[Int]()
    bad.append(1)
    bad.append(2)
    bad.append(1)
    with assert_raises(contains="0 or 1"):
        c.extend(bad)
    assert_equal(c.to01(), String("10"))
    with assert_raises(contains="expected"):
        c.extend(String("12"))
    assert_equal(c.to01(), String("10"))
    assert_invariants(c, ENDIAN_BIG)


def test_insert() raises:
    var setups = List[String]()
    setups.append(String(""))
    setups.append(String(""))
    setups.append(String(""))
    setups.append(String("101"))
    setups.append(String("101"))
    setups.append(String("101"))
    setups.append(String("101"))
    setups.append(String("101"))
    setups.append(String("101"))
    var idxs = List[Int]()
    idxs.append(0)
    idxs.append(5)
    idxs.append(-5)
    idxs.append(0)
    idxs.append(3)
    idxs.append(100)
    idxs.append(-100)
    idxs.append(-1)
    idxs.append(-3)
    var vals = List[Int]()
    for _ in range(9):
        vals.append(1)
    vals[3] = 0
    vals[8] = 0
    var expected = List[String]()
    expected.append(String("1"))
    expected.append(String("1"))
    expected.append(String("1"))
    expected.append(String("0101"))
    expected.append(String("1011"))
    expected.append(String("1011"))
    expected.append(String("1101"))
    expected.append(String("1011"))
    expected.append(String("0101"))
    for big in [True, False]:
        for k in range(9):
            var c = BitArray(setups[k], big)
            c.insert(idxs[k], vals[k])
            assert_equal(c.to01(), expected[k])
            assert_equal(c.endian(), String("big") if big else String("little"))
            assert_invariants(c, big)
    var d = BitArray(String("101"), ENDIAN_BIG)
    d.insert(1, True)
    assert_equal(d.to01(), String("1101"))
    with assert_raises(contains="0 or 1"):
        d.insert(1, 2)
    assert_equal(d.to01(), String("1101"))
    assert_invariants(d, ENDIAN_BIG)


def test_delete() raises:
    var setups = List[String]()
    setups.append(String("101"))
    setups.append(String("101"))
    setups.append(String("101"))
    setups.append(String("101"))
    setups.append(String("101"))
    setups.append(String("1"))
    setups.append(String("10110011"))
    setups.append(String("10110011"))
    var idxs = List[Int]()
    idxs.append(0)
    idxs.append(2)
    idxs.append(1)
    idxs.append(-1)
    idxs.append(-3)
    idxs.append(0)
    idxs.append(7)
    idxs.append(0)
    var expected = List[String]()
    expected.append(String("01"))
    expected.append(String("10"))
    expected.append(String("11"))
    expected.append(String("10"))
    expected.append(String("01"))
    expected.append(String(""))
    expected.append(String("1011001"))
    expected.append(String("0110011"))
    for big in [True, False]:
        for k in range(8):
            var c = BitArray(setups[k], big)
            c.delete(idxs[k])
            assert_equal(c.to01(), expected[k])
            assert_equal(c.endian(), String("big") if big else String("little"))
            assert_invariants(c, big)
    for bad in [3, -4, 100, -100]:
        var e = BitArray(String("101"), ENDIAN_BIG)
        with assert_raises(contains="assignment index out of range"):
            e.delete(bad)
        assert_equal(e.to01(), String("101"))
    var empty = BitArray(String(""), ENDIAN_BIG)
    with assert_raises(contains="assignment index out of range"):
        empty.delete(0)


def test_concat() raises:
    # (left, left_big, right, right_big, expected, result_big)
    var lefts = List[String]()
    lefts.append(String(""))
    lefts.append(String(""))
    lefts.append(String("101"))
    lefts.append(String("10"))
    lefts.append(String("11"))
    lefts.append(String("101"))
    lefts.append(String("1111111"))
    var lb = List[Bool]()
    lb.append(True)
    lb.append(True)
    lb.append(False)
    lb.append(True)
    lb.append(False)
    lb.append(True)
    lb.append(False)
    var rights = List[String]()
    rights.append(String(""))
    rights.append(String("101"))
    rights.append(String(""))
    rights.append(String("11"))
    rights.append(String("10"))
    rights.append(String("01010"))
    rights.append(String("0"))
    var rb = List[Bool]()
    rb.append(False)
    rb.append(True)
    rb.append(True)
    rb.append(False)
    rb.append(True)
    rb.append(True)
    rb.append(False)
    var expected = List[String]()
    expected.append(String(""))
    expected.append(String("101"))
    expected.append(String("101"))
    expected.append(String("1011"))
    expected.append(String("1110"))
    expected.append(String("10101010"))
    expected.append(String("11111110"))
    for k in range(7):
        var a = BitArray(lefts[k], lb[k])
        var b = BitArray(rights[k], rb[k])
        var c = a + b
        assert_equal(c.to01(), expected[k])
        assert_equal(c.big_endian, lb[k])
        # Operands untouched; result storage independent.
        assert_equal(a.to01(), lefts[k])
        assert_equal(b.to01(), rights[k])
        assert_invariants(c, lb[k])
        if len(c) > 0:
            var first = c[0]
            c[0] = 1 - first
            assert_equal(a.to01(), lefts[k])
            assert_invariants(c, lb[k])
    var s = BitArray(String("101"), ENDIAN_BIG)
    assert_equal((s + s).to01(), String("101101"))
    assert_equal(s.to01(), String("101"))


def test_iadd() raises:
    var a = BitArray(String("10"), ENDIAN_BIG)
    a += BitArray(String("11"), ENDIAN_LITTLE)
    assert_equal(a.to01(), String("1011"))
    assert_equal(a.endian(), String("big"))
    assert_invariants(a, ENDIAN_BIG)
    a += a[:]
    assert_equal(a.to01(), String("10111011"))
    assert_invariants(a, ENDIAN_BIG)


def test_equality() raises:
    for big in [True, False]:
        var x = BitArray(String("101"), big)
        assert_true(x == BitArray(String("101"), big))
        assert_true(not (x != BitArray(String("101"), big)))
    # Cross-endian logical equality.
    var be = BitArray(String("101"), ENDIAN_BIG)
    var le = BitArray(String("101"), ENDIAN_LITTLE)
    assert_true(be == le)
    assert_true(not (be != le))
    # Different lengths and different bits compare unequal.
    assert_true(BitArray(String("10"), ENDIAN_BIG) != BitArray(String("101"), ENDIAN_BIG))
    assert_true(BitArray(String("10"), ENDIAN_BIG) != BitArray(String("11"), ENDIAN_BIG))
    assert_true(not (BitArray(String("10"), ENDIAN_BIG) == BitArray(String("101"), ENDIAN_BIG)))
    assert_true(BitArray(String(""), ENDIAN_BIG) == BitArray(String(""), ENDIAN_LITTLE))
    assert_true(BitArray(String(""), ENDIAN_BIG) != BitArray(String("0"), ENDIAN_BIG))
    # Same logical bits built different ways: equal and byte-identical.
    var via_str = BitArray(String("10110011"), ENDIAN_BIG)
    var via_slice = BitArray(String("0101100110"), ENDIAN_BIG)[1:9]
    assert_true(via_str == via_slice)
    assert_equal(via_str.buffer[0], via_slice.buffer[0])
    # Copies compare equal.
    var orig = BitArray(String("10101"), ENDIAN_LITTLE)
    var copied = BitArray(orig.buffer.copy(), orig.length, orig.big_endian)
    assert_true(orig == copied)


def test_ordering() raises:
    assert_true(BitArray(String("10"), ENDIAN_BIG) < BitArray(String("11"), ENDIAN_BIG))
    assert_true(not (BitArray(String("11"), ENDIAN_BIG) < BitArray(String("10"), ENDIAN_BIG)))
    assert_true(BitArray(String(""), ENDIAN_BIG) < BitArray(String("0"), ENDIAN_BIG))
    assert_true(BitArray(String("101"), ENDIAN_BIG) < BitArray(String("1010"), ENDIAN_BIG))
    assert_true(not (BitArray(String("1010"), ENDIAN_BIG) < BitArray(String("101"), ENDIAN_BIG)))
    assert_true(BitArray(String("10"), ENDIAN_BIG) <= BitArray(String("10"), ENDIAN_BIG))
    assert_true(BitArray(String("10"), ENDIAN_BIG) >= BitArray(String("10"), ENDIAN_BIG))
    assert_true(BitArray(String("11"), ENDIAN_BIG) > BitArray(String("10"), ENDIAN_BIG))
    assert_true(not (BitArray(String("10"), ENDIAN_LITTLE) >= BitArray(String("11"), ENDIAN_LITTLE)))
    # Cross-endian ordering follows logical bits.
    assert_true(BitArray(String("10"), ENDIAN_BIG) < BitArray(String("11"), ENDIAN_LITTLE))
    assert_true(BitArray(String("101"), ENDIAN_BIG) <= BitArray(String("101"), ENDIAN_LITTLE))
    assert_true(not (BitArray(String("101"), ENDIAN_LITTLE) > BitArray(String("101"), ENDIAN_BIG)))
    # Equal arrays satisfy all non-strict relations.
    for big in [True, False]:
        var a = BitArray(String("10110"), big)
        var b = BitArray(String("10110"), not big)
        assert_true(a <= b)
        assert_true(a >= b)
        assert_true(not (a < b))
        assert_true(not (a > b))


def test_mutation_sequences() raises:
    # Scripted cross-operation sequence; every expected string below was
    # confirmed against the reference oracle before encoding here.
    for big in [True, False]:
        var a = BitArray(String(""), big)
        a.append(1)
        a.append(0)
        a.extend(String("11"))
        assert_equal(a.to01(), String("1011"))
        a.insert(1, 0)
        assert_equal(a.to01(), String("10011"))
        a.delete(-1)
        assert_equal(a.to01(), String("1001"))
        var b = a + BitArray(String("10"), not big)
        assert_equal(b.to01(), String("100110"))
        assert_equal(b.big_endian, big)
        b += b[:]
        assert_equal(b.to01(), String("100110100110"))
        assert_invariants(a, big)
        assert_invariants(b, big)
    # Boundary sweep: grow 8 -> 9 -> 8 and 9 -> 8 -> 9.
    for big in [True, False]:
        var e = BitArray(String("10110011"), big)
        e.delete(0)
        assert_equal(e.to01(), String("0110011"))
        assert_equal(len(e.buffer), 1)
        e.append(1)
        assert_equal(e.to01(), String("01100111"))
        assert_equal(len(e.buffer), 1)
        e.delete(0)
        e.delete(0)
        assert_equal(len(e.buffer), 1)
        e.append(0)
        e.append(1)
        assert_equal(len(e), 8)
        assert_equal(len(e.buffer), 1)
        assert_invariants(e, big)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
