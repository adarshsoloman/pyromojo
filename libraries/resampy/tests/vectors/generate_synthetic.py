#!/usr/bin/env python3
"""Generate the SYNTHETIC Phase 3 test resources (stdlib only).

This is a one-off generator for committed synthetic fixtures. It does NOT
touch any upstream filter coefficients and does NOT generate Resampy golden
vectors. Run from the repository root::

    .venv/bin/python libraries/resampy/tests/vectors/generate_synthetic.py

The generated files are deterministic and committed; the generator doubles as
a drift check via ``--check``.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RES = ROOT / "libraries" / "resampy" / "resources" / "synthetic"
VEC = ROOT / "libraries" / "resampy" / "tests" / "vectors"

# 8 synthetic Float64 coefficients. NOT Resampy coefficients.
COEFFS = [0.5, 0.25, -0.125, 0.0625, 1e-300, -0.0, 1.0, -1.0]
FILTER_ID = "synthetic_tiny_v1"
PRECISION = 8
ROLLOFF = 0.95


def f64le(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}d", *values)


def bits_le(values: list[float]) -> list[int]:
    return [struct.unpack("<Q", struct.pack("<d", v))[0] for v in values]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_resource() -> tuple[str, bytes]:
    raw = f64le(COEFFS)
    meta = {
        "schema_version": 1,
        "filter_id": FILTER_ID,
        "coefficient_count": len(COEFFS),
        "precision": PRECISION,
        "rolloff": ROLLOFF,
        "dtype": "float64",
        "byte_order": "little",
        "resource_bytes": len(raw),
        "resource_sha256": sha256_hex(raw),
    }
    return json.dumps(meta, indent=2, sort_keys=True) + "\n", raw


SPECIAL_INPUT = [
    0.0,
    -0.0,
    1.0,
    -1.0,
    0.5,
    -0.25,
    1e-300,
    -1e-300,
    1e300,
    -1e300,
    float("nan"),
    float("inf"),
    float("-inf"),
    5e-324,
    math.nextafter(1.0, 2.0),
]


def build_vectors() -> str:
    cases = []

    def add(case_id, description, inp, exp, sr_orig=100, sr_new=200, atol=0.0, rtol=0.0):
        ib, eb = f64le(inp), f64le(exp)
        combined = ib + eb
        cases.append(
            {
                "schema_version": 1,
                "case_id": case_id,
                "description": description,
                "reference_library": "synthetic",
                "reference_version": "1.0",
                "reference_commit": "none",
                "python_version": "3.12.3",
                "numpy_version": "1.26.4",
                "numba_version": "0.60.0",
                "input_dtype": "float64",
                "output_dtype": "float64",
                "byte_order": "little",
                "sr_orig": sr_orig,
                "sr_new": sr_new,
                "filter_id": FILTER_ID,
                "input_count": len(inp),
                "expected_count": len(exp),
                "input_encoding": "base64",
                "expected_encoding": "base64",
                "input_data": base64.b64encode(ib).decode("ascii"),
                "expected_data": base64.b64encode(eb).decode("ascii"),
                "payload_element_count": len(inp) + len(exp),
                "payload_sha256": sha256_hex(combined),
                "atol": atol,
                "rtol": rtol,
            }
        )

    add("empty_vector", "empty input and expected arrays", [], [])
    add("single_value", "one Float64 value", [1.5], [1.5])
    add(
        "positive_negative",
        "positive and negative finite values",
        [1.0, -1.0, 2.5, -3.75],
        [1.0, -1.0, 2.5, -3.75],
    )
    add(
        "zero_and_negzero",
        "positive zero and negative zero bits",
        [0.0, -0.0, 0.0],
        [0.0, -0.0, 0.0],
    )
    add(
        "subnormal",
        "smallest subnormal and near-zero values",
        [5e-324, 1e-320, -5e-324],
        [5e-324, 1e-320, -5e-324],
    )
    add(
        "large_finite",
        "large finite magnitudes",
        [1e300, -1e300, 1.7976931348623157e308],
        [1e300, -1e300, 1.7976931348623157e308],
    )
    add(
        "nonfinite",
        "NaN, positive and negative infinity bit preservation",
        [float("nan"), float("inf"), float("-inf")],
        [float("nan"), float("inf"), float("-inf")],
    )
    add("repeated", "repeated identical values", [0.125] * 8, [0.125] * 8)
    add(
        "special_mixed",
        "mixed finite, subnormal, signed zero and non-finite",
        SPECIAL_INPUT,
        SPECIAL_INPUT,
    )
    add(
        "different_lengths",
        "input and expected arrays of different lengths",
        [1.0, 2.0, 3.0],
        [1.0, 2.0],
    )
    add(
        "tolerances",
        "explicit caller-supplied tolerances (no hardcoded default)",
        [1.0, 2.0, 3.0],
        [1.0, 2.0, 3.0 + 1e-12],
        atol=1e-9,
        rtol=1e-9,
    )
    add(
        "noninteger_ratio",
        "non-integer sampling-rate ratio metadata",
        [0.25, 0.5, 0.75],
        [0.25, 0.5, 0.75],
        sr_orig=22050,
        sr_new=16000,
    )

    bundle = {
        "generator": "generate_synthetic.py",
        "note": "SYNTHETIC Phase 3 representation vectors. Not Resampy output.",
        "cases": cases,
    }
    return json.dumps(bundle, indent=2, ensure_ascii=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    meta_text, raw = build_resource()
    vectors_text = build_vectors()
    targets = {
        RES / "synthetic_filter.json": meta_text,
        RES / "synthetic_filter.bin": raw,
        VEC / "representation_vectors.json": vectors_text,
    }
    RES.mkdir(parents=True, exist_ok=True)
    VEC.mkdir(parents=True, exist_ok=True)

    if args.check:
        problems = []
        for path, expected in targets.items():
            actual = path.read_bytes()
            want = expected.encode("utf-8") if isinstance(expected, str) else expected
            if actual != want:
                problems.append(str(path))
        if problems:
            print("DRIFT:", ", ".join(problems))
            return 1
        print("all synthetic resources match the generator")
        return 0

    for path, content in targets.items():
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_bytes(content)
        print("wrote", path.relative_to(ROOT), len(content), "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
