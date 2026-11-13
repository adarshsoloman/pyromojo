"""Phase 1B native tests: construction, indexing, iteration, slicing.

Mirrors `tests/python_compat/test_sequence_oracle.py` case-for-case: every
expected value below was captured from `bitarray==3.12.3` probe runs, never
from memory. Covers both endiannesses, boundary lengths
(0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65), storage invariants after every
mutating operation, and failure atomicity.
"""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_bitarray import (
    BitArray,
    BitArrayIter,
    ENDIAN_BIG,
    ENDIAN_LITTLE,
    bytes_for_bits,
)


def ilist2(a: Int, b: Int) -> List[Int]:
    var out = List[Int](capacity=2)
    out.append(a)
    out.append(b)
    return out^


def ilist3(a: Int, b: Int, c: Int) -> List[Int]:
    var out = List[Int](capacity=3)
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


def ilist4(a: Int, b: Int, c: Int, d: Int) -> List[Int]:
    var out = List[Int](capacity=4)
    out.append(a)
    out.append(b)
    out.append(c)
    out.append(d)
    return out^


def blist3(a: Bool, b: Bool, c: Bool) -> List[Bool]:
    var out = List[Bool](capacity=3)
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


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


def alternating(n: Int) -> String:
    var s = String("")
    for i in range(n):
        s += String("1") if i % 2 == 0 else String("0")
    return s^


def test_string_construction() raises:
    for big in [True, False]:
        assert_equal(BitArray(String(""), big).to01(), String(""))
        assert_equal(BitArray(String("0"), big).to01(), String("0"))
        assert_equal(BitArray(String("1"), big).to01(), String("1"))
        assert_equal(BitArray(String("101100"), big).to01(), String("101100"))
        assert_equal(BitArray(String("00001111"), big).to01(), String("00001111"))
        # Whitespace and underscores are skipped (reference behavior).
        assert_equal(BitArray(String("1 0_1"), big).to01(), String("101"))
        assert_equal(BitArray(String("1\t0\n1"), big).to01(), String("101"))
        assert_equal(BitArray(String("_"), big).length, 0)
        assert_equal(BitArray(String("   "), big).length, 0)
        var a = BitArray(String("101100"), big)
        assert_equal(len(a), 6)
        assert_invariants(a, big)
    with assert_raises(contains="expected"):
        _ = BitArray(String("102"), ENDIAN_BIG)
    with assert_raises(contains="expected"):
        _ = BitArray(String("abc"), ENDIAN_LITTLE)
    with assert_raises(contains="expected"):
        _ = BitArray(String("1,0"), ENDIAN_BIG)


def test_string_endianness_layout() raises:
    # Same logical sequence, mirrored physical byte (probed reference).
    var be = BitArray(String("10000000"), ENDIAN_BIG)
    var le = BitArray(String("10000000"), ENDIAN_LITTLE)
    assert_equal(be.to01(), le.to01())
    assert_equal(be.buffer[0], UInt8(0x80))
    assert_equal(le.buffer[0], UInt8(0x01))
    assert_equal(be.endian(), String("big"))
    assert_equal(le.endian(), String("little"))


def test_int_list_construction() raises:
    for big in [True, False]:
        assert_equal(BitArray(List[Int](), big).length, 0)
        assert_equal(BitArray(ilist4(1, 0, 1, 1), big).to01(), String("1011"))
        var a = BitArray(ilist4(1, 0, 1, 1), big)
        assert_invariants(a, big)
    with assert_raises(contains="0 or 1"):
        _ = BitArray(ilist2(1, 2), ENDIAN_BIG)
    with assert_raises(contains="0 or 1"):
        _ = BitArray(ilist2(-1, 0), ENDIAN_LITTLE)


def test_bool_list_construction() raises:
    for big in [True, False]:
        assert_equal(BitArray(List[Bool](), big).length, 0)
        var a = BitArray(blist3(True, False, True), big)
        assert_equal(a.to01(), String("101"))
        assert_invariants(a, big)


