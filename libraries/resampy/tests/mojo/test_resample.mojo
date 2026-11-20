"""Phase 4 native tests: windowed-sinc resampling kernel.

Most tests build a small validated ``FilterCoefficients`` in memory so they are
independent of the working directory. One test loads the committed synthetic
resource (the library-local runner sets ``cwd`` to the repository root).
"""

from std.collections import List
from std.math import isnan, isinf
from std.testing import TestSuite, assert_equal, assert_true, assert_raises

from mojo_resampy.coefficients import FilterCoefficients, FilterMetadata, load_filter
from mojo_resampy.resample import output_length, resample
from mojo_resampy.signal import Signal
from test_support import assert_bits_equal, positive_inf, negative_inf, quiet_nan


comptime RES: String = "libraries/resampy/resources/synthetic"
comptime DUMMY_SHA: String = (
    "0000000000000000000000000000000000000000000000000000000000000000"
)


def _filter(values: List[Float64], precision: Int) -> FilterCoefficients:
    var copy = List[Float64](capacity=len(values))
    for v in values:
        copy.append(v)
    var meta = FilterMetadata(
        1,
        "test_filter",
        len(copy),
        precision,
        0.95,
        "float64",
        "little",
        len(copy) * 8,
        DUMMY_SHA,
    )
    return FilterCoefficients(meta, copy^)


def _signal(values: List[Float64]) -> Signal:
    var copy = List[Float64](capacity=len(values))
    for v in values:
        copy.append(v)
    return Signal(copy^)


def _floats(size: Int, start: Float64, step: Float64) -> List[Float64]:
    var out = List[Float64](capacity=size)
    for i in range(size):
        out.append(start + step * Float64(i))
    return out^


def _synthetic_values() -> List[Float64]:
    # Same length/precision shape as the committed synthetic resource, but with
    # arbitrary in-memory values (the kernel tests do not need its exact bits).
    var out = List[Float64](capacity=8)
    out.append(0.9)
    out.append(0.35)
    out.append(-0.1)
    out.append(-0.2)
    out.append(0.05)
    out.append(0.02)
    out.append(-0.01)
    out.append(0.0)
    return out^


def test_validation_rejects_nonpositive_rates() raises:
    var coeffs = _filter(_synthetic_values(), 8)
    var sig = _signal(_floats(8, 0.0, 0.1))
    with assert_raises():
        _ = resample(sig, 0, 2, coeffs)
    with assert_raises():
        _ = resample(sig, 2, 0, coeffs)
    with assert_raises():
        _ = output_length(8, 0, 2)
    with assert_raises():
        _ = output_length(8, 2, 0)


def test_equal_rate_is_bit_exact_copy() raises:
    var values = List[Float64](capacity=6)
    values.append(1.5)
    values.append(-0.0)
    values.append(5e-324)
    values.append(quiet_nan())
    values.append(positive_inf())
    values.append(negative_inf())
    var sig = _signal(values)
    var coeffs = _filter(_synthetic_values(), 8)
    var out = resample(sig, 48000, 48000, coeffs)
    assert_equal(len(out), 6)
    for i in range(6):
        assert_bits_equal(out[i], sig[i])


def test_empty_input_returns_empty() raises:
    var coeffs = _filter(_synthetic_values(), 8)
    var out = resample(_signal(List[Float64]()), 44100, 48000, coeffs)
    assert_equal(len(out), 0)


def test_single_sample_upsample() raises:
    var coeffs = _filter(_synthetic_values(), 8)
    var values = List[Float64](capacity=1)
    values.append(3.0)
    var out = resample(_signal(values), 8000, 16000, coeffs)
    assert_equal(len(out), 2)
    assert_bits_equal(out[0], 2.7)
    assert_bits_equal(out[1], 0.0)


def test_single_sample_downsample_is_empty() raises:
    var coeffs = _filter(_synthetic_values(), 8)
    var values = List[Float64](capacity=1)
    values.append(3.0)
    var out = resample(_signal(values), 8000, 4000, coeffs)
    assert_equal(len(out), 0)


def test_output_length_truncates() raises:
    assert_equal(output_length(10, 3, 2), 6)
    assert_equal(output_length(3, 2, 3), 4)
    assert_equal(output_length(12499, 2, 3), 18748)
    assert_equal(output_length(1, 4, 1), 0)
    assert_equal(output_length(0, 44100, 48000), 0)
    assert_equal(output_length(7, 7, 1), 1)


