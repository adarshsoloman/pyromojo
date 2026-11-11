"""Cross-language tests for extensions and timestamps."""

from __future__ import annotations

import datetime
import struct
import subprocess
from pathlib import Path

import msgpack.fallback
import pytest
from generate_vectors import MapPairs, model_matches, pack_model

import msgpack

STATUS_OK = 0
STATUS_ERROR = 1

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


def test_timestamp_object_semantics() -> None:
    stamp = msgpack.Timestamp(1, 2)
    assert (stamp.seconds, stamp.nanoseconds) == (1, 2)
    assert stamp.to_unix() == 1.000000002
    assert stamp.to_unix_nano() == 1000000002
    assert msgpack.Timestamp.from_unix(1.5) == msgpack.Timestamp(1, 500000000)
    assert msgpack.Timestamp(0, 999999999).nanoseconds == 999999999
    assert stamp == msgpack.Timestamp(1, 2)
    assert hash(stamp) == hash(msgpack.Timestamp(1, 2))

    with pytest.raises(ValueError):
        msgpack.Timestamp(0, 1000000000)
    with pytest.raises(ValueError):
        msgpack.Timestamp(0, -1)


def test_unpack_timestamp_options() -> None:
    golden = bytes.fromhex("d6ff00000001")
    assert msgpack.unpackb(golden) == msgpack.Timestamp(1, 0)
    assert msgpack.unpackb(golden, timestamp=0) == msgpack.Timestamp(1, 0)
    assert msgpack.unpackb(golden, timestamp=1) == 1.0
    assert msgpack.unpackb(golden, timestamp=2) == 1000000000
    assert msgpack.unpackb(golden, timestamp=3) == datetime.datetime(
        1970, 1, 1, 0, 0, 1, tzinfo=datetime.UTC
    )
    for impl in (msgpack.unpackb, msgpack.fallback.unpackb):
        assert impl(golden, timestamp=1) == 1.0
        assert impl(golden, timestamp=3) == datetime.datetime(
            1970, 1, 1, 0, 0, 1, tzinfo=datetime.UTC
        )

    negative = bytes.fromhex("c70cff00000000ffffffffffffffff")
    assert msgpack.unpackb(negative) == msgpack.Timestamp(-1, 0)
    assert msgpack.unpackb(negative, timestamp=1) == -1.0
    assert msgpack.unpackb(negative, timestamp=2) == -1000000000
    assert msgpack.unpackb(negative, timestamp=3) == datetime.datetime(
        1969, 12, 31, 23, 59, 59, tzinfo=datetime.UTC
    )


def test_datetime_packing_semantics() -> None:
    moment = datetime.datetime(2024, 1, 2, 3, 4, 5, 123456, tzinfo=datetime.UTC)
    packed = msgpack.packb(moment, datetime=True)
    assert packed == bytes.fromhex("d7ff1d6f280065937d25")
    assert msgpack.unpackb(packed) == msgpack.Timestamp(1704164645, 123456000)

    eastern = datetime.timezone(datetime.timedelta(hours=-5))
    shifted = datetime.datetime(2024, 1, 1, 22, 4, 5, 123456, tzinfo=eastern)
    assert msgpack.packb(shifted, datetime=True) == packed

    with pytest.raises(ValueError, match="tzinfo=None"):
        msgpack.packb(datetime.datetime(2024, 1, 2, 3, 4, 5, 123456), datetime=True)
    with pytest.raises(TypeError):
        msgpack.packb(moment)

    packer = msgpack.fallback.Packer(use_bin_type=True, datetime=True)
    assert packer.pack(moment) == packed


def test_ext_cross_language(msgpack_cli: Path, vectors_bundle: dict) -> None:
    cases = cases_by(vectors_bundle, "ext", "roundtrip")
    assert len(cases) == 14
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


def test_timestamp_cross_language(msgpack_cli: Path, vectors_bundle: dict) -> None:
    cases = cases_by(vectors_bundle, "timestamp", "roundtrip")
    assert len(cases) == 10
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


