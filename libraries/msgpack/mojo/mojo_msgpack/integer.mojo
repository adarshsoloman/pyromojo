"""Canonical MessagePack integer encoding and integer decoding.

Only the ten integer format families are handled here. Decoded positive
fixints and uint8/16/32/64 become ``Value.unsigned``; negative fixints and
int8/16/32/64 become ``Value.integer``. MessagePack has no independent
signedness bit for non-negative wire values, so signed-positive inputs decode
as unsigned. A failed decode leaves the decoder position unchanged.
"""

from std.collections import List

from mojo_msgpack.value import VALUE_INT, VALUE_UINT, Value


comptime INTEGER_MODEL_BYTES: Int = 9
comptime MODEL_SIGNED: UInt8 = 0
comptime MODEL_UNSIGNED: UInt8 = 1

comptime MARKER_UINT8: UInt8 = 0xCC
comptime MARKER_UINT16: UInt8 = 0xCD
comptime MARKER_UINT32: UInt8 = 0xCE
comptime MARKER_UINT64: UInt8 = 0xCF
comptime MARKER_INT8: UInt8 = 0xD0
comptime MARKER_INT16: UInt8 = 0xD1
comptime MARKER_INT32: UInt8 = 0xD2
comptime MARKER_INT64: UInt8 = 0xD3


def _failure(category: StaticString, offset: Int, detail: String) -> Error:
    return Error(String(category) + ": offset " + String(offset) + ": " + detail)


def _append_be(mut out: List[UInt8], bits: UInt64, width: Int):
    for index in range(width):
        var shift = UInt64((width - 1 - index) * 8)
        out.append(UInt8((bits >> shift) & 0xFF))


def _append_payload(
    mut out: List[UInt8], marker: UInt8, bits: UInt64, width: Int
):
    out.append(marker)
    _append_be(out, bits, width)


def encode_uint(mut out: List[UInt8], value: UInt64):
    """Append the shortest unsigned (or non-negative) representation."""
    if value <= 127:
        out.append(UInt8(value))
    elif value <= 255:
        _append_payload(out, MARKER_UINT8, value, 1)
    elif value <= 65535:
        _append_payload(out, MARKER_UINT16, value, 2)
    elif value <= 4294967295:
        _append_payload(out, MARKER_UINT32, value, 4)
    else:
        _append_payload(out, MARKER_UINT64, value, 8)


def encode_int(mut out: List[UInt8], value: Int64):
    """Append the canonical signed representation used by msgpack-python."""
    if value >= 0:
        encode_uint(out, UInt64(value))
    elif value >= -32:
        out.append(UInt8(UInt64(value.to_bits()) & 0xFF))
    elif value >= -128:
        _append_payload(out, MARKER_INT8, UInt64(value.to_bits()), 1)
    elif value >= -32768:
        _append_payload(out, MARKER_INT16, UInt64(value.to_bits()), 2)
    elif value >= -2147483648:
        _append_payload(out, MARKER_INT32, UInt64(value.to_bits()), 4)
    else:
        _append_payload(out, MARKER_INT64, UInt64(value.to_bits()), 8)


def encode_value(mut out: List[UInt8], value: Value) raises:
    """Encode an integer ``Value``; reject every other kind."""
    if value.kind == VALUE_INT:
        encode_int(out, value.as_int64())
    elif value.kind == VALUE_UINT:
        encode_uint(out, value.as_uint64())
    else:
        raise Error(
            "unsupported-value: kind "
            + String(Int(value.kind))
            + " is not an integer"
        )


def _read_be(data: Span[UInt8, _], marker_offset: Int, width: Int, marker: UInt8) raises -> UInt64:
    if marker_offset + 1 + width > len(data):
        raise _failure(
            "truncated",
            marker_offset,
            "marker "
            + String(Int(marker))
            + " needs "
            + String(width)
            + " payload byte(s), have "
            + String(len(data) - marker_offset - 1),
        )
    var bits: UInt64 = 0
    for index in range(width):
        bits = (bits << 8) | UInt64(data[marker_offset + 1 + index])
    return bits


def _sign_extend(bits: UInt64, width: Int) -> UInt64:
    if width >= 8:
        return bits
    var mask: UInt64 = (UInt64(1) << UInt64(width * 8)) - 1
    var narrowed = bits & mask
    if (narrowed & (UInt64(1) << UInt64(width * 8 - 1))) != 0:
        narrowed |= ~mask
    return narrowed


