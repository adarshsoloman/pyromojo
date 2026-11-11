"""Checks the generated vector module compiles and is self-consistent."""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_msgpack.value import Value

from generated_vectors import VECTOR_COUNT, load_vectors, value_for_case
from vector_support import VectorCase, decode_hex


def _find(cases: List[VectorCase], case_id: StaticString) -> Int:
    for index in range(len(cases)):
        if cases[index].id == case_id:
            return index
    return -1


def test_count_and_metadata() raises:
    var cases = load_vectors()
    assert_equal(len(cases), VECTOR_COUNT)
    for index in range(len(cases)):
        var entry = cases[index]
        assert_equal(entry.encoded_hex.byte_length() % 2, 0)
        assert_equal(entry.has_value, entry.mode != "error")
        if entry.mode == "error":
            assert_equal(entry.has_value, False)
            assert_equal(entry.error_type.byte_length() > 0, True)
        for other in range(index + 1, len(cases)):
            assert_equal(entry.id == cases[other].id, False)


def test_encoded_hex_decodes() raises:
    var cases = load_vectors()
    for index in range(len(cases)):
        var raw = decode_hex(cases[index].encoded_hex)
        assert_equal(len(raw) * 2, cases[index].encoded_hex.byte_length())


def test_every_value_case_builds() raises:
    var cases = load_vectors()
    for index in range(len(cases)):
        if cases[index].has_value:
            var value = value_for_case(cases[index].id)
            assert_equal(value.depth() >= 1, True)


def test_error_cases_have_no_value_model() raises:
    var cases = load_vectors()
    for index in range(len(cases)):
        if cases[index].mode == "error":
            with assert_raises(contains="has no value model"):
                _ = value_for_case(cases[index].id)


def test_scalar_builders() raises:
    assert_equal(value_for_case("nil").is_nil(), True)
    assert_equal(value_for_case("bool_true").as_bool(), True)
    assert_equal(value_for_case("int_negative_fixint_minus_one").as_int64(), -1)
    assert_equal(value_for_case("int_uint64_max").as_uint64(), UInt64.MAX)
    assert_equal(value_for_case("int_int64_min_edge").as_int64(), Int64.MIN)
    assert_equal(
        value_for_case("float32_one_and_half").as_float32_bits(), UInt32(0x3FC00000)
    )
    assert_equal(
        value_for_case("float64_nan_payload").as_float64_bits(), UInt64(0x7FF8000000000001)
    )
    assert_equal(value_for_case("timestamp96_negative_seconds").as_int64(), -1)
    assert_equal(value_for_case("ext_fixext4").ext_code, Int8(42))
    assert_equal(len(value_for_case("ext_fixext4").data), 4)
    assert_equal(len(value_for_case("str_unicode").data), 15)
    assert_equal(len(value_for_case("bin_non_utf8").data), 3)


def test_large_repeat_builders() raises:
    assert_equal(len(value_for_case("array32_repeated_nil").kids), 65536)
    assert_equal(len(value_for_case("map32_repeated_pair").kids), 131072)


def test_duplicate_map_preserves_pairs() raises:
    var value = value_for_case("map_duplicate_keys")
    assert_equal(value.depth(), 2)
    assert_equal(len(value.kids), 4)
    assert_equal(value.kids[0].data[0], UInt8(ord("k")))
    assert_equal(value.kids[2].data[0], UInt8(ord("k")))


def test_error_metadata() raises:
    var cases = load_vectors()
    var index = _find(cases, "error_trailing_bytes")
    assert_equal(index >= 0, True)
    assert_equal(cases[index].error_type, "ExtraData")
    assert_equal(cases[index].error_contains, "extra data")
    var depth_index = _find(cases, "error_reference_depth_limit")
    assert_equal(depth_index >= 0, True)
    assert_equal(cases[depth_index].error_type, "StackError")


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
