"""Exact-byte and boundary tests for the integer codec."""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_msgpack.integer import (
    IntegerDecoder,
    append_integer_model,
    decode_exact,
    decode_integer_model,
    encode_int,
    encode_uint,
    encode_value,
)
from mojo_msgpack.value import VALUE_INT, VALUE_UINT, Value

from vector_support import decode_hex


def _assert_bytes(actual: List[UInt8], expected_hex: StaticString) raises:
    var expected = decode_hex(expected_hex)
    assert_equal(len(actual), len(expected))
    for index in range(len(actual)):
        assert_equal(actual[index], expected[index])


def _encode_signed(value: Int64) raises -> List[UInt8]:
    var out = List[UInt8]()
    encode_int(out, value)
    return out^


def _encode_unsigned(value: UInt64) raises -> List[UInt8]:
    var out = List[UInt8]()
    encode_uint(out, value)
    return out^


def test_positive_encoding_boundaries() raises:
    _assert_bytes(_encode_signed(0), "00")
    _assert_bytes(_encode_signed(1), "01")
    _assert_bytes(_encode_signed(126), "7e")
    _assert_bytes(_encode_signed(127), "7f")
    _assert_bytes(_encode_signed(128), "cc80")
    _assert_bytes(_encode_signed(129), "cc81")
    _assert_bytes(_encode_signed(254), "ccfe")
    _assert_bytes(_encode_signed(255), "ccff")
    _assert_bytes(_encode_signed(256), "cd0100")
    _assert_bytes(_encode_signed(257), "cd0101")
    _assert_bytes(_encode_signed(65535), "cdffff")
    _assert_bytes(_encode_signed(65536), "ce00010000")
    _assert_bytes(_encode_signed(2147483647), "ce7fffffff")
    _assert_bytes(_encode_signed(2147483648), "ce80000000")
    _assert_bytes(_encode_signed(4294967294), "cefffffffe")
    _assert_bytes(_encode_signed(4294967295), "ceffffffff")
    _assert_bytes(_encode_signed(4294967296), "cf0000000100000000")
    _assert_bytes(_encode_signed(Int64.MAX), "cf7fffffffffffffff")


def test_unsigned_encoding_boundaries() raises:
    _assert_bytes(_encode_unsigned(0), "00")
    _assert_bytes(_encode_unsigned(127), "7f")
    _assert_bytes(_encode_unsigned(128), "cc80")
    _assert_bytes(_encode_unsigned(255), "ccff")
    _assert_bytes(_encode_unsigned(256), "cd0100")
    _assert_bytes(_encode_unsigned(65535), "cdffff")
    _assert_bytes(_encode_unsigned(65536), "ce00010000")
    _assert_bytes(_encode_unsigned(4294967295), "ceffffffff")
    _assert_bytes(_encode_unsigned(4294967296), "cf0000000100000000")
    _assert_bytes(_encode_unsigned(9223372036854775808), "cf8000000000000000")
    _assert_bytes(_encode_unsigned(UInt64.MAX), "cfffffffffffffffff")


def test_negative_encoding_boundaries() raises:
    _assert_bytes(_encode_signed(-1), "ff")
    _assert_bytes(_encode_signed(-31), "e1")
    _assert_bytes(_encode_signed(-32), "e0")
    _assert_bytes(_encode_signed(-33), "d0df")
    _assert_bytes(_encode_signed(-127), "d081")
    _assert_bytes(_encode_signed(-128), "d080")
    _assert_bytes(_encode_signed(-129), "d1ff7f")
    _assert_bytes(_encode_signed(-32767), "d18001")
    _assert_bytes(_encode_signed(-32768), "d18000")
    _assert_bytes(_encode_signed(-32769), "d2ffff7fff")
    _assert_bytes(_encode_signed(-2147483647), "d280000001")
    _assert_bytes(_encode_signed(-2147483648), "d280000000")
    _assert_bytes(_encode_signed(-2147483649), "d3ffffffff7fffffff")
    _assert_bytes(_encode_signed(-9223372036854775807), "d38000000000000001")
    _assert_bytes(_encode_signed(Int64.MIN), "d38000000000000000")


