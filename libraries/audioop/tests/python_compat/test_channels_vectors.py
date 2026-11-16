"""Golden-vector tests for the Phase 5 channel cases."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from support import run_frames, tomono_body, tostereo_body

CHANNEL_OPS = {"tomono", "tostereo"}


def vector_body(case: dict) -> bytes:
    args = case["args"]
    lfactor = args["lfactor"]
    rfactor = args["rfactor"]
    if isinstance(lfactor, str):
        lfactor = float(lfactor)
    if isinstance(rfactor, str):
        rfactor = float(rfactor)
    body = tomono_body if case["op"] == "tomono" else tostereo_body
    return body(case["width"], float(lfactor), float(rfactor), bytes.fromhex(args["fragment_hex"]))


@pytest.fixture(scope="module")
def channel_cases(vectors_bundle: dict) -> list[dict]:
    if vectors_bundle["host"]["byte_order"] != sys.byteorder:
        pytest.skip(
            "golden bytes are native-order and were generated on "
            f"{vectors_bundle['host']['byte_order']}-endian"
        )
    return [case for case in vectors_bundle["cases"] if case["op"] in CHANNEL_OPS]


def test_phase5_case_counts(vectors_bundle: dict) -> None:
    cases = vectors_bundle["cases"]
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    assert len(cases) == 1277
    sample = [case for case in cases if case["op"].startswith("sample_")]
    phase2 = [case for case in cases if case["id"].startswith("p2-")]
    phase3 = [case for case in cases if case["id"].startswith("p3-")]
    phase4 = [case for case in cases if case["id"].startswith("p4-")]
    phase5 = [case for case in cases if case["id"].startswith("p5-")]
    phase6 = [case for case in cases if case["id"].startswith("p6-")]
    phase7 = [case for case in cases if case["id"].startswith("p7-")]
    phase8 = [case for case in cases if case["id"].startswith("p8-")]
    remainder = (
        len(cases)
        - len(sample)
        - len(phase2)
        - len(phase3)
        - len(phase4)
        - len(phase5)
        - len(phase6)
        - len(phase7)
        - len(phase8)
    )
    assert len(sample) == 24
    assert len(phase2) == 50
    assert len(phase3) == 69
    assert len(phase4) == 58
    assert len(phase5) == 33
    assert len(phase6) == 31
    assert len(phase7) == 645
    assert len(phase8) == 325
    # the original 42 Phase 0 operation cases are untouched
    assert remainder == 42


def test_channel_vector_replay(audioop_cli: Path, channel_cases: list[dict]) -> None:
    cases = [case for case in channel_cases if case["id"].startswith("p5-")]
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


def test_channel_vector_coverage(channel_cases: list[dict]) -> None:
    phase5 = [case for case in channel_cases if case["id"].startswith("p5-")]
    ops = {case["op"] for case in phase5}
    assert ops == CHANNEL_OPS
    widths = {case["width"] for case in phase5}
    assert {1, 2, 3, 4} <= widths
    errors = {case["op"] for case in phase5 if "error_message" in case["expected"]}
    assert errors == CHANNEL_OPS
    # factor coverage: zero, fractional, large, inf, nan, negatives
    factors: set[object] = set()
    for case in phase5:
        factors.add(case["args"]["lfactor"])
        factors.add(case["args"]["rfactor"])
    assert 0 in factors
    assert 0.5 in factors
    assert "inf" in factors
    assert "nan" in factors
    # empty fragments and boundary samples
    assert any(case["args"]["fragment_hex"] == "" for case in phase5)
    assert any("boundaries" in case["id"] for case in phase5)
