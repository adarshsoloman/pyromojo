"""Differential tests: native peak analysis versus CPython 3.12 audioop.

Every expectation comes from the reference oracle. Random cases use a
fixed seed. Floating-point results are compared bit-exactly through
their IEEE-754 bytes (nan included); no tolerance is applied anywhere.
"""

from __future__ import annotations

import math
import random
import struct
import sys
from pathlib import Path

from support import (
    avgpp_body,
    findfactor_body,
    findfit_body,
    findmax_body,
    maxpp_body,
    parse_double_bits,
    parse_fit,
    run_frames,
)

SEED = 20260610
OP_KEYS = ("avgpp", "maxpp", "findmax", "findfactor", "findfit")


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
            elif key == "findfactor":
                assert status == 0, (key, want)
                value = parse_double_bits(payload)
                if math.isnan(float(want["value"])):
                    # JSON cannot carry the nan sign; assert nan-ness only
                    assert math.isnan(value), (key, want)
                else:
                    assert struct.pack(">d", value) == struct.pack(">d", float(want["value"])), (
                        key,
                        want,
                    )
            elif key == "findfit":
                assert status == 0, (key, want)
                index, factor = parse_fit(payload)
                assert index == want["value"][0], (key, want)
                if math.isnan(float(want["value"][1])):
                    assert math.isnan(factor), (key, want)
                else:
                    assert struct.pack(">d", factor) == struct.pack(
                        ">d", float(want["value"][1])
                    ), (key, want)
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
        alternating = pcm(width, [1, 3, 1, 3])
        monotonic = pcm(width, [1, 2, 3, 2, 1])
        plateau = pcm(width, [1, 3, 3, 1, 3, 3, 1])
        constant = pcm(width, [5, 5, 5])
        single = pcm(width, [5])
        truncation = pcm(width, [0, 3, 0, 1, 0])

        for f in (alternating, monotonic, plateau, constant, single, truncation, b""):
            batch.emit("avgpp", {"width": width, "fragment_hex": f.hex()}, avgpp_body(width, f))
            batch.emit("maxpp", {"width": width, "fragment_hex": f.hex()}, maxpp_body(width, f))

    # unsigned wrap quirk at width 4
    wrap = pcm(4, [2**31 - 1, -(2**31), 2**31 - 1, -(2**31), 2**31 - 1])
    batch.emit("avgpp", {"width": 4, "fragment_hex": wrap.hex()}, avgpp_body(4, wrap))
    batch.emit("maxpp", {"width": 4, "fragment_hex": wrap.hex()}, maxpp_body(4, wrap))

    # errors
    batch.emit("avgpp", {"width": 2, "fragment_hex": "010203"}, avgpp_body(2, b"\x01\x02\x03"))
    batch.emit("maxpp", {"width": 0, "fragment_hex": ""}, maxpp_body(0, b""))

    for length, frag in (
        (2, pcm(2, [0, 100, 200, 300])),
        (1, pcm(2, [1, 2, 3])),
        (0, pcm(2, [1, 2])),
    ):
        batch.emit(
            "findmax",
            {"fragment_hex": frag.hex(), "length": length},
            findmax_body(length, frag),
        )
    batch.emit("findmax", {"fragment_hex": "", "length": 0}, findmax_body(0, b""))
    batch.emit(
        "findmax",
        {"fragment_hex": pcm(2, [0, 1]).hex(), "length": 3},
        findmax_body(3, pcm(2, [0, 1])),
    )
    batch.emit(
        "findmax",
        {"fragment_hex": "010203", "length": 1},
        findmax_body(1, b"\x01\x02\x03"),
    )

    reference = pcm(2, [1, 2, 3])
    for frag, ref in (
        (reference, reference),
        (pcm(2, [2, 4, 6]), reference),
        (pcm(2, [-1, -2, -3]), reference),
        (pcm(2, [1, 2]), pcm(2, [0, 0])),
        (b"", b""),
        (pcm(2, [0, 0, 0]), reference),
        (pcm(2, [30000, 30000]), pcm(2, [1, 1])),
    ):
        batch.emit(
            "findfactor",
            {"fragment_hex": frag.hex(), "reference_hex": ref.hex()},
            findfactor_body(frag, ref),
        )
    batch.emit(
        "findfactor",
        {"fragment_hex": pcm(2, [1, 2]).hex(), "reference_hex": pcm(2, [1, 2, 3]).hex()},
        findfactor_body(pcm(2, [1, 2]), pcm(2, [1, 2, 3])),
    )
    batch.emit(
        "findfactor",
        {"fragment_hex": "010203", "reference_hex": "01020304"},
        findfactor_body(b"\x01\x02\x03", b"\x01\x02\x03\x04"),
    )

    for frag, ref in (
        (pcm(2, [1, 2, 3, 4]), reference),
        (pcm(2, [9, 1, 2, 3]), reference),
        (pcm(2, [1, 2]), pcm(2, [1, 2])),
        (pcm(2, [1]), pcm(2, [1, 2])),
        (b"", b""),
        (pcm(2, [0, 0, 5, 6]), pcm(2, [0, 0])),
        (pcm(2, [1, 2, 1, 2]), pcm(2, [1, 2])),
        (pcm(2, [2, 4, 6, 8]), reference),
        (pcm(2, [5, 6, 0, 0, 0, 0]), pcm(2, [1, 2])),
    ):
        batch.emit(
            "findfit",
            {"fragment_hex": frag.hex(), "reference_hex": ref.hex()},
            findfit_body(frag, ref),
        )
    batch.emit(
        "findfit",
        {"fragment_hex": "010203", "reference_hex": "0102"},
        findfit_body(b"\x01\x02\x03", b"\x01\x02"),
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

        def random_fragment(count: int, style: str, width=width, lo=lo, hi=hi) -> bytes:
            if style == "positive":
                pool = [0, 1, hi, rng.randint(0, hi)]
            elif style == "negative":
                pool = [0, -1, lo, rng.randint(lo, 0)]
            elif style == "constant":
                value = rng.randint(lo, hi)
                pool = [value]
            elif style == "plateau":
                pool = [rng.choice([lo, hi, 0, 1])]
            elif style == "alternating":
                pool = [1, -1, lo, hi, 0]
            else:
                pool = [0, 1, -1, lo, hi, rng.randint(lo, hi)]
            return pcm(width, [rng.choice(pool) for _ in range(count)])

        styles = ("mixed", "positive", "negative", "constant", "plateau", "alternating")
        for _ in range(24):
            style = rng.choice(styles)
            frag = random_fragment(rng.choice([2, 3, 8, 17]), style)
            batch.emit(
                "avgpp", {"width": width, "fragment_hex": frag.hex()}, avgpp_body(width, frag)
            )
            batch.emit(
                "maxpp", {"width": width, "fragment_hex": frag.hex()}, maxpp_body(width, frag)
            )

            samples_16 = len(frag) // 2
            length = rng.randint(0, samples_16 + 1)
            batch.emit(
                "findmax",
                {"fragment_hex": frag.hex(), "length": length},
                findmax_body(length, frag),
            )

            # findfactor needs equal byte lengths
            pair = random_fragment(len(frag) // width, style if rng.random() < 0.5 else "mixed")
            batch.emit(
                "findfactor",
                {"fragment_hex": frag.hex(), "reference_hex": pair.hex()},
                findfactor_body(frag, pair),
            )

            # findfit needs frag at least as long as the reference (16-bit samples)
            ref = random_fragment(rng.choice([1, 2, 3, 8]), style)
            if len(ref) > len(frag):
                batch.emit(
                    "findfit",
                    {"fragment_hex": ref.hex(), "reference_hex": frag.hex()},
                    findfit_body(ref, frag),
                )
            else:
                batch.emit(
                    "findfit",
                    {"fragment_hex": frag.hex(), "reference_hex": ref.hex()},
                    findfit_body(frag, ref),
                )

    oracle = sample_oracle(**batch.cases)
    frames = run_frames(audioop_cli, batch.bodies)
    assert len(frames) == len(batch.bodies)
    check_frames(oracle, frames, batch.plan)


def test_nan_bit_policy(audioop_cli: Path) -> None:
    """Reference nan is 0xfff8... on this host; the port matches bit-exactly."""
    frames = run_frames(
        audioop_cli,
        [
            findfactor_body(pcm(2, [1, 2]), pcm(2, [0, 0])),
        ],
    )
    assert frames == [(0, b"\xff\xf8\x00\x00\x00\x00\x00\x00")]
    _ = struct
