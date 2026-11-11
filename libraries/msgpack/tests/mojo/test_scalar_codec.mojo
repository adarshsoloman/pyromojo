"""Exact-byte and boundary tests for float, string, and binary codecs."""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_msgpack.scalar import (
    decode_scalar_exact,
    encode_bin,
    encode_float32,
    encode_float64,
    encode_scalar_value,
    encode_str,
)
from mojo_msgpack.value import VALUE_BIN, VALUE_FLOAT32, VALUE_FLOAT64, VALUE_STR, Value

from vector_support import decode_hex


def _assert_bytes(actual: List[UInt8], expected_hex: StaticString) raises:
    var expected = decode_hex(expected_hex)
    assert_equal(len(actual), len(expected))
    for index in range(len(actual)):
        assert_equal(actual[index], expected[index])


def _assert_prefix(actual: List[UInt8], expected_hex: StaticString) raises:
    var expected = decode_hex(expected_hex)
    assert_equal(len(actual) >= len(expected), True)
    for index in range(len(expected)):
        assert_equal(actual[index], expected[index])


def _repeat(byte: UInt8, count: Int) -> List[UInt8]:
    var out = List[UInt8](capacity=count)
    for _ in range(count):
        out.append(byte)
    return out^


def _repeat_sequence(unit: List[UInt8], count: Int) -> List[UInt8]:
    var out = List[UInt8](capacity=len(unit) * count)
    for _ in range(count):
        for byte in unit:
            out.append(byte)
    return out^


def _string_value(raw: List[UInt8]) raises -> Value:
    return Value.string(String(from_utf8=Span(raw)))


def _encode_bits32(bits: UInt32) -> List[UInt8]:
    var out = List[UInt8]()
    encode_float32(out, bits)
    return out^


def _encode_bits64(bits: UInt64) -> List[UInt8]:
    var out = List[UInt8]()
    encode_float64(out, bits)
    return out^


def test_float32_exact_bit_encoding() raises:
    _assert_bytes(_encode_bits32(0x00000000), "ca00000000")
    _assert_bytes(_encode_bits32(0x80000000), "ca80000000")
    _assert_bytes(_encode_bits32(0x3FC00000), "ca3fc00000")
    _assert_bytes(_encode_bits32(0x7F7FFFFF), "ca7f7fffff")
    _assert_bytes(_encode_bits32(0x00800000), "ca00800000")
    _assert_bytes(_encode_bits32(0x00000001), "ca00000001")
    _assert_bytes(_encode_bits32(0x80000001), "ca80000001")
    _assert_bytes(_encode_bits32(0x7F800000), "ca7f800000")
    _assert_bytes(_encode_bits32(0xFF800000), "caff800000")
    _assert_bytes(_encode_bits32(0x7FC00001), "ca7fc00001")
    _assert_bytes(_encode_bits32(0x7F800001), "ca7f800001")
    _assert_bytes(_encode_bits32(0xFFC00001), "caffc00001")


def test_float64_exact_bit_encoding() raises:
    _assert_bytes(_encode_bits64(0x0000000000000000), "cb0000000000000000")
    _assert_bytes(_encode_bits64(0x8000000000000000), "cb8000000000000000")
    _assert_bytes(_encode_bits64(0x3FF8000000000000), "cb3ff8000000000000")
    _assert_bytes(_encode_bits64(0x7FEFFFFFFFFFFFFF), "cb7fefffffffffffff")
    _assert_bytes(_encode_bits64(0x0010000000000000), "cb0010000000000000")
    _assert_bytes(_encode_bits64(0x0000000000000001), "cb0000000000000001")
    _assert_bytes(_encode_bits64(0x8000000000000001), "cb8000000000000001")
    _assert_bytes(_encode_bits64(0x7FF0000000000000), "cb7ff0000000000000")
    _assert_bytes(_encode_bits64(0xFFF0000000000000), "cbfff0000000000000")
    _assert_bytes(_encode_bits64(0x7FF8000000000001), "cb7ff8000000000001")
    _assert_bytes(_encode_bits64(0x7FF0000000000001), "cb7ff0000000000001")
    _assert_bytes(_encode_bits64(0xFFF8000000000001), "cbfff8000000000001")


