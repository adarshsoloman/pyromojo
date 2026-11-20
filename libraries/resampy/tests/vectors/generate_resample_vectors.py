#!/usr/bin/env python3
"""Generate Phase 4 resampling golden vectors (pure stdlib, independent ref).

Expected outputs are produced by ``tests/python_compat/resample_reference.py``,
a from-scratch transcription of the upstream algorithm. They are NOT copied
from native Mojo output. Coefficients come from the committed SYNTHETIC
resource only; no upstream Resampy coefficient data is used.

Run from the repository root::

    .venv/bin/python libraries/resampy/tests/vectors/generate_resample_vectors.py
    .venv/bin/python libraries/resampy/tests/vectors/generate_resample_vectors.py --check

The file is deterministic; ``--check`` verifies vector content has not drifted
and ignores the interpreter patch version recorded as provenance.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import platform
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RES = ROOT / "libraries" / "resampy" / "resources" / "synthetic"
VEC = ROOT / "libraries" / "resampy" / "tests" / "vectors"
REFERENCE_DIR = ROOT / "libraries" / "resampy" / "tests" / "python_compat"
sys.path.insert(0, str(REFERENCE_DIR))

import resample_reference  # noqa: E402


def f64le(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}d", *values)


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def lcg(count: int, seed: int = 12345) -> list[float]:
    """Deterministic pseudo-random signal in [-1, 1] (integer LCG)."""
    state = seed
    out: list[float] = []
    for _ in range(count):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        out.append((state / 0x7FFFFFFF) * 2.0 - 1.0)
    return out


def sine(count: int, freq: float, rate: int, amplitude: float = 0.9) -> list[float]:
    return [amplitude * math.sin(2.0 * math.pi * freq * i / rate) for i in range(count)]


def load_resource() -> tuple[str, int, list[float]]:
    meta = json.loads((RES / "synthetic_filter.json").read_text(encoding="utf-8"))
    raw = (RES / "synthetic_filter.bin").read_bytes()
    coeffs = list(struct.unpack(f"<{len(raw) // 8}d", raw))
    return meta["filter_id"], meta["precision"], coeffs


def make_case(
    case_id: str,
    description: str,
    signal: list[float],
    sr_orig: int,
    sr_new: int,
    filter_id: str,
    precision: int,
    coeffs: list[float],
) -> dict:
    expected = resample_reference.resample(signal, sr_orig, sr_new, coeffs, precision)
    input_bytes = f64le(signal)
    expected_bytes = f64le(expected)
    combined = input_bytes + expected_bytes
    return {
        "schema_version": 1,
        "case_id": case_id,
        "description": description,
        "reference_library": "pyromojo_resample_reference",
        "reference_version": "1",
        "reference_commit": "none",
        "python_version": platform.python_version(),
        "numpy_version": "none",
        "numba_version": "none",
        "input_dtype": "float64",
        "output_dtype": "float64",
        "byte_order": "little",
        "sr_orig": sr_orig,
        "sr_new": sr_new,
        "filter_id": filter_id,
        "input_count": len(signal),
        "expected_count": len(expected),
        "input_encoding": "base64",
        "expected_encoding": "base64",
        "input_data": b64(input_bytes),
        "expected_data": b64(expected_bytes),
        "payload_element_count": len(signal) + len(expected),
        "payload_sha256": hashlib.sha256(combined).hexdigest(),
        "atol": 0.0,
        "rtol": 0.0,
    }


def build_vectors() -> str:
    filter_id, precision, coeffs = load_resource()
    cases = [
        make_case(
            "identity_rate",
            "equal rates: exact copy, no interpolation",
            [0.5, -1.25, 2.0, -0.0, 3.5],
            48000,
            48000,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "upsample_2x",
            "integer 2x upsampling of a ramp",
            [0.0, 0.25, 0.5, 0.75, 1.0, 0.75, 0.5, 0.25],
            8000,
            16000,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "upsample_noni",
            "non-integer ratio 44100 -> 48000 sine",
            sine(97, 300.0, 44100),
            44100,
            48000,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "downsample_2x",
            "integer 2x downsampling of a sine",
            sine(128, 200.0, 48000),
            48000,
            24000,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "downsample_noni",
            "non-integer ratio 48000 -> 44100 sine",
            sine(200, 100.0, 48000),
            48000,
            44100,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "downsample_4x",
            "integer 4x downsampling of a constant",
            [1.0] * 50,
            48000,
            12000,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "impulse_mid",
            "unit impulse in the middle",
            [0.0] * 16 + [1.0] + [0.0] * 15,
            8000,
            16000,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "impulse_start",
            "unit impulse at the first sample",
            [1.0] + [0.0] * 31,
            8000,
            12000,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "impulse_end",
            "unit impulse at the last sample",
            [0.0] * 31 + [1.0],
            8000,
            12000,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "constant",
            "constant signal",
            [2.0] * 40,
            10,
            13,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "zero_signal",
            "all zeros",
            [0.0] * 32,
            44100,
            48000,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "sine_low",
            "low-frequency sine",
            sine(64, 440.0, 22050),
            22050,
            44100,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "lcg_noise",
            "deterministic pseudo-random signal",
            lcg(100),
            44100,
            48000,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "short_signal",
            "three-sample input downsampled",
            [1.0, -1.0, 0.5],
            4,
            3,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "single_sample_up",
            "single sample upsampled",
            [3.0],
            8000,
            16000,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "empty_input",
            "empty input yields empty output",
            [],
            44100,
            48000,
            filter_id,
            precision,
            coeffs,
        ),
        make_case(
            "alternating",
            "alternating +/- samples",
            [1.0 if i % 2 == 0 else -1.0 for i in range(40)],
            4000,
            6000,
            filter_id,
            precision,
            coeffs,
        ),
    ]
    bundle = {
        "generator": "generate_resample_vectors.py",
        "note": (
            "SYNTHETIC Phase 4 resampling vectors. Expected outputs come from "
            "tests/python_compat/resample_reference.py (independent, stdlib). "
            "NOT Resampy output; synthetic coefficients only."
        ),
        "cases": cases,
    }
    return json.dumps(bundle, indent=2, ensure_ascii=True) + "\n"


def _content_without_python_version(text: str) -> dict:
    """Return vector content without the environment-dependent provenance field."""
    bundle = json.loads(text)
    for case in bundle["cases"]:
        case.pop("python_version", None)
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    target = VEC / "resampling_vectors.json"
    text = build_vectors()

    if args.check:
        if not target.exists() or _content_without_python_version(
            target.read_text(encoding="utf-8")
        ) != _content_without_python_version(text):
            print("DRIFT:", target)
            return 1
        print("resampling golden vectors match the generator")
        return 0

    VEC.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print("wrote", target.relative_to(ROOT), len(text), "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
