"""Golden-vector tests for the Phase 3 statistics cases."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from support import (
    avg_body,
    cross_body,
    getsample_body,
    max_body,
    minmax_body,
    parse_pair,
    parse_scalar,
    rms_body,
    run_frames,
)

STATISTICS_OPS = {"getsample", "max", "minmax", "avg", "rms", "cross"}


def vector_body(case: dict) -> bytes:
    args = case["args"]
    width = case["width"]
    fragment = bytes.fromhex(args["fragment_hex"])
    if case["op"] == "getsample":
        return getsample_body(width, int(args["index"]), fragment)
    if case["op"] == "max":
        return max_body(width, fragment)
    if case["op"] == "minmax":
        return minmax_body(width, fragment)
    if case["op"] == "avg":
        return avg_body(width, fragment)
    if case["op"] == "rms":
        return rms_body(width, fragment)
    if case["op"] == "cross":
        return cross_body(width, fragment)
    raise AssertionError(f"unsupported op {case['op']}")


@pytest.fixture(scope="module")
def statistics_cases(vectors_bundle: dict) -> list[dict]:
    if vectors_bundle["host"]["byte_order"] != sys.byteorder:
        pytest.skip(
            "golden bytes are native-order and were generated on "
            f"{vectors_bundle['host']['byte_order']}-endian"
        )
    return [case for case in vectors_bundle["cases"] if case["op"] in STATISTICS_OPS]


def test_phase3_case_counts(vectors_bundle: dict) -> None:
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
    # the original 42 Phase 0 operation cases are untouched
    assert remainder == 42


def test_statistics_vector_replay(audioop_cli: Path, statistics_cases: list[dict]) -> None:
    cases = [case for case in statistics_cases if case["id"].startswith("p3-")]
    frames = run_frames(audioop_cli, [vector_body(case) for case in cases])
    assert len(frames) == len(cases)
    for case, (status, payload) in zip(cases, frames, strict=True):
        expected = case["expected"]
        if "error_message" in expected:
            assert status == 1, case["id"]
            assert payload.decode() == expected["error_message"], case["id"]
        elif case["op"] == "minmax":
            assert status == 0, case["id"]
            assert parse_pair(payload) == tuple(expected["value"]), case["id"]
        else:
            assert status == 0, case["id"]
            assert parse_scalar(payload) == expected["value"], case["id"]


def test_statistics_vector_coverage(statistics_cases: list[dict]) -> None:
    phase3 = [case for case in statistics_cases if case["id"].startswith("p3-")]
    ops = {case["op"] for case in phase3}
    assert ops == STATISTICS_OPS
    widths = {case["width"] for case in phase3}
    assert {1, 2, 3, 4} <= widths
    # every operation has both success and error cases (except max: empty
    # and misaligned errors exist; check them)
    errors = {case["op"] for case in phase3 if "error_message" in case["expected"]}
    assert errors == STATISTICS_OPS
    # zero-heavy cross, floor evidence for avg, unsigned results for max/rms
    assert any(case["op"] == "cross" and "zeros" in case["id"] for case in phase3)
    assert any(case["op"] == "avg" and "floor" in case["id"] for case in phase3)
    assert any(
        case["id"] == "p3-max-w4-int-min-only" and case["expected"]["value"] == 2147483648
        for case in phase3
    )
    assert any(
        case["id"] == "p3-rms-w4-all-int-min" and case["expected"]["value"] == 2147483648
        for case in phase3
    )
    # negative and out-of-range getsample indices
    indices = [case["args"]["index"] for case in phase3 if case["op"] == "getsample"]
    assert any(index < 0 for index in indices)
    assert any("error_message" in case["expected"] and case["op"] == "getsample" for case in phase3)
