"""Differential tests: native G.711 codecs versus CPython 3.12 audioop.

Every expectation comes from the reference oracle. The decoder groups
are exhaustive: all 256 A-law codewords and all 256 mu-law codewords at
width 2, plus sampled codewords at widths 1, 3 and 4. Randomized
encoder cases use a fixed seed.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from support import (
    alaw2lin_body,
    lin2alaw_body,
    lin2ulaw_body,
    run_frames,
    ulaw2lin_body,
)

SEED = 20260610


def bounds(width: int) -> tuple[int, int]:
    return -(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1


def pcm(width: int, values: list[int]) -> bytes:
    return b"".join(value.to_bytes(width, sys.byteorder, signed=True) for value in values)


def check_frames(oracle: dict, frames: list, plan: list) -> None:
    keys = ("lin2alaw", "alaw2lin", "lin2ulaw", "ulaw2lin")
    grouped: dict[str, list] = {key: [] for key in keys}
    for key, frame in zip(plan, frames, strict=True):
        grouped[key].append(frame)
    for key in keys:
        for want, (status, payload) in zip(oracle[key], grouped[key], strict=True):
            if "error_type" in want:
                assert status == 1, (key, want)
                assert payload.decode() == want["error_message"], (key, want)
            else:
                assert status == 0, (key, want)
                assert payload.hex() == want["result_hex"], (key, want)


class Batch:
    def __init__(self) -> None:
        self.cases: dict[str, list[dict]] = {
            key: [] for key in ("lin2alaw", "alaw2lin", "lin2ulaw", "ulaw2lin")
        }
        self.bodies: list[bytes] = []
        self.plan: list[str] = []

    def emit(self, key: str, width: int, fragment: bytes) -> None:
        self.cases[key].append({"width": width, "fragment_hex": fragment.hex()})
        body = {
            "lin2alaw": lin2alaw_body,
            "alaw2lin": alaw2lin_body,
            "lin2ulaw": lin2ulaw_body,
            "ulaw2lin": ulaw2lin_body,
        }[key](width, fragment)
        self.bodies.append(body)
        self.plan.append(key)


def test_curated_differential(audioop_cli: Path, sample_oracle) -> None:
    batch = Batch()

    for width in range(1, 5):
        lo, hi = bounds(width)
        batch.emit("lin2alaw", width, pcm(width, [lo, hi, 0, -1, 1]))
        batch.emit("lin2ulaw", width, pcm(width, [lo, hi, 0, -1, 1]))

    # scaling boundaries per width
    batch.emit("lin2ulaw", 1, bytes([127, 128, 64]))
    batch.emit("lin2alaw", 1, bytes([127, 128, 64]))
    batch.emit("lin2ulaw", 2, pcm(2, [8191, -8192, 8192, -8193]))
    batch.emit("lin2alaw", 2, pcm(2, [4095, -4096, 4096, -4097]))
    batch.emit("lin2ulaw", 3, pcm(3, [819199, -819200, 0, 1]))
    batch.emit("lin2alaw", 3, pcm(3, [409599, -409600, 0, 1]))
    batch.emit("lin2ulaw", 4, pcm(4, [2147483647, -2147483648, 0, 1]))
    batch.emit("lin2alaw", 4, pcm(4, [2147483647, -2147483648, 0, 1]))

    batch.emit("lin2alaw", 2, b"")
    batch.emit("lin2ulaw", 2, b"")
    batch.emit("lin2alaw", 0, b"")
    batch.emit("lin2ulaw", 0, b"")
    batch.emit("lin2alaw", 2, b"\x01\x02\x03")
    batch.emit("lin2ulaw", 2, b"\x01")
    batch.emit("lin2alaw", 5, b"")

    # exhaustive decoders at width 2
    for code in range(256):
        batch.emit("alaw2lin", 2, bytes([code]))
    for code in range(256):
        batch.emit("ulaw2lin", 2, bytes([code]))

    # sampled decoder widths
    for code in (0x00, 0x55, 0x2A, 0x7F, 0x80, 0xD5, 0xAA, 0xFF):
        for width in (1, 3, 4):
            batch.emit("alaw2lin", width, bytes([code]))
            batch.emit("ulaw2lin", width, bytes([code]))

    batch.emit("alaw2lin", 2, bytes(range(0, 256, 7)))
    batch.emit("ulaw2lin", 2, bytes(range(255, -1, -11)))
    batch.emit("alaw2lin", 0, b"")
    batch.emit("ulaw2lin", 0, b"")

    oracle = sample_oracle(**batch.cases)
    frames = run_frames(audioop_cli, batch.bodies)
    assert len(frames) == len(batch.bodies)
    check_frames(oracle, frames, batch.plan)


def test_randomized_encoder_differential(audioop_cli: Path, sample_oracle) -> None:
    rng = random.Random(SEED)
    batch = Batch()

    for width in range(1, 5):
        lo, hi = bounds(width)
        for _ in range(30):
            count = rng.choice([1, 2, 3, 8, 17])
            values = [rng.choice([0, 1, -1, lo, hi, rng.randint(lo, hi)]) for _ in range(count)]
            batch.emit("lin2alaw", width, pcm(width, values))
            batch.emit("lin2ulaw", width, pcm(width, values))

    oracle = sample_oracle(**batch.cases)
    frames = run_frames(audioop_cli, batch.bodies)
    assert len(frames) == len(batch.bodies)
    check_frames(oracle, frames, batch.plan)


def test_roundtrip_property(audioop_cli: Path, sample_oracle) -> None:
    """The full encode->decode chain matches the reference end to end."""
    rng = random.Random(SEED + 1)
    encode_requests = {"lin2alaw": [], "lin2ulaw": []}
    plan = []
    for width in range(1, 5):
        lo, hi = bounds(width)
        for _ in range(6):
            values = [rng.randint(lo, hi) for _ in range(9)]
            fragment = pcm(width, values)
            encode_requests["lin2alaw"].append({"width": width, "fragment_hex": fragment.hex()})
            encode_requests["lin2ulaw"].append({"width": width, "fragment_hex": fragment.hex()})
            plan.append((width, fragment))

    encoded = sample_oracle(**encode_requests)
    decode_requests = {"alaw2lin": [], "ulaw2lin": []}
    decode_bodies = []
    decode_widths = []
    for index, (width, _fragment) in enumerate(plan):
        alaw_code = bytes.fromhex(encoded["lin2alaw"][index]["result_hex"])
        ulaw_code = bytes.fromhex(encoded["lin2ulaw"][index]["result_hex"])
        decode_requests["alaw2lin"].append({"width": width, "fragment_hex": alaw_code.hex()})
        decode_requests["ulaw2lin"].append({"width": width, "fragment_hex": ulaw_code.hex()})
        decode_bodies.append(alaw2lin_body(width, alaw_code))
        decode_bodies.append(ulaw2lin_body(width, ulaw_code))
        decode_widths.append((width, "alaw2lin"))
        decode_widths.append((width, "ulaw2lin"))

    decoded = sample_oracle(**decode_requests)
    frames = run_frames(audioop_cli, decode_bodies)
    assert len(frames) == len(decode_bodies)
    # compare pairwise
    a_index = 0
    u_index = 0
    for position, (_width, key) in enumerate(decode_widths):
        expected = decoded[key][a_index if key == "alaw2lin" else u_index]
        status, payload = frames[position]
        if "error_type" in expected:
            assert status == 1, (key, expected)
            assert payload.decode() == expected["error_message"]
        else:
            assert status == 0, (key, expected)
            assert payload.hex() == expected["result_hex"], (key, expected)
        if key == "alaw2lin":
            a_index += 1
        else:
            u_index += 1
