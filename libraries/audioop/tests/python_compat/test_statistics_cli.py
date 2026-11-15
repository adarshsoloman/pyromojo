"""Framing tests for the six Phase 3 statistics opcodes."""

from __future__ import annotations

import struct
from pathlib import Path

from support import (
    OP_PING,
    STATUS_ERROR,
    STATUS_OK,
    avg_body,
    cross_body,
    getsample_body,
    max_body,
    minmax_body,
    rms_body,
    run_frames,
)


def test_phase2_opcodes_still_work(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [bytes([OP_PING]), bytes([0x25, 2, 1, 0, 2, 0])])
    assert frames == [(STATUS_OK, b""), (STATUS_OK, b"\x02\x00\x01\x00")]


def test_getsample_roundtrip(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [getsample_body(2, 2, b"\x01\x00\x02\x00\x03\x00")],
    )
    assert frames == [(STATUS_OK, b"3")]


def test_scalar_roundtrips(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            max_body(2, b"\x01\x00\xff\xff"),
            avg_body(2, b"\xfd\xff\xfe\xff"),
            rms_body(2, b"\x01\x00\x02\x00"),
            cross_body(2, b"\x01\x00\xff\xff"),
        ],
    )
    assert frames == [(STATUS_OK, b"1"), (STATUS_OK, b"-3"), (STATUS_OK, b"1"), (STATUS_OK, b"1")]


def test_minmax_roundtrip_and_sentinel(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            minmax_body(2, b"\x01\x00\xff\xff"),
            minmax_body(2, b""),
        ],
    )
    assert frames == [
        (STATUS_OK, b"-1 1"),
        (STATUS_OK, b"2147483647 -2147483648"),
    ]


def test_getsample_index_transport(audioop_cli: Path) -> None:
    # int64_be index: negative and large indices both reach the port
    frames = run_frames(
        audioop_cli,
        [
            getsample_body(2, -1, b"\x01\x00"),
            getsample_body(2, 2**40, b"\x01\x00"),
            getsample_body(2, 0, b""),
        ],
    )
    for status, payload in frames:
        assert status == STATUS_ERROR
        assert payload == b"Index out of range"


def test_requests_too_short(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            bytes([0x28, 2]),
            bytes([0x28, 2]) + b"\x00" * 7,
            bytes([0x29]),
            bytes([0x2A]),
            bytes([0x2B]),
            bytes([0x2C]),
            bytes([0x2D]),
        ],
    )
    assert frames[0] == (STATUS_ERROR, b"getsample request too short: need width and index")
    assert frames[1] == (STATUS_ERROR, b"getsample request too short: need width and index")
    assert frames[2] == (STATUS_ERROR, b"max request too short: need a width byte")
    assert frames[3] == (STATUS_ERROR, b"minmax request too short: need a width byte")
    assert frames[4] == (STATUS_ERROR, b"avg request too short: need a width byte")
    assert frames[5] == (STATUS_ERROR, b"rms request too short: need a width byte")
    assert frames[6] == (STATUS_ERROR, b"cross request too short: need a width byte")


def test_operation_errors_are_frames(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            max_body(0, b""),
            minmax_body(5, b""),
            avg_body(2, b"\x01"),
            rms_body(2, b"\x01"),
            cross_body(2, b"\x01"),
            getsample_body(0, 0, b""),
        ],
    )
    for status, payload in frames:
        assert status == STATUS_ERROR
        assert payload in (
            b"Size should be 1, 2, 3 or 4",
            b"not a whole number of frames",
        )


def test_empty_fragments_are_valid(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            max_body(2, b""),
            avg_body(2, b""),
            rms_body(2, b""),
            cross_body(2, b""),
        ],
    )
    assert frames == [
        (STATUS_OK, b"0"),
        (STATUS_OK, b"0"),
        (STATUS_OK, b"0"),
        (STATUS_OK, b"-1"),
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
