"""Phase 1D1 native tests: bitwise ops, in-place forms, shifts.

Mirrors `tests/python_compat/test_bitwise_oracle.py` case-for-case: every
expected value below was captured from `bitarray==3.12.3` probe runs.
Covers both endiannesses, boundary lengths
(0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65), shift counts
(0, 1, 2, 7, 8, 9, 15, 16, 63, 64, 65), storage invariants after every
operation, and failure atomicity.
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


def test_bitwise_truth() raises:
    var xs = List[String]()
    xs.append(String("0000"))
    xs.append(String("1111"))
    xs.append(String("1010"))
    xs.append(String("1010"))
    xs.append(String("1010"))
    xs.append(String(""))
    xs.append(String("0"))
    xs.append(String("1010101"))
    var ys = List[String]()
    ys.append(String("0000"))
    ys.append(String("1111"))
    ys.append(String("0101"))
    ys.append(String("1100"))
    ys.append(String("1010"))
    ys.append(String(""))
    ys.append(String("1"))
    ys.append(String("0101010"))
    var wants_and = List[String]()
    wants_and.append(String("0000"))
    wants_and.append(String("1111"))
    wants_and.append(String("0000"))
    wants_and.append(String("1000"))
    wants_and.append(String("1010"))
    wants_and.append(String(""))
    wants_and.append(String("0"))
    wants_and.append(String("0000000"))
    var wants_or = List[String]()
    wants_or.append(String("0000"))
    wants_or.append(String("1111"))
    wants_or.append(String("1111"))
    wants_or.append(String("1110"))
    wants_or.append(String("1010"))
    wants_or.append(String(""))
    wants_or.append(String("1"))
    wants_or.append(String("1111111"))
    var wants_xor = List[String]()
    wants_xor.append(String("0000"))
    wants_xor.append(String("0000"))
    wants_xor.append(String("1111"))
    wants_xor.append(String("0110"))
    wants_xor.append(String("0000"))
    wants_xor.append(String(""))
    wants_xor.append(String("1"))
    wants_xor.append(String("1111111"))
    for big in [True, False]:
        for k in range(len(xs)):
            var a = BitArray(xs[k], big)
            var b = BitArray(ys[k], big)
            var r_and = a & b
            var r_or = a | b
            var r_xor = a ^ b
            assert_equal(r_and.to01(), wants_and[k])
            assert_equal(r_or.to01(), wants_or[k])
            assert_equal(r_xor.to01(), wants_xor[k])
            # Inputs untouched; results keep the operand endianness.
            assert_equal(a.to01(), xs[k])
            assert_equal(b.to01(), ys[k])
            assert_equal(r_and.big_endian, big)
            assert_invariants(r_and, big)
            assert_invariants(r_or, big)
            assert_invariants(r_xor, big)


def test_invert() raises:
    var texts = List[String]()
    texts.append(String(""))
    texts.append(String("0"))
    texts.append(String("1"))
    texts.append(String("1010"))
    texts.append(String("1010101"))
    texts.append(String("11111111"))
    texts.append(String("0000000"))
    var flipped = List[String]()
    flipped.append(String(""))
    flipped.append(String("1"))
    flipped.append(String("0"))
    flipped.append(String("0101"))
    flipped.append(String("0101010"))
    flipped.append(String("00000000"))
    flipped.append(String("1111111"))
    for big in [True, False]:
        for k in range(len(texts)):
            var a = BitArray(texts[k], big)
            var n = ~a
            assert_equal(n.to01(), flipped[k])
            assert_equal(n.endian(), a.endian())
            assert_equal(a.to01(), texts[k])
            assert_invariants(n, big)


def test_bitwise_errors() raises:
    var a = BitArray(String("1010"), ENDIAN_BIG)
    var short = BitArray(String("11"), ENDIAN_BIG)
    var other_endian = BitArray(String("1010"), ENDIAN_LITTLE)
    var both_wrong = BitArray(String("11"), ENDIAN_LITTLE)
    with assert_raises(contains="equal length"):
        _ = a & short
    with assert_raises(contains="equal length"):
        _ = a | BitArray(String(""), ENDIAN_BIG)
    with assert_raises(contains="equal length"):
        _ = BitArray(String(""), ENDIAN_BIG) ^ BitArray(String("1"), ENDIAN_BIG)
    with assert_raises(contains="equal bit-endianness"):
        _ = a & other_endian
    with assert_raises(contains="equal bit-endianness"):
        _ = a | other_endian
    with assert_raises(contains="equal bit-endianness"):
        _ = a ^ other_endian
    # Length is reported before endianness when both differ.
    with assert_raises(contains="equal length"):
        _ = a & both_wrong
    with assert_raises(contains="equal length"):
        _ = a | both_wrong
    # Failed operations leave both inputs untouched.
    assert_equal(a.to01(), String("1010"))
    assert_equal(other_endian.to01(), String("1010"))
    # Empty & empty is legal.
    assert_equal((BitArray(String(""), ENDIAN_BIG) & BitArray(String(""), ENDIAN_BIG)).to01(), String(""))


def test_inplace() raises:
    for big in [True, False]:
        var a = BitArray(String("1010"), big)
        var b = BitArray(String("1100"), big)
        a &= b
        assert_equal(a.to01(), String("1000"))
        assert_equal(a.big_endian, big)
        var c = BitArray(String("1010"), big)
        c |= b
        assert_equal(c.to01(), String("1110"))
        var d = BitArray(String("1010"), big)
        d ^= b
        assert_equal(d.to01(), String("0110"))
        assert_equal(b.to01(), String("1100"))
        assert_invariants(a, big)
        assert_invariants(c, big)
        assert_invariants(d, big)
        # Self-operations via caller snapshot (borrow checker rejects
        # `a &= a`; the observable result matches the reference).
        var s = BitArray(String("1010"), big)
        s &= s[:]
        assert_equal(s.to01(), String("1010"))
        s |= s[:]
        assert_equal(s.to01(), String("1010"))
        s ^= s[:]
        assert_equal(s.to01(), String("0000"))
        # Empty in place.
        var e = BitArray(String(""), big)
        e &= BitArray(String(""), big)
        assert_equal(e.to01(), String(""))


def test_inplace_errors_atomic() raises:
    var a = BitArray(String("1010"), ENDIAN_BIG)
    with assert_raises(contains="equal length"):
        a &= BitArray(String("11"), ENDIAN_BIG)
    assert_equal(a.to01(), String("1010"))
    with assert_raises(contains="equal bit-endianness"):
        a |= BitArray(String("1010"), ENDIAN_LITTLE)
    assert_equal(a.to01(), String("1010"))
    with assert_raises(contains="equal bit-endianness"):
        a ^= BitArray(String("1010"), ENDIAN_LITTLE)
    assert_equal(a.to01(), String("1010"))
    assert_invariants(a, ENDIAN_BIG)


def test_shifts() raises:
    var texts = List[String]()
    texts.append(String("101100"))
    texts.append(String("101100"))
    texts.append(String("101100"))
    texts.append(String("101100"))
    texts.append(String("101100"))
    texts.append(String("101100"))
    texts.append(String(""))
    texts.append(String("1"))
    texts.append(String("1"))
    texts.append(String("0"))
    texts.append(String("10110011"))
    texts.append(String("10110011"))
    texts.append(String("10110011"))
    texts.append(String("10110011"))
    texts.append(String("1111111"))
    texts.append(String("10000001"))
    var counts = List[Int]()
    counts.append(0)
    counts.append(1)
    counts.append(2)
    counts.append(5)
    counts.append(6)
    counts.append(100)
    counts.append(3)
    counts.append(0)
    counts.append(1)
    counts.append(5)
    counts.append(2)
    counts.append(3)
    counts.append(7)
    counts.append(8)
    counts.append(3)
    counts.append(1)
    var wants_left = List[String]()
    wants_left.append(String("101100"))
    wants_left.append(String("011000"))
    wants_left.append(String("110000"))
    wants_left.append(String("000000"))
    wants_left.append(String("000000"))
    wants_left.append(String("000000"))
    wants_left.append(String(""))
    wants_left.append(String("1"))
    wants_left.append(String("0"))
    wants_left.append(String("0"))
    wants_left.append(String("11001100"))
    wants_left.append(String("10011000"))
    wants_left.append(String("10000000"))
    wants_left.append(String("00000000"))
    wants_left.append(String("1111000"))
    wants_left.append(String("00000010"))
    var wants_right = List[String]()
    wants_right.append(String("101100"))
    wants_right.append(String("010110"))
    wants_right.append(String("001011"))
    wants_right.append(String("000001"))
    wants_right.append(String("000000"))
    wants_right.append(String("000000"))
    wants_right.append(String(""))
    wants_right.append(String("1"))
    wants_right.append(String("0"))
    wants_right.append(String("0"))
    wants_right.append(String("00101100"))
    wants_right.append(String("00010110"))
    wants_right.append(String("00000001"))
    wants_right.append(String("00000000"))
    wants_right.append(String("0001111"))
    wants_right.append(String("01000000"))
    for big in [True, False]:
        for k in range(len(texts)):
            var a = BitArray(texts[k], big)
            var l = a << counts[k]
            var r = a >> counts[k]
            assert_equal(l.to01(), wants_left[k])
            assert_equal(r.to01(), wants_right[k])
            assert_equal(l.big_endian, big)
            assert_equal(r.big_endian, big)
            assert_equal(len(l), len(a))
            assert_equal(len(r), len(a))
            assert_equal(a.to01(), texts[k])
            assert_invariants(l, big)
            assert_invariants(r, big)


def test_shift_counts_and_lengths() raises:
    var sizes = List[Int]()
    for n in [0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65]:
        sizes.append(n)
    var counts = List[Int]()
    for k in [0, 1, 2, 7, 8, 9, 15, 16, 63, 64, 65]:
        counts.append(k)
    for i in range(len(sizes)):
        var n = sizes[i]
        for big in [True, False]:
            var pattern = String("")
            for j in range(n):
                pattern += String("1") if j % 2 == 0 else String("0")
            var a = BitArray(pattern, big)
            for m in range(len(counts)):
                var k = counts[m]
                var l = a << k
                var r = a >> k
                assert_equal(len(l), n)
                assert_equal(len(r), n)
                assert_invariants(l, big)
                assert_invariants(r, big)
                if k == 0:
                    assert_equal(l.to01(), pattern)
                    assert_equal(r.to01(), pattern)
                if k >= n:
                    assert_equal(l.to01(), String("") if n == 0 else _zeros(n))
                    assert_equal(r.to01(), String("") if n == 0 else _zeros(n))


def _zeros(n: Int) -> String:
    var s = String("")
    for _ in range(n):
        s += "0"
    return s^


def test_single_bit_shifts() raises:
    # Exactly one set bit: shifting moves it or drops it. Full exact
    # check per position, no popcount needed.
    for big in [True, False]:
        for n in [1, 8, 9, 17]:
            for p in [0, n // 2, n - 1]:
                var text = String("")
                for i in range(n):
                    text += String("1") if i == p else String("0")
                var a = BitArray(text, big)
                for k in [0, 1, n - 1, n, n + 1]:
                    var l = a << k
                    var r = a >> k
                    for i in range(n):
                        var want_l = 1 if (p >= k and i == p - k) else 0
                        var want_r = 1 if (p + k < n and i == p + k) else 0
                        assert_equal(l[i], want_l)
                        assert_equal(r[i], want_r)
                    assert_invariants(l, big)
                    assert_invariants(r, big)


def test_shift_negative() raises:
    for big in [True, False]:
        var a = BitArray(String("101100"), big)
        with assert_raises(contains="negative shift count"):
            _ = a << -1
        with assert_raises(contains="negative shift count"):
            _ = a >> -100
        assert_equal(a.to01(), String("101100"))
        with assert_raises(contains="negative shift count"):
            a <<= -1
        assert_equal(a.to01(), String("101100"))


def test_shift_inplace_and_independence() raises:
    for big in [True, False]:
        var a = BitArray(String("101100"), big)
        a <<= 2
        assert_equal(a.to01(), String("110000"))
        assert_equal(a.big_endian, big)
        a >>= 1
        assert_equal(a.to01(), String("011000"))
        assert_invariants(a, big)
        var b = BitArray(String("101100"), big)
        var c = b << 2
        c[0] = 1 - c[0]
        assert_equal(b.to01(), String("101100"))
        var d = b >> 2
        d[0] = 1 - d[0]
        assert_equal(b.to01(), String("101100"))
        var e = ~b
        e[0] = 1 - e[0]
        assert_equal(b.to01(), String("101100"))
        assert_invariants(c, big)
        assert_invariants(d, big)
        assert_invariants(e, big)


def test_bitwise_boundary_roundtrip() raises:
    var sizes = List[Int]()
    for n in [0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65]:
        sizes.append(n)
    for i in range(len(sizes)):
        var n = sizes[i]
        for big in [True, False]:
            var alt = String("")
            for j in range(n):
                alt += String("1") if j % 2 == 0 else String("0")
            var zeros = _zeros(n)
            var a = BitArray(alt, big)
            var z = BitArray(zeros, big)
            var o = BitArray(_ones(n), big)
            assert_equal((a & o).to01(), alt)
            assert_equal((a | z).to01(), alt)
            assert_equal((a ^ a).to01(), zeros)
            assert_equal((a ^ o).to01(), (~a).to01())
            assert_equal((z & o).to01(), zeros)
            assert_equal((z | o).to01(), _ones(n))
            assert_invariants(a & o, big)
            assert_invariants(a | z, big)
            assert_invariants(a ^ o, big)
            assert_invariants(~a, big)


def _ones(n: Int) -> String:
    var s = String("")
    for _ in range(n):
        s += "1"
    return s^


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
