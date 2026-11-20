"""Upstream Resampy 0.4.3 parity for production ``kaiser_fast`` coefficients.

The upstream package is imported only by this test. Its bundled coefficient
table is written to a temporary resource at runtime; it is never copied into
the repository. The test is skipped when the pinned upstream runtime is absent.
"""

from __future__ import annotations

import hashlib
import json
import math

import pytest
from resampy_compat_support import ok, resample_body

np = pytest.importorskip("numpy")
resampy = pytest.importorskip("resampy")

if resampy.__version__ != "0.4.3":
    pytest.skip(
        f"upstream parity is pinned to resampy 0.4.3, found {resampy.__version__}",
        allow_module_level=True,
    )

FILTER_ID = "kaiser_fast_upstream_0_4_3"


@pytest.fixture(scope="module")
def upstream_filter(tmp_path_factory: pytest.TempPathFactory) -> tuple[bytes, bytes]:
    win, precision, rolloff = resampy.filters.get_filter("kaiser_fast")
    win = np.asarray(win, dtype="<f8")
    raw = win.tobytes(order="C")
    meta = json.dumps(
        {
            "schema_version": 1,
            "filter_id": FILTER_ID,
            "coefficient_count": int(win.size),
            "precision": int(precision),
            "rolloff": float(rolloff),
            "dtype": "float64",
            "byte_order": "little",
            "resource_bytes": len(raw),
            "resource_sha256": hashlib.sha256(raw).hexdigest(),
        },
        sort_keys=True,
    ).encode("utf-8")
    path = tmp_path_factory.mktemp("upstream_filter")
    (path / "kaiser_fast.json").write_bytes(meta)
    (path / "kaiser_fast.bin").write_bytes(raw)
    return meta, raw


def _sine(freq: float, sr: int, n: int = 1000) -> np.ndarray:
    return np.sin(2.0 * math.pi * freq * np.arange(n) / sr)


def _cases() -> list[tuple[str, np.ndarray, int, int]]:
    rng = np.random.default_rng(20261120)
    t = np.arange(1000)
    return [
        ("sine_up_44100_48000", _sine(440.0, 44100), 44100, 48000),
        ("sine_down_48000_44100", _sine(440.0, 48000), 48000, 44100),
        ("sine_down_48000_24000", _sine(440.0, 48000), 48000, 24000),
        ("sine_up_8000_16000", _sine(440.0, 8000), 8000, 16000),
        (
            "chirp_16000_22050",
            np.sin(2 * math.pi * (100 + 5 * t) * t / 16000),
            16000,
            22050,
        ),
        ("impulse_mid", np.eye(1, 512, 256, dtype=np.float64).ravel(), 8000, 16000),
        ("impulse_start", np.eye(1, 512, 0, dtype=np.float64).ravel(), 8000, 16000),
        ("impulse_end", np.eye(1, 512, 511, dtype=np.float64).ravel(), 8000, 16000),
        ("constant", np.full(512, 2.0), 48000, 44100),
        ("random", rng.uniform(-1.0, 1.0, 1000), 44100, 48000),
        ("short", np.linspace(-1.0, 1.0, 17), 44100, 48000),
        ("two", np.array([1.0, -2.0]), 8000, 16000),
        ("down4", _sine(300.0, 48000, 512), 48000, 12000),
        ("noni_44100_32000", _sine(440.0, 44100, 997), 44100, 32000),
        (
            "mixed_32000_44100",
            0.6 * _sine(440.0, 32000) + 0.3 * _sine(1234.0, 32000),
            32000,
            44100,
        ),
    ]


def _assert_bit_identical(got: np.ndarray, want: np.ndarray, label: str) -> None:
    assert got.shape == want.shape, f"{label}: shape {got.shape} != {want.shape}"
    np.testing.assert_array_equal(
        got.view(np.uint64), want.view(np.uint64), err_msg=f"{label}: bit mismatch"
    )


@pytest.mark.parametrize(
    ("label", "signal", "sr_orig", "sr_new"),
    _cases(),
    ids=[case[0] for case in _cases()],
)
def test_kaiser_fast_matches_upstream(
    resampy_cli,
    upstream_filter: tuple[bytes, bytes],
    label: str,
    signal: np.ndarray,
    sr_orig: int,
    sr_new: int,
) -> None:
    meta, raw = upstream_filter
    signal = np.ascontiguousarray(signal, dtype=np.float64)
    want = resampy.resample(signal, sr_orig, sr_new, filter="kaiser_fast")
    got = np.frombuffer(
        ok(resampy_cli, resample_body(signal.tolist(), sr_orig, sr_new, meta, raw, FILTER_ID)),
        dtype="<f8",
    )
    _assert_bit_identical(got, want, label)


@pytest.mark.parametrize(
    ("signal", "sr_orig", "sr_new"),
    [
        ([0.0, math.inf], 1, 2),
        ([math.nan, 0.0], 1, 2),
        ([math.inf, -math.inf], 1, 2),
        ([5e-324, -5e-324], 44100, 48000),
    ],
    ids=["inf_end", "nan_start", "mixed_inf", "subnormal"],
)
def test_nonfinite_and_subnormal_match_upstream(
    resampy_cli,
    upstream_filter: tuple[bytes, bytes],
    signal: list[float],
    sr_orig: int,
    sr_new: int,
) -> None:
    meta, raw = upstream_filter
    x = np.ascontiguousarray(signal, dtype=np.float64)
    want = resampy.resample(x, sr_orig, sr_new, filter="kaiser_fast")
    got = np.frombuffer(
        ok(resampy_cli, resample_body(signal, sr_orig, sr_new, meta, raw, FILTER_ID)),
        dtype="<f8",
    )
    assert got.shape == want.shape
    for i, value in enumerate(want):
        if np.isnan(value):
            assert np.isnan(got[i]), f"expected NaN at {i}, got {got[i]!r}"
        else:
            assert got[i].view(np.uint64) == value.view(np.uint64), (
                f"bit mismatch at {i}: {got[i]!r} != {value!r}"
            )
