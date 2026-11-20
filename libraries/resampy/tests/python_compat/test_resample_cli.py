"""Phase 4 Python compat: resampling kernel via the native CLI.

Compares the Mojo kernel against ``resample_reference.py`` (an independent
stdlib transcription of the upstream algorithm) and against committed,
independently generated golden vectors. Both use synthetic coefficients only.
Zero-tolerance agreement is internal-consistency evidence against the local
reference; it is not upstream Resampy validation.
"""

from __future__ import annotations

import hashlib
import json
import math

import resample_reference
from resampy_compat_support import (
    b64decode,
    bits,
    decode_f64le,
    error,
    f64le,
    ok,
    resample_body,
    sha256_hex,
)


def _load_filter(filter_resource):
    meta, raw = filter_resource
    parsed = json.loads(meta)
    return parsed["filter_id"], parsed["precision"], decode_f64le(raw)


def _meta_for(
    win: list[float], precision: int, filter_id: str = "custom_v1"
) -> tuple[bytes, bytes]:
    raw = f64le(win)
    meta = json.dumps(
        {
            "byte_order": "little",
            "coefficient_count": len(win),
            "dtype": "float64",
            "filter_id": filter_id,
            "precision": precision,
            "resource_bytes": len(raw),
            "resource_sha256": sha256_hex(raw),
            "rolloff": 1.0,
            "schema_version": 1,
        },
        sort_keys=True,
    ).encode("utf-8")
    return meta, raw


def _assert_bit_identical(got: list[float], want: list[float], label: str) -> None:
    assert len(got) == len(want), f"{label}: length {len(got)} != {len(want)}"
    for i, (g, w) in enumerate(zip(got, want, strict=True)):
        assert bits(g) == bits(w), f"{label}: bit mismatch at {i}: {g!r} != {w!r}"


def _assert_semantically_identical(got: list[float], want: list[float], label: str) -> None:
    assert len(got) == len(want), f"{label}: length {len(got)} != {len(want)}"
    for i, (g, w) in enumerate(zip(got, want, strict=True)):
        if math.isnan(w):
            assert math.isnan(g), f"{label}: expected NaN at {i}, got {g!r}"
        elif math.isinf(w):
            assert math.isinf(g) and math.copysign(1.0, g) == math.copysign(1.0, w), (
                f"{label}: infinity mismatch at {i}: {g!r} != {w!r}"
            )
        else:
            assert bits(g) == bits(w), f"{label}: bit mismatch at {i}: {g!r} != {w!r}"


def _lcg(count: int, seed: int = 12345) -> list[float]:
    state = seed
    out: list[float] = []
    for _ in range(count):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        out.append((state / 0x7FFFFFFF) * 2.0 - 1.0)
    return out


def test_algorithm_matches_independent_reference(resampy_cli, filter_resource) -> None:
    meta, raw = filter_resource
    _, precision, coeffs = _load_filter(filter_resource)
    cases = [
        ("identity", [0.5, -1.25, 2.0, -0.0, 3.5], 48000, 48000),
        ("up2", [0.0, 0.25, 0.5, 0.75, 1.0, 0.75, 0.5, 0.25], 8000, 16000),
        ("up_noni", [math.sin(0.01 * i) for i in range(97)], 44100, 48000),
        ("down2", [math.sin(0.02 * i) for i in range(128)], 48000, 24000),
        ("down_noni", [math.sin(0.005 * i) for i in range(200)], 48000, 44100),
        ("down4", [1.0] * 50, 48000, 12000),
        ("impulse_mid", [0.0] * 16 + [1.0] + [0.0] * 15, 8000, 16000),
        ("impulse_start", [1.0] + [0.0] * 31, 8000, 12000),
        ("impulse_end", [0.0] * 31 + [1.0], 8000, 12000),
        ("constant", [2.0] * 40, 10, 13),
        ("zero", [0.0] * 32, 44100, 48000),
        ("lcg", _lcg(100), 44100, 48000),
        ("short", [1.0, -1.0, 0.5], 4, 3),
        ("single_up", [3.0], 8000, 16000),
        ("single_down", [3.0], 8000, 4000),
        ("empty", [], 44100, 48000),
        ("alternating", [1.0 if i % 2 == 0 else -1.0 for i in range(40)], 4000, 6000),
    ]
    for label, signal, sr_orig, sr_new in cases:
        got = decode_f64le(ok(resampy_cli, resample_body(signal, sr_orig, sr_new, meta, raw)))
        want = resample_reference.resample(signal, sr_orig, sr_new, coeffs, precision)
        _assert_bit_identical(got, want, label)


def test_nonfinite_signal_matches_reference(resampy_cli, filter_resource) -> None:
    meta, raw = filter_resource
    _, precision, coeffs = _load_filter(filter_resource)
    cases = [
        ("inf_at_end", [0.0, math.inf], 1, 2),
        ("nan_at_start", [math.nan, 0.0], 1, 2),
        ("mixed_infs", [math.inf, -math.inf], 1, 2),
    ]
    for label, signal, sr_orig, sr_new in cases:
        got = decode_f64le(ok(resampy_cli, resample_body(signal, sr_orig, sr_new, meta, raw)))
        want = resample_reference.resample(signal, sr_orig, sr_new, coeffs, precision)
        _assert_semantically_identical(got, want, label)


