"""Shared helpers for generated MessagePack vector tests."""

from std.collections import List

from mojo_msgpack.value import Value


struct VectorCase(RegisterPassable, ImplicitlyCopyable):
    """Metadata for one golden vector; the value model is built on demand."""

    var id: StaticString
    var category: StaticString
    var mode: StaticString
    var encoded_hex: StaticString
    var has_value: Bool
    var error_type: StaticString
    var error_contains: StaticString

    def __init__(
        out self,
        id: StaticString,
        category: StaticString,
        mode: StaticString,
        encoded_hex: StaticString,
        has_value: Bool,
        error_type: StaticString,
        error_contains: StaticString,
    ):
        self.id = id
        self.category = category
        self.mode = mode
        self.encoded_hex = encoded_hex
        self.has_value = has_value
        self.error_type = error_type
        self.error_contains = error_contains


def _nibble(character: UInt8) raises -> UInt8:
    if character >= UInt8(ord("0")) and character <= UInt8(ord("9")):
        return character - UInt8(ord("0"))
    if character >= UInt8(ord("a")) and character <= UInt8(ord("f")):
        return character - UInt8(ord("a")) + UInt8(10)
    raise Error("invalid lowercase hex digit")


def decode_hex(hex: StaticString) raises -> List[UInt8]:
    var text = String(hex)
    var raw = text.as_bytes()
    if len(raw) % 2 != 0:
        raise Error("hex string must have an even number of digits")
    var out = List[UInt8](capacity=len(raw) // 2)
    for index in range(0, len(raw), 2):
        out.append((_nibble(raw[index]) << 4) | _nibble(raw[index + 1]))
    return out^


def string_from_hex(hex: StaticString) raises -> Value:
    var raw = decode_hex(hex)
    return Value.string(String(from_utf8=Span(raw)))


def ext_from_hex(code: Int8, hex: StaticString) raises -> Value:
    return Value.ext(code, decode_hex(hex))


def uint_from_decimal(decimal: StaticString) raises -> Value:
    var text = String(decimal)
    var magnitude: UInt64 = 0
    for byte in text.as_bytes():
        if byte < UInt8(ord("0")) or byte > UInt8(ord("9")):
            raise Error("invalid unsigned decimal integer")
        var digit = UInt64(byte - UInt8(ord("0")))
        if magnitude > (UInt64.MAX - digit) // 10:
            raise Error("unsigned decimal integer overflows UInt64")
        magnitude = magnitude * 10 + digit
    return Value.unsigned(magnitude)


def int_from_decimal(decimal: StaticString) raises -> Value:
    var text = String(decimal)
    var negative = text.byte_length() > 0 and text.as_bytes()[0] == UInt8(ord("-"))
    var digits = text.as_bytes()[1:] if negative else text.as_bytes()
    var magnitude: UInt64 = 0
    for byte in digits:
        if byte < UInt8(ord("0")) or byte > UInt8(ord("9")):
            raise Error("invalid decimal integer")
        magnitude = magnitude * 10 + UInt64(byte - UInt8(ord("0")))
    if negative:
        if magnitude == 9223372036854775808:
            return Value.integer(Int64.MIN)
        return Value.integer(Int64(0) - Int64(magnitude))
    if magnitude > 9223372036854775807:
        return Value.unsigned(magnitude)
    return Value.integer(Int64(magnitude))
