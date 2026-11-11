"""Byte-level tests for the batch CLI framing protocol."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

STATUS_OK = 0
STATUS_ERROR = 1
STATUS_UNIMPLEMENTED = 2
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


def test_ping_and_echo(msgpack_cli: Path) -> None:
    returncode, stdout, stderr = run_cli(
        msgpack_cli, request(b"\x01") + request(b"\x02\x00\xffhello")
    )
    assert returncode == 0
    assert stderr == b""
    assert parse_frames(stdout) == [(STATUS_OK, b""), (STATUS_OK, b"\x00\xffhello")]


def test_clean_eof_exits_zero_without_output(msgpack_cli: Path) -> None:
    returncode, stdout, stderr = run_cli(msgpack_cli, b"")
    assert returncode == 0
    assert stdout == b""
    assert stderr == b""


def test_clean_eof_after_frames(msgpack_cli: Path) -> None:
    returncode, stdout, _ = run_cli(msgpack_cli, request(b"\x01"))
    assert returncode == 0
    assert parse_frames(stdout) == [(STATUS_OK, b"")]


def test_unknown_opcode_is_an_error_frame(msgpack_cli: Path) -> None:
    returncode, stdout, stderr = run_cli(msgpack_cli, request(b"\x99"))
    assert returncode == 0
    assert stderr == b""
    frames = parse_frames(stdout)
    assert frames[0][0] == STATUS_ERROR
    assert b"unknown opcode" in frames[0][1]


def test_empty_request_body_is_an_error_frame(msgpack_cli: Path) -> None:
    returncode, stdout, _ = run_cli(msgpack_cli, request(b""))
    assert returncode == 0
    frames = parse_frames(stdout)
    assert frames == [(STATUS_ERROR, b"empty request frame")]


def test_decode_and_encode_are_unimplemented(msgpack_cli: Path) -> None:
    returncode, stdout, _ = run_cli(msgpack_cli, request(b"\x10\xc0") + request(b"\x11\xc0"))
    assert returncode == 0
    frames = parse_frames(stdout)
    assert [status for status, _ in frames] == [STATUS_UNIMPLEMENTED, STATUS_UNIMPLEMENTED]
    assert b"Phase 1" in frames[0][1]


def test_echo_is_binary_safe_and_handles_pipe_chunks(msgpack_cli: Path) -> None:
    payload = bytes(range(256)) * 4096
    returncode, stdout, stderr = run_cli(msgpack_cli, request(b"\x02" + payload))
    assert returncode == 0
    assert stderr == b""
    assert parse_frames(stdout) == [(STATUS_OK, payload)]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"\x00\x00", b"truncated frame header"),
        (struct.pack(">I", 3) + b"\x01", b"truncated frame body"),
        (struct.pack(">I", MAX_FRAME_BYTES + 1), b"exceeds limit"),
    ],
)
def test_framing_errors_emit_one_error_frame_and_fail(
    msgpack_cli: Path, data: bytes, message: bytes
) -> None:
    returncode, stdout, stderr = run_cli(msgpack_cli, data)
    assert returncode != 0
    assert stderr != b""
    frames = parse_frames(stdout)
    assert len(frames) == 1
    assert frames[0][0] == STATUS_ERROR
    assert message in frames[0][1]


def test_valid_frame_before_framing_error_is_answered(msgpack_cli: Path) -> None:
    data = request(b"\x01") + struct.pack(">I", 5) + b"\x02ab"
    returncode, stdout, stderr = run_cli(msgpack_cli, data)
    assert returncode != 0
    assert stderr != b""
    frames = parse_frames(stdout)
    assert frames[0] == (STATUS_OK, b"")
    assert frames[1][0] == STATUS_ERROR
    assert len(frames) == 2
