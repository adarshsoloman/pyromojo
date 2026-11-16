"""Framing tests for the four Phase 7 G.711 opcodes."""

from __future__ import annotations

import struct
from pathlib import Path

from support import (
    OP_PING,
    STATUS_ERROR,
    STATUS_OK,
    alaw2lin_body,
    lin2alaw_body,
    lin2ulaw_body,
    run_frames,
    ulaw2lin_body,
)


def test_phase6_opcodes_still_work(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            bytes([OP_PING]),
            bytes([0x35, 2]) + struct.pack(">q", 1) * 5 + b"\x00" + b"\xe8\x03\x18\xfc",
        ],
    )
    assert frames[0] == (STATUS_OK, b"")
    assert frames[1][0] == STATUS_OK


def test_encoders_roundtrip(audioop_cli: Path) -> None:
    lin = b"\x00\x00\x01\x00\xff\xff\x04\x00"
    frames = run_frames(
        audioop_cli,
        [
            lin2alaw_body(2, lin),
            lin2ulaw_body(2, lin),
        ],
    )
    assert frames == [
        (STATUS_OK, b"\xd5\xd5\x55\xd5"),
        (STATUS_OK, b"\xff\xff\x7e\xfe"),
    ]


def test_decoders_roundtrip(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            alaw2lin_body(2, b"\x00\xd5\x55\x2a"),
            ulaw2lin_body(2, b"\x00\x7f\x80\xff"),
        ],
    )
    assert frames == [
        (STATUS_OK, b"\x80\xea\x08\x00\xf8\xff\x00\x82"),
        (STATUS_OK, b"\x84\x82\x00\x00\x7c\x7d\x00\x00"),
    ]


def test_decoder_no_alignment(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            alaw2lin_body(2, b"\x01\x02\x03"),
            ulaw2lin_body(2, b"\x01"),
            alaw2lin_body(2, b""),
            ulaw2lin_body(2, b""),
        ],
    )
    assert frames[0][0] == STATUS_OK
    assert len(frames[0][1]) == 6
    assert frames[1][0] == STATUS_OK
    assert len(frames[1][1]) == 2
    assert frames[2] == (STATUS_OK, b"")
    assert frames[3] == (STATUS_OK, b"")


def test_encoder_widths(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            lin2alaw_body(1, b"\x7f\x80"),
            lin2ulaw_body(1, b"\x7f\x80"),
            lin2alaw_body(4, b"\xff\xff\xff\x7f\x00\x00\x00\x80"),
            lin2ulaw_body(4, b"\xff\xff\xff\x7f\x00\x00\x00\x80"),
        ],
    )
    assert frames == [
        (STATUS_OK, b"\xaa\x2a"),
        (STATUS_OK, b"\x80\x00"),
        (STATUS_OK, b"\xaa\x2a"),
        (STATUS_OK, b"\x80\x00"),
    ]


def test_errors_are_frames(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            lin2alaw_body(0, b""),
            lin2ulaw_body(0, b""),
            alaw2lin_body(0, b""),
            ulaw2lin_body(0, b""),
            lin2alaw_body(2, b"\x01\x02\x03"),
            lin2ulaw_body(2, b"\x01"),
            lin2alaw_body(5, b""),
        ],
    )
    assert frames[0] == (STATUS_ERROR, b"Size should be 1, 2, 3 or 4")
    assert frames[1] == (STATUS_ERROR, b"Size should be 1, 2, 3 or 4")
    assert frames[2] == (STATUS_ERROR, b"Size should be 1, 2, 3 or 4")
    assert frames[3] == (STATUS_ERROR, b"Size should be 1, 2, 3 or 4")
    assert frames[4] == (STATUS_ERROR, b"not a whole number of frames")
    assert frames[5] == (STATUS_ERROR, b"not a whole number of frames")
    assert frames[6] == (STATUS_ERROR, b"Size should be 1, 2, 3 or 4")


def test_requests_too_short(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [bytes([0x36]), bytes([0x37]), bytes([0x38]), bytes([0x39])],
    )
    assert frames[0] == (STATUS_ERROR, b"lin2alaw request too short: need a width byte")
    assert frames[1] == (STATUS_ERROR, b"alaw2lin request too short: need a width byte")
    assert frames[2] == (STATUS_ERROR, b"lin2ulaw request too short: need a width byte")
    assert frames[3] == (STATUS_ERROR, b"ulaw2lin request too short: need a width byte")


def test_large_fragment(audioop_cli: Path) -> None:
    lin = bytes(4096)
    frames = run_frames(audioop_cli, [lin2alaw_body(2, lin)])
    assert frames[0][1] == b"\xd5" * 2048


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
