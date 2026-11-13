"""Byte-level tests for the bitarray batch CLI framing protocol."""

from __future__ import annotations

import struct
from pathlib import Path

STATUS_OK = 0
STATUS_ERROR = 1
MAX_FRAME_BYTES = 64 * 1024 * 1024


def request(body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + body


def run_cli(binary: Path, data: bytes, timeout: float = 60) -> tuple[int, bytes, bytes]:
    import subprocess

    result = subprocess.run(
        [str(binary)],
        input=data,
        capture_output=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def parse_frames(payload: bytes) -> list[tuple[int, bytes]]:
    frames: list[tuple[int, bytes]] = []
    offset = 0
    while offset < len(payload):
        assert len(payload) - offset >= 4, "truncated response header"
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        offset += 4
        assert len(payload) - offset >= length, "truncated response body"
        body = payload[offset : offset + length]
        offset += length
        assert body, "response body must contain a status byte"
        frames.append((body[0], body[1:]))
    return frames


def framed(nbits: int, endian_id: int, data: bytes) -> bytes:
    return struct.pack(">I", nbits) + bytes([endian_id]) + data


def test_ping_and_echo(bitarray_cli: Path) -> None:
    returncode, stdout, stderr = run_cli(
        bitarray_cli, request(b"\x01") + request(b"\x02\x00\xffhello")
    )
    assert returncode == 0
    assert stderr == b""
    assert parse_frames(stdout) == [(STATUS_OK, b""), (STATUS_OK, b"\x00\xffhello")]


def test_clean_eof_exits_zero_without_output(bitarray_cli: Path) -> None:
    returncode, stdout, stderr = run_cli(bitarray_cli, b"")
    assert returncode == 0
    assert stdout == b""
    assert stderr == b""


def test_unknown_opcode_and_empty_frame(bitarray_cli: Path) -> None:
    returncode, stdout, stderr = run_cli(bitarray_cli, request(b"\x99") + request(b""))
    assert returncode == 0
    assert stderr == b""
    assert parse_frames(stdout) == [
        (STATUS_ERROR, b"unknown opcode 153"),
        (STATUS_ERROR, b"empty request frame"),
    ]


def test_encode_decode_roundtrip(bitarray_cli: Path) -> None:
    data = request(b"\x11\x00" + b"10110") + request(b"\x10" + framed(5, 0, b"\xb0"))
    returncode, stdout, stderr = run_cli(bitarray_cli, data)
    assert returncode == 0
    assert stderr == b""
    assert parse_frames(stdout) == [
        (STATUS_OK, framed(5, 0, b"\xb0")),
        (STATUS_OK, b"10110"),
    ]


def test_encode_little_endian(bitarray_cli: Path) -> None:
    returncode, stdout, _ = run_cli(bitarray_cli, request(b"\x11\x01" + b"10110"))
    assert returncode == 0
    assert parse_frames(stdout) == [(STATUS_OK, framed(5, 1, b"\r"))]


def test_encode_empty(bitarray_cli: Path) -> None:
    returncode, stdout, _ = run_cli(bitarray_cli, request(b"\x11\x00"))
    assert returncode == 0
    assert parse_frames(stdout) == [(STATUS_OK, framed(0, 0, b""))]


def test_encode_rejects_bad_input(bitarray_cli: Path) -> None:
    data = request(b"\x11\x05" + b"101") + request(b"\x11\x00" + b"102")
    returncode, stdout, _ = run_cli(bitarray_cli, data)
    assert returncode == 0
    frames = parse_frames(stdout)
    assert frames[0][0] == STATUS_ERROR
    assert b"invalid endian identifier" in frames[0][1]
    assert frames[1][0] == STATUS_ERROR
    assert b"expected '0' or '1'" in frames[1][1]


def test_decode_rejects_malformed_payloads(bitarray_cli: Path) -> None:
    bodies = [
        # Too short for nbits + endian id.
        b"\x10" + framed(5, 0, b"")[:3],
        # Bad endian identifier.
        b"\x10" + framed(5, 2, b"\xb0"),
        # Short and long byte counts.
        b"\x10" + framed(9, 0, b"\xb0"),
        b"\x10" + framed(5, 0, b"\xb0\xff"),
        # Nonzero padding, big-endian (low pad bit set) and
        # little-endian (top pad bit set).
        b"\x10" + framed(5, 0, b"\xb1"),
        b"\x10" + framed(5, 1, b"\x8d"),
    ]
    returncode, stdout, _ = run_cli(bitarray_cli, b"".join(request(b) for b in bodies))
    assert returncode == 0
    frames = parse_frames(stdout)
    assert [status for status, _ in frames] == [STATUS_ERROR] * len(bodies)
    assert b"too short" in frames[0][1]
    assert b"invalid endian" in frames[1][1]
    assert b"byte count" in frames[2][1]
    assert b"byte count" in frames[3][1]
    assert b"nonzero padding" in frames[4][1]
    assert b"nonzero padding" in frames[5][1]


def test_decode_empty_and_boundaries(bitarray_cli: Path) -> None:
    data = request(b"\x10" + framed(0, 0, b"")) + request(b"\x10" + framed(1, 1, b"\x01"))
    returncode, stdout, _ = run_cli(bitarray_cli, data)
    assert returncode == 0
    assert parse_frames(stdout) == [(STATUS_OK, b""), (STATUS_OK, b"1")]


def test_batch_mode_answers_in_order(bitarray_cli: Path) -> None:
    data = (
        request(b"\x01")
        + request(b"\x11\x00" + b"1")
        + request(b"\x10" + framed(1, 0, b"\x80"))
        + request(b"\x99")
        + request(b"")
    )
    returncode, stdout, stderr = run_cli(bitarray_cli, data)
    assert returncode == 0
    assert stderr == b""
    assert parse_frames(stdout) == [
        (STATUS_OK, b""),
        (STATUS_OK, framed(1, 0, b"\x80")),
        (STATUS_OK, b"1"),
        (STATUS_ERROR, b"unknown opcode 153"),
        (STATUS_ERROR, b"empty request frame"),
    ]


def test_truncated_frame_fails_safely(bitarray_cli: Path) -> None:
    # A truncated body is a framing error: one error frame on stdout,
    # a diagnostic on stderr, and a non-zero exit (same as msgpack).
    returncode, stdout, stderr = run_cli(
        bitarray_cli, struct.pack(">I", 40) + b"\x10\x00\x00\x00\x05"
    )
    assert returncode != 0
    assert b"framing error" in stdout or b"framing error" in stderr
