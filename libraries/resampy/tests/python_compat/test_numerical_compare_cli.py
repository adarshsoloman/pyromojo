"""Phase 3 Python compat: numerical comparator semantics via the native CLI."""

from __future__ import annotations

import math

from resampy_compat_support import (
    compare_body,
    ok,
    parse_kv,
)


def test_equal_finite(resampy_cli) -> None:
    r = parse_kv(ok(resampy_cli, compare_body([1.0, -2.5, 0.0], [1.0, -2.5, 0.0], 0.0, 0.0)))
    assert r["lengths_match"] == "1"
    assert r["compared_count"] == "3"
    assert r["mismatch_count"] == "0"
    assert r["passed"] == "1"
    assert float(r["max_abs_error"]) == 0.0
    assert float(r["rmse"]) == 0.0


def test_within_and_outside_tolerance(resampy_cli) -> None:
    loose = parse_kv(ok(resampy_cli, compare_body([1.0 + 1e-12], [1.0], 1e-9, 0.0)))
    assert loose["passed"] == "1"
    tight = parse_kv(ok(resampy_cli, compare_body([1.5], [1.0], 1e-9, 0.0)))
    assert tight["passed"] == "0"
    assert tight["mismatch_count"] == "1"
    assert float(tight["max_abs_error"]) == 0.5


def test_relative_tolerance(resampy_cli) -> None:
    loose = parse_kv(ok(resampy_cli, compare_body([10.1], [10.0], 0.0, 0.02)))
    assert loose["passed"] == "1"
    tight = parse_kv(ok(resampy_cli, compare_body([10.1], [10.0], 0.0, 0.001)))
    assert tight["passed"] == "0"


def test_signed_zero_matches(resampy_cli) -> None:
    r = parse_kv(ok(resampy_cli, compare_body([0.0, -0.0], [-0.0, 0.0], 0.0, 0.0)))
    assert r["passed"] == "1"


def test_nan_matches_nan_only(resampy_cli) -> None:
    nan = float("nan")
    r = parse_kv(ok(resampy_cli, compare_body([nan, nan], [nan, nan], 1e9, 1e9)))
    assert r["mismatch_count"] == "0"
    assert r["has_nonfinite"] == "1"
    assert r["nonfinite_pairs"] == "2"
    assert r["error_metrics_valid"] == "0"
    assert math.isnan(float(r["max_abs_error"]))
    bad = parse_kv(ok(resampy_cli, compare_body([nan], [1.0], 1e9, 1e9)))
    assert bad["mismatch_count"] == "1"
    assert bad["passed"] == "0"


def test_infinities(resampy_cli) -> None:
    pinf, ninf = float("inf"), float("-inf")
    r = parse_kv(
        ok(resampy_cli, compare_body([pinf, ninf, pinf, 1.0], [pinf, ninf, ninf, pinf], 1e9, 1e9))
    )
    assert r["nonfinite_pairs"] == "4"
    # pair 0/1 match; pair 2 (+inf vs -inf) and pair 3 (finite vs inf) mismatch
    assert r["mismatch_count"] == "2"
    assert r["has_nonfinite"] == "1"


def test_different_lengths(resampy_cli) -> None:
    r = parse_kv(ok(resampy_cli, compare_body([1.0, 2.0, 3.0], [1.0], 1e9, 1e9)))
    assert r["lengths_match"] == "0"
    assert r["compared_count"] == "0"
    assert r["passed"] == "0"
    assert r["error_metrics_valid"] == "0"


def test_empty_arrays(resampy_cli) -> None:
    r = parse_kv(ok(resampy_cli, compare_body([], [], 0.0, 0.0)))
    assert r["compared_count"] == "0"
    assert r["passed"] == "1"
    assert r["max_abs_error"] == "0.0"


def test_no_misleading_metrics_when_nonfinite(resampy_cli) -> None:
    r = parse_kv(ok(resampy_cli, compare_body([1.0, float("inf")], [1.0, float("inf")], 0.0, 0.0)))
    assert r["error_metrics_valid"] == "0"
    assert math.isnan(float(r["rmse"]))
    assert math.isnan(float(r["mean_abs_error"]))


def test_explicit_tolerances_not_hardcoded(resampy_cli) -> None:
    a, b = [1.0 + 1e-6], [1.0]
    strict = parse_kv(ok(resampy_cli, compare_body(a, b, 1e-9, 0.0)))
    loose = parse_kv(ok(resampy_cli, compare_body(a, b, 1e-3, 0.0)))
    assert strict["passed"] == "0"
    assert loose["passed"] == "1"


def test_p1_overflow_cases_never_pass(resampy_cli) -> None:
    # P1-01 repros from the independent review: both must fail the gate.
    for a, b, atol, rtol in [
        ([0.0], [1e308], 0.0, 2.0),
        ([1.7e308], [-1.7e308], 1e308, 1.0),
    ]:
        r = parse_kv(ok(resampy_cli, compare_body(a, b, atol, rtol)))
        assert r["passed"] == "0", (a, b)
        assert r["element_wise_match"] == "0"
        assert r["mismatch_count"] == "1"
        assert int(r["overflow_pairs"]) >= 1
        assert r["error_metrics_valid"] == "0"


def test_p2_finite_squared_overflow_invalid_metrics(resampy_cli) -> None:
    r = parse_kv(ok(resampy_cli, compare_body([1e200], [0.0], 0.0, 0.0)))
    assert r["error_metrics_valid"] == "0"
    assert math.isnan(float(r["rmse"]))
    assert math.isnan(float(r["mean_abs_error"]))


def test_gate_contract_separates_element_match_from_validity(resampy_cli) -> None:
    nan = float("nan")
    r = parse_kv(ok(resampy_cli, compare_body([nan], [nan], 0.0, 0.0)))
    assert r["element_wise_match"] == "1"  # NaN/NaN policy preserved
    assert r["error_metrics_valid"] == "0"
    assert r["passed"] == "0"  # safe gate decision
    pinf = float("inf")
    r2 = parse_kv(ok(resampy_cli, compare_body([pinf], [pinf], 0.0, 0.0)))
    assert r2["element_wise_match"] == "1"
    assert r2["passed"] == "0"
    r3 = parse_kv(ok(resampy_cli, compare_body([pinf], [1.0], 1e9, 1e9)))
    assert r3["element_wise_match"] == "0"
    assert r3["passed"] == "0"


def test_empty_arrays_valid_gate(resampy_cli) -> None:
    r = parse_kv(ok(resampy_cli, compare_body([], [], 0.0, 0.0)))
    assert r["lengths_match"] == "1"
    assert r["element_wise_match"] == "1"
    assert r["error_metrics_valid"] == "1"
    assert r["passed"] == "1"
    assert r["compared_count"] == "0"
