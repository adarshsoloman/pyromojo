"""Phase 1D2 native tests: population count and search.

Mirrors `tests/python_compat/test_count_search_oracle.py` case-for-case:
every expected value below was captured from `bitarray==3.12.3` probe
runs. Covers both endiannesses, boundary lengths
(0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65), SWAR-vs-logical cross-checks,
and deterministic pseudo-random differentials.
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


def test_count_default() raises:
    var texts = List[String]()
    texts.append(String(""))
    texts.append(String("0"))
    texts.append(String("1"))
    texts.append(String("10110"))
    var wants = want0()
    wants.append(0)
    wants.append(0)
    wants.append(1)
    wants.append(3)
    for big in [True, False]:
        for k in range(len(texts)):
            var a = BitArray(texts[k], big)
            assert_equal(a.count(), wants[k])
            assert_invariants(a, big)
        var zeros65 = String("")
        var ones65 = String("")
        for _ in range(65):
            zeros65 += "0"
            ones65 += "1"
        assert_equal(BitArray(zeros65, big).count(), 0)
        assert_equal(BitArray(ones65, big).count(), 65)


def test_count_values() raises:
    for big in [True, False]:
        var a = BitArray(String("10110"), big)
        assert_equal(a.count(1), 3)
        assert_equal(a.count(0), 2)
        assert_equal(a.count(True), 3)
        assert_equal(a.count(False), 2)
    with assert_raises(contains="0 or 1"):
        _ = BitArray(String("10110"), ENDIAN_BIG).count(2)


def test_count_boundaries() raises:
    var sizes = want0()
    for n in [0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65]:
        sizes.append(n)
    for i in range(len(sizes)):
        var n = sizes[i]
        for big in [True, False]:
            var alt = String("")
            var ones = String("")
            for j in range(n):
                alt += String("1") if j % 2 == 0 else String("0")
                ones += "1"
            var a = BitArray(alt, big)
            var o = BitArray(ones, big)
            # SWAR total and complement agree with the logical length.
            assert_equal(a.count() + a.count(0), n)
            assert_equal(a.count(1), (n + 1) // 2)
            assert_equal(o.count(), n)
            assert_equal(o.count(0), 0)
            assert_equal(o.nbytes(), (n + 7) // 8)
            assert_invariants(a, big)
            assert_invariants(o, big)


def test_count_bounds_steps() raises:
    var starts = want0()
    starts.append(1)
    starts.append(0)
    starts.append(0)
    starts.append(-4)
    starts.append(-100)
    starts.append(4)
    starts.append(0)
    var stops = want0()
    stops.append(4)
    stops.append(5)
    stops.append(5)
    stops.append(-1)
    stops.append(100)
    stops.append(1)
    stops.append(5)
    var steps = want0()
    steps.append(1)
    steps.append(2)
    steps.append(1)
    steps.append(1)
    steps.append(1)
    steps.append(1)
    steps.append(3)
    var wants = want0()
    wants.append(2)
    wants.append(2)
    wants.append(3)
    wants.append(2)
    wants.append(3)
    wants.append(0)
    wants.append(2)
    for big in [True, False]:
        var a = BitArray(String("10110"), big)
        for k in range(len(wants)):
            assert_equal(a.count(1, starts[k], stops[k], steps[k]), wants[k])
            # Equivalence with slicing, and with the shorter prefixes.
            assert_equal(
                a.count(1, starts[k], stops[k], steps[k]),
                a[starts[k] : stops[k] : steps[k]].count(1),
            )
            assert_equal(a.count(1, starts[k], stops[k]), a.count(1, starts[k], stops[k], 1))
            assert_equal(a.count(1, starts[k]), a.count(1, starts[k], len(a), 1))
            assert_equal(
                a.count(True, starts[k], stops[k]), a.count(1, starts[k], stops[k], 1)
            )
        assert_invariants(a, big)
    with assert_raises(contains="cannot be zero"):
        _ = BitArray(String("10110"), ENDIAN_BIG).count(1, 0, 5, 0)


def test_count_sub_pattern() raises:
    for big in [True, False]:
        var a = BitArray(String("10101"), big)
        assert_equal(a.count(BitArray(String("101"), big)), 1)
        assert_equal(BitArray(String("1111"), big).count(BitArray(String("11"), big)), 2)
        assert_equal(BitArray(String("101"), big).count(BitArray(String(""), big)), 4)
        assert_equal(BitArray(String(""), big).count(BitArray(String(""), big)), 1)
        assert_equal(BitArray(String("10"), big).count(BitArray(String("10101"), big)), 0)
        assert_equal(a.count(BitArray(String("101"), big), 1, 5), 1)
        assert_equal(a.count(BitArray(String("101"), big), 0, 3), 1)
        assert_equal(a.count(BitArray(String("101"), big), 0, 2), 0)
        # Cross-endian patterns match by logical bits.
        assert_equal(a.count(BitArray(String("101"), not big)), 1)
        assert_invariants(a, big)


def test_search_basic() raises:
    for big in [True, False]:
        var a = BitArray(String("10101"), big)
        assert_positions(a.search(BitArray(String("101"), big)), want2(0, 2))
        assert_positions(a.search(BitArray(String("1"), big)), want3(0, 2, 4))
        assert_positions(a.search(BitArray(String("0"), big)), want2(1, 3))
        assert_positions(a.search(1), want3(0, 2, 4))
        assert_positions(a.search(0), want2(1, 3))
        assert_positions(a.search(True), want3(0, 2, 4))
        assert_positions(a.search(False), want2(1, 3))
        assert_positions(
            BitArray(String("1111"), big).search(BitArray(String("11"), big)), want3(0, 1, 2)
        )
        assert_positions(BitArray(String("000"), big).search(BitArray(String("1111"), big)), want0())
        assert_positions(BitArray(String("10"), big).search(BitArray(String("10101"), big)), want0())
        assert_positions(BitArray(String(""), big).search(BitArray(String("1"), big)), want0())
        assert_invariants(a, big)
    with assert_raises(contains="0 or 1"):
        _ = BitArray(String("10101"), ENDIAN_BIG).search(2)


def test_search_empty_pattern() raises:
    for big in [True, False]:
        assert_positions(BitArray(String("101"), big).search(BitArray(String(""), big)), want4(0, 1, 2, 3))
        assert_positions(BitArray(String(""), big).search(BitArray(String(""), big)), want1(0))
        assert_positions(
            BitArray(String("101"), big).search(BitArray(String(""), big), 0, 3, True),
            want4(3, 2, 1, 0),
        )


def test_search_bounds() raises:
    for big in [True, False]:
        var a = BitArray(String("10101"), big)
        assert_positions(a.search(BitArray(String("101"), big), 1, 5), want1(2))
        assert_positions(a.search(BitArray(String("1"), big), -4, -1), want1(2))
        assert_positions(a.search(BitArray(String("1"), big), -100, 100), want3(0, 2, 4))
        assert_positions(a.search(BitArray(String("1"), big), 4, 1), want0())
        assert_positions(a.search(BitArray(String("101"), big), 0, 3), want1(0))
        assert_positions(a.search(BitArray(String("101"), big), 0, 2), want0())
        assert_invariants(a, big)


def test_search_right() raises:
    for big in [True, False]:
        var a = BitArray(String("10101"), big)
        assert_positions(a.search(BitArray(String("101"), big), 0, 5, True), want2(2, 0))
        assert_positions(a.search(BitArray(String("1"), big), 0, 5, True), want3(4, 2, 0))
        assert_positions(a.search(BitArray(String("1"), big), 1, 4, True), want1(2))
        # Cross-endian patterns match by logical bits.
        assert_positions(a.search(BitArray(String("101"), not big)), want2(0, 2))
        assert_invariants(a, big)


def test_search_source_untouched() raises:
    for big in [True, False]:
        var a = BitArray(String("10101"), big)
        var hits = a.search(BitArray(String("101"), big))
        hits.append(99)
        assert_equal(a.to01(), String("10101"))
        assert_equal(len(a.search(BitArray(String("101"), big))), 2)
        assert_invariants(a, big)


def test_count_search_fuzz() raises:
    # Deterministic LCG; SWAR count vs logical read loop, search hits vs
    # per-position naive verification, sub-count vs greedy search model.
    var rng = Lcg(20260603)
    for _ in range(60):
        for big in [True, False]:
            var n = 1 + rng.next(65)
            var text = String("")
            for _ in range(n):
                text += String("1") if rng.next(2) == 0 else String("0")
            var a = BitArray(text, big)
            # SWAR agrees with the logical loop.
            var loop_sum = 0
            for i in range(n):
                loop_sum += a[i]
            assert_equal(a.count(), loop_sum)
            assert_equal(a.count(0), n - loop_sum)
            # Bounded count agrees with the slice loop.
            var lo = rng.next(n + 1)
            var hi = lo + rng.next(n - lo + 1)
            var w = 0
            for i in range(lo, hi):
                w += a[i]
            assert_equal(a.count(1, lo, hi, 1), w)
            # Search: every hit matches, every non-hit does not.
            var m = rng.next(5)
            var ptext = String("")
            for _ in range(m):
                ptext += String("1") if rng.next(2) == 0 else String("0")
            var pat = BitArray(ptext, not big)
            var hits = a.search(pat)
            var hit_set = List[Bool]()
            for _ in range(n + 1):
                hit_set.append(False)
            for k in range(len(hits)):
                assert_true(hits[k] >= 0 and hits[k] + m <= n)
                # Verify the match bit by bit.
                for j in range(m):
                    assert_equal(a[hits[k] + j], pat[j])
                hit_set[hits[k]] = True
            for p in range(n - m + 1):
                if m == 0:
                    assert_true(hit_set[p])
                else:
                    var matches = True
                    for j in range(m):
                        if a[p + j] != pat[j]:
                            matches = False
                    assert_true(hit_set[p] == matches)
            # Non-overlapping sub-count equals the greedy pick over hits.
            var greedy = 0
            var last_end = 0
            for k in range(len(hits)):
                if hits[k] >= last_end:
                    greedy += 1
                    last_end = hits[k] + (m if m > 0 else 1)
            assert_equal(a.count(pat), greedy)
            assert_invariants(a, big)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
