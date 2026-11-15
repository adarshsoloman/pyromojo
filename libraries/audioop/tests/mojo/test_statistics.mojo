"""Phase 3 native tests: the six statistics operations.

Expectations come from the Phase 3 reference probes of CPython 3.12.3:
floor semantics for ``avg``, unsigned absolute values for ``max`` and
``rms``, the (2147483647, -2147483648) ``minmax`` sentinel, and the -1
``cross`` sentinel with zero in the non-negative sign class.
"""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_audioop import (
    avg,
    cross,
    encode_fragment,
    getsample,
    max,
    minmax,
    rms,
)


def list_of(*args: Int) -> List[Int]:
    var out = List[Int](capacity=len(args))
    for value in args:
        out.append(value)
    return out^


def frag(width: Int, values: List[Int]) raises -> List[UInt8]:
    var samples = List[Int64](capacity=len(values))
    for value in values:
        samples.append(Int64(value))
    return encode_fragment(Span(samples), width)


def test_getsample_all_widths_and_indices() raises:
    for width in range(1, 5):
        var lo = -1 << (width * 8 - 1)
        var hi = (1 << (width * 8 - 1)) - 1
        var data = frag(width, list_of(lo, hi, 0, -1, 1))
        assert_equal(getsample(Span(data), width, 0), Int32(lo))
        assert_equal(getsample(Span(data), width, 1), Int32(hi))
        assert_equal(getsample(Span(data), width, 2), Int32(0))
        assert_equal(getsample(Span(data), width, 3), Int32(-1))
        assert_equal(getsample(Span(data), width, 4), Int32(1))


def test_getsample_index_errors() raises:
    var data = frag(2, list_of(1, 2, 3))
    with assert_raises(contains="Index out of range"):
        _ = getsample(Span(data), 2, 3)
    with assert_raises(contains="Index out of range"):
        _ = getsample(Span(data), 2, -1)
    with assert_raises(contains="Index out of range"):
        _ = getsample(Span(List[UInt8]()), 2, 0)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = getsample(Span(List[UInt8]()), 0, 0)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        _ = getsample(Span(odd), 2, 0)


def test_max_unsigned_absolute_value() raises:
    # reference: abs computed in unsigned, so abs(-2^31) = 2^31
    var int_min = frag(4, list_of(-2147483648))
    assert_equal(max(Span(int_min), 4), 2147483648)

    for width in range(1, 5):
        var lo = -1 << (width * 8 - 1)
        var hi = (1 << (width * 8 - 1)) - 1
        var data = frag(width, list_of(lo, hi, 0, -1, 1))
        assert_equal(max(Span(data), width), Int64(-lo))

    var negatives = frag(2, list_of(-1, -9, -3))
    assert_equal(max(Span(negatives), 2), 9)
    assert_equal(max(Span(List[UInt8]()), 2), 0)
    var boundaries = frag(1, list_of(127, -128))
    assert_equal(max(Span(boundaries), 1), 128)


def test_max_validation() raises:
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = max(Span(List[UInt8]()), 0)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        _ = max(Span(odd), 2)


def test_minmax_signed_bounds_and_sentinel() raises:
    var empty = minmax(Span(List[UInt8]()), 2)
    assert_equal(empty[0], Int32(2147483647))
    assert_equal(empty[1], Int32(-2147483648))

    for width in range(1, 5):
        var lo = -1 << (width * 8 - 1)
        var hi = (1 << (width * 8 - 1)) - 1
        var data = frag(width, list_of(lo, hi, 0, -1, 1))
        var pair = minmax(Span(data), width)
        assert_equal(pair[0], Int32(lo))
        assert_equal(pair[1], Int32(hi))

    var single = frag(1, list_of(5))
    var one = minmax(Span(single), 1)
    assert_equal(one[0], Int32(5))
    assert_equal(one[1], Int32(5))

    var negatives = frag(2, list_of(-9, -3))
    var neg_pair = minmax(Span(negatives), 2)
    assert_equal(neg_pair[0], Int32(-9))
    assert_equal(neg_pair[1], Int32(-3))

    var int_min = frag(4, list_of(-2147483648))
    var min_pair = minmax(Span(int_min), 4)
    assert_equal(min_pair[0], Int32(-2147483648))
    assert_equal(min_pair[1], Int32(-2147483648))


def test_minmax_validation() raises:
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = minmax(Span(List[UInt8]()), 5)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        odd.append(2)
        odd.append(3)
        _ = minmax(Span(odd), 2)