struct IntegerDecoder(Movable):
    """Bounded decoder whose position advances only after a complete decode."""

    var data: List[UInt8]
    var pos: Int

    def __init__(out self, var data: List[UInt8]):
        self.data = data^
        self.pos = 0

    @staticmethod
    def from_bytes(bytes: Span[UInt8, _]) -> Self:
        var copy = List[UInt8](capacity=len(bytes))
        for byte in bytes:
            copy.append(byte)
        return Self(copy^)

    def decode(mut self) raises -> Value:
        var start = self.pos
        if start >= len(self.data):
            raise _failure("truncated", start, "need 1 marker byte")

        var marker = self.data[start]
        var next = start + 1
        var value: Value

        if marker <= 0x7F:
            value = Value.unsigned(UInt64(marker))
        elif marker >= 0xE0:
            value = Value.integer(Int64(Int8(from_bits=marker)))
        elif marker == MARKER_UINT8:
            var bits = _read_be(Span(self.data), start, 1, marker)
            value = Value.unsigned(bits)
            next = start + 2
        elif marker == MARKER_UINT16:
            var bits = _read_be(Span(self.data), start, 2, marker)
            value = Value.unsigned(bits)
            next = start + 3
        elif marker == MARKER_UINT32:
            var bits = _read_be(Span(self.data), start, 4, marker)
            value = Value.unsigned(bits)
            next = start + 5
        elif marker == MARKER_UINT64:
            var bits = _read_be(Span(self.data), start, 8, marker)
            value = Value.unsigned(bits)
            next = start + 9
        elif marker == MARKER_INT8:
            var bits = _read_be(Span(self.data), start, 1, marker)
            value = Value.integer(Int64(from_bits=_sign_extend(bits, 1)))
            next = start + 2
        elif marker == MARKER_INT16:
            var bits = _read_be(Span(self.data), start, 2, marker)
            value = Value.integer(Int64(from_bits=_sign_extend(bits, 2)))
            next = start + 3
        elif marker == MARKER_INT32:
            var bits = _read_be(Span(self.data), start, 4, marker)
            value = Value.integer(Int64(from_bits=_sign_extend(bits, 4)))
            next = start + 5
        elif marker == MARKER_INT64:
            var bits = _read_be(Span(self.data), start, 8, marker)
            value = Value.integer(Int64(from_bits=bits))
            next = start + 9
        else:
            raise _failure(
                "unsupported-marker",
                start,
                "marker " + String(Int(marker)) + " is not an integer",
            )

        self.pos = next
        return value^


def decode_exact(bytes: Span[UInt8, _]) raises -> Value:
    """Decode exactly one integer and reject trailing bytes."""
    var decoder = IntegerDecoder.from_bytes(bytes)
    var value = decoder.decode()
    if decoder.pos != len(bytes):
        raise _failure(
            "trailing-data",
            decoder.pos,
            String(len(bytes) - decoder.pos) + " byte(s) remain",
        )
    return value^


def append_integer_model(mut out: List[UInt8], value: Value) raises:
    """Append the 9-byte CLI transfer model: tag byte plus uint64 bits."""
    if value.kind == VALUE_INT:
        out.append(MODEL_SIGNED)
    elif value.kind == VALUE_UINT:
        out.append(MODEL_UNSIGNED)
    else:
        raise Error(
            "unsupported-value: kind "
            + String(Int(value.kind))
            + " is not an integer"
        )
    _append_be(out, value.int_bits, 8)


def decode_integer_model(bytes: Span[UInt8, _]) raises -> Value:
    """Parse the 9-byte CLI transfer model exactly."""
    if len(bytes) < INTEGER_MODEL_BYTES:
        raise _failure(
            "truncated",
            0,
            "integer model needs "
            + String(INTEGER_MODEL_BYTES)
            + " bytes, have "
            + String(len(bytes)),
        )
    if len(bytes) > INTEGER_MODEL_BYTES:
        raise _failure(
            "trailing-data",
            INTEGER_MODEL_BYTES,
            String(len(bytes) - INTEGER_MODEL_BYTES) + " byte(s) remain",
        )
    var tag = bytes[0]
    var bits: UInt64 = 0
    for index in range(8):
        bits = (bits << 8) | UInt64(bytes[1 + index])
    if tag == MODEL_SIGNED:
        return Value.integer(Int64(from_bits=bits))
    if tag == MODEL_UNSIGNED:
        return Value.unsigned(bits)
    raise _failure("invalid-model", 0, "unknown integer model tag " + String(Int(tag)))
