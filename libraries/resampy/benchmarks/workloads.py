"""Deterministic Resampy benchmark workload matrix.

Duration/rate/length axes follow ``docs/benchmark-design.md``. The full cross
product is used: 8 lengths x 5 signal types x 7 rate pairs, minus the single
``length=2, 44100:16000`` cell whose upstream output length is zero (upstream
raises for that case and the native API returns an empty buffer).
"""

from __future__ import annotations

import math

import numpy as np

SEED = 20260610
LENGTHS = [2, 16, 64, 256, 1024, 4096, 16384, 65536]
SIGNAL_TYPES = ["silence", "impulse", "sine", "sweep", "noise"]
RATE_PAIRS = [
    (1, 1),
    (1, 2),
    (2, 1),
    (44100, 16000),
    (16000, 44100),
    (48000, 44100),
    (12499, 15001),
]


def signal_values(length: int, kind: str, seed: int = SEED) -> np.ndarray:
    """Return a deterministic contiguous Float64 signal of ``length`` values."""
    if length < 1:
        raise ValueError(f"length must be positive, got {length}")
    if kind == "silence":
        return np.zeros(length, dtype=np.float64)
    if kind == "impulse":
        out = np.zeros(length, dtype=np.float64)
        out[length // 2] = 1.0
        return out
    t = np.arange(length, dtype=np.float64)
    if kind == "sine":
        return np.sin(2.0 * math.pi * 7.0 * t / float(length))
    if kind == "sweep":
        phase = 2.0 * math.pi * (2.0 * t / float(length) + 5.0 * (t * t) / float(length * length))
        return np.sin(phase)
    if kind == "noise":
        return np.random.default_rng(seed).uniform(-1.0, 1.0, length)
    raise ValueError(f"unknown signal type {kind!r}")


def output_length(length: int, sr_orig: int, sr_new: int) -> int:
    return int(length * float(sr_new) / float(sr_orig))


def is_excluded(length: int, sr_orig: int, sr_new: int) -> bool:
    return output_length(length, sr_orig, sr_new) < 1


def cases(seed: int = SEED) -> list[dict]:
    """Return the benchmark matrix with deterministic signal data."""
    out: list[dict] = []
    for length in LENGTHS:
        for kind in SIGNAL_TYPES:
            for sr_orig, sr_new in RATE_PAIRS:
                if is_excluded(length, sr_orig, sr_new):
                    continue
                out.append(
                    {
                        "case_id": f"n{length:05d}-{kind}-{sr_orig}_{sr_new}",
                        "length": length,
                        "signal_type": kind,
                        "sr_orig": sr_orig,
                        "sr_new": sr_new,
                        "output_length": output_length(length, sr_orig, sr_new),
                        "signal": signal_values(length, kind, seed),
                    }
                )
    return out


def exclusions() -> list[dict]:
    return [
        {
            "length": length,
            "signal_type": kind,
            "sr_orig": sr_orig,
            "sr_new": sr_new,
            "reason": "output length 0; upstream resample requires >= 1 output sample",
        }
        for length in LENGTHS
        for kind in SIGNAL_TYPES
        for sr_orig, sr_new in RATE_PAIRS
        if is_excluded(length, sr_orig, sr_new)
    ]


def self_check() -> None:
    found = cases()
    excluded = exclusions()
    assert len(found) + len(excluded) == len(LENGTHS) * len(SIGNAL_TYPES) * len(RATE_PAIRS)
    assert len(excluded) == len(SIGNAL_TYPES)
    assert all(e["length"] == 2 and (e["sr_orig"], e["sr_new"]) == (44100, 16000) for e in excluded)
    assert len({c["case_id"] for c in found}) == len(found)
    for case in found:
        values = case["signal"]
        assert values.shape == (case["length"],)
        assert values.dtype == np.float64
        assert np.isfinite(values).all()
        assert case["output_length"] >= 1
    print(f"workloads: {len(found)} cells, {len(excluded)} documented exclusions")


if __name__ == "__main__":
    self_check()
