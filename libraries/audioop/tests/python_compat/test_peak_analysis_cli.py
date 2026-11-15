"""Framing tests for the five Phase 4 CLI opcodes."""

from __future__ import annotations

import struct
from pathlib import Path

from support import (
    OP_PING,
    STATUS_ERROR,
    STATUS_OK,
    avgpp_body,
    findfactor_body,
    findfit_body,
    findmax_body,
    maxpp_body,
    parse_double_bits,
    parse_fit,
    run_frames,
)


def test_phase3_opcodes_still_work(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [bytes([OP_PING]), bytes([0x29, 2, 1, 0, 255, 255])])
    assert frames == [(STATUS_OK, b""), (STATUS_OK, b"1")]


def test_avgpp_maxpp_roundtrips(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            avgpp_body(2, b"\x01\x00\x03\x00\x01\x00\x03\x00"),
            maxpp_body(2, b"\x01\x00\x03\x00\x01\x00\x03\x00"),
            maxpp_body(4, struct.pack("<5i", 2**31 - 1, -(2**31), 2**31 - 1, -(2**31), 2**31 - 1)),
        ],
    )
    assert frames == [
        (STATUS_OK, b"2"),
        (STATUS_OK, b"2"),
        (STATUS_OK, b"4294967295"),
    ]


def test_findmax_roundtrip(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            findmax_body(2, b"\x00\x00\xe8\x00\xc8\x00\x2c\x01"),
            findmax_body(0, b"\x01\x00\x02\x00"),
        ],
    )
    assert frames == [(STATUS_OK, b"2"), (STATUS_OK, b"0")]


def test_findfactor_bits_roundtrip(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            findfactor_body(b"\x01\x00\x02\x00\x03\x00", b"\x01\x00\x02\x00\x03\x00"),
            findfactor_body(b"\x02\x00\x04\x00\x06\x00", b"\x01\x00\x02\x00\x03\x00"),
        ],
    )
    assert parse_double_bits(frames[0][1]) == 1.0
    assert parse_double_bits(frames[1][1]) == 2.0


def test_findfit_bits_roundtrip(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            findfit_body(b"\x09\x00\x01\x00\x02\x00\x03\x00", b"\x01\x00\x02\x00\x03\x00"),
            findfit_body(b"\x05\x00\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00", b"\x01\x00\x02\x00"),
        ],
    )
    index, factor = parse_fit(frames[0][1])
    assert (index, factor) == (1, 1.0)
    index, factor = parse_fit(frames[1][1])
    assert (index, factor) == (0, 3.4)


def test_nan_transport_is_bit_exact(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            findfactor_body(b"\x01\x00\x02\x00", b"\x00\x00\x00\x00"),
            findfit_body(b"", b""),
        ],
    )
    reference_nan = struct.pack(">d", float("nan"))
    # the port and the reference both produce -nan (0xfff8...); compare bits
    assert frames[0][1] == b"\xff\xf8\x00\x00\x00\x00\x00\x00"
    index, factor = parse_fit(frames[1][1])
    assert (index, struct.pack(">d", factor)) == (0, b"\xff\xf8\x00\x00\x00\x00\x00\x00")
    _ = reference_nan


def test_requests_too_short(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            bytes([0x2E]),
            bytes([0x2F]),
            bytes([0x30]) + b"\x00" * 4,
            bytes([0x31]),
            bytes([0x31]) + b"\x00\x00\x00\x0a" + b"\x01\x00",
            bytes([0x32]),
            bytes([0x32]) + b"\x00\x00\x00\x0a" + b"\x01\x00",
        ],
    )
    assert frames[0] == (STATUS_ERROR, b"avgpp request too short: need a width byte")
    assert frames[1] == (STATUS_ERROR, b"maxpp request too short: need a width byte")
    assert frames[2] == (STATUS_ERROR, b"findmax request too short: need a length")
    assert frames[3] == (STATUS_ERROR, b"findfactor request too short: need the first length")
    assert frames[4] == (STATUS_ERROR, b"findfactor request too short: first fragment is missing")
    assert frames[5] == (STATUS_ERROR, b"findfit request too short: need the first length")
    assert frames[6] == (STATUS_ERROR, b"findfit request too short: first fragment is missing")


def test_operation_errors_are_frames(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            avgpp_body(0, b""),
            maxpp_body(2, b"\x01"),
            findmax_body(3, b"\x00\x00\x01\x00"),
            findmax_body(-1, b"\x00\x00\x01\x00"),
            findfactor_body(b"\x01\x00", b"\x01\x00\x02\x00\x03\x00"),
            findfit_body(b"\x01\x00", b"\x01\x00\x02\x00\x03\x00"),
        ],
    )
    assert frames[0][1] == b"Size should be 1, 2, 3 or 4"
    assert frames[1][1] == b"not a whole number of frames"
    assert frames[2][1] == b"Input sample should be longer"
    assert frames[3][1] == b"Input sample should be longer"
    assert frames[4][1] == b"Samples should be same size"
    assert frames[5][1] == b"First sample should be longer"
    for status, _ in frames:
        assert status == STATUS_ERROR


def test_odd_byte_errors(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            findmax_body(1, b"\x01\x02\x03"),
            findfactor_body(b"\x01\x02\x03", b"\x01\x02\x03\x04"),
            findfit_body(b"\x01\x02\x03", b"\x01\x02"),
        ],
    )
    for status, payload in frames:
        assert status == STATUS_ERROR
        assert payload == b"Strings should be even-sized"


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