def test_output_length_limit() raises:
    assert_equal(output_length(1_000_000, 1, 1), 1_000_000)
    with assert_raises():
        _ = output_length(1_000_001, 1, 1)
    with assert_raises():
        _ = output_length(600_000, 1, 2)


def test_huge_output_length_diagnostic_safe() raises:
    var message = String("")
    try:
        _ = output_length(9_000_000_000_000_000_000, 1, 1)
    except e:
        message = String(e)
    assert_true("exceeds limit" in message)
    assert_true(not ("-9223372036854775808" in message))


def test_equal_rate_output_limit_rejected() raises:
    var coeffs = _filter(_synthetic_values(), 8)
    var sig = _signal(_floats(1_000_001, 0.0, 0.0))
    with assert_raises():
        _ = resample(sig, 48000, 48000, coeffs)


def test_linear_interpolation_exact() raises:
    # A two-tap filter [1, 0] with P=1 and index_step=1 reduces the windowed-sinc
    # loop to exact linear interpolation, giving hand-checkable expected values.
    var win = List[Float64](capacity=2)
    win.append(1.0)
    win.append(0.0)
    var coeffs = _filter(win, 1)
    var out = resample(_signal(_floats(5, 0.0, 1.0)), 1, 2, coeffs)
    var expected = List[Float64](capacity=10)
    expected.append(0.0)
    expected.append(0.5)
    expected.append(1.0)
    expected.append(1.5)
    expected.append(2.0)
    expected.append(2.5)
    expected.append(3.0)
    expected.append(3.5)
    expected.append(4.0)
    expected.append(2.0)
    assert_equal(len(out), len(expected))
    for i in range(len(expected)):
        assert_bits_equal(out[i], expected[i])


def test_zero_signal_stays_zero() raises:
    var coeffs = _filter(_synthetic_values(), 8)
    var out = resample(_signal(_floats(32, 0.0, 0.0)), 44100, 48000, coeffs)
    assert_equal(len(out), 34)
    for i in range(len(out)):
        assert_bits_equal(out[i], 0.0)


def test_determinism_bit_exact() raises:
    var coeffs = _filter(_synthetic_values(), 8)
    var sig = _signal(_floats(64, -1.0, 0.03125))
    var a = resample(sig, 44100, 32000, coeffs)
    var b = resample(sig, 44100, 32000, coeffs)
    assert_equal(len(a), len(b))
    for i in range(len(a)):
        assert_bits_equal(a[i], b[i])


def test_short_input_boundary_safe() raises:
    var coeffs = _filter(_synthetic_values(), 8)
    var values = List[Float64](capacity=2)
    values.append(1.0)
    values.append(2.0)
    var out = resample(_signal(values), 48000, 44100, coeffs)
    assert_equal(len(out), 1)
    assert_bits_equal(out[0], 0.826875)


def test_impulse_boundaries_finite() raises:
    var coeffs = _filter(_synthetic_values(), 8)
    var n = 40
    var first = List[Float64](capacity=40)
    var last = List[Float64](capacity=40)
    for i in range(n):
        first.append(1.0 if i == 0 else 0.0)
        last.append(1.0 if i == n - 1 else 0.0)
    var a = resample(_signal(first), 8000, 12000, coeffs)
    var b = resample(_signal(last), 8000, 12000, coeffs)
    assert_equal(len(a), 60)
    assert_equal(len(b), 60)
    assert_bits_equal(a[0], 0.9)
    for i in range(1, len(a)):
        assert_bits_equal(a[i], 0.0)
    for i in range(len(b)):
        assert_bits_equal(b[i], 0.0)


def test_terminal_impulse_with_precision_below_count() raises:
    # precision=1 < coefficient_count=4 keeps the terminal input sample inside
    # both wings: it contributes 0.25/0.5/0.75 at outputs 3-5 (right wing) and
    # 1.0/0.75 at outputs 6-7 (left wing). This is a genuine nonzero terminal
    # contribution, unlike the older boundary test whose synthetic filter has
    # precision equal to its coefficient count.
    var win = List[Float64](capacity=4)
    win.append(1.0)
    win.append(0.5)
    win.append(0.0)
    win.append(0.0)
    var coeffs = _filter(win, 1)
    var values = List[Float64](capacity=4)
    values.append(0.0)
    values.append(0.0)
    values.append(0.0)
    values.append(1.0)
    var out = resample(_signal(values), 1, 2, coeffs)
    assert_equal(len(out), 8)
    var expected = List[Float64](capacity=8)
    expected.append(0.0)
    expected.append(0.0)
    expected.append(0.0)
    expected.append(0.25)
    expected.append(0.5)
    expected.append(0.75)
    expected.append(1.0)
    expected.append(0.75)
    for i in range(len(expected)):
        assert_bits_equal(out[i], expected[i])
    assert_true(out[3] != 0.0)