def test_float_decode_preserves_bits() raises:
    var f32_cases = List[StaticString]()
    f32_cases.append("ca00000000")
    f32_cases.append("ca80000000")
    f32_cases.append("ca3fc00000")
    f32_cases.append("ca7f7fffff")
    f32_cases.append("ca00800000")
    f32_cases.append("ca00000001")
    f32_cases.append("ca80000001")
    f32_cases.append("ca7f800000")
    f32_cases.append("caff800000")
    f32_cases.append("ca7fc00001")
    f32_cases.append("ca7f800001")
    f32_cases.append("caffc00001")
    for hex in f32_cases:
        var value = decode_scalar_exact(decode_hex(hex))
        assert_equal(value.kind, VALUE_FLOAT32)
        var encoded = List[UInt8]()
        encode_scalar_value(encoded, value)
        _assert_bytes(encoded, hex)

    var f64_cases = List[StaticString]()
    f64_cases.append("cb0000000000000000")
    f64_cases.append("cb8000000000000000")
    f64_cases.append("cb3ff8000000000000")
    f64_cases.append("cb7fefffffffffffff")
    f64_cases.append("cb0010000000000000")
    f64_cases.append("cb0000000000000001")
    f64_cases.append("cb8000000000000001")
    f64_cases.append("cb7ff0000000000000")
    f64_cases.append("cbfff0000000000000")
    f64_cases.append("cb7ff8000000000001")
    f64_cases.append("cb7ff0000000000001")
    f64_cases.append("cbfff8000000000001")
    for hex in f64_cases:
        var value = decode_scalar_exact(decode_hex(hex))
        assert_equal(value.kind, VALUE_FLOAT64)
        var encoded = List[UInt8]()
        encode_scalar_value(encoded, value)
        _assert_bytes(encoded, hex)


def test_float_truncation_and_trailing_data() raises:
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_scalar_exact(decode_hex("ca3fc000"))
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_scalar_exact(decode_hex("cb3ff80000000000"))
    with assert_raises(contains="trailing-data: offset 5"):
        _ = decode_scalar_exact(decode_hex("ca3fc0000000"))


def test_scalar_dispatch_keeps_integers_and_rejects_nil() raises:
    var integer = decode_scalar_exact(decode_hex("ccff"))
    var encoded = List[UInt8]()
    encode_scalar_value(encoded, integer)
    _assert_bytes(encoded, "ccff")

    with assert_raises(contains="unsupported-marker: offset 0"):
        _ = decode_scalar_exact(decode_hex("c0"))
    with assert_raises(contains="invalid-marker: offset 0"):
        _ = decode_scalar_exact(decode_hex("c1"))


def test_string_marker_boundaries() raises:
    var empty = _string_value(List[UInt8]())
    var empty_encoded = List[UInt8]()
    encode_scalar_value(empty_encoded, empty)
    _assert_bytes(empty_encoded, "a0")

    var cases_31 = _string_value(_repeat(UInt8(ord("x")), 31))
    var e31 = List[UInt8]()
    encode_scalar_value(e31, cases_31)
    assert_equal(len(e31), 32)
    _assert_prefix(e31, "bf")
    assert_equal(e31[31], UInt8(ord("x")))

    var cases_32 = _string_value(_repeat(UInt8(ord("x")), 32))
    var e32 = List[UInt8]()
    encode_scalar_value(e32, cases_32)
    assert_equal(len(e32), 34)
    _assert_prefix(e32, "d920")
    assert_equal(e32[33], UInt8(ord("x")))

    var cases_255 = _string_value(_repeat(UInt8(ord("x")), 255))
    var e255 = List[UInt8]()
    encode_scalar_value(e255, cases_255)
    assert_equal(len(e255), 257)
    _assert_prefix(e255, "d9ff")

    var cases_256 = _string_value(_repeat(UInt8(ord("x")), 256))
    var e256 = List[UInt8]()
    encode_scalar_value(e256, cases_256)
    assert_equal(len(e256), 259)
    _assert_prefix(e256, "da0100")

    var cases_65535 = _string_value(_repeat(UInt8(ord("x")), 65535))
    var e65535 = List[UInt8]()
    encode_scalar_value(e65535, cases_65535)
    assert_equal(len(e65535), 65538)
    _assert_prefix(e65535, "daffff")

    var cases_65536 = _string_value(_repeat(UInt8(ord("x")), 65536))
    var e65536 = List[UInt8]()
    encode_scalar_value(e65536, cases_65536)
    assert_equal(len(e65536), 65541)
    _assert_prefix(e65536, "db00010000")
    assert_equal(e65536[65540], UInt8(ord("x")))


def test_string_marker_uses_utf8_byte_length() raises:
    var euro = decode_hex("e282ac")
    var fix_max_bytes = _string_value(_repeat_sequence(euro, 10).copy() + List[UInt8]([UInt8(ord("x"))]))
    var e1 = List[UInt8]()
    encode_scalar_value(e1, fix_max_bytes)
    assert_equal(len(e1), 32)
    _assert_prefix(e1, "bf")

    var eacute = decode_hex("c3a9")
    var str8_min_bytes = _string_value(_repeat_sequence(eacute, 16))
    var e2 = List[UInt8]()
    encode_scalar_value(e2, str8_min_bytes)
    assert_equal(len(e2), 34)
    _assert_prefix(e2, "d920")


def test_string_decode_valid_utf8() raises:
    var hello = decode_scalar_exact(decode_hex("a568656c6c6f"))
    assert_equal(hello.kind, VALUE_STR)
    assert_equal(len(hello.data), 5)
    assert_equal(hello.data[0], UInt8(ord("h")))

    var unicode_value = decode_scalar_exact(decode_hex("a3e282ac"))
    assert_equal(len(unicode_value.data), 3)
    assert_equal(unicode_value.data[0], 0xE2)

    var embedded_nul = decode_scalar_exact(decode_hex("a3610062"))
    assert_equal(len(embedded_nul.data), 3)
    assert_equal(embedded_nul.data[1], 0)


