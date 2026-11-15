"""Phase 4 native tests: peak analysis and fragment matching.

Expectations come from the Phase 4 probes of CPython 3.12.3: the
first-direction-baseline peak walk, the 4294967295 unsigned wrap at
width 4, first-window tie-breaking, and the fixed 16-bit find* family
with their division-by-zero nan results.
"""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_audioop import avgpp, encode_fragment, findfactor, findfit, findmax, maxpp


def list_of(*args: Int) -> List[Int]:
    var out = List[Int](capacity=len(args))
    for value in args:
        out.append(value)
    return out^


def _hex_digit(byte: UInt8) -> Int:
    if byte >= UInt8(48) and byte <= UInt8(57):
        return Int(byte) - 48
    if byte >= UInt8(97) and byte <= UInt8(102):
        return Int(byte) - 87
    return Int(byte) - 55


def frag(width: Int, values: List[Int]) raises -> List[UInt8]:
    var samples = List[Int64](capacity=len(values))
    for value in values:
        samples.append(Int64(value))
    return encode_fragment(Span(samples), width)


def test_avgpp_and_maxpp_alternating_all_widths() raises:
    for width in range(1, 5):
        var data = frag(width, list_of(1, 3, 1, 3))
        assert_equal(avgpp(Span(data), width), 2)
        assert_equal(maxpp(Span(data), width), 2)


def test_peak_walk_first_direction_is_baseline() raises:
    # one peak never forms a pair: reference returns 0
    var monotonic = frag(2, list_of(1, 2, 3, 2, 1))
    assert_equal(avgpp(Span(monotonic), 2), 0)
    assert_equal(maxpp(Span(monotonic), 2), 0)
    var v_shape = frag(2, list_of(32767, -32768, 32767))
    assert_equal(avgpp(Span(v_shape), 2), 0)
    assert_equal(maxpp(Span(v_shape), 2), 0)
    # two reversals produce one recorded pair
    var triple = frag(2, list_of(1, 3, 1, 3))
    assert_equal(avgpp(Span(triple), 2), 2)


def test_peak_walk_plateaus_and_truncation() raises:
    var plateau = frag(2, list_of(1, 3, 3, 1, 3, 3, 1))
    assert_equal(avgpp(Span(plateau), 2), 2)
    assert_equal(maxpp(Span(plateau), 2), 2)
    # diffs 3, 3, 1: mean 7/3 truncates to 2
    var trunc = frag(2, list_of(0, 3, 0, 1, 0))
    assert_equal(avgpp(Span(trunc), 2), 2)
    assert_equal(maxpp(Span(trunc), 2), 3)


def test_peak_walk_constant_single_empty() raises:
    var constant = frag(2, list_of(5, 5, 5))
    assert_equal(avgpp(Span(constant), 2), 0)
    assert_equal(maxpp(Span(constant), 2), 0)
    var single = frag(2, list_of(5))
    assert_equal(avgpp(Span(single), 2), 0)
    assert_equal(maxpp(Span(single), 2), 0)
    assert_equal(avgpp(Span(List[UInt8]()), 2), 0)
    assert_equal(maxpp(Span(List[UInt8]()), 2), 0)


def test_peak_walk_unsigned_wrap_width4() raises:
    var extremes = frag(
        4, list_of(2147483647, -2147483648, 2147483647, -2147483648, 2147483647)
    )
    assert_equal(avgpp(Span(extremes), 4), 4294967295)
    assert_equal(maxpp(Span(extremes), 4), 4294967295)


def test_peak_walk_validation() raises:
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = avgpp(Span(List[UInt8]()), 0)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        odd.append(2)
        odd.append(3)
        _ = avgpp(Span(odd), 2)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = maxpp(Span(List[UInt8]()), 5)
    with assert_raises(contains="not a whole number of frames"):
        var odd2 = List[UInt8]()
        odd2.append(1)
        _ = maxpp(Span(odd2), 2)


def test_findmax_windows_and_ties() raises:
    var basic = frag(2, list_of(0, 100, 200, 300))
    assert_equal(findmax(Span(basic), 2), 2)
    # ties keep the first window (strict >)
    var tie = frag(2, list_of(1, 2, 1, 2))
    assert_equal(findmax(Span(tie), 2), 0)
    var last = frag(2, list_of(0, 0, 5, 5))
    assert_equal(findmax(Span(last), 2), 2)
    var zero_heavy = frag(2, list_of(0, 0, 0, 7))
    assert_equal(findmax(Span(zero_heavy), 2), 2)


def test_findmax_length_semantics() raises:
    # length is in 16-bit samples
    var data = frag(2, list_of(1, 2, 3))
    assert_equal(findmax(Span(data), 3), 0)
    # energies 1, 4, 9: the last single-sample window wins
    assert_equal(findmax(Span(data), 1), 2)
    assert_equal(findmax(Span(data), 0), 0)
    assert_equal(findmax(Span(List[UInt8]()), 0), 0)
    # fixed 16-bit: a width-4 fragment is read as int16 pairs
    var wide = frag(4, list_of(65536, 2, 3))
    assert_equal(findmax(Span(wide), 3), 2)


