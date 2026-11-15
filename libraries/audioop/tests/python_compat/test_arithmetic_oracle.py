"""Differential tests: native Phase 2 operations versus CPython 3.12 audioop.

Every expectation comes from the reference oracle, which calls the original
audioop module directly. Random cases use fixed seeds so failures are
reproducible. Mul avoids NaN factors (documented UB in both the reference
and the port) but exercises inf and zero-sample/inf combinations.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from support import (
    add_body,
    bias_body,
    byteswap_body,
    lin2lin_body,
    mul_body,
    reverse_body,
    run_frames,
)

SEED = 20260610
OP_KEYS = ("add", "bias", "mul", "reverse", "byteswap", "lin2lin")


def bounds(width: int) -> tuple[int, int]:
    return -(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1


def pcm(width: int, values: list[int]) -> bytes:
    return b"".join(value.to_bytes(width, sys.byteorder, signed=True) for value in values)


def check_frames(oracle: dict, frames: list[tuple[int, bytes]], plan: list[str]) -> None:
    """plan lists the op for each body, aligned 1:1 with bodies and frames."""
    grouped: dict[str, list[tuple[int, bytes]]] = {key: [] for key in OP_KEYS}
    for key, frame in zip(plan, frames, strict=True):
        grouped[key].append(frame)
    for key in OP_KEYS:
        for want, (status, payload) in zip(oracle[key], grouped[key], strict=True):
            if "error_type" in want:
                assert status == 1, (key, want)
                assert payload.decode() == want["error_message"], (key, want)
            else:
                assert status == 0, (key, want)
                assert payload.hex() == want["result_hex"], (key, want)


class Batch:
    """Collects oracle cases and CLI bodies in one aligned sequence."""

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
        frag_neg = pcm(width, [-1, lo, hi - 1])
        frag_pos = pcm(width, [1, hi // 2 if width > 1 else 1, lo + 1])

        for f1, f2 in ((frag, frag_neg), (frag_pos, frag_neg), (frag, b"")):
            batch.emit(
                "add",
                {"width": width, "fragment1_hex": f1.hex(), "fragment2_hex": f2.hex()},
                add_body(width, f1, f2),
            )

        for bias_value in (0, 1, -1, 10, -10, 2**31 - 1, -(2**31)):
            batch.emit(
                "bias",
                {"width": width, "fragment_hex": frag.hex(), "bias": bias_value},
                bias_body(width, bias_value, frag),
            )

        for factor in (0.0, 1.0, -1.0, 0.5, -0.5, 2.5, 0.001, -0.001, 1e6, 1e-6):
            batch.emit(
                "mul",
                {"width": width, "fragment_hex": frag.hex(), "factor": factor},
                mul_body(width, factor, frag),
            )
        # inf factors use a zero-free fragment: 0*inf is NaN, which is
        # undefined in the reference and excluded from equality assertions
        # (the port's documented NaN->zero policy is tested separately).
        batch.emit(
            "mul",
            {"width": width, "fragment_hex": frag_neg.hex(), "factor": "inf"},
            mul_body(width, float("inf"), frag_neg),
        )
        batch.emit(
            "mul",
            {"width": width, "fragment_hex": frag_neg.hex(), "factor": "-inf"},
            mul_body(width, float("-inf"), frag_neg),
        )

        batch.emit(
            "reverse", {"width": width, "fragment_hex": frag.hex()}, reverse_body(width, frag)
        )
        batch.emit(
            "byteswap",
            {"width": width, "fragment_hex": frag.hex()},
            byteswap_body(width, frag),
        )

        for new_width in range(1, 5):
            batch.emit(
                "lin2lin",
                {"width": width, "fragment_hex": frag.hex(), "new_width": new_width},
                lin2lin_body(width, new_width, frag),
            )

    # empty fragments
    batch.emit("add", {"width": 2, "fragment1_hex": "", "fragment2_hex": ""}, add_body(2, b"", b""))
    batch.emit("bias", {"width": 2, "fragment_hex": "", "bias": 5}, bias_body(2, 5, b""))
    batch.emit("mul", {"width": 2, "fragment_hex": "", "factor": 2.0}, mul_body(2, 2.0, b""))
    batch.emit("reverse", {"width": 2, "fragment_hex": ""}, reverse_body(2, b""))
    batch.emit("byteswap", {"width": 2, "fragment_hex": ""}, byteswap_body(2, b""))
    batch.emit("lin2lin", {"width": 2, "fragment_hex": "", "new_width": 3}, lin2lin_body(2, 3, b""))

    # error cases
    batch.emit(
        "add",
        {"width": 2, "fragment1_hex": "0102", "fragment2_hex": "01"},
        add_body(2, b"\x01\x02", b"\x01"),
    )
    batch.emit(
        "bias",
        {"width": 2, "fragment_hex": "0102", "bias": 2**40},
        bias_body(2, 2**40, b"\x01\x02"),
    )
    batch.emit(
        "lin2lin",
        {"width": 5, "fragment_hex": "", "new_width": 2},
        lin2lin_body(5, 2, b""),
    )
    batch.emit(
        "lin2lin",
        {"width": 2, "fragment_hex": "01", "new_width": 1},
        lin2lin_body(2, 1, b"\x01"),
    )
    batch.emit("reverse", {"width": 0, "fragment_hex": ""}, reverse_body(0, b""))
    batch.emit("byteswap", {"width": 2, "fragment_hex": "0102"}, byteswap_body(2, b"\x01\x02"))

    oracle = sample_oracle(**batch.cases)
    frames = run_frames(audioop_cli, batch.bodies)
    assert len(frames) == len(batch.bodies)
    check_frames(oracle, frames, batch.plan)


def test_randomized_differential(audioop_cli: Path, sample_oracle) -> None:
    rng = random.Random(SEED)
    batch = Batch()

    for width in range(1, 5):
        lo, hi = bounds(width)

        def random_fragment(count: int, width=width, lo=lo, hi=hi) -> bytes:
            return pcm(
                width,
                [
                    rng.choice(
                        [0, 1, -1, lo, hi, rng.randint(lo, hi), rng.randint(lo // 2, hi // 2)]
                    )
                    for _ in range(count)
                ],
            )

        for _ in range(40):
            frag1 = random_fragment(rng.choice([1, 2, 3, 8, 17]))
            if rng.random() < 0.9:
                frag2 = random_fragment(len(frag1) // width)
            else:
                frag2 = random_fragment(max(1, len(frag1) // width - 1))
            batch.emit(
                "add",
                {"width": width, "fragment1_hex": frag1.hex(), "fragment2_hex": frag2.hex()},
                add_body(width, frag1, frag2),
            )

            frag = random_fragment(rng.choice([0, 1, 2, 3, 8, 17]))
            bias_value = rng.choice(
                [0, 1, -1, rng.randint(-(2**31), 2**31 - 1), lo, hi, 12345, -12345]
            )
            batch.emit(
                "bias",
                {"width": width, "fragment_hex": frag.hex(), "bias": bias_value},
                bias_body(width, bias_value, frag),
            )

            factor = rng.choice(
                [
                    0.0,
                    1.0,
                    -1.0,
                    0.5,
                    -0.5,
                    0.001,
                    -0.001,
                    2.5,
                    -2.5,
                    1e6,
                    1e-6,
                    -1e6,
                    rng.uniform(-10.0, 10.0),
                    rng.uniform(-1.0, 1.0),
                ]
            )
            batch.emit(
                "mul",
                {"width": width, "fragment_hex": frag.hex(), "factor": factor},
                mul_body(width, factor, frag),
            )

            batch.emit(
                "reverse", {"width": width, "fragment_hex": frag.hex()}, reverse_body(width, frag)
            )
            batch.emit(
                "byteswap",
                {"width": width, "fragment_hex": frag.hex()},
                byteswap_body(width, frag),
            )

            new_width = rng.randint(1, 4)
            batch.emit(
                "lin2lin",
                {"width": width, "fragment_hex": frag.hex(), "new_width": new_width},
                lin2lin_body(width, new_width, frag),
            )

    oracle = sample_oracle(**batch.cases)
    frames = run_frames(audioop_cli, batch.bodies)
    assert len(frames) == len(batch.bodies)
    check_frames(oracle, frames, batch.plan)


def test_nan_factor_documented_policy(audioop_cli: Path) -> None:
    """The reference's (int)NaN is UB; the port defines NaN results as zero."""
    frames = run_frames(audioop_cli, [mul_body(2, float("nan"), b"\x01\x00\xff\xff")])
    assert frames == [(0, b"\x00\x00\x00\x00")]
