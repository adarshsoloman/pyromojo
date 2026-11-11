"""Cross-language tests for recursive arrays and maps."""

from __future__ import annotations

import struct
import subprocess
from pathlib import Path

import msgpack.fallback
import pytest
from generate_vectors import MapPairs, model_matches, pack_model

import msgpack

STATUS_OK = 0
STATUS_ERROR = 1
STATUS_UNIMPLEMENTED = 2

MODEL_SIGNED = 0
MODEL_UNSIGNED = 1
MODEL_FLOAT32 = 0x10
MODEL_FLOAT64 = 0x11
MODEL_STR = 0x12
MODEL_BIN = 0x13
MODEL_ARRAY = 0x14
MODEL_MAP = 0x15
MODEL_NIL = 0xC0
MODEL_FALSE = 0xC2
MODEL_TRUE = 0xC3
MODEL_EXT = 0x16
MODEL_TIMESTAMP = 0x17

MASK64 = (1 << 64) - 1


def request(body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + body


def run_cli(binary: Path, data: bytes, timeout: float = 120) -> tuple[int, bytes, bytes]:
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


def model_for(value: dict) -> bytes:
    tag = value["type"]
    if tag in {"int", "uint"}:
        number = int(value["value"])
        prefix = MODEL_UNSIGNED if tag == "uint" else MODEL_SIGNED
        return bytes([prefix]) + (number & MASK64).to_bytes(8, "big")
    if tag == "float32":
        return bytes([MODEL_FLOAT32]) + bytes.fromhex(value["bits"])
    if tag == "float64":
        return bytes([MODEL_FLOAT64]) + bytes.fromhex(value["bits"])
    if tag == "str":
        return bytes([MODEL_STR]) + value["text"].encode("utf-8")
    if tag == "bin":
        return bytes([MODEL_BIN]) + bytes.fromhex(value["hex"])
    if tag == "nil":
        return bytes([MODEL_NIL])
    if tag == "bool":
        return bytes([MODEL_TRUE if value["value"] else MODEL_FALSE])
    if tag == "ext":
        code = value["code"] & 0xFF
        payload = bytes.fromhex(value["hex"])
        return bytes([MODEL_EXT, code]) + struct.pack(">I", len(payload)) + payload
    if tag == "timestamp":
        seconds = int(value["seconds"])
        return (
            bytes([MODEL_TIMESTAMP])
            + struct.pack(">q", seconds)
            + struct.pack(">I", value["nanoseconds"])
        )
    if tag == "array":
        if "repeat" in value:
            items = [value["repeat"]["item"]] * value["repeat"]["count"]
        else:
            items = value["items"]
        frames = b"".join(
            struct.pack(">I", len(child)) + child for child in (model_for(item) for item in items)
        )
        return bytes([MODEL_ARRAY]) + struct.pack(">I", len(items)) + frames
    if tag == "map":
        if "repeat" in value:
            pairs = [(value["repeat"]["key"], value["repeat"]["value"])] * value["repeat"]["count"]
        else:
            pairs = [(pair["key"], pair["value"]) for pair in value["pairs"]]
        frames = b"".join(
            struct.pack(">I", len(key)) + key + struct.pack(">I", len(item)) + item
            for key, item in ((model_for(key), model_for(item)) for key, item in pairs)
        )
        return bytes([MODEL_MAP]) + struct.pack(">I", len(pairs)) + frames
    raise AssertionError(f"unsupported model tag {tag!r}")


def unpack_model(payload: bytes):
    tag = payload[0]
    if tag in {0, 1}:
        assert len(payload) == 9
        if tag == 0:
            return int.from_bytes(payload[1:], "big", signed=True)
        return int.from_bytes(payload[1:], "big")
    if tag == MODEL_FLOAT32:
        assert len(payload) == 5
        return struct.unpack(">f", payload[1:])[0]
    if tag == MODEL_FLOAT64:
        assert len(payload) == 9
        return struct.unpack(">d", payload[1:])[0]
    if tag == MODEL_STR:
        return payload[1:].decode("utf-8")
    if tag == MODEL_BIN:
        return payload[1:]
    if tag == MODEL_NIL:
        assert len(payload) == 1
        return None
    if tag == MODEL_FALSE:
        assert len(payload) == 1
        return False
    if tag == MODEL_TRUE:
        assert len(payload) == 1
        return True
    if tag == MODEL_EXT:
        assert len(payload) >= 6
        code = payload[1]
        length = struct.unpack(">I", payload[2:6])[0]
        assert len(payload) == 6 + length
        return msgpack.ExtType(int.from_bytes([code], "big", signed=True), payload[6:])
    if tag == MODEL_TIMESTAMP:
        assert len(payload) == 13
        seconds = struct.unpack(">q", payload[1:9])[0]
        nanoseconds = struct.unpack(">I", payload[9:13])[0]
        return msgpack.Timestamp(seconds, nanoseconds)
    if tag == MODEL_ARRAY:
        count = struct.unpack(">I", payload[1:5])[0]
        offset = 5
        items = []
        for _ in range(count):
            length = struct.unpack(">I", payload[offset : offset + 4])[0]
            start = offset + 4
            items.append(unpack_model(payload[start : start + length]))
            offset = start + length
        assert offset == len(payload)
        return items
    if tag == MODEL_MAP:
        count = struct.unpack(">I", payload[1:5])[0]
        offset = 5
        pairs = []
        for _ in range(count):
            key_length = struct.unpack(">I", payload[offset : offset + 4])[0]
            key_start = offset + 4
            key = unpack_model(payload[key_start : key_start + key_length])
            offset = key_start + key_length
            value_length = struct.unpack(">I", payload[offset : offset + 4])[0]
            value_start = offset + 4
            item = unpack_model(payload[value_start : value_start + value_length])
            offset = value_start + value_length
            pairs.append((key, item))
        assert offset == len(payload)
        return MapPairs(pairs)
    raise AssertionError(f"unexpected model tag {tag:#x}")


def assert_model_matches(case: dict, model: bytes) -> None:
    model_matches(case["value"], unpack_model(model))


def cases_by(bundle: dict, category: str, mode: str) -> list[dict]:
    return [
        case for case in bundle["cases"] if case["category"] == category and case["mode"] == mode
    ]


def decode_both_implementations(encoded: bytes):
    hook = lambda pairs: MapPairs(pairs)  # noqa: E731
    expected_c = msgpack.unpackb(encoded, strict_map_key=False, object_pairs_hook=hook)
    expected_fallback = msgpack.fallback.unpackb(
        encoded, strict_map_key=False, object_pairs_hook=hook
    )
    assert type(expected_c) is type(expected_fallback)
    assert repr(expected_c) == repr(expected_fallback)
    return expected_c


def test_array_cross_language(msgpack_cli: Path, vectors_bundle: dict) -> None:
    cases = cases_by(vectors_bundle, "array", "roundtrip")
    assert len(cases) == 9
    for case in cases:
        golden = bytes.fromhex(case["encoded"])
        decode_both_implementations(golden)
        assert pack_model(case["value"]) == golden, case["id"]

        status, model = call(msgpack_cli, b"\x10" + golden)
        assert status == STATUS_OK, case["id"]
        assert_model_matches(case, model)

        status, encoded = call(msgpack_cli, b"\x11" + model_for(case["value"]))
        assert status == STATUS_OK, case["id"]
        assert encoded == golden, case["id"]
        decode_both_implementations(encoded)


def test_map_cross_language(msgpack_cli: Path, vectors_bundle: dict) -> None:
    cases = cases_by(vectors_bundle, "map", "roundtrip")
    assert len(cases) == 5
    for case in cases:
        golden = bytes.fromhex(case["encoded"])
        decode_both_implementations(golden)

        status, model = call(msgpack_cli, b"\x10" + golden)
        assert status == STATUS_OK, case["id"]
        assert_model_matches(case, model)

        status, encoded = call(msgpack_cli, b"\x11" + model_for(case["value"]))
        assert status == STATUS_OK, case["id"]
        assert encoded == golden, case["id"]
        decode_both_implementations(encoded)


def test_map_decode_cases_preserve_order_and_keys(msgpack_cli: Path, vectors_bundle: dict) -> None:
    cases = cases_by(vectors_bundle, "map", "decode")
    assert len(cases) == 5
    for case in cases:
        golden = bytes.fromhex(case["encoded"])
        decode_both_implementations(golden)

        status, model = call(msgpack_cli, b"\x10" + golden)
        assert status == STATUS_OK, case["id"]
        assert_model_matches(case, model)

        status, encoded = call(msgpack_cli, b"\x11" + model)
        assert status == STATUS_OK, case["id"]
        assert encoded == golden, case["id"]


def test_duplicate_map_keys_stay_ordered(msgpack_cli: Path) -> None:
    status, model = call(msgpack_cli, b"\x10\x82\xa1\x6b\x01\xa1\x6b\x02")
    assert status == STATUS_OK
    assert unpack_model(model) == [("k", 1), ("k", 2)]
    status, encoded = call(msgpack_cli, b"\x11" + model)
    assert status == STATUS_OK
    assert encoded == bytes.fromhex("82a16b01a16b02")


def test_fallback_packer_output_decodes_natively(msgpack_cli: Path) -> None:
    packer = msgpack.fallback.Packer(use_bin_type=True)
    value = [{"a": [1, None]}, True]
    encoded = packer.pack(value)
    status, model = call(msgpack_cli, b"\x10" + encoded)
    assert status == STATUS_OK
    assert unpack_model(model) == [MapPairs([("a", [1, None])]), True]

    status, reencoded = call(msgpack_cli, b"\x11" + model)
    assert status == STATUS_OK
    assert msgpack.fallback.unpackb(reencoded, strict_map_key=False, raw=False) == value


def test_nesting_depth_boundary(msgpack_cli: Path) -> None:
    accepted = b"\x91" * 127 + b"\x00"
    assert msgpack.fallback.unpackb(accepted, strict_map_key=False) == msgpack.unpackb(
        accepted, strict_map_key=False
    )
    status, _ = call(msgpack_cli, b"\x10" + accepted)
    assert status == STATUS_OK

    rejected = b"\x91" * 128 + b"\x00"
    assert msgpack.fallback.unpackb(rejected, strict_map_key=False) == msgpack.unpackb(
        rejected, strict_map_key=False
    )
    status, message = call(msgpack_cli, b"\x10" + rejected)
    assert status == STATUS_ERROR
    assert message.startswith(b"depth-exceeded")


def test_reference_depth_limit_is_beyond_native(msgpack_cli: Path, vectors_bundle: dict) -> None:
    case = next(
        case for case in vectors_bundle["cases"] if case["id"] == "error_reference_depth_limit"
    )
    status, message = call(msgpack_cli, b"\x10" + bytes.fromhex(case["encoded"]))
    assert status == STATUS_ERROR
    assert message.startswith(b"depth-exceeded")


def test_container_limits_are_errors(msgpack_cli: Path) -> None:
    status, message = call(msgpack_cli, b"\x10" + bytes.fromhex("dd000f4241"))
    assert status == STATUS_ERROR
    assert message.startswith(b"container-limit")

    status, message = call(msgpack_cli, b"\x10" + bytes.fromhex("df000f4241"))
    assert status == STATUS_ERROR
    assert message.startswith(b"container-limit")

    status, message = call(msgpack_cli, b"\x11\x14" + struct.pack(">I", 1))
    assert status == STATUS_ERROR
    assert message.startswith(b"truncated")

    status, message = call(msgpack_cli, b"\x11\x14\x00\x00\x00\x01\x00\x00\x00\x01\x20")
    assert status == STATUS_ERROR
    assert message.startswith(b"invalid-model")


@pytest.mark.parametrize(
    ("payload", "prefix"),
    [
        (bytes.fromhex("91"), b"truncated"),
        (bytes.fromhex("dc0001"), b"truncated"),
        (bytes.fromhex("dd00000001"), b"truncated"),
        (bytes.fromhex("81a161"), b"truncated"),
        (bytes.fromhex("de0001"), b"truncated"),
        (bytes.fromhex("df00000001"), b"truncated"),
        (bytes.fromhex("ddffffffff"), b"container-limit"),
        (bytes.fromhex("dfffffffff"), b"container-limit"),
        (bytes.fromhex("91c1"), b"invalid-marker"),
    ],
)
def test_malformed_container_wire_values_are_errors(
    msgpack_cli: Path, payload: bytes, prefix: bytes
) -> None:
    status, message = call(msgpack_cli, b"\x10" + payload)
    assert status == STATUS_ERROR
    assert message.startswith(prefix)


def test_bare_nil_and_bool_stay_unimplemented(msgpack_cli: Path) -> None:
    for marker in (b"\xc0", b"\xc2", b"\xc3"):
        status, message = call(msgpack_cli, b"\x10" + marker)
        assert status == STATUS_UNIMPLEMENTED
        assert b"Phase 1" in message

        status, message = call(msgpack_cli, b"\x11" + marker)
        assert status == STATUS_UNIMPLEMENTED
        assert b"Phase 1" in message
