"""Golden-vector tests for the Phase 8 ADPCM cases."""

from __future__ import annotations

from pathlib import Path

import pytest
from support import adpcm2lin_body, lin2adpcm_body, parse_adpcm_response, run_frames

ADPCM_OPS = {"lin2adpcm", "adpcm2lin"}


def vector_state(args: dict):
    state = args.get("state")
    if state is None:
        return None
    return int(state[0]), int(state[1])


@pytest.fixture(scope="module")
def adpcm_cases(vectors_bundle: dict) -> list[dict]:
    return [case for case in vectors_bundle["cases"] if case["op"] in ADPCM_OPS]


def test_phase8_case_counts(vectors_bundle: dict) -> None:
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


def test_adpcm_vector_replay(audioop_cli: Path, adpcm_cases: list[dict]) -> None:
    cases = [case for case in adpcm_cases if case["id"].startswith("p8-")]
    bodies = []
    for case in cases:
        args = case["args"]
        body = lin2adpcm_body if case["op"] == "lin2adpcm" else adpcm2lin_body
        bodies.append(
            body(
                int(args["width"]),
                vector_state(args),
                bytes.fromhex(args["fragment_hex"]),
            )
        )
    frames = run_frames(audioop_cli, bodies)
    assert len(frames) == len(cases)
    for case, (status, payload) in zip(cases, frames, strict=True):
        expected = case["expected"]
        if "error_message" in expected:
            assert status == 1, case["id"]
            assert payload.decode() == expected["error_message"], case["id"]
        else:
            assert status == 0, case["id"]
            output, state = parse_adpcm_response(payload)
            assert output.hex() == expected["result_hex"], case["id"]
            assert [state[0], state[1]] == expected["state"], case["id"]


def test_adpcm_vector_coverage(adpcm_cases: list[dict]) -> None:
    phase8 = [case for case in adpcm_cases if case["id"].startswith("p8-")]
    ops = {case["op"] for case in phase8}
    assert ops == ADPCM_OPS
    # exhaustive decoder: all 256 byte values at width 2
    bytes_seen = {
        bytes.fromhex(case["args"]["fragment_hex"])[0]
        for case in phase8
        if case["op"] == "adpcm2lin"
        and case["width"] == 2
        and case["id"].startswith("p8-adpcm2lin-byte-")
    }
    assert len(bytes_seen) == 256
    # all 16 nibbles
    nibbles = {case["id"][-1] for case in phase8 if case["id"].startswith("p8-adpcm2lin-nibble-")}
    assert len(nibbles) == 16
    # encoder widths
    widths = {
        case["width"]
        for case in phase8
        if case["op"] == "lin2adpcm" and "error_message" not in case["expected"]
    }
    assert {1, 2, 3, 4} <= widths
    # state coverage: initial, continued, empty, odd/even
    assert any("continued" in case["id"] for case in phase8)
    assert any("empty" in case["id"] for case in phase8)
    assert any("one-sample" in case["id"] for case in phase8)
    assert any("three-samples" in case["id"] for case in phase8)
    errors = {case["op"] for case in phase8 if "error_message" in case["expected"]}
    assert errors == ADPCM_OPS
