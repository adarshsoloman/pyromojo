"""Differential tests: native channel operations versus CPython 3.12 audioop.

Every expectation comes from the reference oracle. Random cases use a
fixed seed. Outputs are byte fragments compared as hex; errors compare
exact messages. NaN-factor results match the reference exactly at
widths 1-3 (the port's documented NaN->zero policy); width-4 NaN
combinations are undefined in the reference and are excluded from
equality assertions (see test_w4_nan_undefined).
"""

from __future__ import annotations

import random
import struct
import sys
from pathlib import Path

from support import (
    STATUS_ERROR,
    STATUS_OK,
    run_frames,
    tomono_body,
    tostereo_body,
)

SEED = 20260610
OP_KEYS = ("tomono", "tostereo")


def bounds(width: int) -> tuple[int, int]:
    return -(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1


def pcm(width: int, values: list[int]) -> bytes:
    return b"".join(value.to_bytes(width, sys.byteorder, signed=True) for value in values)


def check_frames(oracle: dict, frames: list, plan: list) -> None:
    grouped: dict[str, list] = {key: [] for key in OP_KEYS}
    for key, frame in zip(plan, frames, strict=True):
        grouped[key].append(frame)
    for key in OP_KEYS:
        for want, (status, payload) in zip(oracle[key], grouped[key], strict=True):
            if "error_type" in want:
                assert status == STATUS_ERROR, (key, want)
                assert payload.decode() == want["error_message"], (key, want)
            else:
                assert status == STATUS_OK, (key, want)
                assert payload.hex() == want["result_hex"], (key, want)


class Batch:
    def __init__(self) -> None:
        self.cases: dict[str, list[dict]] = {key: [] for key in OP_KEYS}
        self.bodies: list[bytes] = []
        self.plan: list[str] = []

    def emit(self, key: str, args: dict, body: bytes) -> None:
        self.cases[key].append(args)
        self.bodies.append(body)
        self.plan.append(key)


def test_curated_differential(audioop_cli: Path, sample_oracle) -> None:
    batch = Batch()

    for width in range(1, 5):
        lo, hi = bounds(width)
        even = pcm(width, [lo, hi, -1, 1])
        mixed = pcm(width, [1, 3, 2, 4, -1, -1])
        boundary_pair = pcm(width, [hi, hi, lo, lo])
        fractional = pcm(width, [1, -2, 3, -4])
        zeros = pcm(width, [0, 0, 0, 0])

        for frag in (even, mixed, boundary_pair, fractional, zeros, b""):
            batch.emit(
                "tomono",
                {"width": width, "fragment_hex": frag.hex(), "lfactor": 0.5, "rfactor": 0.5},
                tomono_body(width, 0.5, 0.5, frag),
            )
            batch.emit(
                "tostereo",
                {"width": width, "fragment_hex": frag.hex(), "lfactor": 0.5, "rfactor": -0.5},
                tostereo_body(width, 0.5, -0.5, frag),
            )

        for left, right in ((0.0, 0.0), (1.0, 1.0), (-1.0, 1.0), (2.0, 0.001), (1e6, -1e6)):
            batch.emit(
                "tomono",
                {"width": width, "fragment_hex": even.hex(), "lfactor": left, "rfactor": right},
                tomono_body(width, left, right, even),
            )
            batch.emit(
                "tostereo",
                {"width": width, "fragment_hex": even.hex(), "lfactor": left, "rfactor": right},
                tostereo_body(width, left, right, even),
            )

        batch.emit(
            "tomono",
            {"width": width, "fragment_hex": even.hex(), "lfactor": "inf", "rfactor": "-inf"},
            tomono_body(width, float("inf"), float("-inf"), even),
        )
        batch.emit(
            "tostereo",
            {"width": width, "fragment_hex": even.hex(), "lfactor": "inf", "rfactor": "-inf"},
            tostereo_body(width, float("inf"), float("-inf"), even),
        )
        # NaN factor: widths 1-3 match the port's NaN->zero policy exactly
        if width < 4:
            batch.emit(
                "tomono",
                {"width": width, "fragment_hex": even.hex(), "lfactor": "nan", "rfactor": 0.5},
                tomono_body(width, float("nan"), 0.5, even),
            )
            batch.emit(
                "tostereo",
                {"width": width, "fragment_hex": even.hex(), "lfactor": "nan", "rfactor": 0.5},
                tostereo_body(width, float("nan"), 0.5, even),
            )

    # alignment/width errors
    batch.emit(
        "tomono",
        {"width": 2, "fragment_hex": pcm(2, [5]).hex(), "lfactor": 1.0, "rfactor": 1.0},
        tomono_body(2, 1.0, 1.0, pcm(2, [5])),
    )
    batch.emit(
        "tomono",
        {"width": 2, "fragment_hex": "010203", "lfactor": 1.0, "rfactor": 1.0},
        tomono_body(2, 1.0, 1.0, b"\x01\x02\x03"),
    )
    batch.emit(
        "tomono",
        {"width": 0, "fragment_hex": "", "lfactor": 1.0, "rfactor": 1.0},
        tomono_body(0, 1.0, 1.0, b""),
    )
    batch.emit(
        "tostereo",
        {"width": 0, "fragment_hex": "", "lfactor": 1.0, "rfactor": 1.0},
        tostereo_body(0, 1.0, 1.0, b""),
    )
    batch.emit(
        "tostereo",
        {"width": 2, "fragment_hex": "01", "lfactor": 1.0, "rfactor": 1.0},
        tostereo_body(2, 1.0, 1.0, b"\x01"),
    )

    oracle = sample_oracle(**batch.cases)
    frames = run_frames(audioop_cli, batch.bodies)
    assert len(frames) == len(batch.bodies)
    check_frames(oracle, frames, batch.plan)


def test_randomized_differential(audioop_cli: Path, sample_oracle) -> None:
    rng = random.Random(SEED)
    batch = Batch()

    for width in range(1, 5):
        lo, hi = bounds(width)

        def random_fragment(pairs: int, width=width, lo=lo, hi=hi) -> bytes:
            pool = [0, 1, -1, lo, hi, rng.randint(lo, hi)]
            return pcm(width, [rng.choice(pool) for _ in range(2 * pairs)])

        def random_factor() -> float:
            return rng.choice(
                [
                    0.0,
                    1.0,
                    -1.0,
                    0.5,
                    -0.5,
                    0.001,
                    2.0,
                    1e6,
                    -1e6,
                    rng.uniform(-10.0, 10.0),
                    rng.uniform(-1.0, 1.0),
                ]
            )

        for _ in range(24):
            frag = random_fragment(rng.choice([0, 1, 2, 3, 8]))
            lfactor = random_factor()
            rfactor = random_factor()
            batch.emit(
                "tomono",
                {
                    "width": width,
                    "fragment_hex": frag.hex(),
                    "lfactor": lfactor,
                    "rfactor": rfactor,
                },
                tomono_body(width, lfactor, rfactor, frag),
            )
            batch.emit(
                "tostereo",
                {
                    "width": width,
                    "fragment_hex": frag.hex(),
                    "lfactor": lfactor,
                    "rfactor": rfactor,
                },
                tostereo_body(width, lfactor, rfactor, frag),
            )
            # inf + (-inf) is NaN, which is undefined at width 4 in the
            # reference; only widths 1-3 participate in this branch
            if width < 4 and rng.random() < 0.3:
                batch.emit(
                    "tomono",
                    {
                        "width": width,
                        "fragment_hex": frag.hex(),
                        "lfactor": "inf",
                        "rfactor": "-inf",
                    },
                    tomono_body(width, float("inf"), float("-inf"), frag),
                )

    oracle = sample_oracle(**batch.cases)
    frames = run_frames(audioop_cli, batch.bodies)
    assert len(frames) == len(batch.bodies)
    check_frames(oracle, frames, batch.plan)


def test_w4_nan_undefined(audioop_cli: Path) -> None:
    """Width-4 NaN is reference UB ((int)NaN = INT_MIN); the port defines
    NaN results as zero. Frozen decision: excluded from equality assertions;
    recorded here as the documented deviation."""
    frames = run_frames(
        audioop_cli,
        [tostereo_body(4, float("nan"), 1.0, struct.pack("<i", 1))],
    )
    status, payload = frames[0]
    assert status == STATUS_OK
    assert payload.hex() == "0000000001000000"
    _ = struct
