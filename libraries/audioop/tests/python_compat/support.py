"""Framed CLI helpers shared by the audioop compatibility tests."""

from __future__ import annotations

import struct
import subprocess
from pathlib import Path

STATUS_OK = 0
STATUS_ERROR = 1
OP_PING = 0x01
OP_ECHO = 0x02
OP_DECODE_FRAGMENT = 0x20
OP_ENCODE_FRAGMENT = 0x21


def request(body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + body


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


def run_frames(binary: Path, bodies: list[bytes]) -> list[tuple[int, bytes]]:
    data = b"".join(request(body) for body in bodies)
    result = subprocess.run(
        [str(binary)],
        input=data,
        capture_output=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert result.stderr == b""
    return parse_frames(result.stdout)


def decode_body(width: int, fragment: bytes) -> bytes:
    return bytes([OP_DECODE_FRAGMENT, width]) + fragment


def encode_body(width: int, values: list[int]) -> bytes:
    text = " ".join(str(value) for value in values)
    return bytes([OP_ENCODE_FRAGMENT, width]) + text.encode("ascii")


def decode_values(payload: bytes) -> list[int]:
    if not payload:
        return []
    return [int(token) for token in payload.decode("ascii").split()]


def encode_values(values: list[int]) -> bytes:
    return " ".join(str(value) for value in values).encode("ascii")
