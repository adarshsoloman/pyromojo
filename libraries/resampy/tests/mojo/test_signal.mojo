"""Phase 3 native tests: Component A (Signal)."""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_true, assert_false, assert_raises

from mojo_resampy.signal import Signal
from test_support import assert_bits_equal, make_values, special_values, positive_inf, negative_inf, quiet_nan


def test_empty_signal() raises:
    var s = Signal()
    assert_equal(len(s), 0)
    assert_true(s.is_empty())


def test_single_sample() raises:
    var v = List[Float64]()
    v.append(3.25)
    var s = Signal(v^)
    assert_equal(len(s), 1)
    assert_bits_equal(s[0], 3.25)


def test_multiple_samples() raises:
    var s = Signal(make_values())
    assert_equal(len(s), 7)
    assert_bits_equal(s[0], 0.0)
    assert_bits_equal(s[2], 1.0)
    assert_bits_equal(s[3], -1.0)
    assert_bits_equal(s[6], 5e-324)


def test_positive_negative_values() raises:
    var v = List[Float64]()
    v.append(-123.456)
    v.append(123.456)
    var s = Signal(v^)
    assert_bits_equal(s[0], -123.456)
    assert_bits_equal(s[1], 123.456)


def test_very_small_and_large_finite() raises:
    var v = List[Float64]()
    v.append(5e-324)
    v.append(1e-320)
    v.append(1e300)
    v.append(1.7976931348623157e308)
    var s = Signal(v^)
    assert_bits_equal(s[0], 5e-324)
    assert_bits_equal(s[2], 1e300)
    assert_bits_equal(s[3], 1.7976931348623157e308)


def test_signed_zero_preserved() raises:
    var v = List[Float64]()
    v.append(0.0)
    v.append(-0.0)
    var s = Signal(v^)
    assert_bits_equal(s[0], 0.0)
    assert_bits_equal(s[1], -0.0)


def test_nonfinite_values_preserved() raises:
    var s = Signal(special_values())
    assert_equal(len(s), 6)
    assert_true(isnan_or_inf(s[0]))
    assert_bits_equal(s[2], -positive_inf())
    assert_bits_equal(s[3], -0.0)


def test_copy_is_independent() raises:
    var s = Signal(make_values())
    var c = s.copy()
    assert_equal(len(c), len(s))
    assert_bits_equal(c[3], s[3])
    var taken = c.take()
    taken[3] = 999.0
    assert_bits_equal(s[3], -1.0)


def test_from_span_copies() raises:
    var s = Signal(make_values())
    var v = s.view()
    var c = Signal.from_span(v)
    assert_equal(len(c), len(s))
    assert_bits_equal(c[1], -0.0)


def test_zeros() raises:
    var s = Signal.zeros(4)
    assert_equal(len(s), 4)
    for i in range(len(s)):
        assert_bits_equal(s[i], 0.0)
    assert_true(Signal.zeros(0).is_empty())


def test_zeros_rejects_negative() raises:
    with assert_raises():
        _ = Signal.zeros(-1)


def test_index_out_of_range() raises:
    var s = Signal(make_values())
    with assert_raises():
        _ = s[7]
    with assert_raises():
        _ = s[-1]


def test_iteration_via_view() raises:
    var s = Signal(make_values())
    var total: Float64 = 0.0
    for i in range(len(s.view())):
        total += s.view()[i]
    assert_true(not isnan_or_inf(total))


def isnan_or_inf(v: Float64) -> Bool:
    from std.math import isnan, isinf
    return isnan(v) or isinf(v)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
