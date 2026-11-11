"""Recursive array and map codecs plus the recursive CLI transfer model.

Wire encoding and decoding share the same depth rule as ``Value``: a scalar has
depth 1 and a container has depth ``1 + max(child depth)``. Decoding rejects a
non-empty container before allocating when the remaining depth is 1. Container
item counts are checked against ``max_container_items`` before allocation and
against the remaining input size, so a declared 4-billion-item array costs one
error, not a 4-billion-element allocation.

``nil`` and ``bool`` are decodable here because reference arrays and maps
contain them. They remain top-level ``UNIMPLEMENTED`` in the CLI, preserving the
Phase 1 transfer behavior. The CLI model is recursive:

    array  := 0x14 | uint32_be count | (uint32_be length | model) * count
    map    := 0x15 | uint32_be pairs | (uint32_be length | key_model |
                                        uint32_be length | value_model) * pairs
    nil    := 0xc0
    false  := 0xc2
    true   := 0xc3

Scalars keep their Phase 3 model tags.
"""

from std.collections import List

from mojo_msgpack.integer import encode_value as encode_integer_value
from mojo_msgpack.scalar import (
    append_scalar_model,
    decode_scalar_at,
    decode_scalar_model,
    encode_bin,
    encode_float32,
    encode_float64,
    encode_str,
)
from mojo_msgpack.value import (
    DEFAULT_MAX_CONTAINER_ITEMS,
    DEFAULT_MAX_DEPTH,
    VALUE_ARRAY,
    VALUE_BIN,
    VALUE_BOOL,
    VALUE_FLOAT32,
    VALUE_FLOAT64,
    VALUE_INT,
    VALUE_MAP,
    VALUE_NIL,
    VALUE_STR,
    VALUE_UINT,
    Value,
)


comptime MODEL_ARRAY: UInt8 = 0x14
comptime MODEL_MAP: UInt8 = 0x15
comptime MODEL_NIL: UInt8 = 0xC0
comptime MODEL_FALSE: UInt8 = 0xC2
comptime MODEL_TRUE: UInt8 = 0xC3

comptime MARKER_FIXARRAY_MIN: UInt8 = 0x90
comptime MARKER_FIXARRAY_MAX: UInt8 = 0x9F
comptime MARKER_ARRAY16: UInt8 = 0xDC
comptime MARKER_ARRAY32: UInt8 = 0xDD
comptime MARKER_FIXMAP_MIN: UInt8 = 0x80
comptime MARKER_FIXMAP_MAX: UInt8 = 0x8F
comptime MARKER_MAP16: UInt8 = 0xDE
comptime MARKER_MAP32: UInt8 = 0xDF
comptime MARKER_NIL: UInt8 = 0xC0
comptime MARKER_FALSE: UInt8 = 0xC2
comptime MARKER_TRUE: UInt8 = 0xC3

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


def _container_limit(offset: Int, kind: StaticString, count: Int, limit: Int) -> Error:
    return _failure(
        "container-limit",
        offset,
        kind
        + " declares "
        + String(count)
        + " item(s), limit is "
        + String(limit),
    )


def _depth_error(offset: Int, kind: StaticString) -> Error:
    return _failure(
        "depth-exceeded",
        offset,
        kind + " is nested deeper than the configured max_depth",
    )


def _array_header(mut out: List[UInt8], count: Int) raises:
    if count > UINT32_MAX_VALUE:
        raise Error("invalid-length: array exceeds the array32 limit")
    if count <= 15:
        out.append(MARKER_FIXARRAY_MIN | UInt8(count))
    elif count <= 65535:
        out.append(MARKER_ARRAY16)
        _append_be(out, UInt64(count), 2)
    else:
        out.append(MARKER_ARRAY32)
        _append_be(out, UInt64(count), 4)


def _map_header(mut out: List[UInt8], pairs: Int) raises:
    if pairs > UINT32_MAX_VALUE:
        raise Error("invalid-length: map exceeds the map32 limit")
    if pairs <= 15:
        out.append(MARKER_FIXMAP_MIN | UInt8(pairs))
    elif pairs <= 65535:
        out.append(MARKER_MAP16)
        _append_be(out, UInt64(pairs), 2)
    else:
        out.append(MARKER_MAP32)
        _append_be(out, UInt64(pairs), 4)


