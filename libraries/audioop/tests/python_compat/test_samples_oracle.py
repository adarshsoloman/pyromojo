"""Differential tests: native sample CLI versus CPython 3.12 audioop.

Decode expectations come from ``audioop.getsample``; encode expectations
are canonical native-order bytes validated through ``getsample``. Fixed
seed and explicit boundary cases keep the suite reproducible.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from support import (
    STATUS_ERROR,
    STATUS_OK,
    decode_body,
    decode_values,
    encode_body,
    run_frames,
)

SEED = 20260610


def bounds(width: int) -> tuple[int, int]:
    return -(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1


def pcm(width: int, values: list[int]) -> bytes:
    return b"".join(value.to_bytes(width, sys.byteorder, signed=True) for value in values)


def test_curated_decode_matches_reference(audioop_cli: Path, sample_oracle) -> None:
    cases: list[tuple[int, bytes]] = []
    for width in range(1, 5):
        lo, hi = bounds(width)
        cases.append((width, pcm(width, [lo, hi, 0, -1, 1])))
        cases.append((width, b""))

    oracle = sample_oracle(
        decode=[{"width": width, "fragment_hex": fragment.hex()} for width, fragment in cases]
    )
    frames = run_frames(audioop_cli, [decode_body(width, fragment) for width, fragment in cases])
    for case, expected, (status, payload) in zip(cases, oracle["decode"], frames, strict=True):
        assert status == STATUS_OK, case
        assert decode_values(payload) == expected["values"], case


def test_randomized_decode_matches_reference(audioop_cli: Path, sample_oracle) -> None:
    rng = random.Random(SEED)
    cases: list[tuple[int, bytes]] = []
    for width in range(1, 5):
        for _ in range(50):
            count = rng.choice([0, 1, 2, 3, 8, 17])
            fragment = bytes(rng.randrange(256) for _ in range(count * width))
            cases.append((width, fragment))

    oracle = sample_oracle(
        decode=[{"width": width, "fragment_hex": fragment.hex()} for width, fragment in cases]
    )
    frames = run_frames(audioop_cli, [decode_body(width, fragment) for width, fragment in cases])
    for case, expected, (status, payload) in zip(cases, oracle["decode"], frames, strict=True):
        assert status == STATUS_OK, case
        assert decode_values(payload) == expected["values"], case


def test_decode_errors_match_reference(audioop_cli: Path, sample_oracle) -> None:
    cases = [
        (0, b""),
        (5, b""),
        (2, b"abc"),
        (3, b"12345"),
        (4, b"abc"),
    ]
    oracle = sample_oracle(
        decode=[{"width": width, "fragment_hex": fragment.hex()} for width, fragment in cases]
    )
    frames = run_frames(audioop_cli, [decode_body(width, fragment) for width, fragment in cases])
    for expected, (status, payload) in zip(oracle["decode"], frames, strict=True):
        assert expected["error_type"] == "error"
        assert status == STATUS_ERROR
        assert payload.decode() == expected["error_message"]


def test_curated_encode_matches_reference(audioop_cli: Path, sample_oracle) -> None:
    cases: list[tuple[int, list[int]]] = []
    for width in range(1, 5):
        lo, hi = bounds(width)
        cases.append((width, [lo, hi, 0, -1, 1]))
        cases.append((width, [lo, lo + 1, -1, 0, 1, hi - 1, hi]))
        cases.append((width, []))
    oracle = sample_oracle(encode=[{"width": width, "values": values} for width, values in cases])
    frames = run_frames(audioop_cli, [encode_body(width, values) for width, values in cases])
    for case, expected, (status, payload) in zip(cases, oracle["encode"], frames, strict=True):
        assert status == STATUS_OK, case
        assert payload.hex() == expected["result_hex"], case
        assert expected["values"] == case[1]


def test_randomized_encode_matches_reference(audioop_cli: Path, sample_oracle) -> None:
    rng = random.Random(SEED + 1)
    cases: list[tuple[int, list[int]]] = []
    for width in range(1, 5):
        lo, hi = bounds(width)
        for _ in range(50):
            count = rng.choice([0, 1, 2, 3, 8, 17])
            values = [rng.randint(lo, hi) for _ in range(count)]
            cases.append((width, values))

    oracle = sample_oracle(encode=[{"width": width, "values": values} for width, values in cases])
    frames = run_frames(audioop_cli, [encode_body(width, values) for width, values in cases])
    for case, expected, (status, payload) in zip(cases, oracle["encode"], frames, strict=True):
        assert status == STATUS_OK, case
        assert payload.hex() == expected["result_hex"], case
        assert expected["values"] == case[1]


def test_invalid_values_are_rejected(audioop_cli: Path, sample_oracle) -> None:
    cases: list[tuple[int, list[int]]] = []
    for width in range(1, 5):
        lo, hi = bounds(width)
        cases.append((width, [lo - 1]))
        cases.append((width, [hi + 1]))
        cases.append((width, [0, hi + 1]))

    oracle = sample_oracle(encode=[{"width": width, "values": values} for width, values in cases])
    frames = run_frames(audioop_cli, [encode_body(width, values) for width, values in cases])
    for (width, values), expected, (status, payload) in zip(
        cases, oracle["encode"], frames, strict=True
    ):
        assert expected["error_type"] == "OverflowError"
        assert status == STATUS_ERROR
        assert payload.decode() == (f"sample value {values[-1]} out of range for width {width}")


def test_invalid_width_encode_matches_reference(audioop_cli: Path, sample_oracle) -> None:
    cases = [(0, []), (5, [])]
    oracle = sample_oracle(encode=[{"width": width, "values": values} for width, values in cases])
    frames = run_frames(audioop_cli, [encode_body(width, values) for width, values in cases])
    for expected, (status, payload) in zip(oracle["encode"], frames, strict=True):
        assert status == STATUS_ERROR
        assert payload.decode() == expected["error_message"]


def test_malformed_value_text_is_rejected(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            b"\x21\x01abc",
            b"\x21\x01" + b"12x",
            b"\x21\x01" + b"-",
        ],
    )
    for status, payload in frames:
        assert status == STATUS_ERROR
        assert payload == b"invalid sample value list"
