"""Phase 2 native tests: the six arithmetic/fragment operations.

Covers normal and boundary values, saturation vs wrap, floor rounding,
empty fragments, invalid widths and lengths, validation order, and every
lin2lin source/destination width pair. Reference expectations come from
the Phase 0 probes of CPython 3.12.3.
"""

from std.collections import List
from std.math import inf
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_audioop import (
    add,
    bias,
    byteswap,
    decode_fragment,
    encode_fragment,
    lin2lin,
    mul,
    reverse,
)


def hex_bytes(text: String) -> List[UInt8]:
    var out = List[UInt8](capacity=text.byte_length() // 2)
    var i = 0
    while i < text.byte_length():
        var high = _hex_digit(text.as_bytes()[i])
        var low = _hex_digit(text.as_bytes()[i + 1])
        out.append(UInt8(high * 16 + low))
        i += 2
    return out^


def _hex_digit(byte: UInt8) -> Int:
    if byte >= UInt8(48) and byte <= UInt8(57):
        return Int(byte) - 48
    if byte >= UInt8(97) and byte <= UInt8(102):
        return Int(byte) - 87
    return Int(byte) - 55


def samples_of(values: List[Int]) -> List[Int64]:
    var out = List[Int64](capacity=len(values))
    for value in values:
        out.append(Int64(value))
    return out^


def i32_list_of(*args: Int) -> List[Int32]:
    var out = List[Int32](capacity=len(args))
    for value in args:
        out.append(Int32(value))
    return out^


def list_of(*args: Int) -> List[Int]:
    # ponytail: Mojo 1.2.0 has no List literal ctor; append builder
    var out = List[Int](capacity=len(args))
    for value in args:
        out.append(value)
    return out^


def frag(width: Int, values: List[Int]) raises -> List[UInt8]:
    return encode_fragment(Span(samples_of(values)), width)


def test_add_matches_reference_examples() raises:
    # Phase 0 vector add-w2: [1000,-2000,30000,-32768] + [500,-500,1000,-1]
    var left = frag(2, list_of(1000, -2000, 30000, -32768))
    var right = frag(2, list_of(500, -500, 1000, -1))
    var result = add(Span(left), Span(right), 2)
    assert_equal(len(result), 8)
    assert_equal(decode_fragment(Span(result), 2), i32_list_of(1500, -2500, 31000, -32768))

    # add-w1 clamps both ways: 127+1 and -128+(-1)
    var hi = frag(1, list_of(127, -128))
    var one = frag(1, list_of(1, -1))
    var clamped = add(Span(hi), Span(one), 1)
    assert_equal(decode_fragment(Span(clamped), 1), i32_list_of(127, -128))


def test_add_all_widths_and_sides() raises:
    for width in range(1, 5):
        var lo = -1 << (width * 8 - 1)
        var hi = (1 << (width * 8 - 1)) - 1
        var a = frag(width, list_of(hi, lo, 0))
        var b = frag(width, list_of(1, -1, 0))
        var result = add(Span(a), Span(b), width)
        var decoded = decode_fragment(Span(result), width)
        assert_equal(len(decoded), 3)
        assert_equal(decoded[0], Int32(hi))
        assert_equal(decoded[1], Int32(lo))
        assert_equal(decoded[2], Int32(0))


def test_add_empty_and_length_mismatch() raises:
    var empty = List[UInt8]()
    var result = add(Span(empty), Span(List[UInt8]()), 2)
    assert_equal(len(result), 0)

    var short = frag(2, list_of(1))
    var long = frag(2, list_of(1, 2))
    with assert_raises(contains="Lengths should be the same"):
        _ = add(Span(short), Span(long), 2)
    with assert_raises(contains="Lengths should be the same"):
        _ = add(Span(long), Span(short), 2)


def test_add_validation_order() raises:
    var data = frag(2, list_of(1))
    var empty = List[UInt8]()
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = add(Span(empty), Span(List[UInt8]()), 0)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        _ = add(Span(odd), Span(List[UInt8]()), 2)
    # width validated first, then length equality
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = add(Span(empty), Span(List[UInt8]()), 7)
    _ = data


def test_bias_wraps_all_widths() raises:
    # max sample + 1 wraps to minimum
    for width in range(1, 5):
        var hi = frag(width, list_of((1 << (width * 8 - 1)) - 1))
        var result = bias(Span(hi), width, 1)
        var decoded = decode_fragment(Span(result), width)
        assert_equal(decoded[0], Int32(-1 << (width * 8 - 1)))
    # min sample - 1 wraps to maximum
    for width in range(1, 5):
        var lo = frag(width, list_of(-1 << (width * 8 - 1)))
        var result = bias(Span(lo), width, -1)
        var decoded = decode_fragment(Span(result), width)
        assert_equal(decoded[0], Int32((1 << (width * 8 - 1)) - 1))


def test_bias_values_and_zero() raises:
    var data = frag(2, list_of(1000, -1000))
    var zero = bias(Span(data), 2, 0)
    assert_equal(decode_fragment(Span(zero), 2), i32_list_of(1000, -1000))

    var shifted = bias(Span(data), 2, 10000)
    var expected = i32_list_of(11000, 9000)
    assert_equal(decode_fragment(Span(shifted), 2), expected)

    # negative bias with wrap: 32767 + (-1) = 32766; -32768 + (-1) = 32767
    var extremes = frag(2, list_of(32767, -32768))
    var result = bias(Span(extremes), 2, -1)
    assert_equal(decode_fragment(Span(result), 2), i32_list_of(32766, 32767))


def test_bias_empty_and_c_int_range() raises:
    var result = bias(Span(List[UInt8]()), 2, 100)
    assert_equal(len(result), 0)

    with assert_raises(contains="Python int too large to convert to C int"):
        _ = bias(Span(List[UInt8]()), 2, 2147483648)
    with assert_raises(contains="Python int too large to convert to C int"):
        _ = bias(Span(List[UInt8]()), 2, -2147483649)
    # boundary values are accepted
    _ = bias(Span(List[UInt8]()), 2, 2147483647)
    _ = bias(Span(List[UInt8]()), 2, -2147483648)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = bias(Span(List[UInt8]()), 0, 1)


def test_mul_floor_and_saturation() raises:
    # 3*0.5=1, -3*0.5=-2 (floor, not round-to-nearest)
    var data = frag(2, list_of(3, -3, 1, -1))
    var half = mul(Span(data), 2, 0.5)
    assert_equal(decode_fragment(Span(half), 2), i32_list_of(1, -2, 0, -1))

    # zero and one factors
    var values = frag(2, list_of(1000, -1000))
    assert_equal(decode_fragment(Span(mul(Span(values), 2, 0)), 2), i32_list_of(0, 0))
    assert_equal(decode_fragment(Span(mul(Span(values), 2, 1.0)), 2), i32_list_of(1000, -1000))

    # negative factor flips signs with floor
    var neg = mul(Span(data), 2, -1.0)
    assert_equal(decode_fragment(Span(neg), 2), i32_list_of(-3, 3, -1, 1))

    # -0.5: 3*-0.5 -> floor(-1.5) = -2; -3*-0.5 -> 1
    var neg_half = mul(Span(data), 2, -0.5)
    assert_equal(decode_fragment(Span(neg_half), 2), i32_list_of(-2, 1, -1, 0))


def test_mul_saturates_and_tiny() raises:
    var extremes = frag(2, list_of(32767, -32768))
    var big = mul(Span(extremes), 2, 100.0)
    assert_equal(decode_fragment(Span(big), 2), i32_list_of(32767, -32768))

    var wide = frag(1, list_of(127, -128))
    var w1 = mul(Span(wide), 1, 100.0)
    assert_equal(decode_fragment(Span(w1), 1), i32_list_of(127, -128))

    # 1000*0.001 is exactly 1.0 in IEEE-754; 999*0.001 = 0.999 floors to 0
    var values = frag(2, list_of(1000, -1000, 999, -999))
    var tiny = mul(Span(values), 2, 0.001)
    assert_equal(decode_fragment(Span(tiny), 2), i32_list_of(1, -1, 0, -1))

    # 1e-308 underflows magnitudes toward zero, but floor(-tiny) = -1
    var underflow = mul(Span(values), 2, 1e-308)
    assert_equal(decode_fragment(Span(underflow), 2), i32_list_of(0, -1, 0, -1))


def test_mul_infinities_and_nan_policy() raises:
    # inf saturates; -inf saturates the other way
    var values = frag(2, list_of(1000, -1000))
    var pos_inf: Float64 = inf[DType.float64]()
    var neg_inf: Float64 = -inf[DType.float64]()
    assert_equal(decode_fragment(Span(mul(Span(values), 2, pos_inf)), 2), i32_list_of(32767, -32768))
    assert_equal(
        decode_fragment(Span(mul(Span(values), 2, neg_inf)), 2), i32_list_of(-32768, 32767)
    )

    # documented port policy: NaN result (NaN factor or 0*inf) is zero
    var nan: Float64 = 0.0 / 0.0
    var nan_result = mul(Span(values), 2, nan)
    assert_equal(decode_fragment(Span(nan_result), 2), i32_list_of(0, 0))

    var zero_and_nonzero = frag(2, list_of(0, 1, -1))
    var mixed = mul(Span(zero_and_nonzero), 2, pos_inf)
    assert_equal(decode_fragment(Span(mixed), 2), i32_list_of(0, 32767, -32768))

    var empty = mul(Span(List[UInt8]()), 2, 2.0)
    assert_equal(len(empty), 0)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = mul(Span(List[UInt8]()), 0, 1.0)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        _ = mul(Span(odd), 2, 1.0)


def test_reverse_all_widths() raises:
    # vector reverse-w2: pcm(1,2,3) -> pcm(3,2,1)
    var data = frag(2, list_of(1, 2, 3))
    var result = reverse(Span(data), 2)
    assert_equal(decode_fragment(Span(result), 2), i32_list_of(3, 2, 1))

    assert_equal(len(reverse(Span(List[UInt8]()), 2)), 0)
    var single = frag(2, list_of(1234))
    var one = reverse(Span(single), 2)
    assert_equal(decode_fragment(Span(one), 2), i32_list_of(1234))

    var mixed = frag(2, list_of(1, -2))
    assert_equal(decode_fragment(Span(reverse(Span(mixed), 2)), 2), i32_list_of(-2, 1))

    for width in range(1, 5):
        var lo = -1 << (width * 8 - 1)
        var hi = (1 << (width * 8 - 1)) - 1
        var values = frag(width, list_of(lo, 0, hi))
        var reversed_values = reverse(Span(values), width)
        assert_equal(
            decode_fragment(Span(reversed_values), width), i32_list_of(hi, 0, lo)
        )
        assert_equal(len(reversed_values), 3 * width)


def test_reverse_validation() raises:
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = reverse(Span(List[UInt8]()), 0)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        odd.append(2)
        odd.append(3)
        _ = reverse(Span(odd), 2)


def test_byteswap_all_widths() raises:
    # vector byteswap-w2: pcm(1,256,-2) -> 00 01 00 01 ff fe
    var data = frag(2, list_of(1, 256, -2))
    var swapped = byteswap(Span(data), 2)
    assert_equal(len(swapped), 6)
    assert_equal(swapped[0], UInt8(0x00))
    assert_equal(swapped[1], UInt8(0x01))
    assert_equal(swapped[2], UInt8(0x01))
    assert_equal(swapped[3], UInt8(0x00))
    assert_equal(swapped[4], UInt8(0xFF))
    assert_equal(swapped[5], UInt8(0xFE))

    # width 1 is a copy
    var single_byte = List[UInt8]()
    single_byte.append(7)
    single_byte.append(8)
    var copied = byteswap(Span(single_byte), 1)
    assert_equal(copied[0], UInt8(7))
    assert_equal(copied[1], UInt8(8))

    for width in range(1, 5):
        var values = frag(width, list_of(1, -2))
        var result = byteswap(Span(values), width)
        assert_equal(len(result), 2 * width)
        # double byteswap restores the original
        var restored = byteswap(Span(result), width)
        assert_equal(
            decode_fragment(Span(restored), width),
            decode_fragment(Span(values), width),
        )


def test_byteswap_preserves_sample_order() raises:
    var values = frag(3, list_of(1, -2, 3))
    var result = byteswap(Span(values), 3)
    for index in range(3):
        for byte in range(3):
            var original = values[index * 3 + byte]
            assert_equal(result[index * 3 + (2 - byte)], original)


def test_byteswap_validation() raises:
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = byteswap(Span(List[UInt8]()), 5)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        _ = byteswap(Span(odd), 2)


def test_lin2lin_all_combinations() raises:
    for width in range(1, 5):
        for new_width in range(1, 5):
            var lo = -1 << (width * 8 - 1)
            var hi = (1 << (width * 8 - 1)) - 1
            var source = frag(width, list_of(lo, hi, -1, 0, 1))
            var result = lin2lin(Span(source), width, new_width)
            assert_equal(len(result), 5 * new_width)
            for index in range(5):
                var sample = decode_fragment(Span(source), width)[index]
                var expected: Int64
                if new_width > width:
                    expected = Int64(sample) << Int64((new_width - width) * 8)
                elif new_width < width:
                    expected = Int64(sample) >> Int64((width - new_width) * 8)
                else:
                    expected = Int64(sample)
                var decoded_new = decode_fragment(Span(result), new_width)[index]
                assert_equal(Int64(decoded_new), expected)


def test_lin2lin_reference_examples() raises:
    # lin2lin-w4-to-w2: arithmetic shift drops high bits (no saturation)
    var source = frag(4, list_of(32768, -32769))
    var result = lin2lin(Span(source), 4, 2)
    assert_equal(decode_fragment(Span(result), 2), i32_list_of(0, -1))

    # -1 stays -1 at every narrowing step (sign extension, not zero fill)
    var wide = frag(4, list_of(-1))
    for narrow in range(1, 4):
        var narrowed = lin2lin(Span(wide), 4, narrow)
        assert_equal(decode_fragment(Span(narrowed), narrow)[0], Int32(-1))

    var empty = lin2lin(Span(List[UInt8]()), 2, 3)
    assert_equal(len(empty), 0)


def test_lin2lin_validation_order() raises:
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = lin2lin(Span(List[UInt8]()), 0, 2)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = lin2lin(Span(List[UInt8]()), 2, 0)
    # source width is validated first: both invalid reports the source message
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = lin2lin(Span(List[UInt8]()), 0, 0)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        odd.append(2)
        odd.append(3)
        _ = lin2lin(Span(odd), 2, 1)


def test_operations_do_not_mutate_inputs() raises:
    var data = frag(2, list_of(1, -2))
    var original = decode_fragment(Span(data), 2)
    _ = add(Span(data), Span(frag(2, list_of(1, -2))), 2)
    _ = bias(Span(data), 2, 5)
    _ = mul(Span(data), 2, 2.0)
    _ = reverse(Span(data), 2)
    _ = byteswap(Span(data), 2)
    _ = lin2lin(Span(data), 2, 4)
    assert_equal(decode_fragment(Span(data), 2), original)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
