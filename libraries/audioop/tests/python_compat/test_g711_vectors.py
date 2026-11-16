"""Golden-vector tests for the Phase 7 G.711 cases."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from support import (
    alaw2lin_body,
    lin2alaw_body,
    lin2ulaw_body,
    run_frames,
    ulaw2lin_body,
)

G711_OPS = {"lin2alaw", "alaw2lin", "lin2ulaw", "ulaw2lin"}


def vector_body(case: dict) -> bytes:
    width = case["width"]
    fragment = bytes.fromhex(case["args"]["fragment_hex"])
    if case["op"] == "lin2alaw":
        return lin2alaw_body(width, fragment)
    if case["op"] == "alaw2lin":
        return alaw2lin_body(width, fragment)
    if case["op"] == "lin2ulaw":
        return lin2ulaw_body(width, fragment)
    if case["op"] == "ulaw2lin":
        return ulaw2lin_body(width, fragment)
    raise AssertionError(f"unsupported op {case['op']}")


@pytest.fixture(scope="module")
def g711_cases(vectors_bundle: dict) -> list[dict]:
    if vectors_bundle["host"]["byte_order"] != sys.byteorder:
        pytest.skip(
            "golden bytes are native-order and were generated on "
            f"{vectors_bundle['host']['byte_order']}-endian"
        )
    return [case for case in vectors_bundle["cases"] if case["op"] in G711_OPS]


def test_phase7_case_counts(vectors_bundle: dict) -> None:
    cases = vectors_bundle["cases"]
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    assert len(cases) == 952
    sample = [case for case in cases if case["op"].startswith("sample_")]
    phase2 = [case for case in cases if case["id"].startswith("p2-")]
    phase3 = [case for case in cases if case["id"].startswith("p3-")]
    phase4 = [case for case in cases if case["id"].startswith("p4-")]
    phase5 = [case for case in cases if case["id"].startswith("p5-")]
    phase6 = [case for case in cases if case["id"].startswith("p6-")]
    phase7 = [case for case in cases if case["id"].startswith("p7-")]
    remainder = (
        len(cases)
        - len(sample)
        - len(phase2)
        - len(phase3)
        - len(phase4)
        - len(phase5)
        - len(phase6)
        - len(phase7)
    )
    assert len(sample) == 24
    assert len(phase2) == 50
    assert len(phase3) == 69
    assert len(phase4) == 58
    assert len(phase5) == 33
    assert len(phase6) == 31
    assert len(phase7) == 645
    # the original 42 Phase 0 operation cases are untouched
    assert remainder == 42


def test_g711_vector_replay(audioop_cli: Path, g711_cases: list[dict]) -> None:
    cases = [case for case in g711_cases if case["id"].startswith("p7-")]
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


def test_g711_vector_coverage(g711_cases: list[dict]) -> None:
    phase7 = [case for case in g711_cases if case["id"].startswith("p7-")]
    ops = {case["op"] for case in phase7}
    assert ops == G711_OPS
    # exhaustive decoders: all 256 codewords at width 2, both codecs
    alaw_codes = {
        bytes.fromhex(case["args"]["fragment_hex"])[0]
        for case in phase7
        if case["op"] == "alaw2lin"
        and case["width"] == 2
        and case["id"].startswith("p7-alaw2lin-code-")
    }
    ulaw_codes = {
        bytes.fromhex(case["args"]["fragment_hex"])[0]
        for case in phase7
        if case["op"] == "ulaw2lin"
        and case["width"] == 2
        and case["id"].startswith("p7-ulaw2lin-code-")
    }
    assert len(alaw_codes) == 256
    assert len(ulaw_codes) == 256
    # encoder widths and errors
    for op in ("lin2alaw", "lin2ulaw"):
        widths = {
            case["width"]
            for case in phase7
            if case["op"] == op and "error_message" not in case["expected"]
        }
        assert {1, 2, 3, 4} <= widths
    errors = {case["op"] for case in phase7 if "error_message" in case["expected"]}
    assert errors == {"lin2alaw", "lin2ulaw", "alaw2lin", "ulaw2lin"}
