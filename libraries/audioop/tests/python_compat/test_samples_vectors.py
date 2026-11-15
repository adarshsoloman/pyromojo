"""Golden-vector tests for the Phase 1 sample representation cases."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from support import (
    STATUS_ERROR,
    STATUS_OK,
    decode_body,
    decode_values,
    encode_body,
    run_frames,
)

SAMPLE_OPS = {"sample_decode", "sample_encode"}


@pytest.fixture(scope="module")
def sample_cases(vectors_bundle: dict) -> list[dict]:
    if vectors_bundle["host"]["byte_order"] != sys.byteorder:
        pytest.skip(
            "golden bytes are native-order and were generated on "
            f"{vectors_bundle['host']['byte_order']}-endian"
        )
    return [case for case in vectors_bundle["cases"] if case["op"] in SAMPLE_OPS]


def test_corpus_preserves_phase0_cases(vectors_bundle: dict) -> None:
    cases = vectors_bundle["cases"]
    assert len(cases) == 276
    ids = [case["id"] for case in cases]
    assert len(set(ids)) == len(ids)
    sample = [case for case in cases if case["op"] in SAMPLE_OPS]
    phase2 = [case for case in cases if case["id"].startswith("p2-")]
    phase3 = [case for case in cases if case["id"].startswith("p3-")]
    phase4 = [case for case in cases if case["id"].startswith("p4-")]
    phase5 = [case for case in cases if case["id"].startswith("p5-")]
    assert len(sample) == 24
    assert len(phase2) == 50
    assert len(phase3) == 69
    assert len(phase4) == 58
    assert len(phase5) == 33
    # the original 42 Phase 0 operation cases are untouched
    assert len(cases) - len(sample) - len(phase2) - len(phase3) - len(phase4) - len(phase5) == 42


def test_sample_vector_coverage(sample_cases: list[dict]) -> None:
    assert len(sample_cases) == 24
    assert {case["width"] for case in sample_cases} == {0, 1, 2, 3, 4, 5}
    ops = {case["op"] for case in sample_cases}
    assert ops == SAMPLE_OPS
    assert any(case["expected"].get("values") == [] for case in sample_cases)
    assert any("error_message" in case["expected"] for case in sample_cases)


def test_decode_vectors(audioop_cli: Path, sample_cases: list[dict]) -> None:
    cases = [case for case in sample_cases if case["op"] == "sample_decode"]
    frames = run_frames(
        audioop_cli,
        [decode_body(case["width"], bytes.fromhex(case["args"]["fragment_hex"])) for case in cases],
    )
    for case, (status, payload) in zip(cases, frames, strict=True):
        expected = case["expected"]
        if "error_message" in expected:
            assert status == STATUS_ERROR, case["id"]
            assert payload.decode() == expected["error_message"], case["id"]
        else:
            assert status == STATUS_OK, case["id"]
            assert decode_values(payload) == expected["values"], case["id"]


def test_encode_vectors(audioop_cli: Path, sample_cases: list[dict]) -> None:
    cases = [case for case in sample_cases if case["op"] == "sample_encode"]
    frames = run_frames(
        audioop_cli,
        [encode_body(case["width"], case["args"]["values"]) for case in cases],
    )
    for case, (status, payload) in zip(cases, frames, strict=True):
        expected = case["expected"]
        if "error_message" in expected:
            assert status == STATUS_ERROR, case["id"]
            assert payload.decode() == expected["error_message"], case["id"]
        else:
            assert status == STATUS_OK, case["id"]
            assert payload.hex() == expected["result_hex"], case["id"]
