"""Golden-vector tests for the Phase 6 ratecv cases."""

from __future__ import annotations

from pathlib import Path

import pytest
from support import parse_ratecv_response, ratecv_body, run_frames


def vector_state(args: dict):
    state = args.get("state")
    if state is None:
        return None
    return (
        int(state["d"]),
        tuple(tuple(int(value) for value in pair) for pair in state["channels"]),
    )


@pytest.fixture(scope="module")
def ratecv_cases(vectors_bundle: dict) -> list[dict]:
    return [case for case in vectors_bundle["cases"] if case["op"] == "ratecv"]


def test_phase6_case_counts(vectors_bundle: dict) -> None:
    cases = vectors_bundle["cases"]
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    assert len(cases) == 307
    sample = [case for case in cases if case["op"].startswith("sample_")]
    phase2 = [case for case in cases if case["id"].startswith("p2-")]
    phase3 = [case for case in cases if case["id"].startswith("p3-")]
    phase4 = [case for case in cases if case["id"].startswith("p4-")]
    phase5 = [case for case in cases if case["id"].startswith("p5-")]
    phase6 = [case for case in cases if case["id"].startswith("p6-")]
    remainder = (
        len(cases)
        - len(sample)
        - len(phase2)
        - len(phase3)
        - len(phase4)
        - len(phase5)
        - len(phase6)
    )
    assert len(sample) == 24
    assert len(phase2) == 50
    assert len(phase3) == 69
    assert len(phase4) == 58
    assert len(phase5) == 33
    assert len(phase6) == 31
    # the original 42 Phase 0 operation cases are untouched
    assert remainder == 42


def test_ratecv_vector_replay(audioop_cli: Path, ratecv_cases: list[dict]) -> None:
    cases = [case for case in ratecv_cases if case["id"].startswith("p6-")]
    bodies = []
    nchannels = []
    for case in cases:
        args = case["args"]
        bodies.append(
            ratecv_body(
                int(args["width"]),
                int(args["nchannels"]),
                int(args["inrate"]),
                int(args["outrate"]),
                int(args["weightA"]),
                int(args["weightB"]),
                vector_state(args),
                bytes.fromhex(args["fragment_hex"]),
            )
        )
        nchannels.append(int(args["nchannels"]))
    frames = run_frames(audioop_cli, bodies)
    assert len(frames) == len(cases)
    for case, chan, (status, payload) in zip(cases, nchannels, frames, strict=True):
        expected = case["expected"]
        if "error_message" in expected:
            assert status == 1, case["id"]
            assert payload.decode() == expected["error_message"], case["id"]
        else:
            assert status == 0, case["id"]
            output, state = parse_ratecv_response(payload, chan)
            assert output.hex() == expected["result_hex"], case["id"]
            assert state[0] == expected["state"][0], case["id"]
            assert [list(pair) for pair in state[1]] == expected["state"][1], case["id"]


def test_ratecv_vector_coverage(ratecv_cases: list[dict]) -> None:
    phase6 = [case for case in ratecv_cases if case["id"].startswith("p6-")]
    widths = {case["width"] for case in phase6 if "error_message" not in case["expected"]}
    assert {1, 2, 3, 4} <= widths
    channels = {
        case["args"]["nchannels"] for case in phase6 if "error_message" not in case["expected"]
    }
    assert {1, 2, 4} <= channels
    # upsample and downsample, equal rates, non-integer ratio, weights
    assert any("upsample" in case["id"] for case in phase6)
    assert any("downsample" in case["id"] for case in phase6)
    assert any("equal-rates" in case["id"] for case in phase6)
    assert any("non-integer-ratio" in case["id"] for case in phase6)
    assert any("weights" in case["id"] for case in phase6)
    # continued state
    assert any("continued" in case["id"] for case in phase6)
    # error cases cover every validation step
    errors = [
        case["expected"]["error_message"] for case in phase6 if "error_message" in case["expected"]
    ]
    assert "Size should be 1, 2, 3 or 4" in errors
    assert "# of channels should be >= 1" in errors
    assert "weightA should be >= 1, weightB should be >= 0" in errors
    assert "not a whole number of frames" in errors
    assert "sampling rate not > 0" in errors
    assert "Python int too large to convert to C int" in errors
    assert "width * nchannels too big for a C int" in errors
