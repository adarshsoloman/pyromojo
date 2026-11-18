"""Shared helpers for Phase 3 native Mojo tests (bit-level assertions)."""

from std.collections import List
from std.math import isnan, isinf
from mojo_resampy.float_codec import float64_to_bits


def assert_bits_equal(actual: Float64, expected: Float64) raises:
    """Assert exact IEEE-754 bit equality (distinguishes -0.0, NaN payloads)."""
    if float64_to_bits(actual) != float64_to_bits(expected):
        raise Error(
            "Float64 bit mismatch: got " + String(float64_to_bits(actual))
            + ", expected " + String(float64_to_bits(expected))
        )


def make_values() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.0)
    out.append(-0.0)
    out.append(1.0)
    out.append(-1.0)
    out.append(1e-300)
    out.append(1e300)
    out.append(5e-324)
    return out^


def runtime_zero() -> Float64:
    """Return 0.0 produced at runtime (inline division literals are folded)."""
    var x: Float64 = 1.0
    return x - x


def positive_inf() -> Float64:
    var z = runtime_zero()
    return 1.0 / z


def negative_inf() -> Float64:
    var z = runtime_zero()
    return -1.0 / z


def quiet_nan() -> Float64:
    var z = runtime_zero()
    return z / z


def special_values() -> List[Float64]:
    var out = List[Float64]()
    out.append(quiet_nan())        # NaN
    out.append(positive_inf())     # +Inf
    out.append(negative_inf())     # -Inf
    out.append(-0.0)
    out.append(5e-324)             # smallest subnormal
    out.append(1.7976931348623157e308)
    return out^


def is_special(v: Float64) -> Bool:
    return isnan(v) or isinf(v) or float64_to_bits(v) == 9223372036854775808
