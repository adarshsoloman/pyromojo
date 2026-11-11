"""Cross-phase regression pins for integer, float, string, binary, and container behavior."""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_msgpack.container import (
    decode_value_exact,
    decode_value_model_exact,
    encode_value,
)
from mojo_msgpack.integer import (
    decode_exact as decode_integer_exact,
    encode_value as encode_integer_value,
)
from mojo_msgpack.scalar import decode_scalar_exact
from mojo_msgpack.value import Value, make_array_chain

from vector_support import decode_hex


def _encode(value: Value) raises -> List[UInt8]:
    var out = List[UInt8]()
    encode_value(out, value)
    return out^


def test_integer_shortest_form_and_boundaries() raises:
    var cases = List[StaticString]()
    cases.append("ccff")
    cases.append("cd0100")
    cases.append("d0df")
    cases.append("cfffffffffffffffff")
    for hex in cases:
        var decoded = decode_integer_exact(decode_hex(hex))
        var out = List[UInt8]()
        encode_integer_value(out, decoded)
        var expected = decode_hex(hex)
        assert_equal(len(out), len(expected))
        for index in range(len(out)):
            assert_equal(out[index], expected[index])
    assert_equal(decode_integer_exact(decode_hex("ccff")).as_uint64(), UInt64(255))
    assert_equal(decode_integer_exact(decode_hex("d0df")).as_int64(), -33)


def test_float_bits_preserved() raises:
    var negative_zero = decode_scalar_exact(decode_hex("ca80000000"))
    assert_equal(negative_zero.as_float32_bits(), UInt32(0x80000000))
    var nan_payload = decode_scalar_exact(decode_hex("cb7ff8000000000001"))
    assert_equal(nan_payload.as_float64_bits(), UInt64(0x7FF8000000000001))
    var reencoded = _encode(nan_payload)
    assert_equal(reencoded[0], UInt8(0xCB))
    assert_equal(reencoded[1], UInt8(0x7F))


def test_string_utf8_still_validated() raises:
    var hello = decode_scalar_exact(decode_hex("a568656c6c6f"))
    assert_equal(len(hello.data), 5)
    with assert_raises(contains="invalid-utf8"):
        _ = decode_scalar_exact(decode_hex("a180"))


def test_binary_bytes_preserved() raises:
    var decoded = decode_scalar_exact(decode_hex("c40300ff80"))
    assert_equal(len(decoded.data), 3)
    assert_equal(decoded.data[0], UInt8(0))
    assert_equal(decoded.data[1], UInt8(0xFF))
    assert_equal(decoded.data[2], UInt8(0x80))


def test_array_map_recursion_and_depth_limits() raises:
    var chain = make_array_chain(9, 10)
    assert_equal(chain.depth(), 10)
    var wire = _encode(chain)
    assert_equal(len(wire), 10)
    assert_equal(decode_value_exact(Span(wire), 10).depth(), 10)
    with assert_raises(contains="depth-exceeded"):
        _ = decode_value_exact(Span(wire), 9)

    var ordered = decode_value_exact(decode_hex("82a16b01a16b02"))
    assert_equal(len(ordered.kids), 4)
    assert_equal(ordered.kids[1].as_uint64(), UInt64(1))
    assert_equal(ordered.kids[3].as_uint64(), UInt64(2))


def test_error_categories_stable() raises:
    with assert_raises(contains="truncated"):
        _ = decode_value_exact(decode_hex("cc"))
    with assert_raises(contains="invalid-marker"):
        _ = decode_value_exact(decode_hex("c1"))
    with assert_raises(contains="trailing-data"):
        _ = decode_value_exact(decode_hex("0000"))
    with assert_raises(contains="unsupported-marker"):
        _ = decode_scalar_exact(decode_hex("c0"))
    with assert_raises(contains="container-limit"):
        _ = decode_value_exact(decode_hex("dd000f4241"))
    with assert_raises(contains="depth-exceeded"):
        _ = decode_value_exact(decode_hex("91919100"), 3)


def test_scalar_api_rejects_containers() raises:
    with assert_raises(contains="unsupported-marker"):
        _ = decode_scalar_exact(decode_hex("90"))
    with assert_raises(contains="unsupported-marker"):
        _ = decode_scalar_exact(decode_hex("80"))


def test_huge_declared_counts_fail_before_allocation() raises:
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_exact(decode_hex("c9000100002a010203"))
    with assert_raises(contains="container-limit"):
        _ = decode_value_exact(decode_hex("ddffffffff"), 128, 100000000)
    with assert_raises(contains="container-limit"):
        _ = decode_value_model_exact(decode_hex("14ffffffff"))
    with assert_raises(contains="truncated: offset 0"):
        _ = decode_value_model_exact(decode_hex("1500000001"))


def test_exhausted_depth_names_the_container() raises:
    var inner = List[Value](capacity=0)
    var outer = List[Value](capacity=1)
    outer.append(Value.array(inner^))
    var value = Value.array(outer^)
    var out = List[UInt8]()
    with assert_raises(contains="depth-exceeded: array exceeds max_depth"):
        encode_value(out, value, 1)


def test_cli_model_tags_unchanged() raises:
    var signed = decode_value_model_exact(decode_hex("000000000000000001"))
    assert_equal(signed.as_int64(), 1)
    var text = decode_value_model_exact(decode_hex("126869"))
    assert_equal(len(text.data), 2)
    var boolean = decode_value_model_exact(decode_hex("c3"))
    assert_equal(boolean.as_bool(), True)
    var array = decode_value_model_exact(decode_hex("1400000000"))
    assert_equal(len(array.kids), 0)
    with assert_raises(contains="invalid-model"):
        _ = decode_value_model_exact(decode_hex("20"))


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
