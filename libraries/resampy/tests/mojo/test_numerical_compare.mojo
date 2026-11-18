"""Phase 3 native tests: Component D (numerical comparator)."""

from std.collections import List
from std.math import isnan
from std.testing import TestSuite, assert_equal, assert_true, assert_false, assert_raises

from mojo_resampy.numerical_compare import compare_arrays
from test_support import assert_bits_equal, positive_inf, negative_inf, quiet_nan


def _vals(*items: Float64) -> List[Float64]:
    var out = List[Float64]()
    for item in items:
        out.append(item)
    return out^


def test_equal_finite_values() raises:
    var a = _vals(1.0, -2.5, 0.0, 3.25)
    var b = _vals(1.0, -2.5, 0.0, 3.25)
    var r = compare_arrays(Span(a), Span(b), 0.0, 0.0)
    assert_true(r.lengths_match)
    assert_equal(r.compared_count, 4)
    assert_equal(r.mismatch_count, 0)
    assert_equal(r.max_abs_error, 0.0)
    assert_equal(r.rmse, 0.0)
    assert_equal(r.mean_abs_error, 0.0)
    assert_false(r.has_nonfinite)
    assert_true(r.error_metrics_valid)
    assert_true(r.passed)


def test_unequal_finite_within_tolerance() raises:
    var a = _vals(1.0, 2.0)
    var b = _vals(1.0 + 1e-12, 2.0 - 1e-12)
    var r = compare_arrays(Span(a), Span(b), 1e-9, 0.0)
    assert_equal(r.mismatch_count, 0)
    assert_true(r.passed)
    assert_true(r.max_abs_error <= 1e-9)


def test_unequal_finite_outside_tolerance() raises:
    var a = _vals(1.0, 2.0, 3.0)
    var b = _vals(1.0, 2.5, 3.0)
    var r = compare_arrays(Span(a), Span(b), 0.0, 0.0)
    assert_equal(r.mismatch_count, 1)
    assert_false(r.passed)
    assert_equal(r.max_abs_error, 0.5)
    assert_equal(r.mean_abs_error, 0.5 / 3.0)


def test_relative_tolerance_condition() raises:
    var a = _vals(10.1)
    var b = _vals(10.0)
    var loose = compare_arrays(Span(a), Span(b), 0.0, 0.02)
    assert_equal(loose.mismatch_count, 0)
    var tight = compare_arrays(Span(a), Span(b), 0.0, 0.001)
    assert_equal(tight.mismatch_count, 1)


def test_positive_and_negative_zero() raises:
    var a = _vals(0.0, -0.0)
    var b = _vals(-0.0, 0.0)
    var r = compare_arrays(Span(a), Span(b), 0.0, 0.0)
    assert_equal(r.mismatch_count, 0)
    assert_true(r.passed)


def test_nan_matches_nan() raises:
    var nan = quiet_nan()
    var a = _vals(nan, nan)
    var b = _vals(nan, nan)
    var r = compare_arrays(Span(a), Span(b), 0.0, 0.0)
    assert_equal(r.mismatch_count, 0)
    assert_true(r.has_nonfinite)
    assert_equal(r.nonfinite_pairs, 2)
    assert_false(r.error_metrics_valid)
    assert_true(isnan(r.max_abs_error))


def test_nan_never_matches_finite() raises:
    var a = _vals(quiet_nan())
    var b = _vals(1.0)
    var r = compare_arrays(Span(a), Span(b), 1e9, 1e9)
    assert_equal(r.mismatch_count, 1)
    assert_false(r.passed)
    assert_true(r.has_nonfinite)


def test_infinities() raises:
    var pinf = positive_inf()
    var ninf = -positive_inf()
    var a = _vals(pinf, ninf, pinf, 1.0, pinf)
    var b = _vals(pinf, ninf, ninf, pinf, 1.0)
    var r = compare_arrays(Span(a), Span(b), 1e9, 1e9)
    # All five pairs involve an infinity. Pairs 0/1 match (+inf/+inf,
    # -inf/-inf); pairs 2/3/4 mismatch (+inf/-inf, finite/+inf, +inf/finite).
    assert_equal(r.nonfinite_pairs, 5)
    assert_equal(r.mismatch_count, 3)
    assert_false(r.passed)
    assert_false(r.error_metrics_valid)


def test_different_lengths_fail() raises:
    var a = _vals(1.0, 2.0, 3.0)
    var b = _vals(1.0, 2.0)
    var r = compare_arrays(Span(a), Span(b), 1e9, 1e9)
    assert_false(r.lengths_match)
    assert_equal(r.compared_count, 0)
    assert_false(r.passed)
    assert_false(r.error_metrics_valid)
    assert_true(isnan(r.max_abs_error))


def test_empty_arrays() raises:
    var a = List[Float64]()
    var b = List[Float64]()
    var r = compare_arrays(Span(a), Span(b), 0.0, 0.0)
    assert_true(r.lengths_match)
    assert_equal(r.compared_count, 0)
    assert_equal(r.mismatch_count, 0)
    assert_equal(r.max_abs_error, 0.0)
    assert_true(r.passed)