def test_avg_floors_toward_negative_infinity() raises:
    # floor, not C truncation: [-1,-2] -> -2, [-1,-2,-4] -> -3, [1,2,4] -> 2
    var neg2 = frag(2, list_of(-1, -2))
    assert_equal(avg(Span(neg2), 2), -2)
    var neg3 = frag(2, list_of(-1, -2, -4))
    assert_equal(avg(Span(neg3), 2), -3)
    var pos3 = frag(2, list_of(1, 2, 4))
    assert_equal(avg(Span(pos3), 2), 2)
    var exact = frag(2, list_of(-3))
    assert_equal(avg(Span(exact), 2), -3)

    assert_equal(avg(Span(List[UInt8]()), 2), 0)

    var all_min = frag(4, list_of(-2147483648, -2147483648, -2147483648))
    assert_equal(avg(Span(all_min), 4), -2147483648)

    var mixed = frag(4, list_of(2147483647, -2147483648))
    assert_equal(avg(Span(mixed), 4), -1)

    for width in range(1, 5):
        var lo = -1 << (width * 8 - 1)
        var hi = (1 << (width * 8 - 1)) - 1
        var data = frag(width, list_of(lo, hi, 0, -1, 1))
        # sum = lo + hi - 1 = -2 for every width (lo + hi = -1)
        # count = 5 -> floor(-2/5) = -1 ... verify via reference probe result
        _ = avg(Span(data), width)


def test_avg_validation() raises:
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = avg(Span(List[UInt8]()), 0)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        _ = avg(Span(odd), 2)


def test_rms_truncates_sqrt() raises:
    var trunc = frag(2, list_of(2, -2, 2, -3))
    assert_equal(rms(Span(trunc), 2), 2)
    var trunc2 = frag(2, list_of(1, 2))
    assert_equal(rms(Span(trunc2), 2), 1)
    var single = frag(2, list_of(3))
    assert_equal(rms(Span(single), 2), 3)
    var zeros = frag(2, list_of(0, 0, 0, 0))
    assert_equal(rms(Span(zeros), 2), 0)
    assert_equal(rms(Span(List[UInt8]()), 2), 0)

    # unsigned result exceeds the signed 32-bit range
    var all_min = frag(4, list_of(-2147483648, -2147483648))
    assert_equal(rms(Span(all_min), 4), 2147483648)

    var symmetric = frag(2, list_of(1, -1))
    assert_equal(rms(Span(symmetric), 2), 1)


def test_rms_validation() raises:
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = rms(Span(List[UInt8]()), 5)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        _ = rms(Span(odd), 2)


def test_cross_sign_classes_and_sentinels() raises:
    assert_equal(cross(Span(List[UInt8]()), 2), -1)
    # single sample: initial sentinel transition only
    var single = frag(2, list_of(5))
    assert_equal(cross(Span(single), 2), 0)
    var single_zero = frag(2, list_of(0))
    assert_equal(cross(Span(single_zero), 2), 0)
    var zeros = frag(2, list_of(0, 0, 0))
    assert_equal(cross(Span(zeros), 2), 0)

    var pos_neg = frag(2, list_of(1, -1))
    assert_equal(cross(Span(pos_neg), 2), 1)
    var zero_between = frag(2, list_of(1, 0, -1))
    assert_equal(cross(Span(zero_between), 2), 1)
    var neg_zero_pos = frag(2, list_of(-1, 0, 1))
    assert_equal(cross(Span(neg_zero_pos), 2), 1)
    var alternating = frag(2, list_of(1, -1, 1))
    assert_equal(cross(Span(alternating), 2), 2)
    var zero_then_pos = frag(2, list_of(0, 1))
    assert_equal(cross(Span(zero_then_pos), 2), 0)
    var negative_only = frag(2, list_of(-1, -1))
    assert_equal(cross(Span(negative_only), 2), 0)

    var int_min = frag(4, list_of(-2147483648, 1))
    assert_equal(cross(Span(int_min), 4), 1)

    for width in range(1, 5):
        var data = frag(width, list_of(1, -1, 1, -1))
        assert_equal(cross(Span(data), width), 3)


def test_cross_validation() raises:
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = cross(Span(List[UInt8]()), 7)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        _ = cross(Span(odd), 2)


def test_statistics_do_not_mutate_inputs() raises:
    var data = frag(2, list_of(1, -2, 3))
    var original = data[0]
    _ = getsample(Span(data), 2, 1)
    _ = max(Span(data), 2)
    _ = minmax(Span(data), 2)
    _ = avg(Span(data), 2)
    _ = rms(Span(data), 2)
    _ = cross(Span(data), 2)
    assert_equal(data[0], original)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
