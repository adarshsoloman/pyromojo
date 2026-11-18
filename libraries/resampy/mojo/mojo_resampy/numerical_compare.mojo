"""Phase 3 / Component D: Float64 array numerical comparator.

Comparison condition (per element pair):

    |a - b| <= atol + rtol * |b|

where ``a`` is the actual value and ``b`` the reference value. Tolerances are
ALWAYS supplied by the caller; nothing is hardcoded. This is a Phase 3 utility,
not an approved Resampy compatibility tolerance (that is calibrated only after
the native interpolation kernel exists).

Element-wise matching policy (preserved from Phase 3):
- NaN matches NaN only; NaN never matches a finite value or infinity.
- +Inf matches +Inf only; -Inf matches -Inf only.
- A finite value never matches an infinity.
- Signed zero compares equal to zero (bit patterns are preserved elsewhere).

Numerical-validity and gate policy (Phase 3.1):
- ``element_wise_match`` reports the per-element policy result only.
- ``error_metrics_valid`` is False if any pair is non-finite OR any finite
  computation overflowed (subtraction, tolerance, or error accumulation).
  Non-finite error metrics are never exposed as valid finite numbers.
- ``passed`` is the SAFE GATE DECISION: it requires both element-wise matching
  and valid error metrics. A downstream gate may safely read only ``passed``.

Overflow handling:
- If ``abs(a - b)``, ``rtol * |b|``, or ``atol + rtol * |b|`` overflows for a
  finite pair, the pair is a mismatch and the metrics are invalidated. Finite
  inputs can therefore never pass merely because an intermediate tolerance
  calculation overflowed.
"""

from std.collections import List
from std.math import abs, isnan, isinf, sqrt, nan


struct ComparisonResult(Copyable, Movable, ImplicitlyCopyable):
    """Structured outcome of comparing two Float64 arrays."""

    var lengths_match: Bool
    var compared_count: Int
    var mismatch_count: Int
    var overflow_pairs: Int
    var max_abs_error: Float64
    var rmse: Float64
    var mean_abs_error: Float64
    var has_nonfinite: Bool
    var nonfinite_pairs: Int
    var error_metrics_valid: Bool
    var element_wise_match: Bool
    var passed: Bool

    def __init__(
        out self,
        lengths_match: Bool,
        compared_count: Int,
        mismatch_count: Int,
        overflow_pairs: Int,
        max_abs_error: Float64,
        rmse: Float64,
        mean_abs_error: Float64,
        has_nonfinite: Bool,
        nonfinite_pairs: Int,
        error_metrics_valid: Bool,
        element_wise_match: Bool,
        passed: Bool,
    ):
        self.lengths_match = lengths_match
        self.compared_count = compared_count
        self.mismatch_count = mismatch_count
        self.overflow_pairs = overflow_pairs
        self.max_abs_error = max_abs_error
        self.rmse = rmse
        self.mean_abs_error = mean_abs_error
        self.has_nonfinite = has_nonfinite
        self.nonfinite_pairs = nonfinite_pairs
        self.error_metrics_valid = error_metrics_valid
        self.element_wise_match = element_wise_match
        self.passed = passed

    def serialize(self) -> String:
        """ASCII key=value record for CLI responses (invalid metrics are 'nan')."""
        return (
            "lengths_match=" + ("1" if self.lengths_match else "0")
            + ";compared_count=" + String(self.compared_count)
            + ";mismatch_count=" + String(self.mismatch_count)
            + ";overflow_pairs=" + String(self.overflow_pairs)
            + ";max_abs_error=" + String(self.max_abs_error)
            + ";rmse=" + String(self.rmse)
            + ";mean_abs_error=" + String(self.mean_abs_error)
            + ";has_nonfinite=" + ("1" if self.has_nonfinite else "0")
            + ";nonfinite_pairs=" + String(self.nonfinite_pairs)
            + ";error_metrics_valid=" + ("1" if self.error_metrics_valid else "0")
            + ";element_wise_match=" + ("1" if self.element_wise_match else "0")
            + ";passed=" + ("1" if self.passed else "0")
        )


