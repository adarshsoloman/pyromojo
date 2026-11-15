"""Golden-vector tests for the Phase 4 peak-analysis cases."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
from support import (
    avgpp_body,
    findfactor_body,
    findfit_body,
    findmax_body,
    maxpp_body,
    parse_double_bits,
    parse_fit,
    run_frames,
)

PEAK_OPS = {"avgpp", "maxpp", "findmax", "findfactor", "findfit"}


def vector_body(case: dict) -> bytes:
    args = case["args"]
    if case["op"] in ("avgpp", "maxpp"):
        return (avgpp_body if case["op"] == "avgpp" else maxpp_body)(
            case["width"], bytes.fromhex(args["fragment_hex"])
        )
    if case["op"] == "findmax":
        return findmax_body(int(args["length"]), bytes.fromhex(args["fragment_hex"]))
    if case["op"] == "findfactor":
        return findfactor_body(
            bytes.fromhex(args["fragment_hex"]), bytes.fromhex(args["reference_hex"])
        )
    if case["op"] == "findfit":
        return findfit_body(
            bytes.fromhex(args["fragment_hex"]), bytes.fromhex(args["reference_hex"])
        )
    raise AssertionError(f"unsupported op {case['op']}")


@pytest.fixture(scope="module")
def peak_cases(vectors_bundle: dict) -> list[dict]:
    if vectors_bundle["host"]["byte_order"] != sys.byteorder:
        pytest.skip(
            "golden bytes are native-order and were generated on "
            f"{vectors_bundle['host']['byte_order']}-endian"
        )
    return [case for case in vectors_bundle["cases"] if case["op"] in PEAK_OPS]


def test_phase4_case_counts(vectors_bundle: dict) -> None:
    cases = vectors_bundle["cases"]
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    assert len(cases) == 243
    sample = [case for case in cases if case["op"].startswith("sample_")]
    phase2 = [case for case in cases if case["id"].startswith("p2-")]
    phase3 = [case for case in cases if case["id"].startswith("p3-")]
    phase4 = [case for case in cases if case["id"].startswith("p4-")]
    remainder = len(cases) - len(sample) - len(phase2) - len(phase3) - len(phase4)
    assert len(sample) == 24
    assert len(phase2) == 50
    assert len(phase3) == 69
    assert len(phase4) == 58
    # the original 42 Phase 0 operation cases are untouched
    assert remainder == 42


def test_peak_vector_replay(audioop_cli: Path, peak_cases: list[dict]) -> None:
    cases = [case for case in peak_cases if case["id"].startswith("p4-")]
    frames = run_frames(audioop_cli, [vector_body(case) for case in cases])
    assert len(frames) == len(cases)
    for case, (status, payload) in zip(cases, frames, strict=True):
        expected = case["expected"]
        if "error_message" in expected:
            assert status == 1, case["id"]
            assert payload.decode() == expected["error_message"], case["id"]
        elif case["op"] == "findfactor":
            assert status == 0, case["id"]
            value = parse_double_bits(payload)
            if math.isnan(float(expected["value"])):
                assert math.isnan(value), case["id"]
            else:
                assert value == float(expected["value"]), case["id"]
        elif case["op"] == "findfit":
            assert status == 0, case["id"]
            index, factor = parse_fit(payload)
            assert index == expected["value"][0], case["id"]
            if math.isnan(float(expected["value"][1])):
                assert math.isnan(factor), case["id"]
            else:
                assert factor == float(expected["value"][1]), case["id"]
        else:
            assert status == 0, case["id"]
            assert int(payload.decode()) == expected["value"], case["id"]


def test_peak_vector_coverage(peak_cases: list[dict]) -> None:
    phase4 = [case for case in peak_cases if case["id"].startswith("p4-")]
    ops = {case["op"] for case in phase4}
    assert ops == PEAK_OPS
    # all four widths for the width-based operations
    for op in ("avgpp", "maxpp"):
        widths = {case["width"] for case in phase4 if case["op"] == op}
        assert {1, 2, 3, 4} <= widths
    # errors for every operation
    errors = {case["op"] for case in phase4 if "error_message" in case["expected"]}
    assert errors == PEAK_OPS
    # unsigned wrap quirk, nan results, tie cases, plateau cases
    assert any(
        case["id"].endswith("unsigned-wrap") and case["expected"]["value"] == 4294967295
        for case in phase4
    )
    assert any(case["op"] == "findfactor" and case["expected"]["value"] == "nan" for case in phase4)
    assert any("tie" in case["id"] for case in phase4)
    assert any("plateau" in case["id"] for case in phase4)
    assert any("zero-window" in case["id"] for case in phase4)
    # window boundary cases
    lengths = [case["args"]["length"] for case in phase4 if case["op"] == "findmax"]
    assert 0 in lengths
    assert any("length-equals-count" in case["id"] or "too-long" in case["id"] for case in phase4)
