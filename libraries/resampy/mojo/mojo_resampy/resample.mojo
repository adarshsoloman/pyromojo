"""Phase 4: 1-D Float64 band-limited windowed-sinc resampling kernel.

This is the first functional numerical operation of the Resampy port. It
reproduces the upstream ``resampy`` 0.4.3 ``core.py:resample`` +
``interpn.py:_resample_loop`` algorithm for one-dimensional Float64 signals,
with the exact upstream mathematics and indexing semantics (see
``docs/reference-audit.md`` §3.3/§3.4):

* ``n_out = int(L * float(sr_new) / float(sr_orig))`` (truncation toward zero);
* ``ratio = float(sr_new) / sr_orig``; ``scale = min(1, ratio)``;
* downsampling multiplies every filter coefficient by ``ratio`` (gain
  compensation + cutoff adaptation);
* ``time_increment = 1 / ratio``; output sample ``t`` maps to input time
  ``tau = t * time_increment``;
* ``index_step = int(scale * P)`` where ``P`` is the filter precision (samples
  per zero-crossing, the stored ``precision`` field);
* two wings around ``n = int(tau)`` using first-order interpolation of the
  half-filter table (``win[q] + eta * delta[q]``, ``delta`` the forward
  difference table);
* zero-extension boundaries implemented by clipping the summation ranges.

Only sequential Float64 accumulation is performed. All arithmetic is
``--fp-mode contract=off`` (no FMA contraction), matching the Phase 2 build
requirement; the Python reference performs the same operations in the same
order, so agreement is expected at the bit level for identical inputs.

Scope limits (Phase 4): no ``resample_nu``, no filter generation, no
``kaiser_best``, no float32/complex, no N-D, no ``axis``, no parallelism.
Coefficients are supplied through the existing validated ``FilterCoefficients``
resource; the committed tests use the synthetic resource only.
"""

from std.collections import List
from std.math import isnan, isinf

from mojo_resampy.coefficients import FilterCoefficients
from mojo_resampy.output import OutputBuffer, MAX_OUTPUT_ELEMENTS
from mojo_resampy.signal import Signal


# Upper bound on the filter ``precision`` field (samples per zero-crossing).
# Bounds ``scale * precision`` before the Float64 -> Int conversion so the
# ``index_step`` computation cannot overflow. The bundled/Loaded resources are
# validated to ``precision > 0``; the synthetic resource uses 8.
comptime MAX_FILTER_PRECISION: Int = 1_000_000


def _validate_rate(value: Int, name: String) raises:
    if value <= 0:
        raise Error(name + " must be a positive integer, got " + String(value))


def _coefficient_at(values: List[Float64], index: Int, label: String) raises -> Float64:
    """Bounds-checked table read (never reads outside the coefficient table)."""
    if index < 0 or index >= len(values):
        raise Error(
            label + " index " + String(index) + " out of range for length "
            + String(len(values))
        )
    return values[index]


def output_length(input_length: Int, sr_orig: Int, sr_new: Int) raises -> Int:
    """Upstream output-length rule: ``int(L * float(sr_new) / float(sr_orig))``.

    Truncates toward zero (never rounds or ceilings). Both rates must be
    positive integers. The result is validated against the output limit before
    any allocation; a result of zero is allowed and yields an empty output.
    """
    _validate_rate(sr_orig, "sr_orig")
    _validate_rate(sr_new, "sr_new")
    if input_length < 0:
        raise Error("input length must be non-negative, got " + String(input_length))
    var value = Float64(input_length) * Float64(sr_new) / Float64(sr_orig)
    if isnan(value) or isinf(value):
        raise Error("computed output length is not finite")
    if value < 0.0:
        raise Error("computed output length is negative")
    # Compare against MAX+1 so that (MAX, MAX+1) truncates into the valid range
    # while avoiding an out-of-range Float64 -> Int conversion for huge values.
    if value >= Float64(MAX_OUTPUT_ELEMENTS + 1):
        raise Error(
            "output length " + String(value) + " exceeds limit "
            + String(MAX_OUTPUT_ELEMENTS)
        )
    return Int(value)