def test_analytic_linear_interpolation(resampy_cli) -> None:
    """Filter [1, 0] with P=1 reduces the kernel to exact linear interpolation."""
    win = [1.0, 0.0]
    meta, raw = _meta_for(win, 1, "lin_v1")
    signal = [0.0, 1.0, 2.0, 3.0, 4.0]
    got = decode_f64le(ok(resampy_cli, resample_body(signal, 1, 2, meta, raw)))

    expected: list[float] = []
    for t in range(len(got)):
        tau = t * 0.5
        n = int(tau)
        frac = tau - n
        if n < len(signal) - 1:
            expected.append((1.0 - frac) * signal[n] + frac * signal[n + 1])
        else:
            expected.append((1.0 - frac) * signal[n])
    assert expected == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 2.0]
    _assert_bit_identical(got, expected, "linear")


def test_terminal_impulse_with_precision_below_count(resampy_cli) -> None:
    """The terminal sample contributes through an interpolated left-wing tap."""
    win = [1.0, 0.5, 0.0, 0.0]
    meta, raw = _meta_for(win, 1, "terminal_v1")
    signal = [0.0, 0.0, 0.0, 1.0]
    got = decode_f64le(ok(resampy_cli, resample_body(signal, 1, 2, meta, raw)))

    expected = [0.0, 0.0, 0.0, 0.25, 0.5, 0.75, 1.0, 0.75]
    _assert_bit_identical(got, expected, "terminal_impulse_expected")
    assert got[3] != 0.0

    want = resample_reference.resample(signal, 1, 2, win, 1)
    _assert_bit_identical(got, want, "terminal_impulse_reference")


def test_rejects_nonpositive_rates(resampy_cli, filter_resource) -> None:
    meta, raw = filter_resource
    error(resampy_cli, resample_body([1.0, 2.0], 0, 2, meta, raw))
    error(resampy_cli, resample_body([1.0, 2.0], 2, 0, meta, raw))


def test_rejects_filter_id_mismatch(resampy_cli, filter_resource) -> None:
    meta, raw = filter_resource
    error(resampy_cli, resample_body([1.0, 2.0], 100, 200, meta, raw, filter_id="wrong"))


def test_rejects_truncated_payload(resampy_cli, filter_resource) -> None:
    meta, raw = filter_resource
    body = resample_body([1.0, 2.0], 100, 200, meta, raw)
    error(resampy_cli, body[:-3])


def test_rejects_trailing_bytes(resampy_cli, filter_resource) -> None:
    meta, raw = filter_resource
    body = resample_body([1.0, 2.0], 100, 200, meta, raw)
    error(resampy_cli, body + b"\x00")


def test_rejects_ratio_too_small(resampy_cli, filter_resource) -> None:
    meta, raw = filter_resource
    error(resampy_cli, resample_body([1.0] * 40, 48000, 3000, meta, raw))


def test_rejects_non_finite_filter_coefficients(resampy_cli) -> None:
    for value in (math.nan, math.inf):
        meta, raw = _meta_for([1.0, value], 2)
        payload = error(resampy_cli, resample_body([1.0, 2.0], 100, 200, meta, raw))
        assert b"not finite" in payload


def test_rejects_precision_above_coefficient_count(resampy_cli) -> None:
    meta, raw = _meta_for([1.0, 0.0], 8)
    payload = error(resampy_cli, resample_body([1.0, 2.0], 100, 200, meta, raw))
    assert b"exceeds non-empty coefficient_count" in payload


def test_determinism_is_byte_identical(resampy_cli, filter_resource) -> None:
    meta, raw = filter_resource
    body = resample_body(_lcg(80), 44100, 32000, meta, raw)
    first = ok(resampy_cli, body)
    second = ok(resampy_cli, body)
    assert first == second


def test_golden_vectors(resampy_cli, filter_resource, resampling_vectors_bundle) -> None:
    meta, raw = filter_resource
    cases = resampling_vectors_bundle["cases"]
    assert cases, "golden vector bundle is empty"
    for case in cases:
        signal = decode_f64le(b64decode(case["input_data"]))
        expected = decode_f64le(b64decode(case["expected_data"]))
        assert len(signal) == case["input_count"]
        assert len(expected) == case["expected_count"]
        body = resample_body(
            signal,
            case["sr_orig"],
            case["sr_new"],
            meta,
            raw,
            filter_id=case["filter_id"],
        )
        got = decode_f64le(ok(resampy_cli, body))
        _assert_bit_identical(got, expected, case["case_id"])


def test_golden_vector_payload_hashes(resampling_vectors_bundle) -> None:
    for case in resampling_vectors_bundle["cases"]:
        combined = b64decode(case["input_data"]) + b64decode(case["expected_data"])
        assert hashlib.sha256(combined).hexdigest() == case["payload_sha256"]
