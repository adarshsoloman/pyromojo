"""Phase 3 Python compat: golden-vector protocol round trips via the native CLI."""

from __future__ import annotations

import hashlib
import json
import math

from resampy_compat_support import (
    OP_GOLDEN_PARSE,
    OP_GOLDEN_SERIALIZE,
    b64decode,
    bits,
    decode_f64le,
    error,
    ok,
    parse_kv,
)


def test_python_encodes_all_cases(vectors_bundle, resampy_cli) -> None:
    """Python can encode each synthetic case into the flat JSON format."""
    for case in vectors_bundle["cases"]:
        body = bytes([OP_GOLDEN_PARSE]) + json.dumps(case).encode("utf-8")
        summary = parse_kv(ok(resampy_cli, body))
        assert summary["case_id"] == case["case_id"]
        assert summary["schema_version"] == "1"
        assert summary["input_count"] == str(case["input_count"])
        assert summary["expected_count"] == str(case["expected_count"])


def test_mojo_serialization_is_decodable(vectors_bundle, resampy_cli) -> None:
    """Python can decode Mojo-generated golden-vector payloads exactly."""
    for case in vectors_bundle["cases"]:
        body = bytes([OP_GOLDEN_SERIALIZE]) + json.dumps(case).encode("utf-8")
        canonical = ok(resampy_cli, body).decode("utf-8")
        parsed = json.loads(canonical)
        assert parsed["schema_version"] == 1
        assert parsed["case_id"] == case["case_id"]
        got_in = decode_f64le(b64decode(parsed["input_data"]))
        want_in = decode_f64le(b64decode(case["input_data"]))
        assert len(got_in) == len(want_in)
        for g, w in zip(got_in, want_in, strict=True):
            assert bits(g) == bits(w), f"input bits differ in {case['case_id']}"


def test_sha256_integrity_validated(vectors_bundle, resampy_cli) -> None:
    for case in vectors_bundle["cases"]:
        combined = b64decode(case["input_data"]) + b64decode(case["expected_data"])
        assert hashlib.sha256(combined).hexdigest() == case["payload_sha256"]
        body = bytes([OP_GOLDEN_PARSE]) + json.dumps(case).encode("utf-8")
        assert parse_kv(ok(resampy_cli, body))["payload_sha256"] == case["payload_sha256"]


def test_exact_bit_patterns_special_case(vectors_bundle, resampy_cli) -> None:
    case = next(c for c in vectors_bundle["cases"] if c["case_id"] == "special_mixed")
    body = bytes([OP_GOLDEN_SERIALIZE]) + json.dumps(case).encode("utf-8")
    parsed = json.loads(ok(resampy_cli, body).decode("utf-8"))
    got = decode_f64le(b64decode(parsed["input_data"]))
    want = decode_f64le(b64decode(case["input_data"]))
    assert len(got) == len(want)
    for g, w in zip(got, want, strict=True):
        assert bits(g) == bits(w)
    assert math.isnan(want[10])
    assert want[11] == float("inf")
    assert want[12] == float("-inf")


def test_reject_malformed_schema(resampy_cli, vectors_bundle) -> None:
    case = dict(vectors_bundle["cases"][1])
    case["schema_version"] = 99
    error(resampy_cli, bytes([OP_GOLDEN_PARSE]) + json.dumps(case).encode("utf-8"))


def test_reject_corrupted_hash(resampy_cli, vectors_bundle) -> None:
    case = dict(vectors_bundle["cases"][1])
    case["payload_sha256"] = "0" * 64
    error(resampy_cli, bytes([OP_GOLDEN_PARSE]) + json.dumps(case).encode("utf-8"))


def test_reject_wrong_counts(resampy_cli, vectors_bundle) -> None:
    case = dict(vectors_bundle["cases"][1])
    case["payload_element_count"] = 999
    error(resampy_cli, bytes([OP_GOLDEN_PARSE]) + json.dumps(case).encode("utf-8"))