def test_string_rejects_invalid_and_truncated_utf8() raises:
    var invalid = List[StaticString]()
    invalid.append("a180")
    invalid.append("a2c080")
    invalid.append("a3eda080")
    invalid.append("a4f4908080")
    invalid.append("a2e282")
    for hex in invalid:
        with assert_raises(contains="invalid-utf8: offset 1"):
            _ = decode_scalar_exact(decode_hex(hex))

    var truncated = List[StaticString]()
    truncated.append("a56162")
    truncated.append("d9056162")
    truncated.append("da00056162")
    truncated.append("db000000056162")
    truncated.append("dbffffffff")
    for hex in truncated:
        with assert_raises(contains="truncated: offset 0"):
            _ = decode_scalar_exact(decode_hex(hex))

    with assert_raises(contains="trailing-data: offset 2"):
        _ = decode_scalar_exact(decode_hex("a16162"))


def test_binary_marker_boundaries_and_all_bytes() raises:
    var empty = Value.binary(List[UInt8]())
    var e0 = List[UInt8]()
    encode_scalar_value(e0, empty)
    _assert_bytes(e0, "c400")

    var all_bytes = List[UInt8](capacity=256)
    for value in range(256):
        all_bytes.append(UInt8(value))
    var all_value = Value.binary(all_bytes^)
    var eall = List[UInt8]()
    encode_scalar_value(eall, all_value)
    assert_equal(len(eall), 259)
    _assert_prefix(eall, "c50100")
    for value in range(256):
        assert_equal(eall[3 + value], UInt8(value))

    var max255 = Value.binary(_repeat(UInt8(0), 255))
    var e255 = List[UInt8]()
    encode_scalar_value(e255, max255)
    assert_equal(len(e255), 257)
    _assert_prefix(e255, "c4ff")

    var size256 = Value.binary(_repeat(UInt8(0), 256))
    var e256 = List[UInt8]()
    encode_scalar_value(e256, size256)
    assert_equal(len(e256), 259)
    _assert_prefix(e256, "c50100")

    var size65535 = Value.binary(_repeat(UInt8(0), 65535))
    var e65535 = List[UInt8]()
    encode_scalar_value(e65535, size65535)
    assert_equal(len(e65535), 65538)
    _assert_prefix(e65535, "c5ffff")

    var size65536 = Value.binary(_repeat(UInt8(0), 65536))
    var e65536 = List[UInt8]()
    encode_scalar_value(e65536, size65536)
    assert_equal(len(e65536), 65541)
    _assert_prefix(e65536, "c600010000")


def test_binary_decode_preserves_bytes() raises:
    var raw = List[UInt8](capacity=256)
    for value in range(256):
        raw.append(UInt8(value))
    var decoded = decode_scalar_exact(decode_hex(
        "c50100" + "000102030405060708090a0b0c0d0e0f"
        "101112131415161718191a1b1c1d1e1f"
        "202122232425262728292a2b2c2d2e2f"
        "303132333435363738393a3b3c3d3e3f"
        "404142434445464748494a4b4c4d4e4f"
        "505152535455565758595a5b5c5d5e5f"
        "606162636465666768696a6b6c6d6e6f"
        "707172737475767778797a7b7c7d7e7f"
        "808182838485868788898a8b8c8d8e8f"
        "909192939495969798999a9b9c9d9e9f"
        "a0a1a2a3a4a5a6a7a8a9aaabacadaeaf"
        "b0b1b2b3b4b5b6b7b8b9babbbcbdbebf"
        "c0c1c2c3c4c5c6c7c8c9cacbcccdcecf"
        "d0d1d2d3d4d5d6d7d8d9dadbdcdddedf"
        "e0e1e2e3e4e5e6e7e8e9eaebecedeeef"
        "f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff"
    ))
    assert_equal(decoded.kind, VALUE_BIN)
    assert_equal(len(decoded.data), 256)
    for index in range(256):
        assert_equal(decoded.data[index], raw[index])


def test_binary_truncation_and_trailing_data() raises:
    var truncated = List[StaticString]()
    truncated.append("c4050102")
    truncated.append("c500050102")
    truncated.append("c6000000050102")
    truncated.append("c6ffffffff")
    for hex in truncated:
        with assert_raises(contains="truncated: offset 0"):
            _ = decode_scalar_exact(decode_hex(hex))

    with assert_raises(contains="trailing-data: offset 3"):
        _ = decode_scalar_exact(decode_hex("c4010102"))


def test_encoding_rejects_unsupported_value_kinds() raises:
    var out = List[UInt8]()
    with assert_raises(contains="unsupported-value"):
        encode_scalar_value(out, Value.nil())
    assert_equal(len(out), 0)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
