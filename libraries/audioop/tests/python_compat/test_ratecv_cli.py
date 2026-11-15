"""Framing and protocol tests for the Phase 6 ratecv opcode."""

from __future__ import annotations

import struct
from pathlib import Path

from support import (
    OP_PING,
    STATUS_ERROR,
    STATUS_OK,
    parse_ratecv_response,
    ratecv_body,
    run_frames,
)


def test_phase5_opcodes_still_work(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            bytes([OP_PING]),
            bytes([0x33, 2])
            + struct.pack(">d", 0.5)
            + struct.pack(">d", 0.5)
            + b"\x01\x00\x03\x00",
        ],
    )
    assert frames == [(STATUS_OK, b""), (STATUS_OK, b"\x02\x00")]


def test_ratecv_fresh_state_roundtrip(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [ratecv_body(2, 1, 8000, 8000, 1, 0, None, b"\xe8\x03")],
    )
    output, state = parse_ratecv_response(frames[0][1], 1)
    assert output == b"\xe8\x03"
    assert state == (-1, ((0, 65536000),))


def test_ratecv_state_roundtrip_and_chunks(audioop_cli: Path) -> None:
    fragment = b"".join(value.to_bytes(2, "little", signed=True) for value in range(-10, 10))
    first = run_frames(audioop_cli, [ratecv_body(2, 1, 8000, 16000, 1, 0, None, fragment[:8])])
    first_output, state = parse_ratecv_response(first[0][1], 1)

    parts = [first_output]
    for chunk in (fragment[8:16], fragment[16:]):
        frames = run_frames(audioop_cli, [ratecv_body(2, 1, 8000, 16000, 1, 0, state, chunk)])
        output, state = parse_ratecv_response(frames[0][1], 1)
        parts.append(output)
    # chunked output must equal the fresh full conversion
    whole = run_frames(audioop_cli, [ratecv_body(2, 1, 8000, 16000, 1, 0, None, fragment)])
    full_output, full_state = parse_ratecv_response(whole[0][1], 1)
    assert b"".join(parts) == full_output
    assert state == full_state


def test_ratecv_multichannel(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            ratecv_body(
                2,
                2,
                8000,
                8000,
                1,
                0,
                None,
                b"\x64\x00\x9c\xff\xc8\x00\x38\xff",
            )
        ],
    )
    output, state = parse_ratecv_response(frames[0][1], 2)
    assert output == b"\x64\x00\x9c\xff\xc8\x00\x38\xff"
    assert state == (-1, ((6553600, 13107200), (-6553600, -13107200)))


def test_ratecv_empty_fragment(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [ratecv_body(2, 1, 8000, 16000, 1, 0, None, b"")])
    output, state = parse_ratecv_response(frames[0][1], 1)
    assert output == b""
    assert state == (-2, ((0, 0),))


def test_ratecv_error_frames(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            ratecv_body(0, 1, 1, 1, 1, 0, None, b""),
            ratecv_body(2, 0, 1, 1, 1, 0, None, b""),
            ratecv_body(2, 1, 1, 1, 0, 0, None, b""),
            ratecv_body(2, 1, 1, 1, 1, -1, None, b""),
            ratecv_body(2, 1, 0, 1, 1, 0, None, b""),
            ratecv_body(2, 1, 1, 1, 1, 0, None, b"\x01"),
        ],
    )
    assert frames[0] == (STATUS_ERROR, b"Size should be 1, 2, 3 or 4")
    assert frames[1] == (STATUS_ERROR, b"# of channels should be >= 1")
    assert frames[2] == (
        STATUS_ERROR,
        b"weightA should be >= 1, weightB should be >= 0",
    )
    assert frames[3] == (
        STATUS_ERROR,
        b"weightA should be >= 1, weightB should be >= 0",
    )
    assert frames[4] == (STATUS_ERROR, b"sampling rate not > 0")
    assert frames[5] == (STATUS_ERROR, b"not a whole number of frames")


def test_ratecv_malformed_requests(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            bytes([0x35]),
            bytes([0x35, 2]) + b"\x00" * 37,
            bytes([0x35, 2]) + struct.pack(">q", 1) * 4 + b"\x01" + struct.pack(">q", 5),
        ],
    )
    for status, payload in frames:
        assert status == STATUS_ERROR
        assert b"too short" in payload


def test_ratecv_state_channel_count(audioop_cli: Path) -> None:
    # state with two channel pairs for a 1-channel request: the CLI reads
    # exactly one pair and passes the rest to the fragment, which then
    # fails frame alignment
    body = (
        bytes([0x35, 2])
        + struct.pack(">q", 1)
        + struct.pack(">q", 8000)
        + struct.pack(">q", 8000)
        + struct.pack(">q", 1)
        + struct.pack(">q", 0)
        + b"\x01"
        + struct.pack(">q", -1)
        + struct.pack(">q", 0)
        + struct.pack(">q", 65536000)
        + struct.pack(">q", 0)
        + struct.pack(">q", 0)
        + b"\xe8"
    )
    frames = run_frames(audioop_cli, [body])
    status, payload = frames[0]
    # the CLI reads one state pair; the trailing pair plus the fragment
    # form a fragment that is misaligned for width 2
    assert status == STATUS_ERROR
    assert b"not a whole number of frames" in payload


def test_unknown_opcode_still_rejected(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [b"\x99"])
    assert frames == [(STATUS_ERROR, b"unknown opcode 153")]


def test_frame_cap_still_enforced(audioop_cli: Path) -> None:
    import subprocess

    result = subprocess.run(
        [str(audioop_cli)],
        input=struct.pack(">I", 64 * 1024 * 1024 + 1) + b"\x01" * 8,
        capture_output=True,
    )
    assert result.returncode != 0
    assert b"exceeds limit" in result.stderr
