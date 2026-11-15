"""Differential tests: native ratecv versus CPython 3.12 audioop.

Every expectation comes from the reference oracle. Random cases use a
fixed seed. Output bytes and returned state are compared exactly; errors
compare exact messages. A dedicated group verifies the chunk-equivalence
invariant against both implementations.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from support import parse_ratecv_response, ratecv_body, run_frames

SEED = 20260610


def bounds(width: int) -> tuple[int, int]:
    return -(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1


def pcm(width: int, values: list[int]) -> bytes:
    return b"".join(value.to_bytes(width, sys.byteorder, signed=True) for value in values)


def check_frames(oracle: list[dict], frames: list) -> None:
    for want, (status, payload) in zip(oracle, frames, strict=True):
        if "error_type" in want:
            assert status == 1, want
            assert payload.decode() == want["error_message"], want
        else:
            assert status == 0, want
            nchannels = len(want["state"]["channels"])
            output, state = parse_ratecv_response(payload, nchannels)
            assert output.hex() == want["result_hex"], want
            assert state[0] == want["state"]["d"], want
            assert [list(pair) for pair in state[1]] == want["state"]["channels"], want


class Batch:
    def __init__(self) -> None:
        self.cases: list[dict] = []
        self.bodies: list[bytes] = []
        self.nchannels: list[int] = []

    def emit(
        self,
        width: int,
        nchannels: int,
        inrate: int,
        outrate: int,
        fragment: bytes,
        state=None,
        weight_a: int = 1,
        weight_b: int = 0,
    ) -> None:
        if state is None:
            oracle_state = None
        else:
            oracle_state = {
                "d": state[0],
                "channels": [list(pair) for pair in state[1]],
            }
        self.cases.append(
            {
                "width": width,
                "nchannels": nchannels,
                "inrate": inrate,
                "outrate": outrate,
                "fragment_hex": fragment.hex(),
                "state": oracle_state,
                "weightA": weight_a,
                "weightB": weight_b,
            }
        )
        self.bodies.append(
            ratecv_body(width, nchannels, inrate, outrate, weight_a, weight_b, state, fragment)
        )
        self.nchannels.append(nchannels)


def test_curated_differential(audioop_cli: Path, sample_oracle) -> None:
    batch = Batch()

    for width in range(1, 5):
        lo, hi = bounds(width)
        batch.emit(width, 1, 8000, 8000, pcm(width, [lo, hi, -1, 1]))
        batch.emit(width, 1, 8000, 16000, pcm(width, [lo, hi, 0, 1]))
        batch.emit(width, 1, 16000, 8000, pcm(width, [lo, hi, 0, -1]))

    batch.emit(2, 1, 8000, 8000, b"")
    batch.emit(2, 1, 8000, 16000, b"")
    batch.emit(2, 1, 8000, 8000, pcm(2, [1000]))
    batch.emit(2, 1, 3, 3, pcm(2, [1000, 2000, 3000]))
    batch.emit(2, 1, 8000, 44100, pcm(2, [1000, 2000, 3000, 4000, 5000]))
    batch.emit(2, 2, 8000, 16000, pcm(2, [1, 2, 3, 4]))
    batch.emit(2, 4, 8000, 8000, pcm(2, [1, 2, 3, 4, 5, 6, 7, 8]))
    batch.emit(4, 1, 8000, 16000, pcm(4, [2147483647, -2147483648, 0, 1]))
    batch.emit(3, 1, 8000, 16000, pcm(3, [-1, 1, 0, 5]))
    batch.emit(2, 1, 8000, 8000, pcm(2, [1000, -1000]), weight_a=2, weight_b=1)
    batch.emit(2, 1, 8000, 8000, pcm(2, [1000, -1000]), weight_a=3, weight_b=2)
    batch.emit(2, 1, 8000, 8000, pcm(2, [1000, -1000]), weight_a=5, weight_b=0)
    batch.emit(2, 1, 8000, 16000, pcm(2, [-32768, 32767]))
    batch.emit(2, 1, 8000, 16000, pcm(2, [1, -1, 1, -1, 1, -1]))
    batch.emit(2, 1, 8000, 16000, pcm(2, [0, 0, 0, 0]))

    # continued state (deterministic seed call on the reference)
    seed_response = sample_oracle(
        ratecv=[
            {
                "width": 2,
                "nchannels": 1,
                "inrate": 8000,
                "outrate": 16000,
                "fragment_hex": pcm(2, [-10, -9, -8, -7]).hex(),
                "state": None,
                "weightA": 1,
                "weightB": 0,
            }
        ]
    )
    seed = seed_response["ratecv"][0]["state"]
    state_tuple = (
        seed["d"],
        tuple(tuple(pair) for pair in seed["channels"]),
    )
    batch.emit(2, 1, 8000, 16000, pcm(2, [-6, -5, -4, -3]), state=state_tuple)
    seed_response2 = sample_oracle(
        ratecv=[
            {
                "width": 2,
                "nchannels": 2,
                "inrate": 8000,
                "outrate": 16000,
                "fragment_hex": pcm(2, [1, 2, 3, 4]).hex(),
                "state": None,
                "weightA": 1,
                "weightB": 0,
            }
        ]
    )
    seed2 = seed_response2["ratecv"][0]["state"]
    state_tuple2 = (
        seed2["d"],
        tuple(tuple(pair) for pair in seed2["channels"]),
    )
    batch.emit(2, 2, 8000, 16000, pcm(2, [5, 6, 7, 8]), state=state_tuple2)

    # error cases
    batch.emit(0, 1, 1, 1, b"")
    batch.emit(2, 0, 1, 1, b"")
    batch.emit(2, 1, 1, 1, b"\x01")
    batch.emit(2, 1, 0, 1, b"")
    batch.emit(2, 1, 1, 0, b"")
    batch.emit(2, 1, 1, 1, b"", weight_a=0)
    batch.emit(2, 1, 1, 1, b"", weight_b=-1)
    batch.emit(2, 1, 2**40, 1, b"")
    batch.emit(2, 2**40, 1, 1, b"")
    batch.emit(4, 2**30, 1, 1, b"")

    oracle = sample_oracle(ratecv=batch.cases)
    frames = run_frames(audioop_cli, batch.bodies)
    assert len(frames) == len(batch.bodies)
    check_frames(oracle["ratecv"], frames)


def test_randomized_differential(audioop_cli: Path, sample_oracle) -> None:
    rng = random.Random(SEED)
    batch = Batch()

    rates = (8000, 16000, 11025, 22050, 44100, 48000, 3, 7, 1)
    for width in range(1, 5):
        lo, hi = bounds(width)
        for _ in range(20):
            nchannels = rng.choice([1, 1, 2, 3])
            frames_count = rng.choice([0, 1, 2, 3, 5, 9])
            values = [
                rng.choice([0, 1, -1, lo, hi, rng.randint(lo, hi)])
                for _ in range(frames_count * nchannels)
            ]
            inrate = rng.choice(rates)
            outrate = rng.choice(rates)
            weight_a = rng.choice([1, 1, 2, 3, 5])
            weight_b = rng.choice([0, 0, 1, 2])
            batch.emit(
                width,
                nchannels,
                inrate,
                outrate,
                pcm(width, values),
                weight_a=weight_a,
                weight_b=weight_b,
            )

    oracle = sample_oracle(ratecv=batch.cases)
    frames = run_frames(audioop_cli, batch.bodies)
    assert len(frames) == len(batch.bodies)
    check_frames(oracle["ratecv"], frames)


def test_chunk_equivalence_reference_and_port(audioop_cli: Path, sample_oracle) -> None:
    """ratecv(full, None) == concat(ratecv(chunk_i, state_i)) for both."""
    values = list(range(-10, 10))
    full = pcm(2, values)

    def ref_ratecv(fragment: bytes, state):
        response = sample_oracle(
            ratecv=[
                {
                    "width": 2,
                    "nchannels": 1,
                    "inrate": 8000,
                    "outrate": 16000,
                    "fragment_hex": fragment.hex(),
                    "state": None
                    if state is None
                    else {
                        "d": state[0],
                        "channels": [list(pair) for pair in state[1]],
                    },
                    "weightA": 1,
                    "weightB": 0,
                }
            ]
        )
        result = response["ratecv"][0]
        assert "error_type" not in result
        returned = result["state"]
        return bytes.fromhex(result["result_hex"]), (
            returned["d"],
            tuple(tuple(pair) for pair in returned["channels"]),
        )

    # reference: full vs chunks
    ref_out, ref_state = ref_ratecv(full, None)
    ref_parts = []
    ref_running = None
    for chunk in (full[:8], full[8:16], full[16:]):
        out, ref_running = ref_ratecv(chunk, ref_running)
        ref_parts.append(out)
    assert b"".join(ref_parts) == ref_out
    assert ref_running == ref_state

    # one-sample chunks on the reference
    ref_parts2 = []
    ref_running2 = None
    for i in range(0, len(full), 2):
        out, ref_running2 = ref_ratecv(full[i : i + 2], ref_running2)
        ref_parts2.append(out)
    assert b"".join(ref_parts2) == ref_out
    assert ref_running2 == ref_state

    # empty chunk between non-empty chunks on the reference
    ref_parts3 = []
    ref_running3 = None
    for chunk in (full[:8], b"", full[8:]):
        out, ref_running3 = ref_ratecv(chunk, ref_running3)
        ref_parts3.append(out)
    assert b"".join(ref_parts3) == ref_out
    assert ref_running3 == ref_state

    # port: full vs chunks through the CLI with state round-trips
    whole_frames = run_frames(audioop_cli, [ratecv_body(2, 1, 8000, 16000, 1, 0, None, full)])
    full_output, full_state = parse_ratecv_response(whole_frames[0][1], 1)
    assert full_output == ref_out
    assert full_state == ref_state

    port_parts = []
    running = None
    for chunk in (full[:8], full[8:16], full[16:]):
        frames = run_frames(audioop_cli, [ratecv_body(2, 1, 8000, 16000, 1, 0, running, chunk)])
        output, running = parse_ratecv_response(frames[0][1], 1)
        port_parts.append(output)
    assert b"".join(port_parts) == full_output
    assert running == full_state

    # one-sample chunks on the port
    port_parts2 = []
    running2 = None
    for i in range(0, len(full), 2):
        frames = run_frames(
            audioop_cli, [ratecv_body(2, 1, 8000, 16000, 1, 0, running2, full[i : i + 2])]
        )
        output, running2 = parse_ratecv_response(frames[0][1], 1)
        port_parts2.append(output)
    assert b"".join(port_parts2) == full_output
    assert running2 == full_state

    # empty chunk between non-empty chunks on the port
    port_parts3 = []
    running3 = None
    for chunk in (full[:8], b"", full[8:]):
        frames = run_frames(audioop_cli, [ratecv_body(2, 1, 8000, 16000, 1, 0, running3, chunk)])
        output, running3 = parse_ratecv_response(frames[0][1], 1)
        port_parts3.append(output)
    assert b"".join(port_parts3) == full_output
    assert running3 == full_state
