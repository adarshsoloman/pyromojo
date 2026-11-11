"""Depth-safety tests for the MessagePack Value model."""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_msgpack.value import (
    DEFAULT_MAX_DEPTH,
    Value,
    make_array_chain,
)


def _set_leaf_bits(mut value: Value, bits: UInt64):
    if len(value.kids) == 0:
        value.int_bits = bits
        return
    _set_leaf_bits(value.kids[0], bits)


def test_scalars() raises:
    assert_equal(Value.nil().depth(), 1)
    assert_equal(Value.bool(True).as_bool(), True)
    assert_equal(Value.bool(False).as_bool(), False)
    assert_equal(Value.integer(-7).as_int64(), -7)
    assert_equal(Value.integer(-9223372036854775807 - 1).as_int64(), Int64.MIN)
    assert_equal(Value.unsigned(18446744073709551615).as_uint64(), UInt64.MAX)
    assert_equal(Value.float32(UInt32(0x3FC00000)).as_float32_bits(), UInt32(0x3FC00000))
    assert_equal(Value.float64(1.5).as_float64(), 1.5)
    assert_equal(Value.float64_bits(0x7FF8000000000001).as_float64_bits(), 0x7FF8000000000001)
    assert_equal(Value.timestamp(-1, 999999999).as_int64(), -1)
    assert_equal(Value.string(String("héllo")).data[1], UInt8(0xC3))


def test_at_limit_is_accepted() raises:
    var value = make_array_chain(DEFAULT_MAX_DEPTH - 1, DEFAULT_MAX_DEPTH)
    assert_equal(value.depth(), DEFAULT_MAX_DEPTH)


def _build_one_past_limit() raises:
    var value = make_array_chain(DEFAULT_MAX_DEPTH, DEFAULT_MAX_DEPTH)


def test_one_past_limit_is_rejected() raises:
    with assert_raises(contains="max_depth"):
        _build_one_past_limit()


def test_check_depth_reports_actual_and_limit() raises:
    var value = make_array_chain(10, 1000)
    with assert_raises(contains="11 exceeds max_depth 10"):
        value.check_depth(10)
    value.check_depth(11)


def test_copy_is_deep() raises:
    var original = make_array_chain(8, 100)
    var duplicate = original.copy()
    _set_leaf_bits(original, 42)
    assert_equal(original.kids[0].kids[0].kids[0].kids[0].kids[0].kids[0].kids[0].kids[0].int_bits, 42)
    assert_equal(duplicate.kids[0].kids[0].kids[0].kids[0].kids[0].kids[0].kids[0].kids[0].int_bits, 0)
    assert_equal(duplicate.depth(), 9)


def test_move_preserves_depth() raises:
    var original = make_array_chain(20, 100)
    var moved = original^
    assert_equal(moved.depth(), 21)


def test_map_depth_counts_pairs() raises:
    var inner_items = List[Value](capacity=1)
    inner_items.append(Value.integer(1))
    var pairs = List[Value](capacity=2)
    pairs.append(Value.string(String("key")))
    pairs.append(Value.array(inner_items^))
    var mapping = Value.map(pairs^)
    assert_equal(mapping.depth(), 3)
    mapping.check_depth(3)


def test_repeat_builders() raises:
    var repeated_array = Value.array_repeat(Value.integer(1), 3)
    assert_equal(repeated_array.depth(), 2)
    assert_equal(len(repeated_array.kids), 3)
    var repeated_map = Value.map_repeat(Value.string(String("k")), Value.nil(), 2)
    assert_equal(repeated_map.depth(), 2)
    assert_equal(len(repeated_map.kids), 4)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
