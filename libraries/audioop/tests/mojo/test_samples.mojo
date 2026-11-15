"""Phase 1 native tests: signed sample representation.

Covers width validation, signed boundaries for widths 1-4, single-sample
encode/decode round-trips, fragment decoding/encoding (including empty,
mixed-sign and repeated-boundary content), 24-bit sign extension,
out-of-range rejection, index errors, validation order, and native byte
order against the Phase 0 reference observations.
"""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_audioop import (
    decode_fragment,
    decode_sample,
    encode_fragment,
    encode_sample,
    in_sample_range,
    native_is_little_endian,
    sample_count,
    sample_max,
    sample_min,
    validate_fragment,
    validate_width,
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


def sample_values(width: Int) raises -> List[Int64]:
    var lo = sample_min(width)
    var hi = sample_max(width)
    var values = List[Int64](capacity=7)
    values.append(Int64(lo))
    values.append(Int64(lo) + 1)
    values.append(Int64(-1))
    values.append(Int64(0))
    values.append(Int64(1))
    values.append(Int64(hi) - 1)
    values.append(Int64(hi))
    return values^


def test_width_validation_accepts_supported_widths() raises:
    for width in range(1, 5):
        validate_width(width)
        assert_equal(sample_min(width) < Int32(0), True)
        assert_equal(sample_max(width) > Int32(0), True)


def test_width_validation_rejects_unsupported_widths() raises:
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        validate_width(0)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        validate_width(-1)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        validate_width(5)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = sample_min(6)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = decode_fragment(List[UInt8](), 0)


def test_signed_boundaries_roundtrip_all_widths() raises:
    for width in range(1, 5):
        for value in sample_values(width):
            var encoded = encode_sample(width, value)
            assert_equal(len(encoded), width)
            var decoded = decode_sample(Span(encoded), width, 0)
            assert_equal(decoded, Int32(value))

            var single = samples_of(List[Int]())
            single.append(value)
            var fragment = encode_fragment(Span(single), width)
            assert_equal(len(fragment), width)
            var back = decode_fragment(Span(fragment), width)
            assert_equal(len(back), 1)
            assert_equal(back[0], Int32(value))


def test_24bit_regression_values() raises:
    var values = List[Int](capacity=7)
    values.append(-8388608)
    values.append(-8388607)
    values.append(-1)
    values.append(0)
    values.append(1)
    values.append(8388606)
    values.append(8388607)

    var little = native_is_little_endian()
    for value in values:
        var encoded = encode_sample(3, Int64(value))
        assert_equal(len(encoded), 3)
        assert_equal(decode_sample(Span(encoded), 3, 0), Int32(value))

        var raw = Int64(value)
        if raw < 0:
            raw += 16777216
        var expected_low = UInt8(raw & 0xFF)
        var expected_mid = UInt8((raw >> 8) & 0xFF)
        var expected_high = UInt8((raw >> 16) & 0xFF)
        if little:
            assert_equal(encoded[0], expected_low)
            assert_equal(encoded[1], expected_mid)
            assert_equal(encoded[2], expected_high)
        else:
            assert_equal(encoded[0], expected_high)
            assert_equal(encoded[1], expected_mid)
            assert_equal(encoded[2], expected_low)


def test_24bit_native_order_reference_bytes() raises:
    # Phase 0 probe: -8388608 is 0x800000 and 8388607 is 0x7FFFFF in
    # native word order; the reference's GETSAMPLE reads the host order.
    if native_is_little_endian():
        var lo = hex_bytes("000080")
        var hi = hex_bytes("ffff7f")
        assert_equal(decode_sample(Span(lo), 3, 0), Int32(-8388608))
        assert_equal(decode_sample(Span(hi), 3, 0), Int32(8388607))
    else:
        var lo = hex_bytes("800000")
        var hi = hex_bytes("7fffff")
        assert_equal(decode_sample(Span(lo), 3, 0), Int32(-8388608))
        assert_equal(decode_sample(Span(hi), 3, 0), Int32(8388607))


def test_native_order_matches_reference_vectors() raises:
    # Reference getsample(b"\x34\x12", 2, 0) == 4660 on a little-endian
    # host; the same bytes read as 0x1234 on a big-endian host.
    if native_is_little_endian():
        var fragment = hex_bytes("3412")
        assert_equal(decode_sample(Span(fragment), 2, 0), Int32(4660))
        var value = encode_sample(2, Int64(4660))
        assert_equal(value[0], UInt8(0x34))
        assert_equal(value[1], UInt8(0x12))
    else:
        var fragment = hex_bytes("1234")
        assert_equal(decode_sample(Span(fragment), 2, 0), Int32(4660))
        var value = encode_sample(2, Int64(4660))
        assert_equal(value[0], UInt8(0x12))
        assert_equal(value[1], UInt8(0x34))


def test_invalid_values_are_rejected_not_wrapped() raises:
    for width in range(1, 5):
        var lo = sample_min(width)
        var hi = sample_max(width)
        with assert_raises(contains="out of range"):
            _ = encode_sample(width, Int64(lo) - 1)
        with assert_raises(contains="out of range"):
            _ = encode_sample(width, Int64(hi) + 1)
        var bad = List[Int64](capacity=2)
        bad.append(Int64(0))
        bad.append(Int64(lo) - 1)
        with assert_raises(contains="out of range"):
            _ = encode_fragment(Span(bad), width)
        with assert_raises(contains="out of range"):
            _ = encode_fragment(Span(bad), width)
        assert_equal(in_sample_range(width, Int64(lo)), True)
        assert_equal(in_sample_range(width, Int64(hi)), True)
        assert_equal(in_sample_range(width, Int64(lo) - 1), False)
        assert_equal(in_sample_range(width, Int64(hi) + 1), False)


def test_empty_fragment_is_valid() raises:
    var empty = List[UInt8]()
    for width in range(1, 5):
        validate_fragment(Span(empty), width)
        var decoded = decode_fragment(Span(empty), width)
        assert_equal(len(decoded), 0)
        assert_equal(sample_count(Span(empty), width), 0)

    var no_samples = List[Int64]()
    for width in range(1, 5):
        var encoded = encode_fragment(Span(no_samples), width)
        assert_equal(len(encoded), 0)


def test_incomplete_fragment_is_rejected() raises:
    for width in range(2, 5):
        var partial = List[UInt8](capacity=width - 1)
        for _ in range(width - 1):
            partial.append(0)
        with assert_raises(contains="not a whole number of frames"):
            _ = decode_fragment(Span(partial), width)
        with assert_raises(contains="not a whole number of frames"):
            _ = decode_sample(Span(partial), width, 0)

    var five = hex_bytes("0000000000")
    with assert_raises(contains="not a whole number of frames"):
        _ = decode_fragment(Span(five), 3)


def test_validation_order_width_before_length() raises:
    var one = hex_bytes("00")
    # Width 0 must report the width error even though 1 % 0 is undefined.
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        validate_fragment(Span(one), 0)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        validate_fragment(Span(one), 5)
    with assert_raises(contains="not a whole number of frames"):
        validate_fragment(Span(one), 2)


def test_sample_index_errors() raises:
    var fragment = hex_bytes("00000100")
    with assert_raises(contains="Index out of range"):
        _ = decode_sample(Span(fragment), 2, -1)
    with assert_raises(contains="Index out of range"):
        _ = decode_sample(Span(fragment), 2, 2)
    with assert_raises(contains="Index out of range"):
        _ = decode_sample(Span(fragment), 2, 99)

    var empty = List[UInt8]()
    with assert_raises(contains="Index out of range"):
        _ = decode_sample(Span(empty), 1, 0)


def test_fragment_content_patterns() raises:
    var zeroes = List[Int](capacity=8)
    for _ in range(8):
        zeroes.append(0)
    var zero_fragment = encode_fragment(Span(samples_of(zeroes)), 2)
    assert_equal(len(zero_fragment), 16)
    var zero_back = decode_fragment(Span(zero_fragment), 2)
    assert_equal(len(zero_back), 8)
    for value in zero_back:
        assert_equal(value, Int32(0))

    var alternating = List[Int](capacity=8)
    for i in range(8):
        if i % 2 == 0:
            alternating.append(1000)
        else:
            alternating.append(-1000)
    var alt_fragment = encode_fragment(Span(samples_of(alternating)), 2)
    var alt_back = decode_fragment(Span(alt_fragment), 2)
    assert_equal(len(alt_back), 8)
    for i in range(8):
        assert_equal(alt_back[i], Int32(alternating[i]))

    for width in range(1, 5):
        var lo = sample_min(width)
        var hi = sample_max(width)
        var extremes = List[Int64](capacity=6)
        for _ in range(3):
            extremes.append(Int64(lo))
            extremes.append(Int64(hi))
        var fragment = encode_fragment(Span(extremes), width)
        assert_equal(len(fragment), 6 * width)
        var back = decode_fragment(Span(fragment), width)
        assert_equal(len(back), 6)
        for i in range(6):
            assert_equal(back[i], Int32(extremes[i]))


def test_sample_count_and_multiple_samples() raises:
    var samples = List[Int](capacity=5)
    samples.append(-3)
    samples.append(-2)
    samples.append(-1)
    samples.append(0)
    samples.append(1)
    for width in range(1, 5):
        var fragment = encode_fragment(Span(samples_of(samples)), width)
        assert_equal(len(fragment), 5 * width)
        assert_equal(sample_count(Span(fragment), width), 5)
        for i in range(5):
            assert_equal(decode_sample(Span(fragment), width, i), Int32(samples[i]))


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
