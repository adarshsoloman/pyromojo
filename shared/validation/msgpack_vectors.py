"""Structural validation for MessagePack golden vector bundles.

The bundle schema is published as JSON Schema, but normal test runs must not
require the optional ``jsonschema`` package. This module implements the checks
that matter for the committed bundle with the standard library only:

* required keys and exact key sets at every level,
* case ids, categories, modes, and marker names,
* the tagged value model used to preserve integer, float, binary, extension,
  timestamp, and ordered-map-pair data through JSON,
* mode-dependent requirements for ``value`` / ``encoded`` / ``error``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
GENERATOR = {"name": "msgpack_vectors", "version": "1.0.0"}
REFERENCE_PACKAGE = "msgpack"
REFERENCE_VERSION = "1.2.4"

MARKERS = {
    "nil",
    "bool",
    "positive_fixint",
    "negative_fixint",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "int8",
    "int16",
    "int32",
    "int64",
    "float32",
    "float64",
    "fixstr",
    "str8",
    "str16",
    "str32",
    "bin8",
    "bin16",
    "bin32",
    "fixarray",
    "array16",
    "array32",
    "fixmap",
    "map16",
    "map32",
    "fixext1",
    "fixext2",
    "fixext4",
    "fixext8",
    "fixext16",
    "ext8",
    "ext16",
    "ext32",
    "timestamp32",
    "timestamp64",
    "timestamp96",
}

CATEGORIES = {
    "nil",
    "bool",
    "int",
    "float",
    "str",
    "bin",
    "array",
    "map",
    "ext",
    "timestamp",
    "error",
}

MODES = {"roundtrip", "decode", "error"}
HEX_RE = re.compile(r"^(?:[0-9a-f]{2})*$")
DECIMAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
ID_RE = re.compile(r"^[a-z0-9_]+$")
INT_MIN = -(2**63)
INT_MAX = 2**64 - 1
TIMESTAMP_SECONDS_MIN = -(2**63)
TIMESTAMP_SECONDS_MAX = 2**63 - 1
REPEAT_MAX = 1_000_000


class BundleError(ValueError):
    """Raised when a bundle cannot be parsed or is structurally invalid."""


def load_bundle(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BundleError("bundle root must be a JSON object")
    return data


def _check_keys(
    obj: dict[str, Any],
    required: set[str],
    allowed: set[str],
    where: str,
    errors: list[str],
) -> None:
    missing = sorted(required - obj.keys())
    unknown = sorted(obj.keys() - allowed)
    if missing:
        errors.append(f"{where}: missing keys {missing}")
    if unknown:
        errors.append(f"{where}: unknown keys {unknown}")


def _validate_value(value: Any, where: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{where}: value model must be an object")
        return
    tag = value.get("type")
    if tag == "nil":
        _check_keys(value, {"type"}, {"type"}, where, errors)
    elif tag == "bool":
        _check_keys(value, {"type", "value"}, {"type", "value"}, where, errors)
        if not isinstance(value.get("value"), bool):
            errors.append(f"{where}: bool value must be true or false")
    elif tag == "int":
        _check_keys(value, {"type", "value"}, {"type", "value"}, where, errors)
        raw = value.get("value")
        if not isinstance(raw, str) or not DECIMAL_RE.fullmatch(raw):
            errors.append(f"{where}: int value must be a canonical decimal string")
        elif not INT_MIN <= int(raw) <= INT_MAX:
            errors.append(f"{where}: integer {raw} is outside the MessagePack int range")
    elif tag in {"float32", "float64"}:
        _check_keys(value, {"type", "bits"}, {"type", "bits"}, where, errors)
        bits = value.get("bits")
        width = 8 if tag == "float32" else 16
        if not isinstance(bits, str) or not re.fullmatch(rf"[0-9a-f]{{{width}}}", bits):
            errors.append(f"{where}: {tag} bits must be {width} lowercase hex digits")
    elif tag == "str":
        _check_keys(value, {"type", "text"}, {"type", "text"}, where, errors)
        text = value.get("text")
        if not isinstance(text, str):
            errors.append(f"{where}: str text must be a string")
        else:
            try:
                text.encode("utf-8")
            except UnicodeEncodeError:
                errors.append(f"{where}: str text is not valid Unicode scalar text")
    elif tag == "bin":
        _check_keys(value, {"type", "hex"}, {"type", "hex"}, where, errors)
        raw = value.get("hex")
        if not isinstance(raw, str) or not HEX_RE.fullmatch(raw):
            errors.append(f"{where}: bin hex must be lowercase even-length hex")
    elif tag == "array":
        if "repeat" in value:
            _check_keys(value, {"type", "repeat"}, {"type", "repeat"}, where, errors)
            _validate_repeat(value["repeat"], where + ".repeat", errors, with_item=True)
        else:
            _check_keys(value, {"type", "items"}, {"type", "items"}, where, errors)
            items = value.get("items")
            if not isinstance(items, list):
                errors.append(f"{where}: array items must be a list")
            else:
                for index, item in enumerate(items):
                    _validate_value(item, f"{where}.items[{index}]", errors)
    elif tag == "map":
        if "repeat" in value:
            _check_keys(value, {"type", "repeat"}, {"type", "repeat"}, where, errors)
            _validate_repeat(value["repeat"], where + ".repeat", errors, with_item=False)
        else:
            _check_keys(value, {"type", "pairs"}, {"type", "pairs"}, where, errors)
            pairs = value.get("pairs")
            if not isinstance(pairs, list):
                errors.append(f"{where}: map pairs must be a list")
            else:
                for index, pair in enumerate(pairs):
                    pair_where = f"{where}.pairs[{index}]"
                    if not isinstance(pair, dict):
                        errors.append(f"{pair_where}: pair must be an object")
                        continue
                    _check_keys(pair, {"key", "value"}, {"key", "value"}, pair_where, errors)
                    if "key" in pair:
                        _validate_value(pair["key"], pair_where + ".key", errors)
                    if "value" in pair:
                        _validate_value(pair["value"], pair_where + ".value", errors)
    elif tag == "ext":
        _check_keys(value, {"type", "code", "hex"}, {"type", "code", "hex"}, where, errors)
        code = value.get("code")
        if not isinstance(code, int) or isinstance(code, bool) or not 0 <= code <= 127:
            errors.append(f"{where}: ext code must be an integer in 0..127")
        raw = value.get("hex")
        if not isinstance(raw, str) or not HEX_RE.fullmatch(raw):
            errors.append(f"{where}: ext hex must be lowercase even-length hex")
    elif tag == "timestamp":
        _check_keys(
            value,
            {"type", "seconds", "nanoseconds"},
            {"type", "seconds", "nanoseconds"},
            where,
            errors,
        )
        seconds = value.get("seconds")
        nanoseconds = value.get("nanoseconds")
        if not isinstance(seconds, str) or not DECIMAL_RE.fullmatch(seconds):
            errors.append(f"{where}: timestamp seconds must be a canonical decimal string")
        elif not TIMESTAMP_SECONDS_MIN <= int(seconds) <= TIMESTAMP_SECONDS_MAX:
            errors.append(f"{where}: timestamp seconds are outside the signed 64-bit range")
        if (
            not isinstance(nanoseconds, int)
            or isinstance(nanoseconds, bool)
            or not 0 <= nanoseconds <= 999_999_999
        ):
            errors.append(f"{where}: timestamp nanoseconds must be an integer in 0..999999999")
    else:
        errors.append(f"{where}: unknown value model type {tag!r}")


def _validate_repeat(repeat: Any, where: str, errors: list[str], *, with_item: bool) -> None:
    if not isinstance(repeat, dict):
        errors.append(f"{where}: repeat must be an object")
        return
    required = {"count", "item"} if with_item else {"count", "key", "value"}
    _check_keys(repeat, required, required, where, errors)
    count = repeat.get("count")
    if not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= REPEAT_MAX:
        errors.append(f"{where}: repeat count must be an integer in 0..{REPEAT_MAX}")
    if with_item and "item" in repeat:
        _validate_value(repeat["item"], where + ".item", errors)
    if not with_item:
        if "key" in repeat:
            _validate_value(repeat["key"], where + ".key", errors)
        if "value" in repeat:
            _validate_value(repeat["value"], where + ".value", errors)


def _validate_case(case: Any, index: int, errors: list[str]) -> str | None:
    where = f"cases[{index}]"
    if not isinstance(case, dict):
        errors.append(f"{where}: case must be an object")
        return None
    _check_keys(
        case,
        {"id", "category", "mode", "markers"},
        {"id", "category", "mode", "markers", "value", "encoded", "error", "note"},
        where,
        errors,
    )
    case_id = case.get("id")
    if not isinstance(case_id, str) or not ID_RE.fullmatch(case_id):
        errors.append(f"{where}: id must match [a-z0-9_]+")
        case_id = None
    else:
        where = f"case {case_id!r}"
    category = case.get("category")
    if category not in CATEGORIES:
        errors.append(f"{where}: unknown category {category!r}")
    mode = case.get("mode")
    if mode not in MODES:
        errors.append(f"{where}: unknown mode {mode!r}")
    markers = case.get("markers")
    if not isinstance(markers, list):
        errors.append(f"{where}: markers must be a list")
    else:
        if len(set(markers)) != len(markers):
            errors.append(f"{where}: markers must be unique")
        for marker in markers:
            if marker not in MARKERS:
                errors.append(f"{where}: unknown marker {marker!r}")

    encoded = case.get("encoded")
    if encoded is not None and (not isinstance(encoded, str) or not HEX_RE.fullmatch(encoded)):
        errors.append(f"{where}: encoded must be lowercase even-length hex")
    if "note" in case and not isinstance(case["note"], str):
        errors.append(f"{where}: note must be a string")

    if mode in {"roundtrip", "decode"}:
        if "value" not in case:
            errors.append(f"{where}: {mode} cases require a value model")
        else:
            _validate_value(case["value"], where + ".value", errors)
        if "encoded" not in case:
            errors.append(f"{where}: {mode} cases require encoded bytes")
        if "error" in case:
            errors.append(f"{where}: {mode} cases must not declare an error")
    elif mode == "error":
        if "encoded" not in case:
            errors.append(f"{where}: error cases require encoded bytes")
        if "value" in case:
            errors.append(f"{where}: error cases must not declare a value model")
        error = case.get("error")
        if not isinstance(error, dict):
            errors.append(f"{where}: error cases require an error object")
        else:
            _check_keys(error, {"type", "contains"}, {"type", "contains"}, where + ".error", errors)
            if not isinstance(error.get("type"), str) or not error.get("type"):
                errors.append(f"{where}.error: type must be a non-empty string")
            if not isinstance(error.get("contains"), str):
                errors.append(f"{where}.error: contains must be a string")
    return case_id


def validate_bundle(bundle: dict[str, Any]) -> list[str]:
    """Return a list of human-readable structural errors (empty means valid)."""
    errors: list[str] = []
    _check_keys(
        bundle,
        {"schema_version", "generator", "reference", "decode_options", "cases"},
        {"schema_version", "generator", "reference", "decode_options", "cases"},
        "bundle",
        errors,
    )
    if bundle.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"bundle: schema_version must be {SCHEMA_VERSION!r}")
    if bundle.get("generator") != GENERATOR:
        errors.append(f"bundle: generator must be {GENERATOR!r}")

    reference = bundle.get("reference")
    if not isinstance(reference, dict):
        errors.append("bundle: reference must be an object")
    else:
        _check_keys(reference, {"package", "version"}, {"package", "version"}, "reference", errors)
        if reference.get("package") != REFERENCE_PACKAGE:
            errors.append(f"reference: package must be {REFERENCE_PACKAGE!r}")
        if reference.get("version") != REFERENCE_VERSION:
            errors.append(f"reference: version must be {REFERENCE_VERSION!r}")

    options = bundle.get("decode_options")
    if not isinstance(options, dict):
        errors.append("bundle: decode_options must be an object")
    else:
        _check_keys(
            options,
            {"strict_map_key", "duplicate_keys"},
            {"strict_map_key", "duplicate_keys"},
            "decode_options",
            errors,
        )
        if options.get("strict_map_key") is not False:
            errors.append("decode_options: strict_map_key must be false")
        if options.get("duplicate_keys") != "preserved_in_order":
            errors.append("decode_options: duplicate_keys must be 'preserved_in_order'")

    cases = bundle.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("bundle: cases must be a non-empty list")
        return errors

    seen: set[str] = set()
    for index, case in enumerate(cases):
        case_id = _validate_case(case, index, errors)
        if case_id is not None:
            if case_id in seen:
                errors.append(f"case {case_id!r}: duplicate id")
            seen.add(case_id)
    return errors


def validate_bundle_file(path: str | Path) -> list[str]:
    return validate_bundle(load_bundle(path))


if __name__ == "__main__":
    import sys

    problems = validate_bundle_file(sys.argv[1])
    for problem in problems:
        print(problem)
    raise SystemExit(1 if problems else 0)
