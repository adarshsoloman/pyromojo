"""Phase 5 native tests: channel operations.

Expectations come from the Phase 5 probes of CPython 3.12.3: the
interleaved-pair mixing formula with fbound (clamp, floor), tostereo's
per-sample expansion with left-first ordering, the stereo-frame
alignment error for tomono, and the port's documented NaN->zero policy
(matching the reference at widths 1-3).
"""

from std.collections import List
from std.math import inf
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_audioop import encode_fragment, tomono, tostereo


def i32_list_of(*args: Int) -> List[Int32]:
    var out = List[Int32](capacity=len(args))
    for value in args:
        out.append(Int32(value))
    return out^


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


def test_tomono_mixes_interleaved_pairs() raises:
    # [1,3],[2,4] with 0.5/0.5: (0.5+1.5)=2, (1+2)=3
    var stereo = frag(2, list_of(1, 3, 2, 4))
    var mono = tomono(Span(stereo), 2, 0.5, 0.5)
    assert_equal(len(mono), 4)
    assert_equal(mono[0], UInt8(0x02))
    assert_equal(mono[1], UInt8(0x00))
    assert_equal(mono[2], UInt8(0x03))
    assert_equal(mono[3], UInt8(0x00))

    # floor of a fractional negative sum: 0.5 - 1.0 = -0.5 -> -1
    var negative = frag(2, list_of(1, -2))
    var result = tomono(Span(negative), 2, 0.5, 0.5)
    assert_equal(result[0], UInt8(0xFF))
    assert_equal(result[1], UInt8(0xFF))


def test_tomono_saturates_all_widths() raises:
    for width in range(1, 5):
        var lo = -1 << (width * 8 - 1)
        var hi = (1 << (width * 8 - 1)) - 1
        var data = frag(width, list_of(hi, hi, lo, lo))
        var result = tomono(Span(data), width, 1.0, 1.0)
        assert_equal(len(result), 2 * width)
        var decoded = decode_values(result, width)
        assert_equal(decoded[0], Int32(hi))
        assert_equal(decoded[1], Int32(lo))


def decode_values(fragment: Span[UInt8, _], width: Int) raises -> List[Int32]:
    var count = len(fragment) // width
    var out = List[Int32](capacity=count)
    for index in range(count):
        var raw: UInt32 = 0
        for i in range(width):
            raw |= UInt32(fragment[index * width + i]) << UInt32(i * 8)
        var bits = width * 8
        if (raw & (UInt32(1) << UInt32(bits - 1))) != 0:
            out.append(Int32(Int64(raw) - (Int64(1) << Int64(bits))))
        else:
            out.append(Int32(raw))
    return out^


def test_tomono_empty_and_alignment() raises:
    var empty = tomono(Span(List[UInt8]()), 2, 1.0, 1.0)
    assert_equal(len(empty), 0)
    with assert_raises(contains="not a whole number of frames"):
        _ = tomono(Span(frag(2, list_of(5))), 2, 1.0, 1.0)
    with assert_raises(contains="not a whole number of frames"):
        _ = tomono(Span(frag(2, list_of(1, 2, 3))), 2, 1.0, 1.0)
    with assert_raises(contains="not a whole number of frames"):
        var odd_bytes = List[UInt8]()
        odd_bytes.append(1)
        _ = tomono(Span(odd_bytes), 2, 1.0, 1.0)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = tomono(Span(List[UInt8]()), 0, 1.0, 1.0)


def test_tomono_factors() raises:
    var data = frag(2, list_of(1000, -1000, 5, -5))
    var zeros = tomono(Span(data), 2, 0.0, 0.0)
    assert_equal(decode_values(Span(zeros), 2), i32_list_of(0, 0))

    var mixed = frag(2, list_of(3, -3, -3, 3))
    var half = tomono(Span(mixed), 2, 0.5, -0.5)
    assert_equal(decode_values(Span(half), 2), i32_list_of(3, -3))

    var large = frag(2, list_of(1, -1, 2, -2))
    var huge = tomono(Span(large), 2, 1e6, -1e6)
    var decoded = decode_values(Span(huge), 2)
    # both pairs sum far beyond the range and clamp to the maximum
    assert_equal(decoded[0], Int32(32767))
    assert_equal(decoded[1], Int32(32767))

    var tiny = frag(2, list_of(1000, -1000, 999, -999))
    var small = tomono(Span(tiny), 2, 0.001, 0.001)
    var small_decoded = decode_values(Span(small), 2)
    # each pair is x*0.001 + (-x)*0.001 = 0 exactly
    assert_equal(small_decoded[0], Int32(0))
    assert_equal(small_decoded[1], Int32(0))