def test_metrics_are_not_misleading_when_nonfinite() raises:
    var pinf = positive_inf()
    var a = _vals(1.0, pinf)
    var b = _vals(1.0, pinf)
    var r = compare_arrays(Span(a), Span(b), 0.0, 0.0)
    assert_true(r.has_nonfinite)
    assert_false(r.error_metrics_valid)
    assert_true(isnan(r.rmse))
    assert_true(isnan(r.mean_abs_error))


def test_reject_negative_tolerance() raises:
    var a = _vals(1.0)
    var b = _vals(1.0)
    with assert_raises():
        _ = compare_arrays(Span(a), Span(b), -1.0, 0.0)
    with assert_raises():
        _ = compare_arrays(Span(a), Span(b), 0.0, -1.0)


def test_reject_nonfinite_tolerance() raises:
    var a = _vals(1.0)
    var b = _vals(1.0)
    with assert_raises():
        _ = compare_arrays(Span(a), Span(b), positive_inf(), 0.0)
    with assert_raises():
        _ = compare_arrays(Span(a), Span(b), quiet_nan(), 0.0)


def test_serialize_record() raises:
    var a = _vals(1.0, 2.0)
    var b = _vals(1.0, 2.0)
    var r = compare_arrays(Span(a), Span(b), 1e-9, 1e-9)
    var text = r.serialize()
    assert_true("passed=1" in text)
    assert_true("compared_count=2" in text)


def test_overflow_tolerance_never_passes() raises:
    # P1-01 repro 1: rtol*|b| overflows to +inf; a grossly wrong value must fail.
    var a = _vals(0.0)
    var b = _vals(1e308)
    var r = compare_arrays(Span(a), Span(b), 0.0, 2.0)
    assert_false(r.passed)
    assert_false(r.element_wise_match)
    assert_equal(r.mismatch_count, 1)
    assert_true(r.overflow_pairs >= 1)
    assert_false(r.error_metrics_valid)
    assert_true(isnan(r.max_abs_error))


def test_overflow_subtraction_and_tolerance_never_passes() raises:
    # P1-01 repro 2: both abs(a-b) and atol + rtol*|b| overflow.
    var a = _vals(1.7e308)
    var b = _vals(-1.7e308)
    var r = compare_arrays(Span(a), Span(b), 1e308, 1.0)
    assert_false(r.passed)
    assert_equal(r.mismatch_count, 1)
    assert_true(r.overflow_pairs >= 1)
    assert_false(r.error_metrics_valid)


def test_finite_subtraction_overflow_metrics_invalid() raises:
    # P2-02/R2: diff is finite (1e200) but diff*diff overflows to +inf.
    var a = _vals(1e200)
    var b = _vals(0.0)
    var r = compare_arrays(Span(a), Span(b), 0.0, 0.0)
    assert_false(r.passed)
    assert_equal(r.mismatch_count, 1)
    assert_false(r.error_metrics_valid)
    assert_true(isnan(r.rmse))
    assert_true(isnan(r.mean_abs_error))


def test_large_finite_small_tolerance() raises:
    # R4: very large finite values with tiny tolerances must be decided exactly.
    var a = _vals(1e308, 1.5e308)
    var b = _vals(1e308, 1.5e308)
    var r = compare_arrays(Span(a), Span(b), 0.0, 1e-15)
    assert_true(r.passed)
    assert_equal(r.mismatch_count, 0)
    assert_true(r.error_metrics_valid)
    assert_equal(r.max_abs_error, 0.0)


def test_gate_contract_nan_and_infinity() raises:
    # P2-03: element-wise match is preserved but the gate rejects invalid metrics.
    var nan = quiet_nan()
    var a = _vals(nan, nan)
    var b = _vals(nan, nan)
    var r = compare_arrays(Span(a), Span(b), 0.0, 0.0)
    assert_true(r.element_wise_match)  # NaN matches NaN policy preserved
    assert_false(r.error_metrics_valid)
    assert_false(r.passed)             # safe gate decision

    var pinf = positive_inf()
    var p = compare_arrays(_vals(pinf), _vals(pinf), 0.0, 0.0)
    assert_true(p.element_wise_match)
    assert_false(p.passed)

    var mixed = compare_arrays(_vals(pinf), _vals(1.0), 1e9, 1e9)
    assert_false(mixed.element_wise_match)
    assert_false(mixed.passed)


def test_empty_arrays_gate() raises:
    # R6: empty arrays compare trivially and remain a valid gate result.
    var a = List[Float64]()
    var b = List[Float64]()
    var r = compare_arrays(Span(a), Span(b), 0.0, 0.0)
    assert_true(r.lengths_match)
    assert_true(r.element_wise_match)
    assert_true(r.error_metrics_valid)
    assert_true(r.passed)
    assert_equal(r.compared_count, 0)


def test_comparison_result_serialized_fields() raises:
    # P2-03: serialized record exposes both element match and gate decision.
    var a = _vals(quiet_nan())
    var b = _vals(quiet_nan())
    var text = compare_arrays(Span(a), Span(b), 0.0, 0.0).serialize()
    assert_true("element_wise_match=1" in text)
    assert_true("error_metrics_valid=0" in text)
    assert_true("passed=0" in text)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
