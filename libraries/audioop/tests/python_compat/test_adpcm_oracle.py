"""Differential tests: native ADPCM versus CPython 3.12 audioop.

Every expectation comes from the reference oracle. Random cases use a
fixed seed. Output bytes and returned state are compared exactly. A
dedicated group verifies chunk composition for both operations (even
encoder chunks compose exactly; odd encoder chunks do not, per
CPython's nibble buffering; decoder chunks always compose).
"""

from __future__ import annotations

import random
from pathlib import Path

from support import (
    adpcm2lin_body,
    lin2adpcm_body,
    parse_adpcm_response,
    run_frames,
)

SEED = 20260610


def bounds(width: int) -> tuple[int, int]:
    return -(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1


def pcm(width: int, values: list[int]) -> bytes:
    return b"".join(value.to_bytes(width, sys_byteorder(), signed=True) for value in values)


def sys_byteorder() -> str:
    import sys  # noqa: PLC0415

    return sys.byteorder


def check_frames(oracle: dict, frames: list, plan: list) -> None:
    keys = ("lin2adpcm", "adpcm2lin")
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
                output, state = parse_adpcm_response(payload)
                assert output.hex() == want["result_hex"], (key, want)
                assert [state[0], state[1]] == want["state"], (key, want)


class Batch:
    def __init__(self) -> None:
        self.cases: dict[str, list[dict]] = {key: [] for key in ("lin2adpcm", "adpcm2lin")}
        self.bodies: list[bytes] = []
        self.plan: list[str] = []

    def emit(
        self,
        key: str,
        width: int,
        fragment: bytes,
        state: tuple[int, int] | None = None,
    ) -> None:
        oracle_state = None if state is None else [state[0], state[1]]
        self.cases[key].append(
            {"width": width, "fragment_hex": fragment.hex(), "state": oracle_state}
        )
        body = lin2adpcm_body if key == "lin2adpcm" else adpcm2lin_body
        self.bodies.append(body(width, state, fragment))
        self.plan.append(key)


def test_curated_differential(audioop_cli: Path, sample_oracle) -> None:
    batch = Batch()

    for width in range(1, 5):
        lo, hi = bounds(width)
        batch.emit("lin2adpcm", width, pcm(width, [lo, hi, 0, -1, 1]))
        batch.emit("lin2adpcm", width, pcm(width, [0, 1, -1, 2, -2]))
        batch.emit("lin2adpcm", width, pcm(width, [hi, hi, lo, lo]))
        batch.emit("lin2adpcm", width, pcm(width, [0, 0, 0, 0]))

    batch.emit("lin2adpcm", 2, b"")
    batch.emit(
        "lin2adpcm",
        2,
        pcm(2, [1000]),
    )
    batch.emit("lin2adpcm", 2, pcm(2, [1, 2, 3]))
    batch.emit("lin2adpcm", 2, pcm(2, [0, 32767, 0, -32768, 0, 32767]))
    batch.emit("lin2adpcm", 2, b"", state=(100, 50))
    batch.emit("lin2adpcm", 2, pcm(2, [-6, -5, -4, -3]), state=(-7, 3))
    batch.emit("lin2adpcm", 2, b"", state=(32768, 0))
    batch.emit("lin2adpcm", 2, b"", state=(0, 89))
    batch.emit("lin2adpcm", 2, b"", state=(0, -1))
    batch.emit("lin2adpcm", 2, b"", state=(-32768, 88))
    batch.emit("lin2adpcm", 0, b"")
    batch.emit("lin2adpcm", 2, b"\x01")
    batch.emit("lin2adpcm", 5, b"")

    # exhaustive decoder bytes at width 2
    for byte in range(256):
        batch.emit("adpcm2lin", 2, bytes([byte]))

    for byte in (0x00, 0x7F, 0x80, 0xFF, 0x55, 0xAA, 0x12, 0xED):
        for width in (1, 3, 4):
            batch.emit("adpcm2lin", width, bytes([byte]))

    batch.emit("adpcm2lin", 2, b"")
    batch.emit("adpcm2lin", 2, b"\x01\x02\x03")
    batch.emit("adpcm2lin", 2, bytes([0x7F] * 6))
    batch.emit("adpcm2lin", 2, bytes([0x0F, 0xF0, 0x0F, 0xF0]))
    batch.emit("adpcm2lin", 2, b"\x34\x78", state=(-1, 14))
    batch.emit("adpcm2lin", 2, b"\x08\x08", state=(0, 55))
    batch.emit("adpcm2lin", 0, b"")
    batch.emit("adpcm2lin", 2, b"", state=(0, 100))

    oracle = sample_oracle(**batch.cases)
    frames = run_frames(audioop_cli, batch.bodies)
    assert len(frames) == len(batch.bodies)
    check_frames(oracle, frames, batch.plan)


def test_randomized_differential(audioop_cli: Path, sample_oracle) -> None:
    rng = random.Random(SEED)
    batch = Batch()

    for width in range(1, 5):
        lo, hi = bounds(width)
        for _ in range(20):
            count = rng.choice([0, 1, 2, 3, 8, 17])
            values = [rng.choice([0, 1, -1, lo, hi, rng.randint(lo, hi)]) for _ in range(count)]
            batch.emit("lin2adpcm", width, pcm(width, values))

    for _ in range(20):
        size = rng.choice([1, 2, 3, 8, 17])
        data = bytes(rng.randrange(256) for _ in range(size))
        batch.emit("adpcm2lin", 2, data)
    for width in (1, 3, 4):
        for _ in range(5):
            size = rng.choice([1, 2, 3])
            data = bytes(rng.randrange(256) for _ in range(size))
            batch.emit("adpcm2lin", width, data)

    oracle = sample_oracle(**batch.cases)
    frames = run_frames(audioop_cli, batch.bodies)
    assert len(frames) == len(batch.bodies)
    check_frames(oracle, frames, batch.plan)


def test_chunk_composition(audioop_cli: Path, sample_oracle) -> None:
    """Encoder: even chunks compose; odd chunks do not. Decoder: always."""
    values = list(range(-10, 10))
    full = pcm(2, values)

    whole_resp = sample_oracle(lin2adpcm=[{"width": 2, "fragment_hex": full.hex(), "state": None}])
    whole = whole_resp["lin2adpcm"][0]
    chunk1_resp = sample_oracle(
        lin2adpcm=[{"width": 2, "fragment_hex": full[:8].hex(), "state": None}]
    )
    chunk1 = chunk1_resp["lin2adpcm"][0]
    chunk2_resp = sample_oracle(
        lin2adpcm=[
            {
                "width": 2,
                "fragment_hex": full[8:].hex(),
                "state": [chunk1["state"][0], chunk1["state"][1]],
            }
        ]
    )
    chunk2 = chunk2_resp["lin2adpcm"][0]
    # two even chunks: concatenation equals the whole encoding
    assert chunk1["result_hex"] + chunk2["result_hex"] == whole["result_hex"]
    assert chunk2["state"] == whole["state"]

    # odd chunk: one sample -> no output bytes, state still advances
    oracle_odd = sample_oracle(
        lin2adpcm=[
            {"width": 2, "fragment_hex": full[:2].hex(), "state": None},
        ]
    )
    odd = oracle_odd["lin2adpcm"][0]
    # sample -10 from a fresh predictor: no output byte, state advances
    assert odd["result_hex"] == ""
    assert odd["state"] == [-10, 6]

    # decoder chunk composition through the CLI with state round-trips
    enc_frames = run_frames(audioop_cli, [lin2adpcm_body(2, None, full)])
    enc_output, _ = parse_adpcm_response(enc_frames[0][1])
    dec_whole = run_frames(audioop_cli, [adpcm2lin_body(2, None, enc_output)])
    dec_output, dec_state = parse_adpcm_response(dec_whole[0][1])
    parts = []
    running = None
    for i in range(0, len(enc_output), 2):
        frames = run_frames(audioop_cli, [adpcm2lin_body(2, running, enc_output[i : i + 2])])
        part, running = parse_adpcm_response(frames[0][1])
        parts.append(part)
    assert b"".join(parts) == dec_output
    assert running == dec_state
