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
OP_ADD = 0x22
OP_BIAS = 0x23
OP_MUL = 0x24
OP_REVERSE = 0x25
OP_BYTESWAP = 0x26
OP_LIN2LIN = 0x27
OP_GETSAMPLE = 0x28
OP_MAX = 0x29
OP_MINMAX = 0x2A
OP_AVG = 0x2B
OP_RMS = 0x2C
OP_CROSS = 0x2D


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


def add_body(width: int, fragment1: bytes, fragment2: bytes) -> bytes:
    return bytes([OP_ADD, width]) + struct.pack(">I", len(fragment1)) + fragment1 + fragment2


def bias_body(width: int, bias: int, fragment: bytes) -> bytes:
    return bytes([OP_BIAS, width]) + struct.pack(">q", bias) + fragment


def mul_body(width: int, factor: float, fragment: bytes) -> bytes:
    return bytes([OP_MUL, width]) + struct.pack(">d", factor) + fragment


def reverse_body(width: int, fragment: bytes) -> bytes:
    return bytes([OP_REVERSE, width]) + fragment


def byteswap_body(width: int, fragment: bytes) -> bytes:
    return bytes([OP_BYTESWAP, width]) + fragment


def lin2lin_body(width: int, new_width: int, fragment: bytes) -> bytes:
    return bytes([OP_LIN2LIN, width, new_width]) + fragment


def getsample_body(width: int, index: int, fragment: bytes) -> bytes:
    return bytes([OP_GETSAMPLE, width]) + struct.pack(">q", index) + fragment


def max_body(width: int, fragment: bytes) -> bytes:
    return bytes([OP_MAX, width]) + fragment


def minmax_body(width: int, fragment: bytes) -> bytes:
    return bytes([OP_MINMAX, width]) + fragment


def avg_body(width: int, fragment: bytes) -> bytes:
    return bytes([OP_AVG, width]) + fragment


def rms_body(width: int, fragment: bytes) -> bytes:
    return bytes([OP_RMS, width]) + fragment


def cross_body(width: int, fragment: bytes) -> bytes:
    return bytes([OP_CROSS, width]) + fragment


def parse_scalar(payload: bytes) -> int:
    return int(payload.decode("ascii"))


def parse_pair(payload: bytes) -> tuple[int, int]:
    first, second = payload.decode("ascii").split()
    return int(first), int(second)