def test_tomono_nan_policy() raises:
    # NaN factor: reference UB; the port defines NaN results as zero
    var data = frag(2, list_of(1, 2, 3, 4))
    var nan: Float64 = 0.0 / 0.0
    var result = tomono(Span(data), 2, nan, 0.5)
    assert_equal(decode_values(Span(result), 2), i32_list_of(0, 0))
    var pos_inf: Float64 = inf[DType.float64]()
    var zero_and_peak = frag(2, list_of(0, 1, 3, 4))
    var mixed_nan = tomono(Span(zero_and_peak), 2, pos_inf, 0.5)
    var decoded = decode_values(Span(mixed_nan), 2)
    assert_equal(decoded[0], Int32(0))
    assert_equal(decoded[1], Int32(32767))


def test_tostereo_expands_left_first() raises:
    var source = frag(2, list_of(5))
    var stereo = tostereo(Span(source), 2, 1.0, 1.0)
    assert_equal(len(stereo), 4)
    assert_equal(stereo[0], UInt8(0x05))
    assert_equal(stereo[1], UInt8(0x00))
    assert_equal(stereo[2], UInt8(0x05))
    assert_equal(stereo[3], UInt8(0x00))

    var mixed = frag(2, list_of(5, -3))
    var result = tostereo(Span(mixed), 2, 0.5, -0.5)
    assert_equal(decode_values(Span(result), 2), i32_list_of(2, -3, -2, 1))


def test_tostereo_saturates_all_widths() raises:
    for width in range(1, 5):
        var lo = -1 << (width * 8 - 1)
        var hi = (1 << (width * 8 - 1)) - 1
        var data = frag(width, list_of(hi, lo))
        var result = tostereo(Span(data), width, 2.0, 2.0)
        assert_equal(len(result), 4 * width)
        var decoded = decode_values(Span(result), width)
        assert_equal(decoded[0], Int32(hi))
        assert_equal(decoded[1], Int32(hi))
        assert_equal(decoded[2], Int32(lo))
        assert_equal(decoded[3], Int32(lo))


def test_tostereo_empty_and_validation() raises:
    var empty = tostereo(Span(List[UInt8]()), 2, 1.0, 1.0)
    assert_equal(len(empty), 0)
    with assert_raises(contains="not a whole number of frames"):
        var odd_bytes = List[UInt8]()
        odd_bytes.append(1)
        _ = tostereo(Span(odd_bytes), 2, 1.0, 1.0)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = tostereo(Span(List[UInt8]()), 0, 1.0, 1.0)


def test_tostereo_floor_and_factors() raises:
    var positive = frag(2, list_of(3))
    var floor_up = tostereo(Span(positive), 2, 0.5, 0.5)
    assert_equal(decode_values(Span(floor_up), 2), i32_list_of(1, 1))
    var negative = frag(2, list_of(-3))
    var floor_down = tostereo(Span(negative), 2, 0.5, 0.5)
    assert_equal(decode_values(Span(floor_down), 2), i32_list_of(-2, -2))

    var data = frag(2, list_of(1000, -1000))
    var zeros = tostereo(Span(data), 2, 0.0, 0.0)
    assert_equal(decode_values(Span(zeros), 2), i32_list_of(0, 0, 0, 0))

    var pos_inf: Float64 = inf[DType.float64]()
    var neg_inf: Float64 = -inf[DType.float64]()
    var bounded = tostereo(Span(data), 2, pos_inf, neg_inf)
    var decoded = decode_values(Span(bounded), 2)
    assert_equal(decoded[0], Int32(32767))
    assert_equal(decoded[1], Int32(-32768))
    assert_equal(decoded[2], Int32(-32768))
    assert_equal(decoded[3], Int32(32767))


def test_tostereo_nan_policy() raises:
    var data = frag(2, list_of(1, 2))
    var nan: Float64 = 0.0 / 0.0
    var result = tostereo(Span(data), 2, nan, 0.5)
    var decoded = decode_values(Span(result), 2)
    # L = NaN -> 0; R = floor(sample * 0.5): floor(0.5) = 0, floor(1.0) = 1
    assert_equal(decoded[0], Int32(0))
    assert_equal(decoded[1], Int32(0))
    assert_equal(decoded[2], Int32(0))
    assert_equal(decoded[3], Int32(1))


def test_channels_do_not_mutate_inputs() raises:
    var data = frag(2, list_of(1, 3, 2, 4))
    var original = data[0]
    _ = tomono(Span(data), 2, 0.5, 0.5)
    _ = tostereo(Span(data), 2, 0.5, 0.5)
    assert_equal(data[0], original)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