def _append_value_at(
    mut out: List[UInt8],
    value: Value,
    depth_remaining: Int,
    max_container_items: Int,
) raises:
    if depth_remaining < 1:
        raise Error("depth-exceeded: max_depth must be at least 1")
    if value.kind == VALUE_NIL:
        out.append(MARKER_NIL)
        return
    if value.kind == VALUE_BOOL:
        out.append(MARKER_TRUE if value.as_bool() else MARKER_FALSE)
        return
    if value.kind == VALUE_ARRAY:
        var count = len(value.kids)
        if count > max_container_items:
            raise Error(
                "container-limit: array has "
                + String(count)
                + " item(s), limit is "
                + String(max_container_items)
            )
        if count > 0 and depth_remaining <= 1:
            raise Error("depth-exceeded: array exceeds max_depth")
        _array_header(out, count)
        for index in range(count):
            _append_value_at(out, value.kids[index], depth_remaining - 1, max_container_items)
        return
    if value.kind == VALUE_MAP:
        if len(value.kids) % 2 != 0:
            raise Error("invalid-value: map children must be key/value pairs")
        var pairs = len(value.kids) // 2
        if pairs > max_container_items:
            raise Error(
                "container-limit: map has "
                + String(pairs)
                + " pair(s), limit is "
                + String(max_container_items)
            )
        if pairs > 0 and depth_remaining <= 1:
            raise Error("depth-exceeded: map exceeds max_depth")
        _map_header(out, pairs)
        for index in range(len(value.kids)):
            _append_value_at(out, value.kids[index], depth_remaining - 1, max_container_items)
        return
    if value.kind == VALUE_INT or value.kind == VALUE_UINT:
        encode_integer_value(out, value)
        return
    if value.kind == VALUE_FLOAT32:
        encode_float32(out, value.as_float32_bits())
        return
    if value.kind == VALUE_FLOAT64:
        encode_float64(out, value.as_float64_bits())
        return
    if value.kind == VALUE_STR:
        encode_str(out, Span(value.data))
        return
    if value.kind == VALUE_BIN:
        encode_bin(out, Span(value.data))
        return
    raise Error(
        "unsupported-value: kind "
        + String(Int(value.kind))
        + " is not supported by the array/map codec"
    )


def encode_value(
    mut out: List[UInt8],
    value: Value,
    max_depth: Int = DEFAULT_MAX_DEPTH,
    max_container_items: Int = DEFAULT_MAX_CONTAINER_ITEMS,
) raises:
    """Append one MessagePack value, rejecting over-limit nesting or counts."""
    if max_depth < 1:
        raise Error("max_depth must be at least 1")
    if max_container_items < 0:
        raise Error("max_container_items must be non-negative")
    _append_value_at(out, value, max_depth, max_container_items)


def _decode_array_body(
    data: Span[UInt8, _],
    mut pos: Int,
    marker_offset: Int,
    count: Int,
    depth_remaining: Int,
    max_container_items: Int,
) raises -> Value:
    if count > max_container_items:
        raise _container_limit(marker_offset, "array", count, max_container_items)
    if count > len(data) - pos:
        raise _failure(
            "truncated",
            marker_offset,
            "array declares "
            + String(count)
            + " item(s), only "
            + String(len(data) - pos)
            + " byte(s) remain",
        )
    if count > 0 and depth_remaining <= 1:
        raise _depth_error(marker_offset, "array")
    var kids = List[Value](capacity=count)
    for _ in range(count):
        kids.append(_decode_value_at(data, pos, depth_remaining - 1, max_container_items))
    return Value.array(kids^)


def _decode_map_body(
    data: Span[UInt8, _],
    mut pos: Int,
    marker_offset: Int,
    pairs: Int,
    depth_remaining: Int,
    max_container_items: Int,
) raises -> Value:
    if pairs > max_container_items:
        raise _container_limit(marker_offset, "map", pairs, max_container_items)
    if pairs > (len(data) - pos) // 2:
        raise _failure(
            "truncated",
            marker_offset,
            "map declares "
            + String(pairs)
            + " pair(s), only "
            + String(len(data) - pos)
            + " byte(s) remain",
        )
    if pairs > 0 and depth_remaining <= 1:
        raise _depth_error(marker_offset, "map")
    var kids = List[Value](capacity=pairs * 2)
    for _ in range(pairs):
        kids.append(_decode_value_at(data, pos, depth_remaining - 1, max_container_items))
        kids.append(_decode_value_at(data, pos, depth_remaining - 1, max_container_items))
    return Value.map(kids^)


