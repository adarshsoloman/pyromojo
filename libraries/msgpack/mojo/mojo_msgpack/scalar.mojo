"""Float, string, and binary MessagePack codecs plus scalar dispatch.

The wire codecs preserve float bit patterns exactly, validate string payloads
as UTF-8, and leave binary payloads untouched. The CLI transfer model keeps
the Phase 2 integer model unchanged and adds tagged float, string, and binary
models for cross-language tests.
"""

from std.collections import List

from mojo_msgpack.integer import (
    MODEL_SIGNED,
    MODEL_UNSIGNED,
    append_integer_model,
    decode_exact as decode_integer_exact,
    decode_integer_model,
    encode_value as encode_integer_value,
)
from mojo_msgpack.value import (
    VALUE_BIN,
    VALUE_FLOAT32,
    VALUE_FLOAT64,
    VALUE_INT,
    VALUE_STR,
    VALUE_UINT,
    Value,
)


comptime MODEL_FLOAT32: UInt8 = 0x10
comptime MODEL_FLOAT64: UInt8 = 0x11
comptime MODEL_STR: UInt8 = 0x12
comptime MODEL_BIN: UInt8 = 0x13

comptime MARKER_FLOAT32: UInt8 = 0xCA
comptime MARKER_FLOAT64: UInt8 = 0xCB
comptime MARKER_STR8: UInt8 = 0xD9
comptime MARKER_STR16: UInt8 = 0xDA
comptime MARKER_STR32: UInt8 = 0xDB
comptime MARKER_BIN8: UInt8 = 0xC4
comptime MARKER_BIN16: UInt8 = 0xC5
comptime MARKER_BIN32: UInt8 = 0xC6


def _failure(category: StaticString, offset: Int, detail: String) -> Error:
    return Error(String(category) + ": offset " + String(offset) + ": " + detail)


def _append_be(mut out: List[UInt8], bits: UInt64, width: Int):
    for index in range(width):
        var shift = UInt64((width - 1 - index) * 8)
        out.append(UInt8((bits >> shift) & 0xFF))


def _read_be(data: Span[UInt8, _], offset: Int, width: Int) -> UInt64:
    var bits: UInt64 = 0
    for index in range(width):
        bits = (bits << 8) | UInt64(data[offset + index])
    return bits


def _require(
    data: Span[UInt8, _], marker_offset: Int, start: Int, count: Int, marker: UInt8, what: String
) raises:
    if start + count > len(data):
        raise _failure(
            "truncated",
            marker_offset,
            "marker "
            + String(Int(marker))
            + " needs "
            + String(count)
            + " "
            + what
            + " byte(s), have "
            + String(len(data) - start),
        )


def _finish(data: Span[UInt8, _], end: Int) raises:
    if end != len(data):
        raise _failure(
            "trailing-data",
            end,
            String(len(data) - end) + " byte(s) remain",
        )


def encode_float32(mut out: List[UInt8], bits: UInt32):
    out.append(MARKER_FLOAT32)
    _append_be(out, UInt64(bits), 4)


def encode_float64(mut out: List[UInt8], bits: UInt64):
    out.append(MARKER_FLOAT64)
    _append_be(out, bits, 8)


def _append_length(mut out: List[UInt8], marker: UInt8, length: Int, width: Int):
    out.append(marker)
    _append_be(out, UInt64(length), width)


def encode_str(mut out: List[UInt8], text: Span[UInt8, _]) raises:
    var length = len(text)
    if length <= 31:
        out.append(0xA0 | UInt8(length))
    elif length <= 255:
        _append_length(out, MARKER_STR8, length, 1)
    elif length <= 65535:
        _append_length(out, MARKER_STR16, length, 2)
    elif length <= 4294967295:
        _append_length(out, MARKER_STR32, length, 4)
    else:
        raise Error("invalid-length: string exceeds the str32 limit")
    for byte in text:
        out.append(byte)


