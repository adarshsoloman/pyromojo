"""Golden-vector tests for the Phase 2 arithmetic cases (and prior ops)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from support import (
    add_body,
    bias_body,
    byteswap_body,
    lin2lin_body,
    mul_body,
    reverse_body,
    run_frames,
)

ARITHMETIC_OPS = {"add", "bias", "mul", "reverse", "byteswap", "lin2lin"}


def vector_body(case: dict) -> bytes:
    args = case["args"]
    width = case["width"]
    if case["op"] == "add":
        return add_body(
            width, bytes.fromhex(args["fragment1_hex"]), bytes.fromhex(args["fragment2_hex"])
        )
    if case["op"] == "bias":
        return bias_body(width, int(args["bias"]), bytes.fromhex(args["fragment_hex"]))
    if case["op"] == "mul":
        factor = args["factor"]
        if isinstance(factor, str):
            factor = float(factor)
        return mul_body(width, float(factor), bytes.fromhex(args["fragment_hex"]))
    if case["op"] == "reverse":
        return reverse_body(width, bytes.fromhex(args["fragment_hex"]))
    if case["op"] == "byteswap":
        return byteswap_body(width, bytes.fromhex(args["fragment_hex"]))
    if case["op"] == "lin2lin":
        return lin2lin_body(width, int(args["new_width"]), bytes.fromhex(args["fragment_hex"]))
    raise AssertionError(f"unsupported op {case['op']}")


@pytest.fixture(scope="module")
def arithmetic_cases(vectors_bundle: dict) -> list[dict]:
    if vectors_bundle["host"]["byte_order"] != sys.byteorder:
        pytest.skip(
            "golden bytes are native-order and were generated on "
            f"{vectors_bundle['host']['byte_order']}-endian"
        )
    return [case for case in vectors_bundle["cases"] if case["op"] in ARITHMETIC_OPS]


def test_phase2_case_counts(vectors_bundle: dict) -> None:
    cases = vectors_bundle["cases"]
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    assert len(cases) == 185
    sample = [case for case in cases if case["op"].startswith("sample_")]
    phase2 = [case for case in cases if case["id"].startswith("p2-")]
    phase3 = [case for case in cases if case["id"].startswith("p3-")]
    remainder = len(cases) - len(sample) - len(phase2) - len(phase3)
    assert len(sample) == 24
    assert len(phase2) == 50
    assert len(phase3) == 69
    assert remainder == 42


def test_arithmetic_vector_replay(audioop_cli: Path, arithmetic_cases: list[dict]) -> None:
    # mul-w2-nan is the frozen undefined-behaviour record: the reference's
    # (int)NaN is UB and the port defines NaN results as zero (documented),
    # so this vector is excluded from equality assertions.
    # add-ragged records a Phase 0 call on 3-byte fragments but stores the
    # args as 2-byte hex; the recorded expectation is correct for the
    # documented call, so the (inconsistent) args are not replayed.
    skip = {"mul-w2-nan", "add-ragged"}
    cases = [case for case in arithmetic_cases if case["id"] not in skip]
    frames = run_frames(audioop_cli, [vector_body(case) for case in cases])
    assert len(frames) == len(cases)
    for case, (status, payload) in zip(cases, frames, strict=True):
        expected = case["expected"]
        if "error_message" in expected:
            assert status == 1, case["id"]
            assert payload.decode() == expected["error_message"], case["id"]
        else:
            assert status == 0, case["id"]
            assert payload.hex() == expected["result_hex"], case["id"]


def test_arithmetic_vector_coverage(arithmetic_cases: list[dict]) -> None:
    phase2 = [case for case in arithmetic_cases if case["id"].startswith("p2-")]
    ops = {case["op"] for case in phase2}
    assert ops == ARITHMETIC_OPS
    # every lin2lin width pair appears
    lin2lin_pairs = {
        (case["width"], case["args"]["new_width"])
        for case in arithmetic_cases
        if case["op"] == "lin2lin" and "error_message" not in case["expected"]
    }
    assert lin2lin_pairs == {(w, n) for w in range(1, 5) for n in range(1, 5)}
    # error vectors exist for add (length mismatch) and bias (C int range);
    # the remaining error paths are covered by native and differential tests
    errors = {case["op"] for case in phase2 if "error_message" in case["expected"]}
    assert errors == {"add", "bias"}
    # mul covers inf and fractions
    factors = {case["args"]["factor"] for case in phase2 if case["op"] == "mul"}
    assert "-inf" in factors
    assert any(isinstance(factor, float) and factor not in (0.0, 1.0) for factor in factors)
