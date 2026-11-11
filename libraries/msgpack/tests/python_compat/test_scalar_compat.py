"""Cross-language tests for float, string, and binary scalars."""

from __future__ import annotations

import struct
import subprocess
from pathlib import Path

import pytest

import msgpack

STATUS_OK = 0
STATUS_ERROR = 1
STATUS_UNIMPLEMENTED = 2

MODEL_FLOAT32 = 0x10
MODEL_FLOAT64 = 0x11
MODEL_STR = 0x12
MODEL_BIN = 0x13


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


def call(binary: Path, body: bytes) -> tuple[int, bytes]:
    returncode, stdout, stderr = run_cli(binary, request(body))
    assert returncode == 0
    assert stderr == b""
    frames = parse_frames(stdout)
    assert len(frames) == 1
    return frames[0]


def model_for(case: dict) -> bytes:
    value = case["value"]
    tag = value["type"]
    if tag in {"int", "uint"}:
        number = int(value["value"])
        return bytes([1 if tag == "uint" else 0]) + (number & ((1 << 64) - 1)).to_bytes(8, "big")
    if tag == "float32":
        return bytes([MODEL_FLOAT32]) + bytes.fromhex(value["bits"])
    if tag == "float64":
        return bytes([MODEL_FLOAT64]) + bytes.fromhex(value["bits"])
    if tag == "str":
        return bytes([MODEL_STR]) + value["text"].encode("utf-8")
    if tag == "bin":
        return bytes([MODEL_BIN]) + bytes.fromhex(value["hex"])
    raise AssertionError(f"unsupported model tag {tag!r}")


def unpack_model(payload: bytes) -> tuple[str, bytes | int]:
    tag = payload[0]
    if tag in {0, 1}:
        assert len(payload) == 9
        number = int.from_bytes(payload[1:], "big")
        if tag == 0:
            return "int", int.from_bytes(payload[1:], "big", signed=True)
        return "uint", number
    if tag == MODEL_FLOAT32:
        assert len(payload) == 5
        return "float32", payload[1:]
    if tag == MODEL_FLOAT64:
        assert len(payload) == 9
        return "float64", payload[1:]
    if tag == MODEL_STR:
        return "str", payload[1:]
    if tag == MODEL_BIN:
        return "bin", payload[1:]
    raise AssertionError(f"unexpected model tag {tag:#x}")


def category_cases(bundle: dict, category: str) -> list[dict]:
    return [
        case for case in bundle["cases"] if case["category"] == category and case["mode"] != "error"
    ]


def python_pack(case: dict) -> bytes:
    value = case["value"]
    tag = value["type"]
    if tag == "float32":
        number = struct.unpack(">f", bytes.fromhex(value["bits"]))[0]
        return msgpack.packb(number, use_single_float=True, use_bin_type=True)
    if tag == "float64":
        number = struct.unpack(">d", bytes.fromhex(value["bits"]))[0]
        return msgpack.packb(number, use_bin_type=True)
    if tag == "str":
        return msgpack.packb(value["text"], use_bin_type=True)
    if tag == "bin":
        return msgpack.packb(bytes.fromhex(value["hex"]), use_bin_type=True)
    raise AssertionError(f"unsupported model tag {tag!r}")


def assert_python_matches(case: dict, encoded: bytes) -> None:
    value = case["value"]
    tag = value["type"]
    actual = msgpack.unpackb(encoded, strict_map_key=False)
    if tag == "float32":
        assert struct.pack(">f", actual).hex() == value["bits"], case["id"]
    elif tag == "float64":
        assert struct.pack(">d", actual).hex() == value["bits"], case["id"]
    elif tag == "str":
        assert actual == value["text"], case["id"]
    elif tag == "bin":
        assert actual == bytes.fromhex(value["hex"]), case["id"]
    else:
        raise AssertionError(tag)


def assert_model_matches(case: dict, model: bytes) -> None:
    value = case["value"]
    tag = value["type"]
    actual_tag, actual = unpack_model(model)
    assert actual_tag == tag, case["id"]
    if tag == "float32" or tag == "float64":
        assert actual.hex() == value["bits"], case["id"]
    elif tag == "str":
        assert actual == value["text"].encode("utf-8"), case["id"]
    elif tag == "bin":
        assert actual == bytes.fromhex(value["hex"]), case["id"]
    else:
        raise AssertionError(tag)


def test_float_cross_language(msgpack_cli: Path, vectors_bundle: dict) -> None:
    cases = category_cases(vectors_bundle, "float")
    assert len(cases) == 26
    for case in cases:
        golden = bytes.fromhex(case["encoded"])
        assert python_pack(case) == golden, case["id"]

        status, model = call(msgpack_cli, b"\x10" + golden)
        assert status == STATUS_OK, case["id"]
        assert_model_matches(case, model)

        status, encoded = call(msgpack_cli, b"\x11" + model_for(case))
        assert status == STATUS_OK, case["id"]
        assert encoded == golden, case["id"]
        assert_python_matches(case, encoded)


def test_float32_python_use_single_float_compatibility(
    msgpack_cli: Path, vectors_bundle: dict
) -> None:
    cases = [
        case
        for case in category_cases(vectors_bundle, "float")
        if case["value"]["type"] == "float32"
    ]
    assert len(cases) == 13
    for case in cases:
        value = struct.unpack(">f", bytes.fromhex(case["value"]["bits"]))[0]
        assert msgpack.packb(value, use_single_float=True).hex() == case["encoded"]
        assert msgpack.packb(value).hex().startswith("cb"), case["id"]


