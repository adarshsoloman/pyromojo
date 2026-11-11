#!/usr/bin/env python3
"""Generate MessagePack golden vectors and the typed Mojo case module.

Single source of truth for correctness cases:

* ``libraries/msgpack/tests/vectors/msgpack_vectors.json`` -- language-neutral
  bundle using an explicit tagged value model.
* ``libraries/msgpack/tests/mojo/generated_vectors.mojo`` -- typed case
  metadata plus lazily built ``Value`` models for Mojo tests.

Both outputs are deterministic. Run with ``--check`` (as the pytest suite does)
to fail when a committed artifact drifts from the generator.

Reference semantics come from ``msgpack==1.2.4`` with ``strict_map_key=False``
and an ``object_pairs_hook`` that preserves map order and duplicate keys.
"""

from __future__ import annotations

import argparse
import difflib
import importlib.metadata
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any

import msgpack

SCHEMA_VERSION = "1.1.0"
GENERATOR_NAME = "msgpack_vectors"
GENERATOR_VERSION = "1.1.0"
REFERENCE_VERSION = "1.2.4"
REPEAT_MAX = 1_000_000

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BUNDLE = ROOT / "libraries/msgpack/tests/vectors/msgpack_vectors.json"
DEFAULT_MOJO = ROOT / "libraries/msgpack/tests/mojo/generated_vectors.mojo"


class MapPairs(list):
    """Marker type returned by the object_pairs_hook."""


def _pairs_hook(pairs: list[tuple[Any, Any]]) -> MapPairs:
    return MapPairs(pairs)


def decode_bytes(encoded: bytes) -> Any:
    return msgpack.unpackb(
        encoded,
        strict_map_key=False,
        object_pairs_hook=_pairs_hook,
    )


# ---------------------------------------------------------------------------
# Tagged value model helpers
# ---------------------------------------------------------------------------


def v_nil() -> dict[str, Any]:
    return {"type": "nil"}


def v_bool(value: bool) -> dict[str, Any]:
    return {"type": "bool", "value": value}


def v_int(value: int) -> dict[str, Any]:
    assert -(2**63) <= value <= 2**63 - 1, value
    return {"type": "int", "value": str(value)}


def v_uint(value: int) -> dict[str, Any]:
    assert 0 <= value <= 2**64 - 1, value
    return {"type": "uint", "value": str(value)}


def v_float32(bits: str) -> dict[str, Any]:
    assert re.fullmatch(r"[0-9a-f]{8}", bits), bits
    return {"type": "float32", "bits": bits}


def v_float64_bits(bits: str) -> dict[str, Any]:
    assert re.fullmatch(r"[0-9a-f]{16}", bits), bits
    return {"type": "float64", "bits": bits}


def v_float64(value: float) -> dict[str, Any]:
    return v_float64_bits(struct.pack(">d", value).hex())


def v_str(text: str) -> dict[str, Any]:
    text.encode("utf-8")
    return {"type": "str", "text": text}


def v_bin(payload: bytes) -> dict[str, Any]:
    return {"type": "bin", "hex": payload.hex()}


def v_array(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "array", "items": items}


def v_array_repeat(item: dict[str, Any], count: int) -> dict[str, Any]:
    assert 0 <= count <= REPEAT_MAX
    return {"type": "array", "repeat": {"item": item, "count": count}}


