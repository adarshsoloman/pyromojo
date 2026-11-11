"""Golden-vector integrity and reference replay tests."""

from __future__ import annotations

import importlib.metadata
import subprocess
import sys
from pathlib import Path

import pytest
from generate_vectors import decode_bytes, model_matches, pack_model
from shared.validation.msgpack_vectors import MARKERS, validate_bundle

ROOT = Path(__file__).resolve().parents[4]
GENERATOR = ROOT / "libraries/msgpack/python_reference/generate_vectors.py"


def test_bundle_is_structurally_valid(vectors_bundle: dict) -> None:
    assert validate_bundle(vectors_bundle) == []


def test_reference_version_is_pinned(vectors_bundle: dict) -> None:
    assert vectors_bundle["reference"] == {"package": "msgpack", "version": "1.2.4"}
    assert importlib.metadata.version("msgpack") == "1.2.4"


def test_committed_artifacts_are_current() -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_reference_replays_every_case(vectors_bundle: dict) -> None:
    for case in vectors_bundle["cases"]:
        case_id = case["id"]
        raw = bytes.fromhex(case["encoded"])
        if case["mode"] == "roundtrip":
            packed = pack_model(case["value"])
            assert packed == raw, f"{case_id}: reference encoding drifted"
            model_matches(case["value"], decode_bytes(raw))
        elif case["mode"] == "decode":
            model_matches(case["value"], decode_bytes(raw))
        else:
            expected = case["error"]
            try:
                decode_bytes(raw)
            except Exception as exc:  # noqa: BLE001 - asserting reference behavior
                assert type(exc).__name__ == expected["type"], (
                    f"{case_id}: expected {expected['type']}, got {type(exc).__name__}"
                )
                assert expected["contains"] in str(exc), (
                    f"{case_id}: {expected['contains']!r} not in {str(exc)!r}"
                )
            else:
                pytest.fail(f"{case_id}: reference accepted invalid input")


def test_marker_coverage_is_complete(vectors_bundle: dict) -> None:
    covered = {marker for case in vectors_bundle["cases"] for marker in case["markers"]}
    assert covered == MARKERS


def test_large_container_vectors_are_actually_large(vectors_bundle: dict) -> None:
    big_markers = {"str32", "bin32", "ext32", "array32", "map32"}
    seen: set[str] = set()
    for case in vectors_bundle["cases"]:
        if big_markers & set(case["markers"]):
            assert len(bytes.fromhex(case["encoded"])) >= 65536, case["id"]
            seen |= big_markers & set(case["markers"])
    assert seen == big_markers


def test_duplicate_map_keys_preserve_order(vectors_bundle: dict) -> None:
    case = next(case for case in vectors_bundle["cases"] if case["id"] == "map_duplicate_keys")
    actual = list(decode_bytes(bytes.fromhex(case["encoded"])))
    assert actual == [("k", 1), ("k", 2)]


def test_array_keys_are_accepted_as_pairs(vectors_bundle: dict) -> None:
    case = next(case for case in vectors_bundle["cases"] if case["id"] == "map_array_key")
    actual = list(decode_bytes(bytes.fromhex(case["encoded"])))
    assert actual == [([1, 2], None)]


def test_binary_payload_retains_non_utf8_bytes(vectors_bundle: dict) -> None:
    case = next(case for case in vectors_bundle["cases"] if case["id"] == "bin_non_utf8")
    assert decode_bytes(bytes.fromhex(case["encoded"])) == b"\x00\xff\x80"


def test_json_bundle_is_stable_text() -> None:
    path = ROOT / "libraries/msgpack/tests/vectors/msgpack_vectors.json"
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert not text.startswith("\ufeff")
