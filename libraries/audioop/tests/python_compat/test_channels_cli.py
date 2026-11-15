"""Framing tests for the two Phase 5 channel opcodes."""

from __future__ import annotations

import struct
from pathlib import Path

from support import (
    OP_PING,
    STATUS_ERROR,
    STATUS_OK,
    run_frames,
    tomono_body,
    tostereo_body,
)


def test_phase4_opcodes_still_work(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [bytes([OP_PING]), bytes([0x25, 2, 1, 0, 2, 0])])
    assert frames == [(STATUS_OK, b""), (STATUS_OK, b"\x02\x00\x01\x00")]


def test_tomono_roundtrip(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli, [tomono_body(2, 0.5, 0.5, b"\x01\x00\x03\x00\x02\x00\x04\x00")]
    )
    assert frames == [(STATUS_OK, b"\x02\x00\x03\x00")]


def test_tostereo_roundtrip(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [tostereo_body(2, 1.0, 1.0, b"\x05\x00")])
    assert frames == [(STATUS_OK, b"\x05\x00\x05\x00")]


def test_factor_bits_transport(audioop_cli: Path) -> None:
    # factors travel as IEEE-754 bits, so nan and inf survive exactly
    frames = run_frames(
        audioop_cli,
        [
            tomono_body(2, float("nan"), 0.5, b"\x01\x00\x02\x00\x03\x00\x04\x00"),
            tomono_body(2, float("inf"), 0.5, b"\x01\x00\x02\x00\x03\x00\x04\x00"),
            tomono_body(2, float("-inf"), 0.5, b"\x01\x00\x02\x00\x03\x00\x04\x00"),
        ],
    )
    assert frames == [
        (STATUS_OK, b"\x00\x00\x00\x00"),
        (STATUS_OK, b"\xff\x7f\xff\x7f"),
        (STATUS_OK, b"\x00\x80\x00\x80"),
    ]


def test_tomono_alignment_errors(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            tomono_body(2, 1.0, 1.0, b""),
            tomono_body(2, 1.0, 1.0, b"\x05\x00"),
            tomono_body(2, 1.0, 1.0, b"\x01\x00\x02\x00\x03\x00"),
            tomono_body(2, 1.0, 1.0, b"\x01"),
        ],
    )
    assert frames == [
        (STATUS_OK, b""),
        (STATUS_ERROR, b"not a whole number of frames"),
        (STATUS_ERROR, b"not a whole number of frames"),
        (STATUS_ERROR, b"not a whole number of frames"),
    ]


def test_tostereo_alignment_and_width(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            tostereo_body(2, 1.0, 1.0, b""),
            tostereo_body(2, 1.0, 1.0, b"\x05\x00"),
            tostereo_body(0, 1.0, 1.0, b""),
            tostereo_body(2, 1.0, 1.0, b"\x01"),
        ],
    )
    assert frames == [
        (STATUS_OK, b""),
        (STATUS_OK, b"\x05\x00\x05\x00"),
        (STATUS_ERROR, b"Size should be 1, 2, 3 or 4"),
        (STATUS_ERROR, b"not a whole number of frames"),
    ]


def test_requests_too_short(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            bytes([0x33]),
            bytes([0x33, 2]) + b"\x00" * 8,
            bytes([0x33, 2]) + b"\x00" * 15,
            bytes([0x34]),
            bytes([0x34, 2]) + b"\x00" * 8,
            bytes([0x34, 2]) + b"\x00" * 15,
        ],
    )
    for status, payload in frames:
        assert status == STATUS_ERROR
        assert payload in (
            b"tomono request too short: need width and two factors",
            b"tostereo request too short: need width and two factors",
        )


def test_saturation_boundaries(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            tomono_body(2, 1.0, 1.0, b"\xff\x7f\xff\x7f"),
            tomono_body(2, 1.0, 1.0, b"\x00\x80\x00\x80"),
            tomono_body(4, 1.0, 1.0, struct.pack("<2i", 2**31 - 1, -(2**31))),
            tostereo_body(2, 2.0, 2.0, b"\xff\x7f"),
            tostereo_body(2, 2.0, 2.0, b"\x00\x80"),
        ],
    )
    assert frames == [
        (STATUS_OK, b"\xff\x7f"),
        (STATUS_OK, b"\x00\x80"),
        (STATUS_OK, b"\xff\xff\xff\xff"),
        (STATUS_OK, b"\xff\x7f\xff\x7f"),
        (STATUS_OK, b"\x00\x80\x00\x80"),
    ]


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