def test_reject_bad_base64(resampy_cli, vectors_bundle) -> None:
    case = dict(vectors_bundle["cases"][1])
    case["input_data"] = "YQ"
    error(resampy_cli, bytes([OP_GOLDEN_PARSE]) + json.dumps(case).encode("utf-8"))


def test_reject_unknown_key(resampy_cli, vectors_bundle) -> None:
    case = dict(vectors_bundle["cases"][1])
    case["unexpected"] = 1
    error(resampy_cli, bytes([OP_GOLDEN_PARSE]) + json.dumps(case).encode("utf-8"))


def test_reject_missing_key(resampy_cli) -> None:
    error(resampy_cli, bytes([OP_GOLDEN_PARSE]) + b'{"schema_version":1}')


def test_synthetic_reference_metadata_only(vectors_bundle) -> None:
    """No case claims Resampy compatibility or upstream coefficients."""
    for case in vectors_bundle["cases"]:
        assert case["reference_library"] == "synthetic"
        assert case["byte_order"] == "little"
        assert case["input_encoding"] == "base64"
        assert case["input_dtype"] == "float64"


def _base_case(vectors_bundle):
    case = dict(vectors_bundle["cases"][1])
    return case


def test_reject_nonpositive_rates(resampy_cli, vectors_bundle) -> None:
    for key, bad in [("sr_orig", 0), ("sr_new", -5)]:
        case = _base_case(vectors_bundle)
        case[key] = bad
        error(resampy_cli, bytes([OP_GOLDEN_PARSE]) + json.dumps(case).encode("utf-8"))


def test_reject_empty_provenance(resampy_cli, vectors_bundle) -> None:
    for key in [
        "case_id",
        "description",
        "reference_library",
        "reference_version",
        "reference_commit",
        "python_version",
        "numpy_version",
        "numba_version",
        "filter_id",
    ]:
        case = _base_case(vectors_bundle)
        case[key] = ""
        error(resampy_cli, bytes([OP_GOLDEN_PARSE]) + json.dumps(case).encode("utf-8"))


def test_reject_nonfinite_tolerances(resampy_cli, vectors_bundle) -> None:
    # json.dumps(inf) emits bare Infinity, which the strict parser rejects.
    for key in ["atol", "rtol"]:
        case = _base_case(vectors_bundle)
        case[key] = float("inf")
        error(resampy_cli, bytes([OP_GOLDEN_PARSE]) + json.dumps(case).encode("utf-8"))


def test_reject_numeric_overflow_token(resampy_cli, vectors_bundle) -> None:
    # Raw 1e400 must be rejected at parse time (Float64 overflow), not read as inf.
    case = _base_case(vectors_bundle)
    text = json.dumps(case).replace('"atol": 0.0', '"atol": 1e400')
    error(resampy_cli, bytes([OP_GOLDEN_PARSE]) + text.encode("utf-8"))


def test_valid_but_inconsistent_metadata_rejected(resampy_cli, vectors_bundle) -> None:
    # A valid payload hash must not rescue inconsistent metadata.
    case = _base_case(vectors_bundle)
    case["payload_element_count"] = 999
    error(resampy_cli, bytes([OP_GOLDEN_PARSE]) + json.dumps(case).encode("utf-8"))


def test_serialized_output_parses_with_python_json(resampy_cli, vectors_bundle) -> None:
    # Every serialized vector must be parseable by Python's json.loads, which
    # rejects bare inf/nan tokens.
    for case in vectors_bundle["cases"]:
        payload = ok(resampy_cli, bytes([OP_GOLDEN_SERIALIZE]) + json.dumps(case).encode("utf-8"))
        parsed = json.loads(payload.decode("utf-8"))
        assert parsed["schema_version"] == 1
        assert math.isfinite(parsed["atol"])
        assert math.isfinite(parsed["rtol"])