def encode_bin(mut out: List[UInt8], payload: Span[UInt8, _]) raises:
    var length = len(payload)
    if length <= 255:
        _append_length(out, MARKER_BIN8, length, 1)
    elif length <= 65535:
        _append_length(out, MARKER_BIN16, length, 2)
    elif length <= 4294967295:
        _append_length(out, MARKER_BIN32, length, 4)
    else:
        raise Error("invalid-length: binary exceeds the bin32 limit")
    for byte in payload:
        out.append(byte)


def encode_scalar_value(mut out: List[UInt8], value: Value) raises:
    if value.kind == VALUE_INT or value.kind == VALUE_UINT:
        encode_integer_value(out, value)
    elif value.kind == VALUE_FLOAT32:
        encode_float32(out, value.as_float32_bits())
    elif value.kind == VALUE_FLOAT64:
        encode_float64(out, value.as_float64_bits())
    elif value.kind == VALUE_STR:
        encode_str(out, Span(value.data))
    elif value.kind == VALUE_BIN:
        encode_bin(out, Span(value.data))
    else:
        raise Error(
            "unsupported-value: kind "
            + String(Int(value.kind))
            + " is not a supported scalar"
        )


def _read_length(
    data: Span[UInt8, _], marker_offset: Int, marker: UInt8, width: Int
) raises -> Int:
    _require(data, marker_offset, marker_offset + 1, width, marker, "length")
    return Int(_read_be(data, marker_offset + 1, width))


def _decode_str(data: Span[UInt8, _], marker_offset: Int, length: Int, header: Int) raises -> Value:
    var start = marker_offset + header
    _require(data, marker_offset, start, length, data[marker_offset], "payload")
    var end = start + length
    var text: String
    try:
        text = String(from_utf8=Span(data)[start:end])
    except error:
        raise _failure("invalid-utf8", start, String(error))
    return Value.string(text^)


def _decode_bin(data: Span[UInt8, _], marker_offset: Int, length: Int, header: Int) raises -> Value:
    var start = marker_offset + header
    _require(data, marker_offset, start, length, data[marker_offset], "payload")
    var end = start + length
    var payload = List[UInt8](capacity=length)
    for byte in data[start:end]:
        payload.append(byte)
    return Value.binary(payload^)


def _is_integer_marker(marker: UInt8) -> Bool:
    if marker <= 0x7F or marker >= 0xE0:
        return True
    return (
        marker == 0xCC
        or marker == 0xCD
        or marker == 0xCE
        or marker == 0xCF
        or marker == 0xD0
        or marker == 0xD1
        or marker == 0xD2
        or marker == 0xD3
    )


def _integer_marker_width(marker: UInt8) -> Int:
    if marker <= 0x7F or marker >= 0xE0:
        return 1
    if marker == 0xCC or marker == 0xD0:
        return 2
    if marker == 0xCD or marker == 0xD1:
        return 3
    if marker == 0xCE or marker == 0xD2:
        return 5
    return 9


def decode_scalar_at(data: Span[UInt8, _], mut pos: Int) raises -> Value:
    """Decode one scalar at ``pos`` and advance past it on success.

    Containers are deliberately not handled here; the recursive container
    decoder dispatches those before calling this function.
    """
    if pos >= len(data):
        raise _failure("truncated", pos, "need 1 marker byte")
    var marker = data[pos]

    if _is_integer_marker(marker):
        var width = _integer_marker_width(marker)
        _require(data, pos, pos + 1, width - 1, marker, "payload")
        var end = pos + width
        var value = decode_integer_exact(Span(data)[pos:end])
        pos = end
        return value^

    if marker == MARKER_FLOAT32:
        _require(data, pos, pos + 1, 4, marker, "payload")
        var value = Value.float32(UInt32(_read_be(data, pos + 1, 4)))
        pos += 5
        return value^
    if marker == MARKER_FLOAT64:
        _require(data, pos, pos + 1, 8, marker, "payload")
        var value = Value.float64_bits(_read_be(data, pos + 1, 8))
        pos += 9
        return value^

    if marker >= 0xA0 and marker <= 0xBF:
        var length = Int(marker & 0x1F)
        var value = _decode_str(data, pos, length, 1)
        pos += 1 + length
        return value^
    if marker == MARKER_STR8:
        var length = _read_length(data, pos, marker, 1)
        var value = _decode_str(data, pos, length, 2)
        pos += 2 + length
        return value^
    if marker == MARKER_STR16:
        var length = _read_length(data, pos, marker, 2)
        var value = _decode_str(data, pos, length, 3)
        pos += 3 + length
        return value^
    if marker == MARKER_STR32:
        var length = _read_length(data, pos, marker, 4)
        var value = _decode_str(data, pos, length, 5)
        pos += 5 + length
        return value^

    if marker == MARKER_BIN8:
        var length = _read_length(data, pos, marker, 1)
        var value = _decode_bin(data, pos, length, 2)
        pos += 2 + length
        return value^
    if marker == MARKER_BIN16:
        var length = _read_length(data, pos, marker, 2)
        var value = _decode_bin(data, pos, length, 3)
        pos += 3 + length
        return value^
    if marker == MARKER_BIN32:
        var length = _read_length(data, pos, marker, 4)
        var value = _decode_bin(data, pos, length, 5)
        pos += 5 + length
        return value^

    if marker == 0xC1:
        raise _failure("invalid-marker", pos, "marker 193 is permanently reserved")
    raise _failure(
        "unsupported-marker",
        pos,
        "marker " + String(Int(marker)) + " is not a supported scalar",
    )


