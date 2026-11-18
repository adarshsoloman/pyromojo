"""Phase 3 native tests: golden-vector protocol (parse/serialize/validate)."""

from std.collections import List
from std.io import FileHandle
from std.testing import TestSuite, assert_equal, assert_true, assert_raises

from mojo_resampy.golden_vector import (
    GOLDEN_SCHEMA_VERSION,
    parse_golden_vector,
    serialize_golden_vector,
)
from mojo_resampy.float_codec import float64_to_bits
from mojo_resampy.json_codec import parse_json_object
from test_support import assert_bits_equal, positive_inf, negative_inf, quiet_nan


comptime VEC: String = "libraries/resampy/tests/vectors/representation_vectors.json"


def _read_text(path: String) raises -> String:
    var f = FileHandle(path, "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=Span(raw))


def _case_texts() raises -> List[String]:
    """Extract each case as an individual flat JSON object from the bundle.

    The bundle has one outer object and a ``cases`` array; the strict flat JSON
    reader intentionally rejects arrays/nesting, so we split here. We capture
    only objects that OPEN at brace depth >= 1 (i.e. the case objects), not the
    outer bundle object itself.
    """
    var text = _read_text(VEC)
    var out = List[String]()
    var i = 0
    var n = text.byte_length()
    var depth = 0
    var in_string = False
    while i < n:
        var c = text.as_bytes()[i]
        if c == 34 and (i == 0 or text.as_bytes()[i - 1] != 92):
            in_string = not in_string
            i += 1
            continue
        if in_string:
            i += 1
            continue
        if c == 123:  # '{'
            depth += 1
            if depth == 2:  # start of a case object
                var start = i
                var inner = 1
                var inner_string = False
                i += 1
                while i < n and inner > 0:
                    var cc = text.as_bytes()[i]
                    if cc == 34 and (i == 0 or text.as_bytes()[i - 1] != 92):
                        inner_string = not inner_string
                    elif not inner_string:
                        if cc == 123:
                            inner += 1
                        elif cc == 125:
                            inner -= 1
                    i += 1
                var segment = List[UInt8]()
                for j in range(start, i):
                    segment.append(text.as_bytes()[j])
                out.append(String(from_utf8=Span(segment)))
                depth -= 1  # case object closed, back to outer depth 1
                continue
        elif c == 125:  # '}'
            depth -= 1
        i += 1
    return out^


def test_all_synthetic_cases_parse() raises:
    var texts = _case_texts()
    assert_equal(len(texts), 12)
    for i in range(len(texts)):
        var gv = parse_golden_vector(texts[i])
        assert_equal(gv.schema_version, GOLDEN_SCHEMA_VERSION)
        assert_equal(gv.reference_library, "synthetic")
        assert_equal(gv.byte_order, "little")
        assert_equal(gv.input_dtype, "float64")
        assert_equal(gv.output_dtype, "float64")


def test_exact_bits_roundtrip_all_cases() raises:
    var texts = _case_texts()
    for i in range(len(texts)):
        var gv = parse_golden_vector(texts[i])
        var reserialized = serialize_golden_vector(gv)
        var gv2 = parse_golden_vector(reserialized)
        assert_equal(len(gv2.input_values), len(gv.input_values))
        assert_equal(len(gv2.expected_values), len(gv.expected_values))
        for j in range(len(gv.input_values)):
            if float64_to_bits(gv.input_values[j]) != float64_to_bits(gv2.input_values[j]):
                raise Error("input bits changed in case " + gv.case_id)
        for j in range(len(gv.expected_values)):
            if float64_to_bits(gv.expected_values[j]) != float64_to_bits(gv2.expected_values[j]):
                raise Error("expected bits changed in case " + gv.case_id)


def test_empty_case() raises:
    var texts = _case_texts()
    var gv = parse_golden_vector(texts[0])
    assert_equal(gv.case_id, "empty_vector")
    assert_equal(gv.input_count, 0)
    assert_equal(gv.expected_count, 0)
    assert_equal(len(gv.input_values), 0)


def test_nonfinite_case_bits() raises:
    var texts = _case_texts()
    for i in range(len(texts)):
        var obj = parse_json_object(texts[i])
        if obj.get_string("case_id") == "nonfinite":
            var gv = parse_golden_vector(texts[i])
            assert_equal(len(gv.input_values), 3)
            assert_bits_equal(gv.input_values[1], positive_inf())
            assert_bits_equal(gv.input_values[2], -positive_inf())
            return
    raise Error("nonfinite case not found")


def test_reject_wrong_schema_version() raises:
    var texts = _case_texts()
    var bad = texts[1].replace("\"schema_version\": 1", "\"schema_version\": 2")
    with assert_raises():
        _ = parse_golden_vector(bad)


def test_reject_bad_byte_order() raises:
    var texts = _case_texts()
    var bad = texts[1].replace("\"byte_order\": \"little\"", "\"byte_order\": \"big\"")
    with assert_raises():
        _ = parse_golden_vector(bad)


def test_reject_bad_encoding() raises:
    var texts = _case_texts()
    var bad = texts[1].replace("\"input_encoding\": \"base64\"", "\"input_encoding\": \"hex\"")
    with assert_raises():
        _ = parse_golden_vector(bad)


def test_reject_wrong_payload_count() raises:
    var texts = _case_texts()
    var bad = texts[1].replace("\"payload_element_count\": 2", "\"payload_element_count\": 99")
    with assert_raises():
        _ = parse_golden_vector(bad)


def test_reject_corrupted_payload_hash() raises:
    var texts = _case_texts()
    var bad = texts[1].replace("\"payload_sha256\": \"", "\"payload_sha256\": \"0")
    with assert_raises():
        _ = parse_golden_vector(bad)


def test_reject_unknown_key() raises:
    var texts = _case_texts()
    var bad = "{\"bogus\":1," + texts[1][byte=1:]
    with assert_raises():
        _ = parse_golden_vector(bad)


def test_reject_missing_key() raises:
    with assert_raises():
        _ = parse_golden_vector("{\"schema_version\":1}")


def test_reject_truncated_base64() raises:
    var texts = _case_texts()
    var obj = parse_json_object(texts[1])
    var data = obj.get_string("input_data")
    var bad = texts[1].replace("\"input_data\": \"" + data + "\"", "\"input_data\": \"YQ\"")
    with assert_raises():
        _ = parse_golden_vector(bad)


def _first_case() raises -> String:
    var texts = _case_texts()
    assert_equal(len(texts), 12)
    var out = String("")
    out += texts[1]  # single_value: one finite float in/out
    return out^


def _patched(text: String, key: String, value: String) raises -> String:
    var needle = String("\"") + key + String("\":")
    var pos = text.find(needle)
    if pos < 0:
        raise Error("key not found: " + key)
    var start = pos + needle.byte_length()
    while text.as_bytes()[start] == 32:
        start += 1
    var end = start
    var c = text.as_bytes()[end]
    if c == 34:
        end += 1
        while text.as_bytes()[end] != 34:
            if text.as_bytes()[end] == 92:
                end += 1
            end += 1
        end += 1
    else:
        while end < text.byte_length() and text.as_bytes()[end] != 44 and text.as_bytes()[end] != 125:
            end += 1
    var out = text[byte=0:start] + value + text[byte=end:]
    return out^


def test_reject_nonpositive_sampling_rates() raises:
    var base = _first_case()
    with assert_raises():
        _ = parse_golden_vector(_patched(base, "sr_orig", "0"))
    with assert_raises():
        _ = parse_golden_vector(_patched(base, "sr_new", "-1"))


def test_reject_empty_identifiers_and_provenance() raises:
    var base = _first_case()
    for key in ["case_id", "description", "reference_library", "reference_version",
                "reference_commit", "python_version", "numpy_version", "numba_version",
                "filter_id"]:
        with assert_raises():
            _ = parse_golden_vector(_patched(base, key, "\"\""))


def test_reject_nonfinite_tolerances() raises:
    var base = _first_case()
    with assert_raises():
        _ = parse_golden_vector(_patched(base, "atol", "1e400"))
    with assert_raises():
        _ = parse_golden_vector(_patched(base, "rtol", "1e400"))


def test_payload_integrity_still_enforced() raises:
    # A consistent metadata set with a corrupted hash must still be rejected.
    var base = _first_case()
    var bad = _patched(base, "payload_sha256", "\"0000000000000000000000000000000000000000000000000000000000000000\"")
    with assert_raises():
        _ = parse_golden_vector(bad)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
