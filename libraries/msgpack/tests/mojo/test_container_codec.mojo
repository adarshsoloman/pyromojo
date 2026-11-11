"""Exact-byte, boundary, and limit tests for arrays and maps."""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_msgpack.container import (
    append_value_model,
    decode_value_exact,
    decode_value_model_exact,
    encode_value,
)
from mojo_msgpack.value import VALUE_ARRAY, VALUE_MAP, Value, make_array_chain

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


def _encode(
    value: Value, max_depth: Int = 128, max_container_items: Int = 1_000_000
) raises -> List[UInt8]:
    var out = List[UInt8]()
    encode_value(out, value, max_depth, max_container_items)
    return out^


def _decode(hex: StaticString) raises -> Value:
    return decode_value_exact(decode_hex(hex))


def test_empty_containers_and_headers() raises:
    _assert_bytes(_encode(Value.array(List[Value]())), "90")
    _assert_bytes(_encode(Value.map(List[Value]())), "80")

    var items = List[Value](capacity=4)
    items.append(Value.integer(1))
    items.append(Value.string(String("two")))
    items.append(Value.bool(True))
    items.append(Value.nil())
    _assert_bytes(_encode(Value.array(items^)), "9401a374776fc3c0")

    var pairs = List[Value](capacity=2)
    pairs.append(Value.string(String("a")))
    pairs.append(Value.integer(1))
    _assert_bytes(_encode(Value.map(pairs^)), "81a16101")


def test_nested_containers_roundtrip() raises:
    var pair_items = List[Value](capacity=2)
    pair_items.append(Value.string(String("k")))
    pair_items.append(Value.array(List[Value]()))
    var mapping = Value.map(pair_items^)

    var outer = List[Value](capacity=2)
    outer.append(mapping^)
    outer.append(Value.bool(False))
    var value = Value.array(outer^)

    var encoded = _encode(value)
    _assert_bytes(encoded, "9281a16b90c2")
    var decoded = decode_value_exact(Span(encoded))
    assert_equal(decoded.kind, VALUE_ARRAY)
    assert_equal(len(decoded.kids), 2)
    assert_equal(decoded.kids[0].kind, VALUE_MAP)
    assert_equal(decoded.kids[0].kids[1].kind, VALUE_ARRAY)
    assert_equal(decoded.kids[1].as_bool(), False)
    _assert_bytes(_encode(decoded), "9281a16b90c2")


def test_array_marker_boundaries() raises:
    var a15 = _encode(Value.array_repeat(Value.unsigned(0), 15))
    _assert_prefix(a15, "9f")
    var a16 = _encode(Value.array_repeat(Value.unsigned(0), 16))
    _assert_prefix(a16, "dc0010")
    var a65535 = _encode(Value.array_repeat(Value.unsigned(0), 65535))
    _assert_prefix(a65535, "dcffff")
    var a65536 = _encode(Value.array_repeat(Value.unsigned(0), 65536))
    _assert_prefix(a65536, "dd00010000")


def test_map_marker_boundaries() raises:
    var m15 = _encode(Value.map_repeat(Value.unsigned(0), Value.nil(), 15))
    _assert_prefix(m15, "8f")
    var m16 = _encode(Value.map_repeat(Value.unsigned(0), Value.nil(), 16))
    _assert_prefix(m16, "de0010")
    var m65535 = _encode(Value.map_repeat(Value.unsigned(0), Value.nil(), 65535))
    _assert_prefix(m65535, "deffff")
    var m65536 = _encode(Value.map_repeat(Value.unsigned(0), Value.nil(), 65536))
    _assert_prefix(m65536, "df00010000")


def test_decodes_array16_and_array32_headers() raises:
    var fixed16 = List[UInt8]()
    fixed16.append(0xDC)
    fixed16.append(0)
    fixed16.append(2)
    fixed16.append(0)
    fixed16.append(1)
    var decoded16 = decode_value_exact(Span(fixed16))
    assert_equal(decoded16.kind, VALUE_ARRAY)
    assert_equal(len(decoded16.kids), 2)
    assert_equal(decoded16.kids[0].as_uint64(), UInt64(0))
    assert_equal(decoded16.kids[1].as_uint64(), UInt64(1))

    var fixed32 = List[UInt8]()
    fixed32.append(0xDD)
    fixed32.append(0)
    fixed32.append(0)
    fixed32.append(0)
    fixed32.append(2)
    fixed32.append(0xC3)
    fixed32.append(0xC0)
    var decoded32 = decode_value_exact(Span(fixed32))
    assert_equal(len(decoded32.kids), 2)
    assert_equal(decoded32.kids[0].as_bool(), True)
    assert_equal(decoded32.kids[1].is_nil(), True)


def test_depth_boundary_for_decode_and_encode() raises:
    var at_limit = List[UInt8]()
    for _ in range(127):
        at_limit.append(0x91)
    at_limit.append(0)
    var decoded = decode_value_exact(Span(at_limit))
    assert_equal(decoded.depth(), 128)
    var reencoded = _encode(decoded)
    assert_equal(len(reencoded), 128)
    assert_equal(reencoded[0], UInt8(0x91))
    assert_equal(reencoded[127], UInt8(0))

    var over_limit = List[UInt8]()
    for _ in range(128):
        over_limit.append(0x91)
    over_limit.append(0)
    with assert_raises(contains="depth-exceeded"):
        _ = decode_value_exact(Span(over_limit))

    var chain = make_array_chain(127, 1000)
    assert_equal(len(_encode(chain)), 127 + 1)
    var deeper = make_array_chain(128, 1000)
    with assert_raises(contains="depth-exceeded"):
        _ = _encode(deeper)


