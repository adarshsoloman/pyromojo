"""Independent, pure-stdlib reference for the Phase 4 resampling kernel.

This module is a from-scratch transcription of the upstream resampy 0.4.3
``core.py:resample`` + ``interpn.py:_resample_loop`` algorithm (see
``docs/reference-audit.md`` §3.3/§3.4). It deliberately does **not** import
NumPy, call the Mojo CLI, or reuse any Mojo-produced intermediate value: it
exists to independently validate the native kernel on synthetic coefficients.

Python's ``float`` is IEEE-754 binary64 and ``int()`` truncates toward zero, so
this reproduces the same Float64 operations in the same order as the Mojo
kernel (built with ``--fp-mode contract=off``).
"""

from __future__ import annotations


def output_length(input_length: int, sr_orig: int, sr_new: int) -> int:
    """Upstream output-length rule, truncating toward zero."""
    if sr_orig <= 0:
        raise ValueError(f"Invalid sample rate: sr_orig={sr_orig}")
    if sr_new <= 0:
        raise ValueError(f"Invalid sample rate: sr_new={sr_new}")
    if input_length < 0:
        raise ValueError("input_length must be non-negative")
    return int(input_length * float(sr_new) / float(sr_orig))


def _checked(values: list[float], index: int, label: str) -> float:
    if index < 0 or index >= len(values):
        raise IndexError(f"{label} index {index} out of range for length {len(values)}")
    return values[index]


def resample(
    signal: list[float],
    sr_orig: int,
    sr_new: int,
    coefficients: list[float],
    precision: int,
) -> list[float]:
    """Resample ``signal`` from ``sr_orig`` to ``sr_new`` using a half-filter.

    ``precision`` is the stored samples-per-zero-crossing value (the upstream
    ``num_table`` / ``P``). Returns an empty list when the truncating output
    length is zero. Equal rates return an exact copy (upstream early return).
    """
    if sr_orig <= 0:
        raise ValueError(f"Invalid sample rate: sr_orig={sr_orig}")
    if sr_new <= 0:
        raise ValueError(f"Invalid sample rate: sr_new={sr_new}")

    length = len(signal)
    if sr_orig == sr_new:
        return list(signal)

    n_out = output_length(length, sr_orig, sr_new)
    if n_out == 0:
        return []

    ratio = float(sr_new) / float(sr_orig)
    if ratio <= 0.0 or ratio != ratio or ratio in (float("inf"), float("-inf")):
        raise ValueError("invalid sampling-rate ratio")

    if precision <= 0:
        raise ValueError(f"filter precision {precision} must be positive")
    if not coefficients:
        raise ValueError("filter must have at least one coefficient")

    scale = ratio if ratio < 1.0 else 1.0
    index_step = int(scale * precision)
    if index_step < 1:
        raise ValueError(
            f"sampling-rate ratio {ratio} is too small for filter precision "
            f"{precision}: int(scale * precision) < 1"
        )

    downscale = ratio < 1.0
    win = [(c * ratio if downscale else c) for c in coefficients]
    nwin = len(win)
    delta = [win[j + 1] - win[j] for j in range(nwin - 1)] + [0.0]

    time_increment = 1.0 / ratio
    out = [0.0] * n_out

    for t in range(n_out):
        tau = float(t) * time_increment
        n = int(tau)
        if n < 0:
            n = 0
        if n >= length:
            n = length - 1

        f = scale * (tau - float(n))
        o = int(f * precision)
        eta = f * precision - float(o)

        left_max = min(n + 1, (nwin - o) // index_step)
        if left_max < 0:
            left_max = 0
        acc = 0.0
        for i in range(left_max):
            q = o + i * index_step
            weight = _checked(win, q, "coefficient") + eta * _checked(delta, q, "delta")
            acc += weight * signal[n - i]

        f = scale - f
        o = int(f * precision)
        eta = f * precision - float(o)

        right_max = min(length - n - 1, (nwin - o) // index_step)
        if right_max < 0:
            right_max = 0
        for k in range(right_max):
            q = o + k * index_step
            weight = _checked(win, q, "coefficient") + eta * _checked(delta, q, "delta")
            acc += weight * signal[n + k + 1]

        out[t] = acc

    return out
