"""Framed CLI + golden-vector helpers for Phase 3 Python compatibility tests.

Uses only the Python standard library (``struct``, ``base64``, ``hashlib``,
``json``, ``math``). NumPy is NOT required for the golden-vector protocol.
"""

from __future__ import annotations

import base64
import hashlib
import math
import struct
import subprocess
from pathlib import Path

STATUS_OK = 0
STATUS_ERROR = 1
OP_PING = 0x01
OP_ECHO = 0x02
OP_SIGNAL_INFO = 0x20
OP_OUTPUT_ALLOC = 0x21
OP_OUTPUT_SET = 0x22
OP_F64_ENCODE = 0x23
OP_F64_DECODE = 0x24
OP_SHA256 = 0x25
OP_COMPARE = 0x26
OP_GOLDEN_PARSE = 0x27
OP_GOLDEN_SERIALIZE = 0x28
OP_FILTER_LOAD = 0x29


def f64le(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}d", *values)


def decode_f64le(raw: bytes) -> list[float]:
    if len(raw) % 8 != 0:
        raise ValueError(f"Float64 payload length {len(raw)} not a multiple of 8")
    return list(struct.unpack(f"<{len(raw) // 8}d", raw))


def bits(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def from_bits(value: int) -> float:
    return struct.unpack("<d", struct.pack("<Q", value))[0]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64decode(text: str) -> bytes:
    return base64.b64decode(text, validate=True)


def request(body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + body


def parse_frames(payload: bytes) -> list[tuple[int, bytes]]:
    frames: list[tuple[int, bytes]] = []
    offset = 0
    while offset < len(payload):
        if len(payload) - offset < 4:
            raise AssertionError("truncated response header")
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        offset += 4
        if len(payload) - offset < length:
            raise AssertionError("truncated response body")
        body = payload[offset : offset + length]
        offset += length
        if not body:
            raise AssertionError("response body must contain a status byte")
        frames.append((body[0], body[1:]))
    return frames


def run_frames(cli: Path, bodies: list[bytes]) -> list[tuple[int, bytes]]:
    wire = b"".join(request(body) for body in bodies)
    result = subprocess.run([str(cli)], input=wire, capture_output=True, timeout=120)
    if result.returncode != 0:
        raise AssertionError(f"CLI exited {result.returncode}: {result.stderr.decode()[:400]}")
    return parse_frames(result.stdout)


def run_one(cli: Path, body: bytes) -> tuple[int, bytes]:
    frames = run_frames(cli, [body])
    assert len(frames) == 1, f"expected 1 frame, got {len(frames)}"
    return frames[0]


def ok(cli: Path, body: bytes) -> bytes:
    status, payload = run_one(cli, body)
    assert status == STATUS_OK, f"expected OK, got status {status}: {payload!r}"
    return payload


def error(cli: Path, body: bytes) -> bytes:
    status, payload = run_one(cli, body)
    assert status == STATUS_ERROR, f"expected ERROR, got status {status}: {payload!r}"
    return payload


def parse_kv(payload: bytes) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in payload.decode("ascii").split(";"):
        key, _, value = part.partition("=")
        out[key] = value
    return out


def compare_body(actual: list[float], reference: list[float], atol: float, rtol: float) -> bytes:
    a, b = f64le(actual), f64le(reference)
    return (
        bytes([OP_COMPARE])
        + f64le([atol, rtol])
        + struct.pack(">I", len(actual))
        + a
        + struct.pack(">I", len(reference))
        + b
    )


def filter_load_body(meta: bytes, resource: bytes) -> bytes:
    return (
        bytes([OP_FILTER_LOAD])
        + struct.pack(">I", len(meta))
        + meta
        + struct.pack(">I", len(resource))
        + resource
    )


SPECIAL_VALUES = [
    0.0,
    -0.0,
    1.0,
    -1.0,
    0.5,
    1e-300,
    -1e-300,
    1e300,
    -1e300,
    float("nan"),
    float("inf"),
    float("-inf"),
    5e-324,
    math.nextafter(1.0, 2.0),
]
