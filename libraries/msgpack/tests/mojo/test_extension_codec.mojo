"""Exact-byte and validation tests for extensions and timestamps."""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_msgpack.container import (
    append_value_model,
    decode_value_exact,
    decode_value_model_exact,
    encode_value,
)
from mojo_msgpack.value import VALUE_ARRAY, VALUE_EXT, VALUE_TIMESTAMP, Value

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


def _encode(value: Value) raises -> List[UInt8]:
    var out = List[UInt8]()
    encode_value(out, value)
    return out^


def _bytes(count: Int, byte: UInt8) -> List[UInt8]:
    var out = List[UInt8](capacity=count)
    for _ in range(count):
        out.append(byte)
    return out^


def _decode(hex: StaticString) raises -> Value:
    return decode_value_exact(decode_hex(hex))


def test_fixext_markers_and_shortest_selection() raises:
    _assert_bytes(_encode(Value.ext(Int8(3), _bytes(1, 1))), "d40301")
    _assert_bytes(_encode(Value.ext(Int8(3), _bytes(2, 1))), "d5030101")
    _assert_bytes(_encode(Value.ext(Int8(3), _bytes(4, 1))), "d60301010101")
    _assert_bytes(
        _encode(Value.ext(Int8(3), _bytes(8, 1))), "d7030101010101010101"
    )
    _assert_bytes(
        _encode(Value.ext(Int8(3), _bytes(16, 1))),
        "d80301010101010101010101010101010101",
    )
    _assert_bytes(_encode(Value.ext(Int8(3), _bytes(3, 2))), "c70303020202")
    _assert_bytes(_encode(Value.ext(Int8(3), _bytes(5, 2))), "c705030202020202")
    _assert_prefix(_encode(Value.ext(Int8(3), _bytes(17, 4))), "c71103")


def test_varlen_boundaries() raises:
    _assert_prefix(_encode(Value.ext(Int8(42), _bytes(255, 0))), "c7ff2a")
    assert_equal(len(_encode(Value.ext(Int8(42), _bytes(255, 0)))), 258)
    _assert_prefix(_encode(Value.ext(Int8(42), _bytes(256, 0))), "c801002a")
    assert_equal(len(_encode(Value.ext(Int8(42), _bytes(256, 0)))), 260)
    _assert_prefix(_encode(Value.ext(Int8(42), _bytes(65535, 0))), "c8ffff2a")
    _assert_prefix(_encode(Value.ext(Int8(42), _bytes(65536, 0))), "c9000100002a")


def test_empty_payload_and_negative_codes() raises:
    var empty = _encode(Value.ext(Int8(42), List[UInt8]()))
    _assert_bytes(empty, "c7002a")
    assert_equal(_decode("c7002a").ext_code, Int8(42))
    assert_equal(len(_decode("c7002a").data), 0)

    var negative = _encode(Value.ext(Int8(-128), _bytes(1, 0x2A)))
    _assert_bytes(negative, "d4802a")
    var decoded = _decode("d4802a")
    assert_equal(decoded.kind, VALUE_EXT)
    assert_equal(decoded.ext_code, Int8(-128))
    assert_equal(decoded.data[0], UInt8(0x2A))

    var minus_two = _encode(Value.ext(Int8(-2), _bytes(2, 7)))
    _assert_bytes(minus_two, "d5fe0707")
    assert_equal(_decode("d5fe0707").ext_code, Int8(-2))


def test_timestamp_shortest_selection() raises:
    _assert_bytes(_encode(Value.timestamp(0, 0)), "d6ff00000000")
    _assert_bytes(_encode(Value.timestamp(4294967295, 0)), "d6ffffffffff")
    _assert_prefix(_encode(Value.timestamp(4294967295, 1)), "d7ff")
    _assert_prefix(_encode(Value.timestamp(4294967296, 0)), "d7ff")
    _assert_bytes(
        _encode(Value.timestamp(17179869183, 999999999)), "d7ffee6b27ffffffffff"
    )
    _assert_bytes(
        _encode(Value.timestamp(17179869184, 0)),
        "c70cff000000000000000400000000",
    )
    _assert_bytes(
        _encode(Value.timestamp(-1, 0)), "c70cff00000000ffffffffffffffff"
    )
    _assert_prefix(_encode(Value.timestamp(0, 999999999)), "d7ff")


def test_timestamp_decode_preserves_values() raises:
    var ts32 = _decode("d6ff00000001")
    assert_equal(ts32.kind, VALUE_TIMESTAMP)
    assert_equal(ts32.as_int64(), 1)
    assert_equal(ts32.nsec, UInt32(0))
    _assert_bytes(_encode(ts32), "d6ff00000001")

    var ts64 = _decode("d7ffee6b27ffffffffff")
    assert_equal(ts64.as_int64(), 17179869183)
    assert_equal(ts64.nsec, UInt32(999999999))
    _assert_bytes(_encode(ts64), "d7ffee6b27ffffffffff")

    var ts96 = _decode("c70cff00000000ffffffffffffffff")
    assert_equal(ts96.as_int64(), -1)
    assert_equal(ts96.nsec, UInt32(0))
    _assert_bytes(_encode(ts96), "c70cff00000000ffffffffffffffff")