def test_constant_signal_finite() raises:
    var coeffs = _filter(_synthetic_values(), 8)
    var out = resample(_signal(_floats(40, 2.0, 0.0)), 10, 13, coeffs)
    assert_equal(len(out), 52)
    assert_bits_equal(out[0], 1.8)
    assert_bits_equal(out[4], 1.1230769230769255)
    assert_bits_equal(out[9], 1.1230769230769178)
    assert_bits_equal(out[13], 1.8)
    assert_bits_equal(out[26], 1.8)
    assert_bits_equal(out[39], 1.7999999999999687)
    assert_bits_equal(out[51], 0.0)


def test_nonfinite_signal_propagation_unequal_rates() raises:
    var win = List[Float64](capacity=2)
    win.append(1.0)
    win.append(0.0)
    var coeffs = _filter(win, 1)

    var inf_signal = List[Float64](capacity=2)
    inf_signal.append(0.0)
    inf_signal.append(positive_inf())
    var inf_out = resample(_signal(inf_signal), 1, 2, coeffs)
    assert_equal(len(inf_out), 4)
    assert_true(isnan(inf_out[0]))
    for i in range(1, len(inf_out)):
        assert_true(isinf(inf_out[i]) and inf_out[i] > 0.0)

    var nan_signal = List[Float64](capacity=2)
    nan_signal.append(quiet_nan())
    nan_signal.append(0.0)
    var nan_out = resample(_signal(nan_signal), 1, 2, coeffs)
    assert_equal(len(nan_out), 4)
    for i in range(len(nan_out)):
        assert_true(isnan(nan_out[i]))


def test_non_finite_filter_coefficients_rejected() raises:
    var sig = _signal(_floats(8, 0.0, 0.1))
    var nan_filter = List[Float64](capacity=2)
    nan_filter.append(1.0)
    nan_filter.append(quiet_nan())
    with assert_raises():
        _ = resample(sig, 1000, 2000, _filter(nan_filter, 1))
    var inf_filter = List[Float64](capacity=2)
    inf_filter.append(1.0)
    inf_filter.append(positive_inf())
    with assert_raises():
        _ = resample(sig, 1000, 2000, _filter(inf_filter, 1))


def test_precision_above_coefficient_count_rejected() raises:
    var sig = _signal(_floats(8, 0.0, 0.1))
    var values = List[Float64](capacity=2)
    values.append(1.0)
    values.append(0.0)
    var message = String("")
    try:
        _ = resample(sig, 1000, 2000, _filter(values, 8))
    except e:
        message = String(e)
    assert_true("exceeds coefficient count" in message)


def test_ratio_too_small_rejected() raises:
    # ratio = 0.0625, precision 8 -> int(scale*precision) = 0.
    var coeffs = _filter(_synthetic_values(), 8)
    var sig = _signal(_floats(40, 1.0, 0.0))
    with assert_raises():
        _ = resample(sig, 48000, 3000, coeffs)


def test_invalid_precision_rejected() raises:
    var sig = _signal(_floats(8, 0.0, 0.1))
    with assert_raises():
        _ = resample(sig, 1000, 2000, _filter(_synthetic_values(), 0))
    with assert_raises():
        _ = resample(sig, 1000, 2000, _filter(_synthetic_values(), 1_000_001))


def test_empty_filter_rejected() raises:
    var sig = _signal(_floats(8, 0.0, 0.1))
    with assert_raises():
        _ = resample(sig, 1000, 2000, _filter(List[Float64](), 8))


def test_committed_synthetic_resource() raises:
    var resource = load_filter(RES + "/synthetic_filter.json", RES + "/synthetic_filter.bin")
    assert_equal(resource.metadata.filter_id, "synthetic_tiny_v1")
    var out = resample(_signal(_floats(64, -1.0, 0.03125)), 44100, 48000, resource)
    assert_equal(len(out), 69)
    assert_bits_equal(out[0], -0.5)
    assert_bits_equal(out[1], -0.3269531249999999)
    assert_bits_equal(out[11], -0.19765625000000098)
    assert_bits_equal(out[13], -0.24218749999999956)
    assert_bits_equal(out[34], 0.0)
    assert_bits_equal(out[67], 0.0)
    assert_bits_equal(out[68], 0.0)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
