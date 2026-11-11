"""Cross-language integer codec tests through the native CLI."""

from __future__ import annotations

import struct
import subprocess
from pathlib import Path

import pytest

import msgpack

STATUS_OK = 0
STATUS_ERROR = 1
STATUS_UNIMPLEMENTED = 2
UINT64_MASK = (1 << 64) - 1


def request(body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + body


def run_cli(binary: Path, data: bytes, timeout: float = 60) -> tuple[int, bytes, bytes]:
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
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        offset += 4
        body = payload[offset : offset + length]
        offset += length
        frames.append((body[0], body[1:]))
    return frames


def integer_cases(bundle: dict) -> list[dict]:
    return [case for case in bundle["cases"] if case["category"] == "int"]


def model_for(case: dict) -> bytes:
    value = int(case["value"]["value"])
    tag = 1 if case["value"]["type"] == "uint" else 0
    return bytes([tag]) + (value & UINT64_MASK).to_bytes(8, "big")


def decode_model(payload: bytes) -> tuple[str, int]:
    assert len(payload) == 9, payload
    tag = payload[0]
    bits = int.from_bytes(payload[1:], "big")
    if tag == 0:
        return "int", int.from_bytes(payload[1:], "big", signed=True)
    assert tag == 1
    return "uint", bits


def call(binary: Path, body: bytes) -> tuple[int, bytes, bytes]:
    returncode, stdout, stderr = run_cli(binary, request(body))
    assert returncode == 0
    assert stderr == b""
    frames = parse_frames(stdout)
    assert len(frames) == 1
    return frames[0][0], frames[0][1], stderr


def test_python_encodes_golden_bytes_and_mojo_decodes(
    msgpack_cli: Path, vectors_bundle: dict
) -> None:
    cases = integer_cases(vectors_bundle)
    assert len(cases) == 35
    for case in cases:
        value = int(case["value"]["value"])
        packed = msgpack.packb(value, use_bin_type=True)
        assert packed == bytes.fromhex(case["encoded"]), case["id"]
        status, payload, _ = call(msgpack_cli, b"\x10" + packed)
        assert status == STATUS_OK, case["id"]
        assert decode_model(payload) == (case["value"]["type"], value), case["id"]


def test_mojo_encodes_golden_bytes_and_python_decodes(
    msgpack_cli: Path, vectors_bundle: dict
) -> None:
    for case in integer_cases(vectors_bundle):
        value = int(case["value"]["value"])
        status, encoded, _ = call(msgpack_cli, b"\x11" + model_for(case))
        assert status == STATUS_OK, case["id"]
        assert encoded == bytes.fromhex(case["encoded"]), case["id"]
        assert msgpack.unpackb(encoded) == value, case["id"]


def test_signed_and_unsigned_models_encode_identically(msgpack_cli: Path) -> None:
    for value, expected_hex in [
        (0, "00"),
        (127, "7f"),
        (128, "cc80"),
        (255, "ccff"),
        (256, "cd0100"),
    ]:
        signed_model = bytes([0]) + value.to_bytes(8, "big")
        unsigned_model = bytes([1]) + value.to_bytes(8, "big")
        for model in (signed_model, unsigned_model):
            status, encoded, _ = call(msgpack_cli, b"\x11" + model)
            assert status == STATUS_OK
            assert encoded.hex() == expected_hex
    status, encoded, _ = call(msgpack_cli, b"\x11\x01" + b"\xff" * 8)
    assert status == STATUS_OK
    assert encoded.hex() == "cfffffffffffffffff"


def test_negative_models_roundtrip(msgpack_cli: Path) -> None:
    for value in [-1, -32, -33, -128, -129, -32768, -32769, -(2**31), -(2**31) - 1, -(2**63)]:
        model = bytes([0]) + (value & UINT64_MASK).to_bytes(8, "big")
        status, encoded, _ = call(msgpack_cli, b"\x11" + model)
        assert status == STATUS_OK
        assert encoded == msgpack.packb(value)
        status, decoded, _ = call(msgpack_cli, b"\x10" + encoded)
        assert status == STATUS_OK
        assert decode_model(decoded) == ("int", value)


def test_required_boundaries_are_present(vectors_bundle: dict) -> None:
    values = {int(case["value"]["value"]) for case in integer_cases(vectors_bundle)}
    required = {
        -(2**63),
        -(2**31),
        -32769,
        -32768,
        -129,
        -128,
        -33,
        -32,
        -1,
        0,
        1,
        127,
        128,
        255,
        256,
        65535,
        65536,
        2**31 - 1,
        2**31,
        2**32 - 1,
        2**32,
        2**64 - 1,
    }
    assert required <= values


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        bytes.fromhex("cc"),
        bytes.fromhex("cd01"),
        bytes.fromhex("ce000000"),
        bytes.fromhex("cf00000000000000"),
        bytes.fromhex("d0"),
        bytes.fromhex("d1ff"),
        bytes.fromhex("d2000000"),
        bytes.fromhex("d300000000000000"),
    ],
)
def test_truncated_integer_payloads_report_offset(msgpack_cli: Path, payload: bytes) -> None:
    status, message, _ = call(msgpack_cli, b"\x10" + payload)
    assert status == STATUS_ERROR
    assert message.startswith(b"truncated: offset 0")


def test_trailing_integer_bytes_are_rejected(msgpack_cli: Path) -> None:
    status, message, _ = call(msgpack_cli, b"\x10\x01\x02")
    assert status == STATUS_ERROR
    assert message.startswith(b"trailing-data: offset 1")


def test_non_integer_marker_is_unimplemented(msgpack_cli: Path) -> None:
    status, message, _ = call(msgpack_cli, b"\x10\xc0")
    assert status == STATUS_UNIMPLEMENTED
    assert b"Phase 1" in message


def test_invalid_integer_model_tag_is_an_error(msgpack_cli: Path) -> None:
    status, message, _ = call(msgpack_cli, b"\x11" + bytes([2]) + b"\xff" * 8)
    assert status == STATUS_ERROR
    assert message.startswith(b"invalid-model: offset 0")


def test_truncated_and_trailing_integer_models_are_errors(msgpack_cli: Path) -> None:
    status, message, _ = call(msgpack_cli, b"\x11\x00\xff")
    assert status == STATUS_ERROR
    assert message.startswith(b"truncated: offset 0")

    status, message, _ = call(msgpack_cli, b"\x11" + b"\x00" + b"\xff" * 9)
    assert status == STATUS_ERROR
    assert message.startswith(b"trailing-data: offset 9")