def test_string_cross_language(msgpack_cli: Path, vectors_bundle: dict) -> None:
    cases = category_cases(vectors_bundle, "str")
    assert len(cases) == 12
    for case in cases:
        golden = bytes.fromhex(case["encoded"])
        assert python_pack(case) == golden, case["id"]

        status, model = call(msgpack_cli, b"\x10" + golden)
        assert status == STATUS_OK, case["id"]
        assert_model_matches(case, model)

        status, encoded = call(msgpack_cli, b"\x11" + model_for(case))
        assert status == STATUS_OK, case["id"]
        assert encoded == golden, case["id"]
        assert_python_matches(case, encoded)


@pytest.mark.parametrize(
    ("text", "header"),
    [
        ("", "a0"),
        ("x" * 31, "bf"),
        ("x" * 32, "d920"),
        ("x" * 255, "d9ff"),
        ("x" * 256, "da0100"),
        ("x" * 65535, "daffff"),
        ("x" * 65536, "db00010000"),
        ("€" * 10 + "x", "bf"),
        ("é" * 16, "d920"),
    ],
)
def test_string_marker_boundaries(msgpack_cli: Path, text: str, header: str) -> None:
    encoded = msgpack.packb(text, use_bin_type=True)
    assert encoded.hex().startswith(header)
    assert len(encoded) == len(header) // 2 + len(text.encode("utf-8"))

    status, model = call(msgpack_cli, b"\x10" + encoded)
    assert status == STATUS_OK
    assert unpack_model(model) == ("str", text.encode("utf-8"))

    status, encoded_by_mojo = call(msgpack_cli, b"\x11" + bytes([MODEL_STR]) + text.encode())
    assert status == STATUS_OK
    assert encoded_by_mojo == encoded


def test_binary_cross_language(msgpack_cli: Path, vectors_bundle: dict) -> None:
    cases = category_cases(vectors_bundle, "bin")
    assert len(cases) == 7
    for case in cases:
        golden = bytes.fromhex(case["encoded"])
        assert python_pack(case) == golden, case["id"]

        status, model = call(msgpack_cli, b"\x10" + golden)
        assert status == STATUS_OK, case["id"]
        assert_model_matches(case, model)

        status, encoded = call(msgpack_cli, b"\x11" + model_for(case))
        assert status == STATUS_OK, case["id"]
        assert encoded == golden, case["id"]
        assert_python_matches(case, encoded)


@pytest.mark.parametrize(
    ("payload", "header"),
    [
        (b"", "c400"),
        (bytes(range(256)), "c50100"),
        (b"x" * 255, "c4ff"),
        (b"x" * 256, "c50100"),
        (b"x" * 65535, "c5ffff"),
        (b"x" * 65536, "c600010000"),
    ],
)
def test_binary_boundaries_and_all_bytes(msgpack_cli: Path, payload: bytes, header: str) -> None:
    encoded = msgpack.packb(payload, use_bin_type=True)
    assert encoded.hex().startswith(header)
    assert len(encoded) == len(header) // 2 + len(payload)

    status, model = call(msgpack_cli, b"\x10" + encoded)
    assert status == STATUS_OK
    assert unpack_model(model) == ("bin", payload)

    status, encoded_by_mojo = call(msgpack_cli, b"\x11" + bytes([MODEL_BIN]) + payload)
    assert status == STATUS_OK
    assert encoded_by_mojo == encoded


@pytest.mark.parametrize(
    ("payload", "prefix"),
    [
        (bytes.fromhex("a180"), b"invalid-utf8: offset 1"),
        (bytes.fromhex("a2e282"), b"invalid-utf8: offset 1"),
        (bytes.fromhex("a3eda080"), b"invalid-utf8: offset 1"),
        (bytes.fromhex("a56162"), b"truncated: offset 0"),
        (bytes.fromhex("dbffffffff"), b"truncated: offset 0"),
        (bytes.fromhex("c4050102"), b"truncated: offset 0"),
        (bytes.fromhex("ca3fc000"), b"truncated: offset 0"),
        (bytes.fromhex("a16162"), b"trailing-data: offset 2"),
        (bytes.fromhex("c1"), b"invalid-marker: offset 0"),
    ],
)
def test_malformed_scalar_wire_values_are_errors(
    msgpack_cli: Path, payload: bytes, prefix: bytes
) -> None:
    status, message = call(msgpack_cli, b"\x10" + payload)
    assert status == STATUS_ERROR
    assert message.startswith(prefix)


def test_unimplemented_markers_and_models(msgpack_cli: Path) -> None:
    status, message = call(msgpack_cli, b"\x10\xc0")
    assert status == STATUS_UNIMPLEMENTED
    assert b"Phase 1" in message

    status, message = call(msgpack_cli, b"\x11\xc0")
    assert status == STATUS_UNIMPLEMENTED
    assert b"Phase 1" in message


@pytest.mark.parametrize(
    ("model", "prefix"),
    [
        (bytes([MODEL_FLOAT32]) + b"\x00\x00\x00", b"truncated: offset 0"),
        (bytes([MODEL_FLOAT32]) + b"\x00\x00\x00\x00\x00", b"trailing-data: offset 5"),
        (bytes([MODEL_STR, 0x80]), b"invalid-utf8: offset 1"),
        (bytes([0x20]), b"invalid-model: offset 0"),
    ],
)
def test_malformed_scalar_models_are_errors(msgpack_cli: Path, model: bytes, prefix: bytes) -> None:
    status, message = call(msgpack_cli, b"\x11" + model)
    assert status == STATUS_ERROR
    assert message.startswith(prefix)