def _decode_value_at(
    data: Span[UInt8, _],
    mut pos: Int,
    depth_remaining: Int,
    max_container_items: Int,
) raises -> Value:
    if depth_remaining < 1:
        raise _failure("depth-exceeded", pos, "value is nested deeper than max_depth")
    if pos >= len(data):
        raise _failure("truncated", pos, "need 1 marker byte")
    var marker_offset = pos
    var marker = data[pos]

    if marker >= MARKER_FIXARRAY_MIN and marker <= MARKER_FIXARRAY_MAX:
        pos += 1
        return _decode_array_body(
            data, pos, marker_offset, Int(marker & 0x0F), depth_remaining, max_container_items
        )
    if marker == MARKER_ARRAY16:
        _require(data, marker_offset, pos + 1, 2, "array16 count")
        var count = Int(_read_be(data, pos + 1, 2))
        pos += 3
        return _decode_array_body(
            data, pos, marker_offset, count, depth_remaining, max_container_items
        )
    if marker == MARKER_ARRAY32:
        _require(data, marker_offset, pos + 1, 4, "array32 count")
        var count = Int(_read_be(data, pos + 1, 4))
        pos += 5
        return _decode_array_body(
            data, pos, marker_offset, count, depth_remaining, max_container_items
        )

    if marker >= MARKER_FIXMAP_MIN and marker <= MARKER_FIXMAP_MAX:
        pos += 1
        return _decode_map_body(
            data, pos, marker_offset, Int(marker & 0x0F), depth_remaining, max_container_items
        )
    if marker == MARKER_MAP16:
        _require(data, marker_offset, pos + 1, 2, "map16 count")
        var pairs = Int(_read_be(data, pos + 1, 2))
        pos += 3
        return _decode_map_body(
            data, pos, marker_offset, pairs, depth_remaining, max_container_items
        )
    if marker == MARKER_MAP32:
        _require(data, marker_offset, pos + 1, 4, "map32 count")
        var pairs = Int(_read_be(data, pos + 1, 4))
        pos += 5
        return _decode_map_body(
            data, pos, marker_offset, pairs, depth_remaining, max_container_items
        )

    if marker == MARKER_NIL:
        pos += 1
        return Value.nil()
    if marker == MARKER_FALSE:
        pos += 1
        return Value.bool(False)
    if marker == MARKER_TRUE:
        pos += 1
        return Value.bool(True)

    return decode_scalar_at(data, pos)


def decode_value_exact(
    data: Span[UInt8, _],
    max_depth: Int = DEFAULT_MAX_DEPTH,
    max_container_items: Int = DEFAULT_MAX_CONTAINER_ITEMS,
) raises -> Value:
    """Decode exactly one MessagePack value with recursive limits."""
    if max_depth < 1:
        raise Error("max_depth must be at least 1")
    if max_container_items < 0:
        raise Error("max_container_items must be non-negative")
    var pos = 0
    var value = _decode_value_at(data, pos, max_depth, max_container_items)
    _finish(data, pos)
    return value^


def _append_framed_model(
    mut out: List[UInt8],
    value: Value,
    depth_remaining: Int,
    max_container_items: Int,
) raises:
    var child = List[UInt8]()
    _append_value_model_at(child, value, depth_remaining, max_container_items)
    if len(child) > UINT32_MAX_VALUE:
        raise Error("invalid-length: child model exceeds the uint32 length limit")
    _append_be(out, UInt64(len(child)), 4)
    for byte in child:
        out.append(byte)


def _append_value_model_at(
    mut out: List[UInt8],
    value: Value,
    depth_remaining: Int,
    max_container_items: Int,
) raises:
    if depth_remaining < 1:
        raise Error("depth-exceeded: max_depth must be at least 1")
    if value.kind == VALUE_NIL:
        out.append(MODEL_NIL)
        return
    if value.kind == VALUE_BOOL:
        out.append(MODEL_TRUE if value.as_bool() else MODEL_FALSE)
        return
    if value.kind == VALUE_ARRAY:
        var count = len(value.kids)
        if count > max_container_items:
            raise Error(
                "container-limit: array has "
                + String(count)
                + " item(s), limit is "
                + String(max_container_items)
            )
        if count > 0 and depth_remaining <= 1:
            raise Error("depth-exceeded: array exceeds max_depth")
        out.append(MODEL_ARRAY)
        _append_be(out, UInt64(count), 4)
        for index in range(count):
            _append_framed_model(out, value.kids[index], depth_remaining - 1, max_container_items)
        return
    if value.kind == VALUE_MAP:
        if len(value.kids) % 2 != 0:
            raise Error("invalid-value: map children must be key/value pairs")
        var pairs = len(value.kids) // 2
        if pairs > max_container_items:
            raise Error(
                "container-limit: map has "
                + String(pairs)
                + " pair(s), limit is "
                + String(max_container_items)
            )
        if pairs > 0 and depth_remaining <= 1:
            raise Error("depth-exceeded: map exceeds max_depth")
        out.append(MODEL_MAP)
        _append_be(out, UInt64(pairs), 4)
        for index in range(len(value.kids)):
            _append_framed_model(out, value.kids[index], depth_remaining - 1, max_container_items)
        return
    append_scalar_model(out, value)


