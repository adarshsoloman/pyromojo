"""Extension and timestamp wire codecs plus their CLI transfer models.

All eight extension families are supported: fixext1/2/4/8/16 and
ext8/16/32. Extension type codes are signed 8-bit values preserved exactly;
the reference Python package only accepts codes 0..127, but the wire format
and this codec accept the full signed int8 range. Timestamp is extension
type -1 with 4-, 8-, or 12-byte payloads (timestamp32/64/96).

A malformed timestamp extension (wrong payload length for type -1, or
nanoseconds outside 0..999999999) is reported as ``invalid-timestamp`` and is
never reinterpreted as a generic extension value.
"""

from std.collections import List

from mojo_msgpack.value import VALUE_EXT, VALUE_TIMESTAMP, Value


comptime MODEL_EXT: UInt8 = 0x16
comptime MODEL_TIMESTAMP: UInt8 = 0x17

comptime MARKER_FIXEXT1: UInt8 = 0xD4
comptime MARKER_FIXEXT2: UInt8 = 0xD5
comptime MARKER_FIXEXT4: UInt8 = 0xD6
comptime MARKER_FIXEXT8: UInt8 = 0xD7
comptime MARKER_FIXEXT16: UInt8 = 0xD8
comptime MARKER_EXT8: UInt8 = 0xC7
comptime MARKER_EXT16: UInt8 = 0xC8
comptime MARKER_EXT32: UInt8 = 0xC9

comptime EXT_TIMESTAMP_CODE: Int8 = -1
comptime MAX_NANOSECONDS: UInt32 = 999_999_999

comptime UINT32_MAX_VALUE: Int = 4_294_967_295


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
    data: Span[UInt8, _], marker_offset: Int, start: Int, count: Int, what: String
) raises:
    if start + count > len(data):
        raise _failure(
            "truncated",
            marker_offset,
            "need "
            + String(count)
            + " "
            + what
            + " byte(s), have "
            + String(len(data) - start),
        )


def _finish(data: Span[UInt8, _], end: Int) raises:
    if end != len(data):
        raise _failure("trailing-data", end, String(len(data) - end) + " byte(s) remain")


def is_ext_marker(marker: UInt8) -> Bool:
    if marker >= MARKER_FIXEXT1 and marker <= MARKER_FIXEXT16:
        return True
    return marker == MARKER_EXT8 or marker == MARKER_EXT16 or marker == MARKER_EXT32


def encode_ext(mut out: List[UInt8], code: Int8, payload: Span[UInt8, _]) raises:
    """Append one extension value using the shortest valid marker."""
    var length = len(payload)
    if length == 1:
        out.append(MARKER_FIXEXT1)
    elif length == 2:
        out.append(MARKER_FIXEXT2)
    elif length == 4:
        out.append(MARKER_FIXEXT4)
    elif length == 8:
        out.append(MARKER_FIXEXT8)
    elif length == 16:
        out.append(MARKER_FIXEXT16)
    elif length <= 255:
        out.append(MARKER_EXT8)
        _append_be(out, UInt64(length), 1)
    elif length <= 65535:
        out.append(MARKER_EXT16)
        _append_be(out, UInt64(length), 2)
    elif length <= UINT32_MAX_VALUE:
        out.append(MARKER_EXT32)
        _append_be(out, UInt64(length), 4)
    else:
        raise Error("invalid-length: extension exceeds the ext32 limit")
    out.append(UInt8(UInt64(code.to_bits()) & 0xFF))
    for byte in payload:
        out.append(byte)


def encode_timestamp(mut out: List[UInt8], seconds: Int64, nanoseconds: UInt32) raises:
    """Append one timestamp using the shortest valid representation."""
    if nanoseconds > MAX_NANOSECONDS:
        raise Error(
            "invalid-timestamp: nanoseconds "
            + String(nanoseconds)
            + " exceeds 999999999"
        )
    var payload = List[UInt8]()
    if nanoseconds == 0 and seconds >= 0 and UInt64(seconds) <= 4294967295:
        _append_be(payload, UInt64(seconds), 4)
    elif seconds >= 0 and (UInt64(seconds) >> 34) == 0:
        var data64 = (UInt64(nanoseconds) << 34) | UInt64(seconds)
        _append_be(payload, data64, 8)
    else:
        _append_be(payload, UInt64(nanoseconds), 4)
        _append_be(payload, UInt64(seconds.to_bits()), 8)
    encode_ext(out, EXT_TIMESTAMP_CODE, Span(payload))


def encode_ext_value(mut out: List[UInt8], value: Value) raises:
    if value.kind == VALUE_TIMESTAMP:
        encode_timestamp(out, value.as_int64(), value.nsec)
    elif value.kind == VALUE_EXT:
        encode_ext(out, value.ext_code, Span(value.data))
    else:
        raise Error(
            "unsupported-value: kind "
            + String(Int(value.kind))
            + " is not an extension"
        )


