"""Differential tests: native statistics versus CPython 3.12 audioop.

Every expectation comes from the reference oracle. Random cases use a
fixed seed and cover positive-only, negative-only, mixed-sign, zero-heavy,
empty and single-sample sequences, plus random valid and invalid
``getsample`` indices.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from support import (
    avg_body,
    cross_body,
    getsample_body,
    max_body,
    minmax_body,
    rms_body,
    run_frames,
)

SEED = 20260610
OP_KEYS = ("getsample", "max", "minmax", "avg", "rms", "cross")


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
                assert status == 1, (key, want)
                assert payload.decode() == want["error_message"], (key, want)
            elif key == "minmax":
                assert status == 0, (key, want)
                first, second = payload.decode().split()
                assert [int(first), int(second)] == want["value"], (key, want)
            else:
                assert status == 0, (key, want)
                assert int(payload.decode()) == want["value"], (key, want)


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
        frag = pcm(width, [lo, hi, 0, -1, 1])
        negatives = pcm(width, [-1, lo + 1, -3])
        positives = pcm(width, [1, hi, 2])
        zeros = pcm(width, [0, 0, 0])
        single = pcm(width, [5])
        alternating = pcm(width, [1, -1, 1, -1])

        for index in (0, 4):
            batch.emit(
                "getsample",
                {"width": width, "fragment_hex": frag.hex(), "index": index},
                getsample_body(width, index, frag),
            )

        for f in (frag, negatives, positives, zeros, single, alternating, b""):
            batch.emit("max", {"width": width, "fragment_hex": f.hex()}, max_body(width, f))
            batch.emit("minmax", {"width": width, "fragment_hex": f.hex()}, minmax_body(width, f))
            batch.emit("avg", {"width": width, "fragment_hex": f.hex()}, avg_body(width, f))
            batch.emit("rms", {"width": width, "fragment_hex": f.hex()}, rms_body(width, f))
            batch.emit("cross", {"width": width, "fragment_hex": f.hex()}, cross_body(width, f))

        batch.emit(
            "getsample",
            {"width": width, "fragment_hex": frag.hex(), "index": 5},
            getsample_body(width, 5, frag),
        )

    # floor/truncation evidence
    avg_floor_frag = pcm(2, [-1, -2])
    batch.emit(
        "avg", {"width": 2, "fragment_hex": avg_floor_frag.hex()}, avg_body(2, avg_floor_frag)
    )
    avg_floor3_frag = pcm(2, [-1, -2, -4])
    batch.emit(
        "avg",
        {"width": 2, "fragment_hex": avg_floor3_frag.hex()},
        avg_body(2, avg_floor3_frag),
    )
    avg_floor_pos_frag = pcm(2, [1, 2, 4])
    batch.emit(
        "avg",
        {"width": 2, "fragment_hex": avg_floor_pos_frag.hex()},
        avg_body(2, avg_floor_pos_frag),
    )
    rms_trunc_frag = pcm(2, [2, -2, 2, -3])
    batch.emit(
        "rms",
        {"width": 2, "fragment_hex": rms_trunc_frag.hex()},
        rms_body(2, rms_trunc_frag),
    )
    batch.emit(
        "rms",
        {"width": 4, "fragment_hex": pcm(4, [-2147483648, -2147483648]).hex()},
        rms_body(4, pcm(4, [-2147483648, -2147483648])),
    )
    batch.emit(
        "max",
        {"width": 4, "fragment_hex": pcm(4, [-2147483648]).hex()},
        max_body(4, pcm(4, [-2147483648])),
    )
    batch.emit(
        "cross",
        {"width": 4, "fragment_hex": pcm(4, [-2147483648, 1]).hex()},
        cross_body(4, pcm(4, [-2147483648, 1])),
    )

    # error cases
    batch.emit(
        "getsample",
        {"width": 2, "fragment_hex": pcm(2, [1, 2, 3]).hex(), "index": -1},
        getsample_body(2, -1, pcm(2, [1, 2, 3])),
    )
    batch.emit(
        "getsample",
        {"width": 2, "fragment_hex": "", "index": 0},
        getsample_body(2, 0, b""),
    )
    batch.emit(
        "getsample",
        {"width": 2, "fragment_hex": "010203", "index": 0},
        getsample_body(2, 0, b"\x01\x02\x03"),
    )
    batch.emit("avg", {"width": 0, "fragment_hex": ""}, avg_body(0, b""))
    batch.emit("rms", {"width": 5, "fragment_hex": ""}, rms_body(5, b""))
    batch.emit("cross", {"width": 2, "fragment_hex": "01"}, cross_body(2, b"\x01"))
    batch.emit("minmax", {"width": 7, "fragment_hex": ""}, minmax_body(7, b""))
    batch.emit("max", {"width": 2, "fragment_hex": "01"}, max_body(2, b"\x01"))

    oracle = sample_oracle(**batch.cases)
    frames = run_frames(audioop_cli, batch.bodies)
    assert len(frames) == len(batch.bodies)
    check_frames(oracle, frames, batch.plan)


def test_randomized_differential(audioop_cli: Path, sample_oracle) -> None:
    rng = random.Random(SEED)
    batch = Batch()

    for width in range(1, 5):
        lo, hi = bounds(width)

        def random_fragment(count: int, style: str, width=width, lo=lo, hi=hi) -> bytes:
            if style == "positive":
                pool = [0, 1, hi, rng.randint(0, hi)]
            elif style == "negative":
                pool = [0, -1, lo, rng.randint(lo, 0)]
            elif style == "zeros":
                pool = [0]
            elif style == "boundary":
                pool = [0, lo, hi, 1, -1]
            else:
                pool = [0, 1, -1, lo, hi, rng.randint(lo, hi)]
            return pcm(width, [rng.choice(pool) for _ in range(count)])

        styles = ("mixed", "positive", "negative", "zeros", "boundary")
        for _ in range(40):
            style = rng.choice(styles)
            frag = random_fragment(rng.choice([0, 1, 2, 3, 8, 17]), style)

            count = len(frag) // width
            index = rng.randint(-2, count + 1)  # valid and invalid indices
            batch.emit(
                "getsample",
                {"width": width, "fragment_hex": frag.hex(), "index": index},
                getsample_body(width, index, frag),
            )

            for op, body_fn in (
                ("max", max_body),
                ("minmax", minmax_body),
                ("avg", avg_body),
                ("rms", rms_body),
                ("cross", cross_body),
            ):
                batch.emit(op, {"width": width, "fragment_hex": frag.hex()}, body_fn(width, frag))

    oracle = sample_oracle(**batch.cases)
    frames = run_frames(audioop_cli, batch.bodies)
    assert len(frames) == len(batch.bodies)
    check_frames(oracle, frames, batch.plan)


def test_scalar_payload_shapes(audioop_cli: Path) -> None:
    """max and rms can exceed the signed 32-bit range but stay ASCII decimal."""
    import struct as _struct

    frames = run_frames(
        audioop_cli,
        [
            max_body(4, _struct.pack("<i", -(2**31))),
            rms_body(4, _struct.pack("<ii", -(2**31), -(2**31))),
        ],
    )
    assert frames == [(0, b"2147483648"), (0, b"2147483648")]