def decode_scalar_exact(data: Span[UInt8, _]) raises -> Value:
    """Decode exactly one integer, float, string, or binary value."""
    var pos = 0
    var value = decode_scalar_at(data, pos)
    _finish(data, pos)
    return value^


def append_scalar_model(mut out: List[UInt8], value: Value) raises:
    """Append the CLI transfer model for a supported scalar."""
    if value.kind == VALUE_INT or value.kind == VALUE_UINT:
        append_integer_model(out, value)
    elif value.kind == VALUE_FLOAT32:
        out.append(MODEL_FLOAT32)
        _append_be(out, UInt64(value.as_float32_bits()), 4)
    elif value.kind == VALUE_FLOAT64:
        out.append(MODEL_FLOAT64)
        _append_be(out, value.as_float64_bits(), 8)
    elif value.kind == VALUE_STR:
        out.append(MODEL_STR)
        for byte in value.data:
            out.append(byte)
    elif value.kind == VALUE_BIN:
        out.append(MODEL_BIN)
        for byte in value.data:
            out.append(byte)
    else:
        raise Error(
            "unsupported-value: kind "
            + String(Int(value.kind))
            + " is not a supported scalar"
        )


def _require_model_length(bytes: Span[UInt8, _], expected: Int) raises:
    if len(bytes) < expected:
        raise _failure(
            "truncated",
            0,
            "scalar model needs " + String(expected) + " bytes, have " + String(len(bytes)),
        )
    if len(bytes) > expected:
        raise _failure(
            "trailing-data",
            expected,
            String(len(bytes) - expected) + " byte(s) remain",
        )


def decode_scalar_model(bytes: Span[UInt8, _]) raises -> Value:
    """Parse one CLI scalar transfer model exactly."""
    if len(bytes) == 0:
        raise _failure("truncated", 0, "scalar model needs a tag byte")
    var tag = bytes[0]

    if tag == MODEL_SIGNED or tag == MODEL_UNSIGNED:
        return decode_integer_model(bytes)
    if tag == MODEL_FLOAT32:
        _require_model_length(bytes, 5)
        return Value.float32(UInt32(_read_be(bytes, 1, 4)))
    if tag == MODEL_FLOAT64:
        _require_model_length(bytes, 9)
        return Value.float64_bits(_read_be(bytes, 1, 8))
    if tag == MODEL_STR:
        var text: String
        try:
            text = String(from_utf8=Span(bytes)[1:])
        except error:
            raise _failure("invalid-utf8", 1, String(error))
        return Value.string(text^)
    if tag == MODEL_BIN:
        var payload = List[UInt8](capacity=len(bytes) - 1)
        for byte in Span(bytes)[1:]:
            payload.append(byte)
        return Value.binary(payload^)

    raise _failure("invalid-model", 0, "unknown scalar model tag " + String(Int(tag)))