def test_empty_container_is_allowed_at_depth_one() raises:
    var empty = decode_value_exact(decode_hex("90"), 1)
    assert_equal(empty.kind, VALUE_ARRAY)
    var empty_map = decode_value_exact(decode_hex("80"), 1)
    assert_equal(empty_map.kind, VALUE_MAP)
    with assert_raises(contains="depth-exceeded"):
        _ = decode_value_exact(decode_hex("9100"), 1)
    with assert_raises(contains="depth-exceeded"):
        _ = decode_value_exact(decode_hex("8100c0"), 1)
    with assert_raises(contains="max_depth"):
        _ = decode_value_exact(decode_hex("90"), 0)


def test_wire_container_limits_are_checked_before_allocation() raises:
    with assert_raises(contains="container-limit"):
        _ = decode_value_exact(decode_hex("dd000f4241"))
    with assert_raises(contains="container-limit"):
        _ = decode_value_exact(decode_hex("df000f4241"))
    with assert_raises(contains="container-limit"):
        _ = decode_value_exact(decode_hex("9b"), 128, 10)
    with assert_raises(contains="container-limit"):
        _ = decode_value_exact(decode_hex("8b"), 128, 10)
    with assert_raises(contains="container-limit"):
        _ = _encode(Value.array_repeat(Value.nil(), 11), 128, 10)
    with assert_raises(contains="container-limit"):
        _ = _encode(Value.map_repeat(Value.nil(), Value.nil(), 11), 128, 10)


def test_truncated_and_reserved_container_children() raises:
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_exact(decode_hex("dc"))
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_exact(decode_hex("dd0001"))
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_exact(decode_hex("91"))
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_exact(decode_hex("81"))
    with assert_raises(contains="truncated: offset 3"):
        _ = decode_value_exact(decode_hex("81a161"))
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_exact(decode_hex("82a16100"))
    with assert_raises(contains="invalid-marker: offset 1"):
        _ = decode_value_exact(decode_hex("91c1"))
    with assert_raises(contains="trailing-data: offset 1"):
        _ = decode_value_exact(decode_hex("9000"))
    with assert_raises(contains="truncated: offset 5"):
        _ = decode_value_exact(decode_hex("92c7010203"))


def test_nil_and_bool_decode_as_children() raises:
    var decoded = decode_value_exact(decode_hex("93c0c2c3"))
    assert_equal(decoded.kind, VALUE_ARRAY)
    assert_equal(decoded.kids[0].is_nil(), True)
    assert_equal(decoded.kids[1].as_bool(), False)
    assert_equal(decoded.kids[2].as_bool(), True)
    _assert_bytes(_encode(decoded), "93c0c2c3")


def test_recursive_model_roundtrip() raises:
    var inner = List[Value](capacity=4)
    inner.append(Value.string(String("k")))
    inner.append(Value.nil())
    inner.append(Value.bool(True))
    inner.append(Value.integer(-3))
    var mapping = Value.map(inner^)

    var outer = List[Value](capacity=2)
    outer.append(mapping^)
    outer.append(Value.array(List[Value]()))
    var value = Value.array(outer^)

    var model = List[UInt8]()
    append_value_model(model, value)
    var decoded_model = decode_value_model_exact(Span(model))
    assert_equal(decoded_model.depth(), value.depth())
    assert_equal(decoded_model.kind, VALUE_ARRAY)
    assert_equal(decoded_model.kids[0].kind, VALUE_MAP)
    assert_equal(decoded_model.kids[0].kids[1].is_nil(), True)
    assert_equal(decoded_model.kids[0].kids[3].as_int64(), -3)
    _assert_bytes(_encode(decoded_model), "9282a16bc0c3fd90")


def test_model_limits_depth_and_truncation() raises:
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_model_exact(decode_hex("14"))
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_model_exact(decode_hex("15"))
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_model_exact(decode_hex("1400000001"))
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_model_exact(decode_hex("140000000100000000"))
    with assert_raises(contains="container-limit"):
        _ = decode_value_model_exact(decode_hex("140000000b"), 128, 10)
    with assert_raises(contains="container-limit"):
        _ = decode_value_model_exact(decode_hex("150000000b"), 128, 10)
    with assert_raises(contains="depth-exceeded"):
        _ = decode_value_model_exact(decode_hex("14000000010000000114"), 1)
    with assert_raises(contains="trailing-data: offset 1"):
        _ = decode_value_model_exact(decode_hex("c000"))
    with assert_raises(contains="invalid-model"):
        _ = decode_value_model_exact(decode_hex("20"))


def test_model_append_limits_and_nil_bool_tags() raises:
    var model = List[UInt8]()
    append_value_model(model, Value.nil())
    append_value_model(model, Value.bool(False))
    append_value_model(model, Value.bool(True))
    _assert_bytes(model, "c0c2c3")

    var decoded = decode_value_model_exact(decode_hex("c0"))
    assert_equal(decoded.is_nil(), True)
    var false_value = decode_value_model_exact(decode_hex("c2"))
    assert_equal(false_value.as_bool(), False)
    var true_value = decode_value_model_exact(decode_hex("c3"))
    assert_equal(true_value.as_bool(), True)

    var over = List[UInt8]()
    with assert_raises(contains="container-limit"):
        append_value_model(over, Value.array_repeat(Value.nil(), 11), 128, 10)
    assert_equal(len(over), 0)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