def append_value_model(
    mut out: List[UInt8],
    value: Value,
    max_depth: Int = DEFAULT_MAX_DEPTH,
    max_container_items: Int = DEFAULT_MAX_CONTAINER_ITEMS,
) raises:
    """Append the recursive CLI model for any supported value."""
    if max_depth < 1:
        raise Error("max_depth must be at least 1")
    if max_container_items < 0:
        raise Error("max_container_items must be non-negative")
    _append_value_model_at(out, value, max_depth, max_container_items)


def _read_model_count(bytes: Span[UInt8, _], offset: Int, what: String) raises -> Int:
    _require(bytes, 0, offset, 4, what)
    return Int(_read_be(bytes, offset, 4))


def _decode_model_container(
    bytes: Span[UInt8, _],
    depth_remaining: Int,
    max_container_items: Int,
    is_map: Bool,
) raises -> Value:
    var kind: StaticString = "array"
    if is_map:
        kind = "map"
    var count = _read_model_count(
        bytes, 1, "map pair count" if is_map else "array item count"
    )
    if count > max_container_items:
        raise _container_limit(0, kind, count, max_container_items)
    var pos = 5
    var minimum = 10 if is_map else 5
    if count > (len(bytes) - pos) // minimum:
        raise _failure(
            "truncated",
            0,
            String(kind)
            + " model declares "
            + String(count)
            + " item(s), only "
            + String(len(bytes) - pos)
            + " byte(s) remain",
        )
    if count > 0 and depth_remaining <= 1:
        raise _depth_error(0, kind)

    var kids = List[Value](capacity=(count * 2) if is_map else count)
    for _ in range(count):
        if is_map:
            var key_length = _read_model_count(bytes, pos, "map key length")
            pos += 4
            _require(bytes, 0, pos, key_length, "map key model")
            var key_end = pos + key_length
            kids.append(
                _decode_value_model_at(
                    Span(bytes)[pos:key_end], depth_remaining - 1, max_container_items
                )
            )
            pos = key_end
            var value_length = _read_model_count(bytes, pos, "map value length")
            pos += 4
            _require(bytes, 0, pos, value_length, "map value model")
            var value_end = pos + value_length
            kids.append(
                _decode_value_model_at(
                    Span(bytes)[pos:value_end], depth_remaining - 1, max_container_items
                )
            )
            pos = value_end
        else:
            var length = _read_model_count(bytes, pos, "array item length")
            pos += 4
            _require(bytes, 0, pos, length, "array item model")
            var end = pos + length
            kids.append(
                _decode_value_model_at(
                    Span(bytes)[pos:end], depth_remaining - 1, max_container_items
                )
            )
            pos = end

    _finish(bytes, pos)
    return Value.map(kids^) if is_map else Value.array(kids^)


def _decode_value_model_at(
    bytes: Span[UInt8, _],
    depth_remaining: Int,
    max_container_items: Int,
) raises -> Value:
    if depth_remaining < 1:
        raise _failure("depth-exceeded", 0, "value is nested deeper than max_depth")
    if len(bytes) == 0:
        raise _failure("truncated", 0, "value model needs a tag byte")
    var tag = bytes[0]

    if tag == MODEL_NIL:
        _finish(bytes, 1)
        return Value.nil()
    if tag == MODEL_FALSE:
        _finish(bytes, 1)
        return Value.bool(False)
    if tag == MODEL_TRUE:
        _finish(bytes, 1)
        return Value.bool(True)
    if tag == MODEL_ARRAY:
        return _decode_model_container(bytes, depth_remaining, max_container_items, False)
    if tag == MODEL_MAP:
        return _decode_model_container(bytes, depth_remaining, max_container_items, True)

    return decode_scalar_model(bytes)


def decode_value_model_exact(
    bytes: Span[UInt8, _],
    max_depth: Int = DEFAULT_MAX_DEPTH,
    max_container_items: Int = DEFAULT_MAX_CONTAINER_ITEMS,
) raises -> Value:
    """Parse exactly one recursive CLI transfer model with the same limits."""
    if max_depth < 1:
        raise Error("max_depth must be at least 1")
    if max_container_items < 0:
        raise Error("max_container_items must be non-negative")
    return _decode_value_model_at(bytes, max_depth, max_container_items)