def test_nested_ext_and_timestamp_cross_language(msgpack_cli: Path, vectors_bundle: dict) -> None:
    for case_id in ("array_ext_timestamp", "map_timestamp_key"):
        case = next(case for case in vectors_bundle["cases"] if case["id"] == case_id)
        golden = bytes.fromhex(case["encoded"])
        decode_both_implementations(golden)

        status, model = call(msgpack_cli, b"\x10" + golden)
        assert status == STATUS_OK, case_id
        assert_model_matches(case, model)

        status, encoded = call(msgpack_cli, b"\x11" + model)
        assert status == STATUS_OK, case_id
        assert encoded == golden, case_id


def test_timestamp_key_preserves_value(msgpack_cli: Path) -> None:
    status, model = call(
        msgpack_cli, b"\x10\x82\xd6\xff\x00\x00\x00\x05\xa1\x74\xa1\x65\xd4\x07\x00"
    )
    assert status == STATUS_OK
    assert unpack_model(model) == [
        (msgpack.Timestamp(5, 0), "t"),
        ("e", msgpack.ExtType(7, b"\x00")),
    ]


def test_negative_ext_code_deviation(msgpack_cli: Path) -> None:
    with pytest.raises(ValueError, match="code must be 0~127"):
        msgpack.unpackb(bytes.fromhex("d4fe2a"), strict_map_key=False)

    status, model = call(msgpack_cli, b"\x10\xd4\xfe\x2a")
    assert status == STATUS_OK
    # The reference ExtType cannot represent this; compare the raw model.
    assert model == bytes([MODEL_EXT, 0xFE]) + struct.pack(">I", 1) + b"\x2a"

    status, encoded = call(msgpack_cli, b"\x11\x16\xfe\x00\x00\x00\x01\x2a")
    assert status == STATUS_OK
    assert encoded == bytes.fromhex("d4fe2a")


@pytest.mark.parametrize(
    ("payload", "prefix"),
    [
        (bytes.fromhex("d4"), b"truncated"),
        (bytes.fromhex("d401"), b"truncated"),
        (bytes.fromhex("c7"), b"truncated"),
        (bytes.fromhex("c8"), b"truncated"),
        (bytes.fromhex("c900000001"), b"truncated"),
        (bytes.fromhex("d6ff000000"), b"truncated"),
        (bytes.fromhex("c700ff"), b"invalid-timestamp"),
        (bytes.fromhex("c705ff0102030405"), b"invalid-timestamp"),
        (bytes.fromhex("d8ff") + b"\x00" * 16, b"invalid-timestamp"),
        (
            bytes.fromhex("c70cff3b9aca000000000000000001"),
            b"invalid-timestamp",
        ),
        (bytes.fromhex("d7fffffffffc00000000"), b"invalid-timestamp"),
        (bytes.fromhex("d401022a"), b"trailing-data"),
    ],
)
def test_malformed_ext_and_timestamp_wire_values_are_errors(
    msgpack_cli: Path, payload: bytes, prefix: bytes
) -> None:
    status, message = call(msgpack_cli, b"\x10" + payload)
    assert status == STATUS_ERROR
    assert message.startswith(prefix)


@pytest.mark.parametrize(
    ("model", "prefix"),
    [
        (bytes([MODEL_EXT]), b"truncated"),
        (bytes([MODEL_TIMESTAMP]), b"truncated"),
        (bytes([MODEL_TIMESTAMP]) + b"\x00" * 13, b"trailing-data"),
        (bytes([0x18]), b"invalid-model"),
        (bytes([MODEL_EXT, 0xFF, 0, 0, 0, 1, 0x02]), b"invalid-timestamp"),
        (
            bytes([MODEL_TIMESTAMP]) + b"\x00" * 8 + bytes.fromhex("3b9aca00"),
            b"invalid-timestamp",
        ),
    ],
)
def test_malformed_ext_and_timestamp_models_are_errors(
    msgpack_cli: Path, model: bytes, prefix: bytes
) -> None:
    status, message = call(msgpack_cli, b"\x11" + model)
    assert status == STATUS_ERROR
    assert message.startswith(prefix)