def test_introspection_boundaries() raises:
    var sizes = List[Int]()
    for n in [0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65]:
        sizes.append(n)
    for i in range(len(sizes)):
        var n = sizes[i]
        for big in [True, False]:
            var text = String("")
            for _ in range(n):
                text += "1"
            var a = BitArray(text, big)
            assert_equal(len(a), n)
            assert_equal(a.nbytes(), (n + 7) // 8)
            assert_equal(a.padbits(), (8 - n % 8) % 8)
            assert_equal(a.endian(), String("big") if big else String("little"))
            assert_invariants(a, big)


def test_indexing() raises:
    for big in [True, False]:
        var a = BitArray(String("101100"), big)
        assert_equal(a[0], 1)
        assert_equal(a[2], 1)
        assert_equal(a[5], 0)
        assert_equal(a[-1], 0)
        assert_equal(a[-6], 1)
        assert_equal(a[-3], 1)
    with assert_raises(contains="index out of range"):
        _ = BitArray(String("101100"), ENDIAN_BIG)[6]
    with assert_raises(contains="index out of range"):
        _ = BitArray(String("101100"), ENDIAN_BIG)[-7]
    with assert_raises(contains="index out of range"):
        _ = BitArray(String(""), ENDIAN_BIG)[0]


def test_assignment() raises:
    for big in [True, False]:
        var b = BitArray(String("101100"), big)
        b[0] = 0
        b[-1] = 1
        b[2] = 0
        assert_equal(b.to01(), String("000101"))
        # Mojo `=` syntax requires an Int RHS (matching `__getitem__`);
        # bools go through the same dunder explicitly.
        b.__setitem__(0, True)
        b.__setitem__(1, False)
        assert_equal(b.to01(), String("100101"))
        assert_equal(len(b), 6)
        assert_invariants(b, big)
    var c = BitArray(String("101"), ENDIAN_BIG)
    with assert_raises(contains="0 or 1"):
        c[0] = 2
    with assert_raises(contains="0 or 1"):
        c[0] = -1
    assert_equal(c.to01(), String("101"))
    with assert_raises(contains="assignment index out of range"):
        c[3] = 1
    with assert_raises(contains="assignment index out of range"):
        c[-4] = 1


def test_iteration() raises:
    for big in [True, False]:
        var empty = BitArray(String(""), big)
        var count = 0
        for _ in empty:
            count += 1
        assert_equal(count, 0)
        var one = BitArray(String("1"), big)
        var total = 0
        for x in one:
            total += x
        assert_equal(total, 1)
        var bits = BitArray(String("10110"), big)
        var seen = List[Int]()
        for x in bits:
            seen.append(x)
        var listed = bits.tolist()
        assert_equal(len(seen), len(listed))
        for i in range(len(seen)):
            assert_equal(seen[i], listed[i])
        var joined = String("")
        for x in bits:
            joined += String("1") if x == 1 else String("0")
        assert_equal(joined, bits.to01())
        assert_equal(joined, String("10110"))
        var it: BitArrayIter = bits.__iter__()
        assert_equal(len(it), 5)
        assert_equal(it.__next__(), 1)
        assert_equal(len(it), 4)


def test_slices_section8() raises:
    var cases = List[String]()
    cases.append(String("10110011"))
    for i in range(len(cases)):
        for big in [True, False]:
            var a = BitArray(cases[i], big)
            assert_equal(a[1:4].to01(), String("011"))
            assert_equal(a[:3].to01(), String("101"))
            assert_equal(a[2:].to01(), String("110011"))
            assert_equal(a[-3:].to01(), String("011"))
            assert_equal(a[:].to01(), String("10110011"))
            assert_equal(a[::2].to01(), String("1101"))
            assert_equal(a[::-1].to01(), String("11001101"))
            assert_equal(a[4:1].to01(), String(""))
            assert_invariants(a[1:4], big)
            assert_invariants(a[::-1], big)


def test_slice_edges() raises:
    for big in [True, False]:
        var a = BitArray(String("10110011"), big)
        assert_equal(a[100:200].to01(), String(""))
        assert_equal(a[-100:2].to01(), String("10"))
        assert_equal(a[6:2:-1].to01(), String("1001"))
        assert_equal(a[-1:].to01(), String("1"))
        # Empty source stays empty under any slice.
        var e = BitArray(String(""), big)
        assert_equal(e[:].to01(), String(""))
        assert_equal(e[::-1].to01(), String(""))
        # Slices keep endianness and own independent storage.
        var full = a[:]
        assert_equal(full.endian(), a.endian())
        full[0] = 0
        assert_equal(a[0], 1)
        assert_equal(full[0], 0)
        assert_invariants(full, big)
    with assert_raises(contains="cannot be zero"):
        _ = BitArray(String("10101"), ENDIAN_BIG)[::0]


def test_slice_assignment_resize() raises:
    var setups = List[String]()
    setups.append(String("111"))
    setups.append(String("0"))
    setups.append(String("101"))
    setups.append(String(""))
    var expected = List[String]()
    expected.append(String("111110011"))
    expected.append(String("100011"))
    expected.append(String("11010110011"))
    expected.append(String("100011"))
    for big in [True, False]:
        var los = List[Int]()
        los.append(1)
        los.append(2)
        los.append(1)
        los.append(2)
        var his = List[Int]()
        his.append(3)
        his.append(5)
        his.append(1)
        his.append(4)
        for k in range(4):
            var c = BitArray(String("10110011"), big)
            var repl = BitArray(setups[k], big)
            c[los[k] : his[k]] = repl
            assert_equal(c.to01(), expected[k])
            assert_invariants(c, big)
        # Empty replacement deletes; empty target + replacement inserts.
        var d = BitArray(String("101"), big)
        d[:] = BitArray(String(""), big)
        assert_equal(d.to01(), String(""))
        assert_invariants(d, big)
        # Replacement endianness is irrelevant; target keeps its own.
        var x = BitArray(String("10101"), ENDIAN_LITTLE)
        x[1:3] = BitArray(String("11"), ENDIAN_BIG)
        assert_equal(x.to01(), String("11101"))
        assert_equal(x.endian(), String("little"))
        # Self-assignment snapshots before resizing. Mojo's borrow
        # checker rejects `y[1:3] = y` (mut + imm alias), so the caller
        # snapshots; the result matches the reference `c[1:3] = c`.
        var y = BitArray(String("10101"), big)
        y[1:3] = y[:]
        assert_equal(y.to01(), String("11010101"))
        assert_invariants(y, big)


def test_slice_assignment_extended() raises:
    for big in [True, False]:
        var c = BitArray(String("10101"), big)
        c[::2] = BitArray(String("111"), big)
        assert_equal(c.to01(), String("10101"))
        c[::-1] = BitArray(String("11111"), big)
        assert_equal(c.to01(), String("11111"))
        var d = BitArray(String("10101"), big)
        d[1:4:2] = BitArray(String("00"), big)
        assert_equal(d.to01(), String("10101"))
        assert_invariants(d, big)
        # Length mismatch fails atomically.
        var e = BitArray(String("10101"), big)
        with assert_raises(contains="extended slice"):
            e[::2] = BitArray(String("11"), big)
        assert_equal(e.to01(), String("10101"))
        # Self-assignment through a stepped slice works (snapshot).
        var f = BitArray(String("10101"), big)
        f[::2] = f[::2]
        assert_equal(f.to01(), String("10101"))


def test_slice_assignment_broadcast() raises:
    # Broadcasts use explicit `__setitem__`: Mojo `=` syntax only accepts
    # a BitArray RHS for slices (it must match `__getitem__`'s return).
    for big in [True, False]:
        var c = BitArray(String("10101"), big)
        c.__setitem__(slice(1, 3), 1)
        assert_equal(c.to01(), String("11101"))
        var g = BitArray(String("10001"), big)
        g.__setitem__(slice(1, 4), True)
        assert_equal(g.to01(), String("11111"))
        var h = BitArray(String("10001"), big)
        h.__setitem__(slice(None, None, 2), False)
        assert_equal(h.to01(), String("00000"))
        assert_invariants(h, big)
        # Empty selection is a no-op, never a resize.
        var n = BitArray(String("10101"), big)
        n.__setitem__(slice(1, 1), 1)
        assert_equal(n.to01(), String("10101"))
        assert_equal(len(n), 5)
        # Bad broadcast value fails atomically.
        with assert_raises(contains="0 or 1"):
            n.__setitem__(slice(1, 3), 5)
        assert_equal(n.to01(), String("10101"))
        with assert_raises(contains="0 or 1"):
            n.__setitem__(slice(None, None, None), 9)
        assert_equal(n.to01(), String("10101"))


def test_conversions() raises:
    for big in [True, False]:
        var e = BitArray(String(""), big)
        assert_equal(e.to01(), String(""))
        assert_equal(len(e.tolist()), 0)
        var a = BitArray(String("10110"), big)
        assert_equal(a.to01(), String("10110"))
        var items = a.tolist()
        assert_equal(len(items), 5)
        assert_equal(items[0], 1)
        assert_equal(items[1], 0)
        assert_equal(items[4], 0)
        assert_equal(BitArray(String("1"), big).tolist()[0], 1)


def test_boundary_roundtrip() raises:
    var sizes = List[Int]()
    for n in [0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65]:
        sizes.append(n)
    for i in range(len(sizes)):
        var n = sizes[i]
        var pattern = alternating(n)
        for big in [True, False]:
            var a = BitArray(pattern, big)
            assert_equal(len(a), n)
            assert_equal(a.to01(), pattern)
            assert_invariants(a, big)
            # Exercise assignment at the last valid bit, then restore.
            if n > 0:
                var last = a[-1]
                a[-1] = 0
                assert_equal(a[-1], 0)
                a[-1] = last
                assert_equal(a.to01(), pattern)
                assert_invariants(a, big)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
