"""Phase 1D3 native tests: reverse, fill, copy, rotate, find, index.

Mirrors `tests/python_compat/test_sequence_extras_oracle.py` case-for-case:
every expected value below was captured from `bitarray==3.12.3` probe
runs. Covers both endiannesses, boundary lengths
(0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65), storage invariants, failure
atomicity, and deterministic pseudo-random differentials including the
reference's asymmetric bound rule (find/index/sub-count do not clamp an
over-length start above; search uses slice bounds).
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


def assert_positions(found: List[Int], want: List[Int]) raises:
    assert_equal(len(found), len(want))
    for i in range(len(want)):
        assert_equal(found[i], want[i])


def want0() -> List[Int]:
    return List[Int]()


def want1(a: Int) -> List[Int]:
    var out = List[Int](capacity=1)
    out.append(a)
    return out^


def want2(a: Int, b: Int) -> List[Int]:
    var out = List[Int](capacity=2)
    out.append(a)
    out.append(b)
    return out^


def want3(a: Int, b: Int, c: Int) -> List[Int]:
    var out = List[Int](capacity=3)
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


def want4(a: Int, b: Int, c: Int, d: Int) -> List[Int]:
    var out = List[Int](capacity=4)
    out.append(a)
    out.append(b)
    out.append(c)
    out.append(d)
    return out^


struct Lcg:
    """Deterministic PRNG (state threaded through `mut self`)."""

    var s: UInt64

    def __init__(out self, seed: Int):
        self.s = UInt64(seed)

    def next(mut self, bound: Int) -> Int:
        self.s = self.s * UInt64(1103515245) + UInt64(12345)
        return Int(self.s % UInt64(bound))


def test_reverse() raises:
    var texts = List[String]()
    texts.append(String(""))
    texts.append(String("1"))
    texts.append(String("10110011"))
    texts.append(String("10000"))
    var wants = List[String]()
    wants.append(String(""))
    wants.append(String("1"))
    wants.append(String("11001101"))
    wants.append(String("00001"))
    for big in [True, False]:
        for k in range(len(texts)):
            var c = BitArray(texts[k], big)
            c.reverse()
            assert_equal(c.to01(), wants[k])
            assert_equal(c.endian(), String("big") if big else String("little"))
            assert_equal(len(c), texts[k].byte_length())
            assert_invariants(c, big)
        # Double reversal is identity, including non-aligned lengths.
        var d = BitArray(String("1011011"), big)
        d.reverse()
        d.reverse()
        assert_equal(d.to01(), String("1011011"))


def test_fill() raises:
    var texts = List[String]()
    texts.append(String(""))
    texts.append(String("10110011"))
    texts.append(String("10110"))
    texts.append(String("1"))
    texts.append(String("10110"))
    texts.append(String("10110"))
    texts.append(String("101"))
    texts.append(String("1011"))
    var ms = List[Int]()
    ms.append(8)
    ms.append(8)
    ms.append(8)
    ms.append(8)
    ms.append(1)
    ms.append(16)
    ms.append(3)
    ms.append(3)
    var wants = List[String]()
    wants.append(String(""))
    wants.append(String("10110011"))
    wants.append(String("10110000"))
    wants.append(String("10000000"))
    wants.append(String("10110"))
    wants.append(String("1011000000000000"))
    wants.append(String("101"))
    wants.append(String("101100"))
    var added = List[Int]()
    added.append(0)
    added.append(0)
    added.append(3)
    added.append(7)
    added.append(0)
    added.append(11)
    added.append(0)
    added.append(2)
    for big in [True, False]:
        for k in range(len(texts)):
            var c = BitArray(texts[k], big)
            assert_equal(c.fill(ms[k]), added[k])
            assert_equal(c.to01(), wants[k])
            assert_equal(c.endian(), String("big") if big else String("little"))
            assert_equal(c.nbytes(), (wants[k].byte_length() + 7) // 8)
            assert_invariants(c, big)
        # Default fill pads to a byte boundary.
        var d = BitArray(String("10110"), big)
        assert_equal(d.fill(), 3)
        assert_equal(d.to01(), String("10110000"))


def test_fill_bad_m() raises:
    var f0 = BitArray(String("101"), ENDIAN_BIG)
    with assert_raises(contains="positive integer"):
        _ = f0.fill(0)
    var f1 = BitArray(String("101"), ENDIAN_BIG)
    with assert_raises(contains="positive integer"):
        _ = f1.fill(-3)
    var c = BitArray(String("101"), ENDIAN_BIG)
    with assert_raises(contains="positive integer"):
        _ = c.fill(0)
    assert_equal(c.to01(), String("101"))
    assert_invariants(c, ENDIAN_BIG)


def test_copy() raises:
    var sizes = List[Int]()
    for n in [0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65]:
        sizes.append(n)
    for i in range(len(sizes)):
        var n = sizes[i]
        for big in [True, False]:
            var text = String("")
            for j in range(n):
                text += String("1") if j % 2 == 0 else String("0")
            var c = BitArray(text, big)
            var d = c.copy()
            assert_equal(d.to01(), text)
            assert_equal(d.endian(), c.endian())
            assert_equal(len(d), n)
            assert_invariants(c, big)
            assert_invariants(d, big)
            if n > 0:
                d[0] = 1 - d[0]
                assert_equal(c.to01(), text)
                assert_invariants(c, big)
                assert_invariants(d, big)


def test_rotate() raises:
    var texts = List[String]()
    texts.append(String("10110011"))
    texts.append(String("10110011"))
    texts.append(String("10110011"))
    texts.append(String("10110011"))
    texts.append(String("10110011"))
    texts.append(String("10110011"))
    texts.append(String(""))
    texts.append(String("1"))
    texts.append(String("10110"))
    texts.append(String("10110"))
    var ks = List[Int]()
    ks.append(1)
    ks.append(0)
    ks.append(2)
    ks.append(-2)
    ks.append(8)
    ks.append(10)
    ks.append(3)
    ks.append(5)
    ks.append(3)
    ks.append(-7)
    var wants = List[String]()
    wants.append(String("11011001"))
    wants.append(String("10110011"))
    wants.append(String("11101100"))
    wants.append(String("11001110"))
    wants.append(String("10110011"))
    wants.append(String("11101100"))
    wants.append(String(""))
    wants.append(String("1"))
    wants.append(String("11010"))
    wants.append(String("11010"))
    for big in [True, False]:
        for k in range(len(texts)):
            var c = BitArray(texts[k], big)
            c.rotate(ks[k])
            assert_equal(c.to01(), wants[k])
            assert_equal(c.endian(), String("big") if big else String("little"))
            assert_equal(len(c), texts[k].byte_length())
            assert_invariants(c, big)
        # Default rotation is right by one.
        var d = BitArray(String("10110011"), big)
        d.rotate()
        assert_equal(d.to01(), String("11011001"))


def test_rotate_roundtrip() raises:
    var rng = Lcg(20260605)
    for _ in range(30):
        for big in [True, False]:
            var n = 1 + rng.next(65)
            var text = String("")
            for _ in range(n):
                text += String("1") if rng.next(2) == 0 else String("0")
            var k = rng.next(6 * n + 11) - 3 * n - 5
            var c = BitArray(text, big)
            c.rotate(k)
            c.rotate(-k)
            assert_equal(c.to01(), text)
            assert_invariants(c, big)


def test_find() raises:
    var a = BitArray(String("10101"), ENDIAN_BIG)
    assert_equal(a.find(BitArray(String("101"), ENDIAN_BIG)), 0)
    assert_equal(a.find(BitArray(String("1"), ENDIAN_BIG)), 0)
    assert_equal(a.find(BitArray(String("0"), ENDIAN_BIG)), 1)
    assert_equal(a.find(BitArray(String("1111"), ENDIAN_BIG)), -1)
    assert_equal(BitArray(String("10"), ENDIAN_BIG).find(BitArray(String("10101"), ENDIAN_BIG)), -1)
    assert_equal(BitArray(String("101"), ENDIAN_BIG).find(BitArray(String(""), ENDIAN_BIG)), 0)
    assert_equal(BitArray(String(""), ENDIAN_BIG).find(BitArray(String(""), ENDIAN_BIG)), 0)
    assert_equal(BitArray(String(""), ENDIAN_BIG).find(BitArray(String("1"), ENDIAN_BIG)), -1)
    assert_equal(a.find(1), 0)
    assert_equal(a.find(True), 0)
    assert_equal(a.find(False), 1)
    with assert_raises(contains="0 or 1"):
        _ = a.find(9)
    assert_equal(a.find(BitArray(String("101"), ENDIAN_BIG), 1, 5), 2)
    assert_equal(a.find(BitArray(String("1"), ENDIAN_BIG), -4, -1), 2)
    assert_equal(a.find(BitArray(String("1"), ENDIAN_BIG), -100, 100), 0)
    assert_equal(a.find(BitArray(String("1"), ENDIAN_BIG), 4, 1), -1)
    assert_equal(a.find(BitArray(String("101"), ENDIAN_LITTLE)), 0)
    assert_equal(a.find(BitArray(String(""), ENDIAN_BIG), 1, 5), 1)
    assert_equal(a.find(BitArray(String(""), ENDIAN_BIG), 4, 1), -1)
    assert_invariants(a, ENDIAN_BIG)


def test_find_right() raises:
    var a = BitArray(String("10101"), ENDIAN_BIG)
    assert_equal(a.find(BitArray(String("101"), ENDIAN_BIG), 0, 5, True), 2)
    assert_equal(a.find(BitArray(String("1"), ENDIAN_BIG), 0, 5, True), 4)
    assert_equal(a.find(BitArray(String("1111"), ENDIAN_BIG), 0, 5, True), -1)
    assert_equal(a.find(BitArray(String("1"), ENDIAN_BIG), 1, 4, True), 2)
    assert_equal(a.find(BitArray(String(""), ENDIAN_BIG), 1, 5, True), 5)
    var b = BitArray(String("10101"), ENDIAN_LITTLE)
    assert_equal(b.find(BitArray(String("101"), ENDIAN_BIG), 0, 5, True), 2)
    assert_invariants(a, ENDIAN_BIG)


def test_index() raises:
    var a = BitArray(String("10101"), ENDIAN_BIG)
    assert_equal(a.index(BitArray(String("101"), ENDIAN_BIG)), 0)
    assert_equal(a.index(0), 1)
    assert_equal(a.index(True), 0)
    assert_equal(a.index(BitArray(String(""), ENDIAN_BIG), 1, 5), 1)
    assert_equal(a.index(BitArray(String("1"), ENDIAN_BIG), 0, 5, True), 4)
    with assert_raises(contains="not in bitarray"):
        _ = a.index(BitArray(String("1111"), ENDIAN_BIG))
    with assert_raises(contains="0 not in bitarray"):
        _ = BitArray(String("111"), ENDIAN_BIG).index(0)
    with assert_raises(contains="True not in bitarray"):
        _ = BitArray(String("000"), ENDIAN_BIG).index(True)
    with assert_raises(contains="False not in bitarray"):
        _ = BitArray(String("111"), ENDIAN_LITTLE).index(False)
    with assert_raises(contains="0 or 1"):
        _ = a.index(9)
    assert_equal(BitArray(String("000"), ENDIAN_BIG).index(False), 0)
    assert_equal(BitArray(String("111"), ENDIAN_LITTLE).index(True, 0, 3, True), 2)
    assert_invariants(a, ENDIAN_BIG)


def test_find_index_fuzz() raises:
    # Deterministic LCG; models the reference's asymmetric bound rule:
    # find/index/sub-count do NOT clamp an over-length start above
    # (empty window when start > stop), while search uses slice bounds.
    var rng = Lcg(20260606)
    for _ in range(120):
        for big in [True, False]:
            var n = rng.next(66)
            if n == 0:
                n = rng.next(2)
            var text = String("")
            for _ in range(n):
                text += String("1") if rng.next(2) == 0 else String("0")
            var a = BitArray(text, big)
            var m = rng.next(6)
            var ptext = String("")
            for _ in range(m):
                ptext += String("1") if rng.next(2) == 0 else String("0")
            var sub = BitArray(ptext, not big)
            var lo = rng.next(2 * n + 7) - n - 3
            var hi = rng.next(2 * n + 7) - n - 3
            # Slice-clamped window (search rule).
            var sloc = lo + n if lo < 0 else lo
            sloc = max(0, min(n, sloc))
            var shoc = hi + n if hi < 0 else hi
            shoc = max(0, min(n, shoc))
            # Unclamped-start window (find/index/sub-count rule).
            var floc = lo + n if lo < 0 else lo
            floc = max(0, floc)
            var fhoc = hi + n if hi < 0 else hi
            fhoc = max(0, min(n, fhoc))
            var smodel = want0()
            var fmodel = want0()
            if shoc >= sloc:
                if m == 0:
                    var q = sloc
                    while q <= shoc:
                        smodel.append(q)
                        q += 1
                else:
                    var q = sloc
                    while q + m <= shoc:
                        if _matches(a, sub, q):
                            smodel.append(q)
                        q += 1
            if fhoc >= floc:
                if m == 0:
                    var q2 = floc
                    while q2 <= fhoc:
                        fmodel.append(q2)
                        q2 += 1
                else:
                    var q2 = floc
                    while q2 + m <= fhoc:
                        if _matches(a, sub, q2):
                            fmodel.append(q2)
                        q2 += 1
            assert_positions(a.search(sub, lo, hi), smodel)
            var want_first = fmodel[0] if len(fmodel) > 0 else -1
            assert_equal(a.find(sub, lo, hi), want_first)
            var rmodel = want0()
            var rk = len(fmodel) - 1
            while rk >= 0:
                rmodel.append(fmodel[rk])
                rk -= 1
            var want_last = rmodel[0] if len(rmodel) > 0 else -1
            assert_equal(a.find(sub, lo, hi, True), want_last)
            if len(fmodel) > 0:
                assert_equal(a.index(sub, lo, hi), fmodel[0])
            else:
                with assert_raises(contains="not in bitarray"):
                    _ = a.index(sub, lo, hi)
            # Non-overlapping sub-count equals the greedy pick.
            var greedy = 0
            var last_end = floc
            for k in range(len(fmodel)):
                if fmodel[k] >= last_end:
                    greedy += 1
                    last_end = fmodel[k] + (m if m > 0 else 1)
            assert_equal(a.count(sub, lo, hi), greedy)
            assert_invariants(a, big)


def _matches(a: BitArray, pat: BitArray, at: Int) raises -> Bool:
    for k in range(len(pat)):
        if a[at + k] != pat[k]:
            return False
    return True


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