def test_timestamp_rejects_invalid_values() raises:
    var bad_nsec = List[UInt8]()
    with assert_raises(contains="invalid-timestamp"):
        encode_value(bad_nsec, Value.timestamp(0, UInt32(1000000000)))
    assert_equal(len(bad_nsec), 0)

    var invalid = List[StaticString]()
    invalid.append("c700ff")
    invalid.append("c705ff0102030405")
    invalid.append("d4ff01")
    invalid.append("d5ff0102")
    invalid.append("d8ff00000000000000000000000000000001")
    for hex in invalid:
        with assert_raises(contains="invalid-timestamp: offset 0"):
            _ = _decode(hex)

    with assert_raises(contains="invalid-timestamp: offset 0"):
        _ = _decode("c70cff3b9aca000000000000000001")
    with assert_raises(contains="invalid-timestamp: offset 0"):
        _ = _decode("d7fffffffffc00000000")


def test_truncated_extensions() raises:
    var truncated = List[StaticString]()
    truncated.append("d4")
    truncated.append("d401")
    truncated.append("c7")
    truncated.append("c701")
    truncated.append("c8")
    truncated.append("c900000001")
    truncated.append("d6ff000000")
    for hex in truncated:
        with assert_raises(contains="truncated: offset 0"):
            _ = _decode(hex)

    with assert_raises(contains="truncated: offset 0"):
        _ = _decode("c9000100002a78787878787878787878")
    with assert_raises(contains="trailing-data: offset 3"):
        _ = _decode("d401022a")


def test_nested_ext_and_timestamp() raises:
    var items = List[Value](capacity=3)
    items.append(Value.ext(Int8(3), _bytes(3, 1)))
    items.append(Value.timestamp(4294967296, 0))
    items.append(Value.nil())
    var value = Value.array(items^)
    var encoded = _encode(value)
    _assert_bytes(encoded, "93c70303010101d7ff0000000100000000c0")
    var decoded = decode_value_exact(Span(encoded))
    assert_equal(decoded.kind, VALUE_ARRAY)
    assert_equal(decoded.kids[0].kind, VALUE_EXT)
    assert_equal(decoded.kids[1].as_int64(), 4294967296)
    assert_equal(decoded.kids[2].is_nil(), True)
    _assert_bytes(_encode(decoded), "93c70303010101d7ff0000000100000000c0")

    var pairs = List[Value](capacity=4)
    pairs.append(Value.timestamp(5, 0))
    pairs.append(Value.string(String("t")))
    pairs.append(Value.string(String("e")))
    pairs.append(Value.ext(Int8(7), _bytes(1, 0)))
    var mapping = Value.map(pairs^)
    var mencoded = _encode(mapping)
    _assert_bytes(mencoded, "82d6ff00000005a174a165d40700")
    var mdecoded = decode_value_exact(Span(mencoded))
    assert_equal(mdecoded.kids[0].as_int64(), 5)
    assert_equal(mdecoded.kids[3].ext_code, Int8(7))


def test_ext_model_roundtrip() raises:
    var items = List[Value](capacity=2)
    items.append(Value.ext(Int8(42), _bytes(2, 9)))
    items.append(Value.timestamp(-3, 250))
    var model = List[UInt8]()
    append_value_model(model, Value.array(items^))
    var decoded = decode_value_model_exact(Span(model))
    assert_equal(decoded.kind, VALUE_ARRAY)
    assert_equal(len(decoded.kids), 2)
    assert_equal(decoded.kids[0].ext_code, Int8(42))
    assert_equal(decoded.kids[0].data[1], UInt8(9))
    assert_equal(decoded.kids[1].as_int64(), -3)
    assert_equal(decoded.kids[1].nsec, UInt32(250))
    _assert_bytes(_encode(decoded), "92d52a0909c70cff000000fafffffffffffffffd")


def _append_value_model_check_timestamp_code() raises -> List[UInt8]:
    var out = List[UInt8]()
    append_value_model(out, Value.ext(Int8(-1), _bytes(1, 0)))
    return out^


def test_ext_model_rejects_malformed() raises:
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_model_exact(decode_hex("16"))
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_model_exact(decode_hex("17"))
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_model_exact(decode_hex("16ff000000"))
    with assert_raises(contains="trailing-data: offset 7"):
        _ = decode_value_model_exact(decode_hex("162a000000010100"))
    with assert_raises(contains="invalid-model"):
        _ = decode_value_model_exact(decode_hex("18"))
    with assert_raises(contains="invalid-timestamp"):
        _ = decode_value_model_exact(decode_hex("16ff0000000102"))
    with assert_raises(contains="invalid-timestamp: offset 0"):
        _ = decode_value_model_exact(decode_hex("1700000000000000003b9aca00"))
    with assert_raises(contains="invalid-value"):
        _ = _append_value_model_check_timestamp_code()


def test_timestamp_model_validates_and_decodes_reserved_code() raises:
    var decoded = decode_value_model_exact(decode_hex("16ff0000000400000001"))
    assert_equal(decoded.kind, VALUE_TIMESTAMP)
    assert_equal(decoded.as_int64(), 1)

    var out = List[UInt8]()
    with assert_raises(contains="invalid-timestamp"):
        append_value_model(out, Value.timestamp(0, UInt32(1000000000)))


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