def _decode_timestamp(
    payload: Span[UInt8, _], marker_offset: Int
) raises -> Value:
    if len(payload) == 4:
        return Value.timestamp(Int64(_read_be(payload, 0, 4)), UInt32(0))
    if len(payload) == 8:
        var data64 = _read_be(payload, 0, 8)
        var nanoseconds = UInt32(data64 >> 34)
        if nanoseconds > MAX_NANOSECONDS:
            raise _failure(
                "invalid-timestamp",
                marker_offset,
                "nanoseconds "
                + String(nanoseconds)
                + " exceeds 999999999",
            )
        return Value.timestamp(Int64(data64 & 0x3FFFFFFFF), nanoseconds)
    if len(payload) == 12:
        var nanoseconds = UInt32(_read_be(payload, 0, 4))
        if nanoseconds > MAX_NANOSECONDS:
            raise _failure(
                "invalid-timestamp",
                marker_offset,
                "nanoseconds "
                + String(nanoseconds)
                + " exceeds 999999999",
            )
        return Value.timestamp(Int64(from_bits=_read_be(payload, 4, 8)), nanoseconds)
    raise _failure(
        "invalid-timestamp",
        marker_offset,
        "extension type -1 needs 4, 8, or 12 payload bytes, have "
        + String(len(payload)),
    )


def decode_ext_at(data: Span[UInt8, _], mut pos: Int) raises -> Value:
    """Decode one extension value at ``pos`` and advance past it on success."""
    if pos >= len(data):
        raise _failure("truncated", pos, "need 1 marker byte")
    var marker_offset = pos
    var marker = data[pos]

    var length = 0
    var header = 0
    if marker == MARKER_FIXEXT1:
        length = 1
        header = 2
    elif marker == MARKER_FIXEXT2:
        length = 2
        header = 2
    elif marker == MARKER_FIXEXT4:
        length = 4
        header = 2
    elif marker == MARKER_FIXEXT8:
        length = 8
        header = 2
    elif marker == MARKER_FIXEXT16:
        length = 16
        header = 2
    elif marker == MARKER_EXT8:
        _require(data, marker_offset, pos + 1, 1, "ext8 length")
        length = Int(_read_be(data, pos + 1, 1))
        header = 3
    elif marker == MARKER_EXT16:
        _require(data, marker_offset, pos + 1, 2, "ext16 length")
        length = Int(_read_be(data, pos + 1, 2))
        header = 4
    elif marker == MARKER_EXT32:
        _require(data, marker_offset, pos + 1, 4, "ext32 length")
        length = Int(_read_be(data, pos + 1, 4))
        header = 6
    else:
        raise _failure(
            "unsupported-marker",
            marker_offset,
            "marker " + String(Int(marker)) + " is not an extension",
        )

    _require(data, marker_offset, pos + header - 1, 1, "extension type")
    var code = Int8(from_bits=data[pos + header - 1])
    _require(data, marker_offset, pos + header, length, "extension payload")
    var start = pos + header
    var end = start + length
    pos = end

    if code == EXT_TIMESTAMP_CODE:
        return _decode_timestamp(Span(data)[start:end], marker_offset)

    var payload = List[UInt8](capacity=length)
    for byte in data[start:end]:
        payload.append(byte)
    return Value.ext(code, payload^)


def append_ext_model(mut out: List[UInt8], value: Value) raises:
    """Append the CLI transfer model for an extension or timestamp value."""
    if value.kind == VALUE_EXT:
        if value.ext_code == EXT_TIMESTAMP_CODE:
            raise Error(
                "invalid-value: extension type -1 must use the timestamp model"
            )
        out.append(MODEL_EXT)
        out.append(UInt8(UInt64(value.ext_code.to_bits()) & 0xFF))
        if len(value.data) > UINT32_MAX_VALUE:
            raise Error("invalid-length: extension exceeds the ext32 limit")
        _append_be(out, UInt64(len(value.data)), 4)
        for byte in value.data:
            out.append(byte)
    elif value.kind == VALUE_TIMESTAMP:
        if value.nsec > MAX_NANOSECONDS:
            raise Error(
                "invalid-timestamp: nanoseconds "
                + String(value.nsec)
                + " exceeds 999999999"
            )
        out.append(MODEL_TIMESTAMP)
        _append_be(out, UInt64(value.as_int64().to_bits()), 8)
        _append_be(out, UInt64(value.nsec), 4)
    else:
        raise Error(
            "unsupported-value: kind "
            + String(Int(value.kind))
            + " is not an extension"
        )


def decode_ext_model(bytes: Span[UInt8, _]) raises -> Value:
    """Parse exactly one extension or timestamp transfer model."""
    if len(bytes) == 0:
        raise _failure("truncated", 0, "extension model needs a tag byte")
    var tag = bytes[0]

    if tag == MODEL_EXT:
        _require(bytes, 0, 1, 5, "extension model header")
        var code = Int8(from_bits=bytes[1])
        var length = Int(_read_be(bytes, 2, 4))
        _require(bytes, 0, 6, length, "extension model payload")
        _finish(bytes, 6 + length)
        if code == EXT_TIMESTAMP_CODE:
            return _decode_timestamp(Span(bytes)[6 : 6 + length], 0)
        var payload = List[UInt8](capacity=length)
        for byte in Span(bytes)[6 : 6 + length]:
            payload.append(byte)
        return Value.ext(code, payload^)

    if tag == MODEL_TIMESTAMP:
        _require(bytes, 0, 1, 12, "timestamp model body")
        _finish(bytes, 13)
        var seconds = Int64(from_bits=_read_be(bytes, 1, 8))
        var nanoseconds = UInt32(_read_be(bytes, 9, 4))
        if nanoseconds > MAX_NANOSECONDS:
            raise _failure(
                "invalid-timestamp",
                0,
                "nanoseconds "
                + String(nanoseconds)
                + " exceeds 999999999",
            )
        return Value.timestamp(seconds, nanoseconds)

    raise _failure("invalid-model", 0, "unknown extension model tag " + String(Int(tag)))
