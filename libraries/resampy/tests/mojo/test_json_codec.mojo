"""Phase 3 native tests: strict minimal JSON codec."""

from std.testing import TestSuite, assert_equal, assert_true, assert_raises

from mojo_resampy.json_codec import (
    JSON_BOOL,
    JSON_FLOAT,
    JSON_INT,
    JSON_NULL,
    JSON_STRING,
    JsonObject,
    parse_json_object,
)


def test_empty_object() raises:
    var obj = parse_json_object("{}")
    assert_equal(len(obj.keys()), 0)


def test_whitespace_tolerant() raises:
    var obj = parse_json_object("  { \"a\" : 1 , \"b\" : 2 }  ")
    assert_equal(obj.get_int("a"), 1)
    assert_equal(obj.get_int("b"), 2)


def test_all_scalar_types() raises:
    var obj = parse_json_object(
        "{\"s\":\"hi\",\"i\":42,\"f\":1e-09,\"t\":true,\"z\":null}"
    )
    assert_equal(obj.get_string("s"), "hi")
    assert_equal(obj.get_int("i"), 42)
    assert_true(obj.get_bool("t"))
    assert_true(obj.is_null("z"))
    assert_true(obj.get("f").kind == JSON_FLOAT)


def test_string_escapes() raises:
    var obj = parse_json_object("{\"s\":\"a\\\"b\\\\c\\nd\\u0041\"}")
    assert_equal(obj.get_string("s"), "a\"b\\c\ndA")


def test_serialize_roundtrip() raises:
    var o = JsonObject()
    o.set_string("case_id", "x\"y")
    o.set_int("n", 7)
    o.set_float("tol", 1e-9)
    o.set_bool("ok", True)
    o.set_null("commit")
    var text = o.serialize()
    var back = parse_json_object(text)
    assert_equal(back.get_string("case_id"), "x\"y")
    assert_equal(back.get_int("n"), 7)
    assert_true(back.get_bool("ok"))
    assert_true(back.is_null("commit"))


def test_reject_nested_object() raises:
    with assert_raises():
        _ = parse_json_object("{\"a\": {\"b\": 1}}")


def test_reject_array() raises:
    with assert_raises():
        _ = parse_json_object("{\"a\": [1, 2]}")


def test_reject_trailing_content() raises:
    with assert_raises():
        _ = parse_json_object("{\"a\":1} garbage")


def test_reject_duplicate_key() raises:
    with assert_raises():
        _ = parse_json_object("{\"a\":1,\"a\":2}")


def test_reject_leading_zero() raises:
    with assert_raises():
        _ = parse_json_object("{\"a\":01}")


def test_reject_bare_identifier() raises:
    with assert_raises():
        _ = parse_json_object("{\"a\":yes}")


def test_reject_single_quotes() raises:
    with assert_raises():
        _ = parse_json_object("{'a':1}")


def test_reject_bad_escape() raises:
    with assert_raises():
        _ = parse_json_object("{\"a\":\"\\q\"}")


def test_reject_raw_control_in_string() raises:
    with assert_raises():
        _ = parse_json_object("{\"a\":\"x\ny\"}")


def test_missing_key_error() raises:
    var obj = parse_json_object("{\"a\":1}")
    with assert_raises():
        _ = obj.get_string("b")


def test_reject_numeric_overflow_tokens() raises:
    # P1-02/P2-01: parseFloat used to return inf silently for these tokens.
    with assert_raises():
        _ = parse_json_object("{\"x\": 1e400}")
    with assert_raises():
        _ = parse_json_object("{\"x\": -1e400}")


def test_reject_nonfinite_literal_tokens() raises:
    for token in ["nan", "inf", "-inf"]:
        var text = String("{\"x\": ") + token + String("}")
        with assert_raises():
            _ = parse_json_object(text)


def test_underflow_is_finite_zero() raises:
    var obj = parse_json_object("{\"x\": 1e-400}")
    assert_equal(obj.get_float("x"), 0.0)


def test_valid_extreme_finite_numbers() raises:
    var tiny = parse_json_object("{\"x\": 5e-324}")
    assert_true(tiny.get_float("x") > 0.0)
    var huge = parse_json_object("{\"x\": 1.7976931348623157e308}")
    assert_true(huge.get_float("x") > 1e300)


def test_set_float_rejects_nonfinite() raises:
    var z: Float64 = 0.0
    with assert_raises():
        var o1 = JsonObject()
        o1.set_float("x", z / z)  # NaN
    with assert_raises():
        var o2 = JsonObject()
        o2.set_float("x", 1.0 / z)  # +Inf


def test_serialized_output_is_valid_json_text() raises:
    # No bare nan/inf tokens may be emitted for finite inputs.
    var o = JsonObject()
    o.set_float("a", 1e-300)
    o.set_float("b", 1.7976931348623157e308)
    var text = o.serialize()
    assert_true("nan" not in text)
    assert_true("inf" not in text)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