def _special_match(a: Float64, b: Float64) -> Bool:
    """Return True if a non-finite pair matches under the documented policy."""
    if isnan(a) and isnan(b):
        return True
    if isinf(a) and isinf(b):
        return (a > 0.0) == (b > 0.0)
    return False


def _invalid_result() raises -> ComparisonResult:
    """Result for a length mismatch or otherwise non-comparable pair set."""
    var bad = nan[DType.float64]()
    return ComparisonResult(
        False, 0, 0, 0,
        bad, bad, bad,
        False, 0, False, False, False,
    )


def compare_arrays(
    actual: Span[Float64, _],
    reference: Span[Float64, _],
    atol: Float64,
    rtol: Float64,
) raises -> ComparisonResult:
    """Compare two Float64 arrays with caller-supplied tolerances."""
    if isnan(atol) or isnan(rtol) or isinf(atol) or isinf(rtol) or atol < 0.0 or rtol < 0.0:
        raise Error("tolerances must be finite and non-negative")
    if len(actual) != len(reference):
        return _invalid_result()

    var count = len(actual)
    var mismatches = 0
    var overflow_pairs = 0
    var nonfinite_pairs = 0
    var metrics_ok = True
    var max_abs: Float64 = 0.0
    var sum_abs: Float64 = 0.0
    var sum_sq: Float64 = 0.0

    for i in range(count):
        var a = actual[i]
        var b = reference[i]
        var a_special = isnan(a) or isinf(a)
        var b_special = isnan(b) or isinf(b)
        if a_special or b_special:
            nonfinite_pairs += 1
            if not _special_match(a, b):
                mismatches += 1
            continue

        # Subtraction overflow: a finite pair whose difference is non-finite.
        var diff = abs(a - b)
        if isinf(diff) or isnan(diff):
            overflow_pairs += 1
            mismatches += 1
            metrics_ok = False
            continue

        # Overflow-safe tolerance evaluation. A non-finite intermediate is a
        # failure, never a free pass.
        var rel = rtol * abs(b)
        if isinf(rel) or isnan(rel):
            overflow_pairs += 1
            mismatches += 1
            metrics_ok = False
            continue
        var tolerance = atol + rel
        if isinf(tolerance) or isnan(tolerance):
            overflow_pairs += 1
            mismatches += 1
            metrics_ok = False
            continue

        if diff > tolerance:
            mismatches += 1
        if diff > max_abs:
            max_abs = diff
        sum_abs += diff
        var squared = diff * diff
        if isinf(squared) or isnan(squared):
            metrics_ok = False  # cannot accumulate a finite squared error
        else:
            sum_sq += squared
        if isinf(sum_abs) or isnan(sum_abs) or isinf(sum_sq) or isnan(sum_sq):
            metrics_ok = False

    var has_nonfinite = nonfinite_pairs > 0
    var metrics_valid = not has_nonfinite and metrics_ok
    var max_value: Float64
    var mean_abs: Float64
    var rmse_value: Float64
    if metrics_valid and count > 0:
        max_value = max_abs
        mean_abs = sum_abs / Float64(count)
        rmse_value = sqrt(sum_sq / Float64(count))
        if isnan(max_value) or isinf(max_value) or isnan(mean_abs) or isinf(mean_abs) or isnan(rmse_value) or isinf(rmse_value):
            metrics_valid = False
    elif metrics_valid:
        max_value = 0.0
        mean_abs = 0.0
        rmse_value = 0.0
    else:
        max_value = nan[DType.float64]()
        mean_abs = nan[DType.float64]()
        rmse_value = nan[DType.float64]()

    var element_match = mismatches == 0
    return ComparisonResult(
        True, count, mismatches, overflow_pairs,
        max_value, rmse_value, mean_abs,
        has_nonfinite, nonfinite_pairs, metrics_valid,
        element_match, element_match and metrics_valid,
    )
