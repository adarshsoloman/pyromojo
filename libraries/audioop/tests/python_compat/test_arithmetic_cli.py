"""Framing tests for the six Phase 2 CLI opcodes."""

from __future__ import annotations

import struct
from pathlib import Path

from support import (
    OP_PING,
    STATUS_ERROR,
    STATUS_OK,
    add_body,
    bias_body,
    byteswap_body,
    decode_body,
    encode_body,
    lin2lin_body,
    mul_body,
    reverse_body,
    run_frames,
)


def test_phase1_opcodes_still_work(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli, [bytes([OP_PING]), decode_body(2, b"\x34\x12"), encode_body(2, [4660])]
    )
    assert frames == [
        (STATUS_OK, b""),
        (STATUS_OK, b"4660"),
        (STATUS_OK, b"\x34\x12"),
    ]


def test_add_roundtrip(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [add_body(2, b"\x01\x00\x02\x00", b"\x01\x00\x02\x00")])
    assert frames == [(STATUS_OK, b"\x02\x00\x04\x00")]


def test_bias_roundtrip(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [bias_body(2, -1, b"\x01\x00")])
    assert frames == [(STATUS_OK, b"\x00\x00")]


def test_mul_roundtrip_with_float_bits(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [mul_body(2, 0.5, b"\x06\x00\xfd\xff")])
    assert frames == [(STATUS_OK, b"\x03\x00\xfe\xff")]


def test_reverse_and_byteswap_roundtrips(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            reverse_body(2, b"\x01\x00\x02\x00\x03\x00"),
            byteswap_body(2, b"\x01\x00\x02\x00"),
        ],
    )
    assert frames == [
        (STATUS_OK, b"\x03\x00\x02\x00\x01\x00"),
        (STATUS_OK, b"\x00\x01\x00\x02"),
    ]


def test_lin2lin_roundtrip(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [lin2lin_body(2, 4, b"\x01\x00\xff\xff")])
    assert frames == [(STATUS_OK, b"\x00\x00\x01\x00\x00\x00\xff\xff")]


def test_add_request_too_short(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            bytes([0x22, 2]),
            bytes([0x22, 2]) + b"\x00\x00\x00\x0a" + b"\x01\x00\x02\x00",
        ],
    )
    assert frames[0] == (STATUS_ERROR, b"add request too short: need width and first length")
    assert frames[1] == (STATUS_ERROR, b"add request too short: first fragment is missing")


def test_bias_mul_lin2lin_requests_too_short(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [bytes([0x23, 2]), bytes([0x24, 2]), bytes([0x27, 2]), bytes([0x27, 2, 3])],
    )
    assert frames[0] == (STATUS_ERROR, b"bias request too short: need width and bias")
    assert frames[1] == (STATUS_ERROR, b"mul request too short: need width and factor")
    assert frames[2] == (STATUS_ERROR, b"lin2lin request too short: need width and new width")
    # lin2lin with only a width byte and empty fragment is valid (4 bytes = 1+1+2? no: 3 bytes)
    # frames[3] has width + newwidth but zero-length fragment -> valid empty result
    assert frames[3] == (STATUS_OK, b"")


def test_reverse_byteswap_need_width(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [bytes([0x25]), bytes([0x26])])
    assert frames[0] == (STATUS_ERROR, b"reverse request too short: need a width byte")
    assert frames[1] == (STATUS_ERROR, b"byteswap request too short: need a width byte")


def test_operation_errors_are_frames(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            add_body(2, b"\x01\x00", b"\x01\x00\x02\x00"),
            bias_body(2, 2**40, b"\x01\x00"),
            lin2lin_body(0, 2, b""),
            reverse_body(2, b"\x01"),
            byteswap_body(5, b""),
        ],
    )
    assert frames[0] == (STATUS_ERROR, b"Lengths should be the same")
    assert frames[1] == (STATUS_ERROR, b"Python int too large to convert to C int")
    assert frames[2] == (STATUS_ERROR, b"Size should be 1, 2, 3 or 4")
    assert frames[3] == (STATUS_ERROR, b"not a whole number of frames")
    assert frames[4] == (STATUS_ERROR, b"Size should be 1, 2, 3 or 4")


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
