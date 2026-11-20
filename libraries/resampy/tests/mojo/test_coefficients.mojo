"""Phase 3 native tests: coefficient resource loader and validation.

Resources are read from the repository via paths resolved relative to the
test's working directory; the library-local runner sets ``RESAMPY_ROOT``.
"""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises, assert_true

from mojo_resampy.coefficients import (
    load_filter,
    parse_filter_metadata,
    validate_filter_resource,
)
from mojo_resampy.float_codec import encode_f64le
from mojo_resampy.sha256 import sha256_hex
from test_support import assert_bits_equal


comptime RES: String = "libraries/resampy/resources/synthetic"


def _meta_text() raises -> String:
    from std.io import FileHandle
    var f = FileHandle(RES + "/synthetic_filter.json", "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=Span(raw))


def _bin_bytes() raises -> List[UInt8]:
    from std.io import FileHandle
    var f = FileHandle(RES + "/synthetic_filter.bin", "r")
    var raw = f.read_bytes()
    f.close()
    return raw^


def test_load_synthetic_resource() raises:
    var r = load_filter(RES + "/synthetic_filter.json", RES + "/synthetic_filter.bin")
    assert_equal(r.count(), 8)
    assert_equal(r.metadata.filter_id, "synthetic_tiny_v1")
    assert_equal(r.metadata.coefficient_count, 8)
    assert_equal(r.metadata.precision, 8)
    assert_equal(r.metadata.byte_order, "little")
    assert_equal(r.metadata.dtype, "float64")
    assert_equal(r.metadata.resource_bytes, 64)
    assert_bits_equal(r[0], 0.5)
    assert_bits_equal(r[7], -1.0)


def test_metadata_sha256_matches_bytes() raises:
    var meta = parse_filter_metadata(_meta_text())
    var payload = _bin_bytes()
    assert_equal(sha256_hex(Span(payload)), meta.resource_sha256)


def test_reject_truncated_resource() raises:
    var payload = _bin_bytes()
    var short = List[UInt8]()
    for i in range(len(payload) - 8):
        short.append(payload[i])
    with assert_raises():
        _ = validate_filter_resource(_meta_text(), Span(short))


def test_reject_corrupted_hash() raises:
    var payload = _bin_bytes()
    payload[0] = UInt8((Int(payload[0]) + 1) & 0xFF)
    with assert_raises():
        _ = validate_filter_resource(_meta_text(), Span(payload))


def test_reject_wrong_schema_version() raises:
    var bad = String(from_utf8=Span(_bytes("{\"schema_version\":2,\"filter_id\":\"x\",\"coefficient_count\":0,\"precision\":8,\"rolloff\":0.9,\"dtype\":\"float64\",\"byte_order\":\"little\",\"resource_bytes\":0,\"resource_sha256\":\"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\"}")))
    with assert_raises():
        _ = parse_filter_metadata(bad)


def test_reject_big_endian() raises:
    var bad = String(from_utf8=Span(_bytes("{\"schema_version\":1,\"filter_id\":\"x\",\"coefficient_count\":0,\"precision\":8,\"rolloff\":0.9,\"dtype\":\"float64\",\"byte_order\":\"big\",\"resource_bytes\":0,\"resource_sha256\":\"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\"}")))
    with assert_raises():
        _ = parse_filter_metadata(bad)


def test_reject_wrong_dtype() raises:
    var bad = String(from_utf8=Span(_bytes("{\"schema_version\":1,\"filter_id\":\"x\",\"coefficient_count\":0,\"precision\":8,\"rolloff\":0.9,\"dtype\":\"float32\",\"byte_order\":\"little\",\"resource_bytes\":0,\"resource_sha256\":\"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\"}")))
    with assert_raises():
        _ = parse_filter_metadata(bad)


def test_reject_count_bytes_mismatch() raises:
    var bad = String(from_utf8=Span(_bytes("{\"schema_version\":1,\"filter_id\":\"x\",\"coefficient_count\":4,\"precision\":4,\"rolloff\":0.9,\"dtype\":\"float64\",\"byte_order\":\"little\",\"resource_bytes\":64,\"resource_sha256\":\"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\"}")))
    with assert_raises():
        _ = parse_filter_metadata(bad)


def test_reject_invalid_rolloff() raises:
    var bad = String(from_utf8=Span(_bytes("{\"schema_version\":1,\"filter_id\":\"x\",\"coefficient_count\":0,\"precision\":8,\"rolloff\":1.5,\"dtype\":\"float64\",\"byte_order\":\"little\",\"resource_bytes\":0,\"resource_sha256\":\"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\"}")))
    with assert_raises():
        _ = parse_filter_metadata(bad)


def test_reject_short_hash() raises:
    var bad = String(from_utf8=Span(_bytes("{\"schema_version\":1,\"filter_id\":\"x\",\"coefficient_count\":0,\"precision\":8,\"rolloff\":0.9,\"dtype\":\"float64\",\"byte_order\":\"little\",\"resource_bytes\":0,\"resource_sha256\":\"abcd\"}")))
    with assert_raises():
        _ = parse_filter_metadata(bad)


def test_empty_resource_valid() raises:
    var empty_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    var meta = (
        "{\"schema_version\":1,\"filter_id\":\"empty\",\"coefficient_count\":0,"
        + "\"precision\":8,\"rolloff\":0.9,\"dtype\":\"float64\","
        + "\"byte_order\":\"little\",\"resource_bytes\":0,"
        + "\"resource_sha256\":\"" + empty_sha + "\"}"
    )
    var r = validate_filter_resource(meta, Span(List[UInt8]()))
    assert_equal(r.count(), 0)


def test_reject_unknown_metadata_key() raises:
    var bad = String(from_utf8=Span(_bytes("{\"schema_version\":1,\"filter_id\":\"x\",\"coefficient_count\":0,\"precision\":8,\"rolloff\":0.9,\"dtype\":\"float64\",\"byte_order\":\"little\",\"resource_bytes\":0,\"resource_sha256\":\"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\",\"extra\":1}")))
    with assert_raises():
        _ = parse_filter_metadata(bad)


def test_reject_missing_metadata_key() raises:
    var bad = String(from_utf8=Span(_bytes("{\"schema_version\":1}")))
    with assert_raises():
        _ = parse_filter_metadata(bad)


def test_missing_file() raises:
    with assert_raises():
        _ = load_filter(RES + "/does_not_exist.json", RES + "/synthetic_filter.bin")


def _bytes(text: String) -> List[UInt8]:
    var out = List[UInt8]()
    for byte in text.as_bytes():
        out.append(byte)
    return out^


def _meta_with_count(count: Int) raises -> String:
    return (
        String("{\"schema_version\":1,\"filter_id\":\"x\",\"coefficient_count\":")
        + String(count)
        + String(",\"precision\":8,\"rolloff\":0.9,\"dtype\":\"float64\",")
        + String("\"byte_order\":\"little\",\"resource_bytes\":")
        + String(count * 8)
        + String(",\"resource_sha256\":\"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\"}")
    )


def test_zero_count_metadata_accepted() raises:
    var meta = parse_filter_metadata(_meta_with_count(0))
    assert_equal(meta.coefficient_count, 0)
    assert_equal(meta.resource_bytes, 0)


def test_ordinary_count_metadata_accepted() raises:
    var meta = parse_filter_metadata(_meta_with_count(8))
    assert_equal(meta.coefficient_count, 8)
    assert_equal(meta.resource_bytes, 64)


def test_reject_precision_above_nonempty_count() raises:
    var message = String("")
    try:
        _ = parse_filter_metadata(_meta_with_count(2))
    except e:
        message = String(e)
    assert_true("exceeds non-empty coefficient_count" in message)


def test_maximum_count_metadata_accepted() raises:
    var meta = parse_filter_metadata(_meta_with_count(1_000_000))
    assert_equal(meta.coefficient_count, 1_000_000)
    assert_equal(meta.resource_bytes, 8_000_000)


def test_excessive_count_metadata_rejected() raises:
    # Count above the limit must be rejected BEFORE count * 8 (no wraparound).
    with assert_raises():
        _ = parse_filter_metadata(_meta_with_count(1_000_001))
    with assert_raises():
        _ = parse_filter_metadata(_meta_with_count(2**61))


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