def v_map(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    return {
        "type": "map",
        "pairs": [{"key": key, "value": value} for key, value in pairs],
    }


def v_map_repeat(key: dict[str, Any], value: dict[str, Any], count: int) -> dict[str, Any]:
    assert 0 <= count <= REPEAT_MAX
    return {"type": "map", "repeat": {"key": key, "value": value, "count": count}}


def v_ext(code: int, payload: bytes) -> dict[str, Any]:
    assert 0 <= code <= 127, code
    return {"type": "ext", "code": code, "hex": payload.hex()}


def v_timestamp(seconds: int, nanoseconds: int = 0) -> dict[str, Any]:
    assert -(2**63) <= seconds <= 2**63 - 1, seconds
    assert 0 <= nanoseconds <= 999_999_999, nanoseconds
    return {
        "type": "timestamp",
        "seconds": str(seconds),
        "nanoseconds": nanoseconds,
    }


# ---------------------------------------------------------------------------
# Model conversion and comparison
# ---------------------------------------------------------------------------


def model_to_python(model: dict[str, Any]) -> Any:
    tag = model["type"]
    if tag == "nil":
        return None
    if tag == "bool":
        return model["value"]
    if tag in {"int", "uint"}:
        return int(model["value"])
    if tag == "float32":
        raise AssertionError("float32 values are decode-only for the Python reference")
    if tag == "float64":
        return struct.unpack(">d", bytes.fromhex(model["bits"]))[0]
    if tag == "str":
        return model["text"]
    if tag == "bin":
        return bytes.fromhex(model["hex"])
    if tag == "ext":
        return msgpack.ExtType(model["code"], bytes.fromhex(model["hex"]))
    if tag == "timestamp":
        return msgpack.Timestamp(int(model["seconds"]), model["nanoseconds"])
    if tag == "array":
        if "repeat" in model:
            item = model_to_python(model["repeat"]["item"])
            return [item for _ in range(model["repeat"]["count"])]
        return [model_to_python(item) for item in model["items"]]
    if tag == "map":
        if "repeat" in model:
            raise AssertionError("repeated maps are decode-only; keys must be unique")
        result: dict[Any, Any] = {}
        for pair in model["pairs"]:
            key = model_to_python(pair["key"])
            value = model_to_python(pair["value"])
            if key in result:
                raise AssertionError(f"roundtrip map key {key!r} is duplicated")
            result[key] = value
        return result
    raise AssertionError(f"unknown model tag {tag!r}")


def model_matches(model: dict[str, Any], actual: Any, path: str = "$") -> None:
    """Raise AssertionError unless ``actual`` decodes to ``model``."""
    tag = model["type"]
    if tag == "nil":
        if actual is not None:
            raise AssertionError(f"{path}: expected nil, got {type(actual).__name__}")
        return
    if tag == "bool":
        if type(actual) is not bool or actual != model["value"]:
            raise AssertionError(f"{path}: expected bool {model['value']}, got {actual!r}")
        return
    if tag in {"int", "uint"}:
        if type(actual) is not int or actual != int(model["value"]):
            raise AssertionError(f"{path}: expected {tag} {model['value']}, got {actual!r}")
        return
    if tag == "float32":
        if not isinstance(actual, float) or struct.pack(">f", actual).hex() != model["bits"]:
            raise AssertionError(f"{path}: expected float32 bits {model['bits']}, got {actual!r}")
        return
    if tag == "float64":
        if not isinstance(actual, float) or struct.pack(">d", actual).hex() != model["bits"]:
            raise AssertionError(f"{path}: expected float64 bits {model['bits']}, got {actual!r}")
        return
    if tag == "str":
        if type(actual) is not str or actual != model["text"]:
            raise AssertionError(f"{path}: expected str {model['text']!r}, got {actual!r}")
        return
    if tag == "bin":
        expected = bytes.fromhex(model["hex"])
        if type(actual) is not bytes or actual != expected:
            raise AssertionError(f"{path}: expected bin of {len(expected)} bytes")
        return
    if tag == "ext":
        expected = msgpack.ExtType(model["code"], bytes.fromhex(model["hex"]))
        if actual != expected:
            raise AssertionError(f"{path}: expected ext {expected!r}, got {actual!r}")
        return
    if tag == "timestamp":
        expected = (int(model["seconds"]), model["nanoseconds"])
        if not isinstance(actual, msgpack.Timestamp):
            raise AssertionError(f"{path}: expected Timestamp, got {type(actual).__name__}")
        if (actual.seconds, actual.nanoseconds) != expected:
            raise AssertionError(f"{path}: expected timestamp {expected}, got {actual!r}")
        return
    if tag == "array":
        if type(actual) is not list:
            raise AssertionError(f"{path}: expected list, got {type(actual).__name__}")
        if "repeat" in model:
            repeat = model["repeat"]
            if len(actual) != repeat["count"]:
                raise AssertionError(f"{path}: expected {repeat['count']} items, got {len(actual)}")
            for index, item in enumerate(actual):
                model_matches(repeat["item"], item, f"{path}[{index}]")
            return
        items = model["items"]
        if len(actual) != len(items):
            raise AssertionError(f"{path}: expected {len(items)} items, got {len(actual)}")
        for index, (expected_item, actual_item) in enumerate(zip(items, actual, strict=True)):
            model_matches(expected_item, actual_item, f"{path}[{index}]")
        return
    if tag == "map":
        if not isinstance(actual, MapPairs):
            raise AssertionError(f"{path}: expected ordered map pairs, got {type(actual).__name__}")
        if "repeat" in model:
            repeat = model["repeat"]
            if len(actual) != repeat["count"]:
                raise AssertionError(f"{path}: expected {repeat['count']} pairs, got {len(actual)}")
            for index, (key, value) in enumerate(actual):
                model_matches(repeat["key"], key, f"{path}.key[{index}]")
                model_matches(repeat["value"], value, f"{path}.value[{index}]")
            return
        pairs = model["pairs"]
        if len(actual) != len(pairs):
            raise AssertionError(f"{path}: expected {len(pairs)} pairs, got {len(actual)}")
        for index, (pair, entry) in enumerate(zip(pairs, actual, strict=True)):
            model_matches(pair["key"], entry[0], f"{path}.key[{index}]")
            model_matches(pair["value"], entry[1], f"{path}.value[{index}]")
        return
    raise AssertionError(f"unknown model tag {tag!r}")


# ---------------------------------------------------------------------------
# Case construction
# ---------------------------------------------------------------------------


def _case(
    *,
    case_id: str,
    category: str,
    mode: str,
    markers: list[str],
    value: dict[str, Any] | None = None,
    encoded: bytes | None = None,
    error: dict[str, str] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": case_id,
        "category": category,
        "mode": mode,
        "markers": markers,
    }
    if value is not None:
        result["value"] = value
    if encoded is not None:
        result["encoded"] = encoded.hex()
    if error is not None:
        result["error"] = error
    if note:
        result["note"] = note
    return result


def roundtrip_case(
    case_id: str,
    category: str,
    markers: list[str],
    value: dict[str, Any],
    note: str | None = None,
) -> dict[str, Any]:
    encoded = msgpack.packb(model_to_python(value), use_bin_type=True)
    model_matches(value, decode_bytes(encoded))
    return _case(
        case_id=case_id,
        category=category,
        mode="roundtrip",
        markers=markers,
        value=value,
        encoded=encoded,
        note=note,
    )


def decode_case(
    case_id: str,
    category: str,
    markers: list[str],
    value: dict[str, Any],
    encoded: bytes,
    note: str | None = None,
) -> dict[str, Any]:
    model_matches(value, decode_bytes(encoded))
    return _case(
        case_id=case_id,
        category=category,
        mode="decode",
        markers=markers,
        value=value,
        encoded=encoded,
        note=note,
    )


def error_case(
    case_id: str,
    encoded: bytes,
    expected_type: str,
    contains: str,
    markers: list[str] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    try:
        decode_bytes(encoded)
    except BaseException as exc:  # noqa: BLE001 - reference behavior is the point
        actual_type = type(exc).__name__
        if actual_type != expected_type:
            raise AssertionError(
                f"{case_id}: expected {expected_type}, got {actual_type}: {exc}"
            ) from exc
        if contains and contains not in str(exc):
            raise AssertionError(
                f"{case_id}: expected message containing {contains!r}, got {str(exc)!r}"
            ) from exc
    else:
        raise AssertionError(f"{case_id}: reference accepted invalid input")
    return _case(
        case_id=case_id,
        category="error",
        mode="error",
        markers=markers or [],
        encoded=encoded,
        error={"type": expected_type, "contains": contains},
        note=note,
    )


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    # nil and bool ---------------------------------------------------------
    cases.append(roundtrip_case("nil", "nil", ["nil"], v_nil()))
    cases.append(roundtrip_case("bool_true", "bool", ["bool"], v_bool(True)))
    cases.append(roundtrip_case("bool_false", "bool", ["bool"], v_bool(False)))

    # integers -------------------------------------------------------------
    integer_cases = [
        ("int_positive_fixint_zero", 0),
        ("int_one", 1),
        ("int_positive_fixint_126", 126),
        ("int_positive_fixint_max", 127),
        ("int_uint8_min", 128),
        ("int_uint8_129", 129),
        ("int_uint8_254", 254),
        ("int_uint8_max", 255),
        ("int_uint16_min", 256),
        ("int_uint16_257", 257),
        ("int_uint16_max", 65535),
        ("int_uint32_min", 65536),
        ("int_uint32_signed_max", 2147483647),
        ("int_uint32_signed_over", 2147483648),
        ("int_uint32_4294967294", 4294967294),
        ("int_uint32_max", 4294967295),
        ("int_uint64_min", 4294967296),
        ("int_int64_max", 9223372036854775807),
        ("int_uint64_above_int64", 9223372036854775808),
        ("int_uint64_max", 18446744073709551615),
        ("int_negative_fixint_minus_one", -1),
        ("int_negative_fixint_minus_31", -31),
        ("int_negative_fixint_min", -32),
        ("int_int8_min", -33),
        ("int_int8_minus_127", -127),
        ("int_int8_min_edge", -128),
        ("int_int16_min", -129),
        ("int_int16_minus_32767", -32767),
        ("int_int16_min_edge", -32768),
        ("int_int32_min", -32769),
        ("int_int32_minus_2147483647", -2147483647),
        ("int_int32_min_edge", -2147483648),
        ("int_int64_min", -2147483649),
        ("int_int64_above_min", -9223372036854775807),
        ("int_int64_min_edge", -9223372036854775808),
    ]

    def integer_marker(value: int) -> str:
        if value >= 0:
            if value <= 127:
                return "positive_fixint"
            if value <= 255:
                return "uint8"
            if value <= 65535:
                return "uint16"
            if value <= 4294967295:
                return "uint32"
            return "uint64"
        if value >= -32:
            return "negative_fixint"
        if value >= -128:
            return "int8"
        if value >= -32768:
            return "int16"
        if value >= -2147483648:
            return "int32"
        return "int64"

    for case_id, value in integer_cases:
        model = v_uint(value) if value >= 0 else v_int(value)
        cases.append(roundtrip_case(case_id, "int", [integer_marker(value)], model))

    # floats ---------------------------------------------------------------
    cases.append(roundtrip_case("float64_one_and_half", "float", ["float64"], v_float64(1.5)))
    cases.append(roundtrip_case("float64_negative_zero", "float", ["float64"], v_float64(-0.0)))
    cases.append(
        roundtrip_case(
            "float64_positive_infinity",
            "float",
            ["float64"],
            v_float64_bits("7ff0000000000000"),
        )
    )
    cases.append(
        roundtrip_case(
            "float64_nan_payload",
            "float",
            ["float64"],
            v_float64_bits("7ff8000000000001"),
            note="NaN payload bits must survive the reference codec.",
        )
    )
    for case_id, bits in [
        ("float32_one_and_half", "3fc00000"),
        ("float32_negative_zero", "80000000"),
        ("float32_positive_infinity", "7f800000"),
    ]:
        cases.append(
            decode_case(
                case_id,
                "float",
                ["float32"],
                v_float32(bits),
                bytes.fromhex("ca" + bits),
                note="The Python reference packs only float64, so float32 is decode-only.",
            )
        )

    # strings --------------------------------------------------------------
    cases.append(roundtrip_case("str_empty", "str", ["fixstr"], v_str("")))
    cases.append(roundtrip_case("str_ascii", "str", ["fixstr"], v_str("hello")))
    cases.append(roundtrip_case("str_unicode", "str", ["fixstr"], v_str("héllo € 😀")))
    cases.append(
        roundtrip_case(
            "str_embedded_nul",
            "str",
            ["fixstr"],
            v_str("a\u0000b"),
            note="Embedded NUL is data, not a terminator.",
        )
    )
    cases.append(roundtrip_case("str_fixstr_max", "str", ["fixstr"], v_str("x" * 31)))
    cases.append(roundtrip_case("str_str8_min", "str", ["str8"], v_str("x" * 32)))
    cases.append(roundtrip_case("str_str8_max", "str", ["str8"], v_str("x" * 255)))
    cases.append(roundtrip_case("str_str16", "str", ["str16"], v_str("x" * 256)))
    cases.append(roundtrip_case("str_str32", "str", ["str32"], v_str("x" * 65536)))

    # binary ---------------------------------------------------------------
    cases.append(roundtrip_case("bin_empty", "bin", ["bin8"], v_bin(b"")))
    cases.append(
        roundtrip_case(
            "bin_non_utf8", "bin", ["bin8"], v_bin(b"\x00\xff\x80"), note="Binary is not text."
        )
    )
    cases.append(roundtrip_case("bin_bin8_max", "bin", ["bin8"], v_bin(b"x" * 255)))
    cases.append(roundtrip_case("bin_bin16", "bin", ["bin16"], v_bin(b"x" * 256)))
    cases.append(roundtrip_case("bin_bin32", "bin", ["bin32"], v_bin(b"x" * 65536)))

    # arrays ---------------------------------------------------------------
    cases.append(roundtrip_case("array_empty", "array", ["fixarray"], v_array([])))
    cases.append(
        roundtrip_case(
            "array_mixed", "array", ["fixarray"], v_array([v_int(1), v_str("two"), v_bool(True)])
        )
    )
    cases.append(
        roundtrip_case(
            "array_nested",
            "array",
            ["fixarray"],
            v_array([v_array([]), v_array([v_int(1)])]),
        )
    )
    cases.append(
        roundtrip_case(
            "array16",
            "array",
            ["array16"],
            v_array([v_int(index) for index in range(16)]),
        )
    )
    cases.append(
        roundtrip_case(
            "array32_repeated_nil",
            "array",
            ["array32"],
            v_array_repeat(v_nil(), 65536),
            note="Repeated model keeps the JSON compact; encoding covers array32.",
        )
    )

    # maps -----------------------------------------------------------------
    cases.append(roundtrip_case("map_empty", "map", ["fixmap"], v_map([])))
    cases.append(
        roundtrip_case(
            "map_mixed_keys",
            "map",
            ["fixmap"],
            v_map(
                [
                    (v_str("name"), v_str("pyromojo")),
                    (v_int(1), v_bool(True)),
                    (v_bool(False), v_nil()),
                ]
            ),
        )
    )
    cases.append(
        roundtrip_case(
            "map16",
            "map",
            ["map16"],
            v_map([(v_str(f"k{index}"), v_int(index)) for index in range(16)]),
        )
    )
    cases.append(
        decode_case(
            "map_duplicate_keys",
            "map",
            ["fixmap"],
            v_map([(v_str("k"), v_int(1)), (v_str("k"), v_int(2))]),
            bytes.fromhex("82a16b01a16b02"),
            note="Duplicate keys decode as ordered pairs; the last value is not collapsed.",
        )
    )
    cases.append(
        decode_case(
            "map_array_key",
            "map",
            ["fixmap"],
            v_map([(v_array([v_int(1), v_int(2)]), v_nil())]),
            bytes.fromhex("81920102c0"),
            note="Non-hashable keys are accepted as ordered pairs by the reference.",
        )
    )
    cases.append(
        decode_case(
            "map32_repeated_pair",
            "map",
            ["map32"],
            v_map_repeat(v_int(0), v_nil(), 65536),
            bytes.fromhex("df00010000") + b"\x00\xc0" * 65536,
            note="map32 header with 65536 identical key/value pairs.",
        )
    )

    # extensions -----------------------------------------------------------
    ext_cases = [
        ("ext_fixext1", "fixext1", 42, b"\x01"),
        ("ext_fixext2", "fixext2", 42, b"\x01\x02"),
        ("ext_fixext4", "fixext4", 42, b"\x00\x00\x00\x01"),
        ("ext_fixext8", "fixext8", 42, b"\x00\x00\x00\x00\x00\x00\x00\x01"),
        (
            "ext_fixext16",
            "fixext16",
            127,
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01",
        ),
        ("ext_ext8", "ext8", 42, b"\x00\x01\x02"),
        (
            "ext_ext16",
            "ext16",
            42,
            b"x" * 256,
        ),
        (
            "ext_ext32",
            "ext32",
            42,
            b"x" * 65536,
        ),
    ]
    for case_id, marker, code, payload in ext_cases:
        cases.append(roundtrip_case(case_id, "ext", [marker], v_ext(code, payload)))

    # timestamps -----------------------------------------------------------
    timestamp_cases = [
        ("timestamp32_zero", "timestamp32", 1, 0),
        ("timestamp32_max", "timestamp32", 2**32 - 1, 0),
        ("timestamp64_min", "timestamp64", 2**32, 1),
        ("timestamp64_max", "timestamp64", 2**34 - 1, 999_999_999),
        ("timestamp96_negative_seconds", "timestamp96", -1, 0),
        ("timestamp96_extended", "timestamp96", 2**34, 999_999_999),
    ]
    for case_id, marker, seconds, nanoseconds in timestamp_cases:
        cases.append(
            roundtrip_case(
                case_id,
                "timestamp",
                [marker],
                v_timestamp(seconds, nanoseconds),
            )
        )

    # errors ---------------------------------------------------------------
    cases.append(error_case("error_empty_input", b"", "ValueError", "incomplete input"))
    cases.append(
        error_case(
            "error_truncated_uint16",
            bytes.fromhex("cd01"),
            "ValueError",
            "incomplete input",
        )
    )
    cases.append(
        error_case(
            "error_truncated_str8",
            bytes.fromhex("d9056162"),
            "ValueError",
            "incomplete input",
        )
    )
    cases.append(
        error_case(
            "error_reserved_marker",
            bytes.fromhex("c1"),
            "FormatError",
            "",
            note="0xc1 is the only permanently reserved MessagePack marker.",
        )
    )
    cases.append(
        error_case(
            "error_trailing_bytes",
            bytes.fromhex("0000"),
            "ExtraData",
            "extra data",
        )
    )
    cases.append(
        error_case(
            "error_invalid_utf8",
            bytes.fromhex("a180"),
            "UnicodeDecodeError",
            "invalid start byte",
        )
    )
    cases.append(
        error_case(
            "error_reference_depth_limit",
            b"\x91" * 1025 + b"\x00",
            "StackError",
            "",
            note="msgpack 1.2.4 caps nesting at 1024; PyroMojo's default is 128.",
        )
    )

    return cases


def build_bundle(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
        "reference": {"package": "msgpack", "version": REFERENCE_VERSION},
        "decode_options": {
            "strict_map_key": False,
            "duplicate_keys": "preserved_in_order",
        },
        "cases": cases,
    }


# ---------------------------------------------------------------------------
# Mojo emission
# ---------------------------------------------------------------------------


def mojo_string(text: str) -> str:
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


class _MojoBuilder:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.counter = 0

    def _tmp(self, stem: str) -> str:
        self.counter += 1
        return f"{stem}_{self.counter}"

    def expression(self, model: dict[str, Any]) -> str:
        tag = model["type"]
        if tag == "nil":
            return "Value.nil()"
        if tag == "bool":
            return f"Value.bool({'True' if model['value'] else 'False'})"
        if tag == "int":
            return f"int_from_decimal({mojo_string(model['value'])})"
        if tag == "uint":
            return f"uint_from_decimal({mojo_string(model['value'])})"
        if tag == "float32":
            return f"Value.float32(UInt32(0x{model['bits']}))"
        if tag == "float64":
            return f"Value.float64_bits(UInt64(0x{model['bits']}))"
        if tag == "str":
            return f"string_from_hex({mojo_string(model['text'].encode('utf-8').hex())})"
        if tag == "bin":
            return f"Value.binary(decode_hex({mojo_string(model['hex'])}))"
        if tag == "ext":
            return f"ext_from_hex(Int8({model['code']}), {mojo_string(model['hex'])})"
        if tag == "timestamp":
            return f"Value.timestamp(Int64({model['seconds']}), UInt32({model['nanoseconds']}))"
        if tag == "array":
            if "repeat" in model:
                item = self.expression(model["repeat"]["item"])
                return f"Value.array_repeat({item}, {model['repeat']['count']})"
            items = model["items"]
            if not items:
                return "Value.array(List[Value]())"
            name = self._tmp("items")
            self.lines.append(f"    var {name} = List[Value](capacity={len(items)})")
            for item in items:
                self.lines.append(f"    {name}.append({self.expression(item)})")
            return f"Value.array({name}^)"
        if tag == "map":
            if "repeat" in model:
                key = self.expression(model["repeat"]["key"])
                value = self.expression(model["repeat"]["value"])
                return f"Value.map_repeat({key}, {value}, {model['repeat']['count']})"
            pairs = model["pairs"]
            if not pairs:
                return "Value.map(List[Value]())"
            name = self._tmp("pairs")
            self.lines.append(f"    var {name} = List[Value](capacity={len(pairs) * 2})")
            for pair in pairs:
                self.lines.append(f"    {name}.append({self.expression(pair['key'])})")
                self.lines.append(f"    {name}.append({self.expression(pair['value'])})")
            return f"Value.map({name}^)"
        raise AssertionError(f"unknown model tag {tag!r}")


def build_mojo(cases: list[dict[str, Any]]) -> str:
    lines = [
        '"""Generated by libraries/msgpack/python_reference/generate_vectors.py.',
        "",
        "Do not edit by hand. Regenerate and use --check to detect drift.",
        '"""',
        "",
        "from std.collections import List",
        "",
        "from mojo_msgpack.value import Value",
        "",
        "from vector_support import (",
        "    VectorCase,",
        "    decode_hex,",
        "    ext_from_hex,",
        "    int_from_decimal,",
        "    string_from_hex,",
        "    uint_from_decimal,",
        ")",
        "",
        f"comptime VECTOR_COUNT: Int = {len(cases)}",
        "",
    ]

    for case in cases:
        case_id = case["id"]
        if "value" not in case:
            continue
        builder = _MojoBuilder()
        expression = builder.expression(case["value"])
        lines.append(f"def _build_{case_id}() raises -> Value:")
        lines.extend(builder.lines)
        lines.append(f"    return {expression}")
        lines.append("")

    lines.append("def value_for_case(case_id: StaticString) raises -> Value:")
    for case in cases:
        if "value" not in case:
            continue
        lines.append(f'    if case_id == "{case["id"]}":')
        lines.append(f"        return _build_{case['id']}()")
    lines.append('    raise Error("case " + String(case_id) + " has no value model (error case)")')
    lines.append("")

    lines.append("def load_vectors() -> List[VectorCase]:")
    lines.append("    return [")
    for case in cases:
        error_type = case.get("error", {}).get("type", "")
        error_contains = case.get("error", {}).get("contains", "")
        lines.append(
            "        VectorCase("
            f"{mojo_string(case['id'])}, "
            f"{mojo_string(case['category'])}, "
            f"{mojo_string(case['mode'])}, "
            f"{mojo_string(case['encoded'])}, "
            f"{'True' if 'value' in case else 'False'}, "
            f"{mojo_string(error_type)}, "
            f"{mojo_string(error_contains)}"
            "),"
        )
    lines.append("    ]")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output and drift detection
# ---------------------------------------------------------------------------


def _json_text(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _check(path: Path, text: str, label: str) -> bool:
    if not path.exists():
        print(f"{label}: missing {path}", file=sys.stderr)
        return False
    current = path.read_text(encoding="utf-8")
    if current == text:
        return True
    diff = list(
        difflib.unified_diff(
            current.splitlines(),
            text.splitlines(),
            fromfile=f"{path} (committed)",
            tofile=f"{path} (generated)",
            lineterm="",
            n=2,
        )
    )
    print(f"{label}: drift detected in {path}", file=sys.stderr)
    for line in diff[:80]:
        print(line, file=sys.stderr)
    if len(diff) > 80:
        print(f"... {len(diff) - 80} more diff lines", file=sys.stderr)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--mojo", type=Path, default=DEFAULT_MOJO)
    args = parser.parse_args(argv)

    installed = importlib.metadata.version("msgpack")
    if installed != REFERENCE_VERSION:
        parser.exit(
            2,
            f"msgpack {REFERENCE_VERSION} required, found {installed}. "
            "Install libraries/msgpack/python_reference/requirements.txt.\n",
        )

    cases = build_cases()
    bundle = build_bundle(cases)
    bundle_text = _json_text(bundle)
    mojo_text = build_mojo(cases)

    if args.check:
        ok = _check(args.bundle, bundle_text, "bundle")
        ok = _check(args.mojo, mojo_text, "mojo") and ok
        if ok:
            print(f"vectors: {len(cases)} cases, committed artifacts are current")
        return 0 if ok else 1

    _write(args.bundle, bundle_text)
    _write(args.mojo, mojo_text)
    print(f"vectors: wrote {len(cases)} cases to {args.bundle} and {args.mojo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