def test_findmax_validation() raises:
    var data = frag(2, list_of(0, 1))
    with assert_raises(contains="Input sample should be longer"):
        _ = findmax(Span(data), 3)
    with assert_raises(contains="Input sample should be longer"):
        _ = findmax(Span(data), -1)
    with assert_raises(contains="Strings should be even-sized"):
        var odd = List[UInt8]()
        odd.append(1)
        odd.append(2)
        odd.append(3)
        _ = findmax(Span(odd), 1)


def test_findfactor_scales_and_zero_reference() raises:
    var reference = frag(2, list_of(1, 2, 3))
    var same = frag(2, list_of(1, 2, 3))
    assert_equal(findfactor(Span(reference), Span(same)), 1.0)
    var scaled = frag(2, list_of(2, 4, 6))
    assert_equal(findfactor(Span(scaled), Span(reference)), 2.0)
    var negated = frag(2, list_of(-1, -2, -3))
    assert_equal(findfactor(Span(negated), Span(reference)), -1.0)

    var zero_ref = frag(2, list_of(0, 0, 0))
    var nan_factor = findfactor(Span(reference), Span(zero_ref))
    assert_equal(nan_factor != nan_factor, True)

    var zero_frag = frag(2, list_of(0, 0, 0))
    assert_equal(findfactor(Span(zero_frag), Span(reference)), 0.0)
    var large = frag(2, list_of(30000, 30000))
    var small = frag(2, list_of(1, 1))
    assert_equal(findfactor(Span(large), Span(small)), 30000.0)


def hex_bytes(text: String) -> List[UInt8]:
    var out = List[UInt8](capacity=text.byte_length() // 2)
    var i = 0
    while i < text.byte_length():
        var high = _hex_digit(text.as_bytes()[i])
        var low = _hex_digit(text.as_bytes()[i + 1])
        out.append(UInt8(high * 16 + low))
        i += 2
    return out^


def test_findfactor_fixed_16bit() raises:
    # width-4 bytes are read as int16 pairs (reference-verified value)
    var a = hex_bytes("0000010001000000")
    var b = hex_bytes("0080000001000000")
    var factor = findfactor(Span(a), Span(b))
    assert_equal(factor > 9.313225737481167e-10 and factor < 9.313225737481169e-10, True)


def test_findfactor_validation() raises:
    var two = frag(2, list_of(1, 2))
    var three = frag(2, list_of(1, 2, 3))
    with assert_raises(contains="Samples should be same size"):
        _ = findfactor(Span(two), Span(three))
    with assert_raises(contains="Strings should be even-sized"):
        var odd = List[UInt8]()
        odd.append(1)
        odd.append(2)
        odd.append(3)
        _ = findfactor(Span(odd), Span(three))


def test_findfit_windows_ties_and_nan() raises:
    var reference = frag(2, list_of(1, 2, 3))
    var exact = frag(2, list_of(1, 2, 3, 4))
    var fit0 = findfit(Span(exact), Span(reference))
    assert_equal(fit0.index, 0)
    assert_equal(fit0.factor, 1.0)

    var shifted = frag(2, list_of(9, 1, 2, 3))
    var fit1 = findfit(Span(shifted), Span(reference))
    assert_equal(fit1.index, 1)
    assert_equal(fit1.factor, 1.0)

    var scaled = frag(2, list_of(2, 4, 6, 8))
    var fit2 = findfit(Span(scaled), Span(reference))
    assert_equal(fit2.index, 0)
    assert_equal(fit2.factor, 2.0)

    # tie: strict < keeps the first window
    var tie_frag = frag(2, list_of(1, 2, 1, 2))
    var tie_ref = frag(2, list_of(1, 2))
    assert_equal(findfit(Span(tie_frag), Span(tie_ref)).index, 0)

    # zero-energy windows: nan factor
    var empty = findfit(Span(List[UInt8]()), Span(List[UInt8]()))
    assert_equal(empty.index, 0)
    assert_equal(empty.factor != empty.factor, True)

    var zero_window = frag(2, list_of(0, 0, 5, 6))
    var zero_ref = frag(2, list_of(0, 0))
    var zero_fit = findfit(Span(zero_window), Span(zero_ref))
    assert_equal(zero_fit.index, 0)
    assert_equal(zero_fit.factor != zero_fit.factor, True)

    # nan candidate never beats a finite best
    var mid = frag(2, list_of(5, 6, 0, 0, 0, 0))
    var mid_fit = findfit(Span(mid), Span(tie_ref))
    assert_equal(mid_fit.index, 0)
    assert_equal(mid_fit.factor, 3.4)


def test_findfit_validation() raises:
    var two = frag(2, list_of(1, 2))
    var three = frag(2, list_of(1, 2, 3))
    with assert_raises(contains="First sample should be longer"):
        _ = findfit(Span(two), Span(three))
    with assert_raises(contains="Strings should be even-sized"):
        var odd = List[UInt8]()
        odd.append(1)
        odd.append(2)
        odd.append(3)
        _ = findfit(Span(odd), Span(two))


def test_peak_analysis_does_not_mutate_inputs() raises:
    var data = frag(2, list_of(1, 3, 1, 3))
    var other = frag(2, list_of(1, 2, 3, 4))
    var original = data[0]
    _ = avgpp(Span(data), 2)
    _ = maxpp(Span(data), 2)
    _ = findmax(Span(data), 2)
    _ = findfactor(Span(data), Span(other))
    _ = findfit(Span(data), Span(other))
    assert_equal(data[0], original)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