def resample(
    signal: Signal,
    sr_orig: Int,
    sr_new: Int,
    filter: FilterCoefficients,
) raises -> OutputBuffer:
    """Resample a 1-D Float64 signal from ``sr_orig`` to ``sr_new``.

    Equal rates return an exact copy of the input (no interpolation), matching
    upstream's early return. A computed output length of zero returns an empty
    buffer.

    Note on upstream parity: upstream ``resample`` raises ``ValueError`` when
    the computed output length is ``< 1`` (including empty input). Phase 4
    scope explicitly lists empty/single-sample input and the zero-length
    truncation case as supported, so this kernel returns an empty
    ``OutputBuffer`` instead of raising. Rate validation (``sr <= 0``) still
    matches upstream.
    """
    _validate_rate(sr_orig, "sr_orig")
    _validate_rate(sr_new, "sr_new")

    var input_length = len(signal)

    if sr_orig == sr_new:
        var out = OutputBuffer(input_length)
        for i in range(input_length):
            out.set(i, signal[i])
        return out^

    var n_out = output_length(input_length, sr_orig, sr_new)
    if n_out == 0:
        return OutputBuffer(0)

    var sample_ratio = Float64(sr_new) / Float64(sr_orig)
    if isnan(sample_ratio) or isinf(sample_ratio) or sample_ratio <= 0.0:
        raise Error("invalid sampling-rate ratio")

    var precision = filter.metadata.precision
    if precision <= 0 or precision > MAX_FILTER_PRECISION:
        raise Error(
            "filter precision " + String(precision) + " is outside [1, "
            + String(MAX_FILTER_PRECISION) + "]"
        )
    var nwin = filter.count()
    if nwin < 1:
        raise Error("filter must have at least one coefficient")
    if precision > nwin:
        raise Error(
            "filter precision " + String(precision)
            + " exceeds coefficient count " + String(nwin)
        )
    for i in range(nwin):
        var c = filter[i]
        if isnan(c) or isinf(c):
            raise Error("filter coefficient " + String(i) + " is not finite")

    var scale: Float64 = sample_ratio if sample_ratio < 1.0 else 1.0
    var index_step = Int(scale * Float64(precision))
    if index_step < 1:
        raise Error(
            "sampling-rate ratio " + String(sample_ratio)
            + " is too small for filter precision " + String(precision)
            + ": int(scale * precision) < 1"
        )

    # Build the effective half-window and its forward-difference table. The
    # downsampling gain/cutoff adjustment multiplies the table by the ratio
    # (upstream: ``interp_win = sample_ratio * interp_win`` only when
    # ``sample_ratio < 1``).
    var downscale = sample_ratio < 1.0
    var win = List[Float64](capacity=nwin)
    for i in range(nwin):
        var c = filter[i]
        if downscale:
            c = c * sample_ratio
        win.append(c)
    var delta = List[Float64](capacity=nwin)
    for j in range(nwin):
        if j + 1 < nwin:
            delta.append(win[j + 1] - win[j])
        else:
            delta.append(0.0)

    var time_increment = 1.0 / sample_ratio
    var p = Float64(precision)
    var out = OutputBuffer(n_out)

    for t in range(n_out):
        var tau = Float64(t) * time_increment
        var n = Int(tau)
        # ponytail: defensive FP guard; tau >= 0 and < L mathematically, but a
        # rounding edge at extreme ratios could otherwise read out of bounds.
        if n < 0:
            n = 0
        if n >= input_length:
            n = input_length - 1

        var f = scale * (tau - Float64(n))
        var o = Int(f * p)
        var eta = f * p - Float64(o)

        var left_max = n + 1
        var table_limit = (nwin - o) // index_step
        if table_limit < left_max:
            left_max = table_limit
        if left_max < 0:
            left_max = 0
        var acc: Float64 = 0.0
        for i in range(left_max):
            var q = o + i * index_step
            var weight = _coefficient_at(win, q, "coefficient") + eta * _coefficient_at(delta, q, "delta")
            acc += weight * signal[n - i]

        f = scale - f
        o = Int(f * p)
        eta = f * p - Float64(o)

        var right_max = input_length - n - 1
        table_limit = (nwin - o) // index_step
        if table_limit < right_max:
            right_max = table_limit
        if right_max < 0:
            right_max = 0
        for k in range(right_max):
            var q = o + k * index_step
            var weight = _coefficient_at(win, q, "coefficient") + eta * _coefficient_at(delta, q, "delta")
            acc += weight * signal[n + k + 1]

        out.set(t, acc)

    return out^