def test_decode_all_integer_families() raises:
    var zero = decode_exact(decode_hex("00"))
    assert_equal(zero.kind, VALUE_UINT)
    assert_equal(zero.as_uint64(), 0)

    var fix_127 = decode_exact(decode_hex("7f"))
    assert_equal(fix_127.as_uint64(), 127)

    var fix_negative = decode_exact(decode_hex("e0"))
    assert_equal(fix_negative.kind, VALUE_INT)
    assert_equal(fix_negative.as_int64(), -32)

    var uint8 = decode_exact(decode_hex("ccff"))
    assert_equal(uint8.kind, VALUE_UINT)
    assert_equal(uint8.as_uint64(), 255)

    var uint16 = decode_exact(decode_hex("cd0100"))
    assert_equal(uint16.as_uint64(), 256)

    var uint32 = decode_exact(decode_hex("ce00010000"))
    assert_equal(uint32.as_uint64(), 65536)

    var uint64_value = decode_exact(decode_hex("cfffffffffffffffff"))
    assert_equal(uint64_value.kind, VALUE_UINT)
    assert_equal(uint64_value.as_uint64(), UInt64.MAX)

    var int8 = decode_exact(decode_hex("d080"))
    assert_equal(int8.kind, VALUE_INT)
    assert_equal(int8.as_int64(), -128)

    var int16 = decode_exact(decode_hex("d18000"))
    assert_equal(int16.as_int64(), -32768)

    var int32 = decode_exact(decode_hex("d280000000"))
    assert_equal(int32.as_int64(), -2147483648)

    var int64_value = decode_exact(decode_hex("d38000000000000000"))
    assert_equal(int64_value.kind, VALUE_INT)
    assert_equal(int64_value.as_int64(), Int64.MIN)


def test_truncated_payloads_keep_position() raises:
    var payloads = List[StaticString]()
    payloads.append("cc")
    payloads.append("cd01")
    payloads.append("ce000000")
    payloads.append("cf00000000000000")
    payloads.append("d0")
    payloads.append("d1ff")
    payloads.append("d2000000")
    payloads.append("d300000000000000")
    for hex in payloads:
        var decoder = IntegerDecoder(decode_hex(hex))
        with assert_raises(contains="truncated: offset 0"):
            _ = decoder.decode()
        assert_equal(decoder.pos, 0)
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_exact(List[UInt8]())


def test_truncated_after_success_reports_marker_offset() raises:
    var decoder = IntegerDecoder(decode_hex("01cd01"))
    var first = decoder.decode()
    assert_equal(first.as_uint64(), 1)
    assert_equal(decoder.pos, 1)
    with assert_raises(contains="truncated: offset 1"):
        _ = decoder.decode()
    assert_equal(decoder.pos, 1)


def test_unsupported_marker_reports_category_and_offset() raises:
    var decoder = IntegerDecoder(decode_hex("c0"))
    with assert_raises(contains="unsupported-marker: offset 0"):
        _ = decoder.decode()
    assert_equal(decoder.pos, 0)
    with assert_raises(contains="unsupported-marker: offset 0"):
        _ = decode_exact(decode_hex("ca3fc00000"))


def test_trailing_data_is_rejected() raises:
    with assert_raises(contains="trailing-data: offset 1"):
        _ = decode_exact(decode_hex("0102"))


def test_decoder_advances_only_on_success() raises:
    var decoder = IntegerDecoder(decode_hex("01d0ffcc80"))
    var first = decoder.decode()
    var second = decoder.decode()
    var third = decoder.decode()
    assert_equal(first.as_uint64(), 1)
    assert_equal(second.as_int64(), -1)
    assert_equal(third.as_uint64(), 128)
    assert_equal(decoder.pos, 5)


def test_integer_model_preserves_tags() raises:
    var signed_model = List[UInt8]()
    append_integer_model(signed_model, Value.integer(-1))
    assert_equal(len(signed_model), 9)
    var signed = decode_integer_model(Span(signed_model))
    assert_equal(signed.kind, VALUE_INT)
    assert_equal(signed.as_int64(), -1)

    var unsigned_model = List[UInt8]()
    append_integer_model(unsigned_model, Value.unsigned(UInt64.MAX))
    assert_equal(unsigned_model[0], 1)
    var unsigned = decode_integer_model(Span(unsigned_model))
    assert_equal(unsigned.kind, VALUE_UINT)
    assert_equal(unsigned.as_uint64(), UInt64.MAX)

    with assert_raises(contains="invalid-model: offset 0"):
        _ = decode_integer_model(decode_hex("02ffffffffffffffff"))
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_integer_model(decode_hex("00ff"))


def test_encode_value_rejects_non_integers() raises:
    var out = List[UInt8]()
    with assert_raises(contains="unsupported-value"):
        encode_value(out, Value.string("x"))
    assert_equal(len(out), 0)


def test_signed_unsigned_roundtrip_extremes() raises:
    var values = List[Value]()
    values.append(Value.integer(Int64.MIN))
    values.append(Value.integer(-1))
    values.append(Value.integer(0))
    values.append(Value.integer(Int64.MAX))
    values.append(Value.unsigned(0))
    values.append(Value.unsigned(UInt64.MAX))
    for index in range(len(values)):
        var encoded = List[UInt8]()
        encode_value(encoded, values[index])
        var decoded = decode_exact(Span(encoded))
        assert_equal(decoded.int_bits, values[index].int_bits)
        if not values[index].is_unsigned() and values[index].as_int64() < 0:
            assert_equal(decoded.kind, VALUE_INT)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
