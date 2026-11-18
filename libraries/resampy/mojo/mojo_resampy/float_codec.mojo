"""Phase 3 / Component E: exact Float64 byte/Base64/Hex codec.

All conversions preserve the exact IEEE-754 bit pattern, including negative
zero, subnormals, infinities and NaN payloads. Byte order is explicitly
LITTLE-ENDIAN and is never inferred from the host.

Mojo 1.2.0 provides ``std.base64`` (``b64encode`` / ``b64decode``); it is
reused here with an additional strict validator because the stdlib decoder
silently accepts trailing whitespace/newlines and missing padding.

There is no JSON or SHA-256 module in Mojo 1.2.0; those live in ``json_codec``
and ``sha256`` respectively.
"""

from std.base64 import b64encode, b64decode
from std.collections import List
from std.memory import bitcast


comptime FLOAT64_BYTES: Int = 8


def float64_to_bits(value: Float64) -> UInt64:
    """Reinterpret the Float64 bits as UInt64 (no numeric change)."""
    return bitcast[DType.uint64, 1](value)[0]


def bits_to_float64(bits: UInt64) -> Float64:
    """Reinterpret UInt64 bits as Float64 (no numeric change)."""
    return bitcast[DType.float64, 1](SIMD[DType.uint64, 1](bits))[0]


def encode_f64le(values: Span[Float64, _]) -> List[UInt8]:
    """Serialize Float64 values as little-endian IEEE-754 bytes."""
    var out = List[UInt8](capacity=len(values) * FLOAT64_BYTES)
    for value in values:
        var bits = float64_to_bits(value)
        for j in range(FLOAT64_BYTES):
            out.append(UInt8((bits >> UInt64(8 * j)) & 0xFF))
    return out^


def decode_f64le(bytes: Span[UInt8, _]) raises -> List[Float64]:
    """Deserialize little-endian IEEE-754 bytes into Float64 values.

    Rejects payloads whose length is not a multiple of 8; never truncates.
    """
    if len(bytes) % FLOAT64_BYTES != 0:
        raise Error(
            "Float64 payload length " + String(len(bytes))
            + " is not a multiple of 8 bytes"
        )
    var count = len(bytes) // FLOAT64_BYTES
    var out = List[Float64](capacity=count)
    for i in range(count):
        var bits: UInt64 = 0
        for j in range(FLOAT64_BYTES):
            bits |= UInt64(bytes[i * FLOAT64_BYTES + j]) << UInt64(8 * j)
        out.append(bits_to_float64(bits))
    return out^


def bytes_to_hex(bytes: Span[UInt8, _]) raises -> String:
    """Lowercase hex, two characters per byte."""
    comptime DIGITS: String = "0123456789abcdef"
    var out = List[UInt8](capacity=len(bytes) * 2)
    for byte in bytes:
        out.append(DIGITS.as_bytes()[Int(byte >> 4)])
        out.append(DIGITS.as_bytes()[Int(byte & 0x0F)])
    return String(from_utf8=Span(out))


def hex_to_bytes(text: String) raises -> List[UInt8]:
    """Strict lowercase/uppercase hex decode; rejects odd length and bad chars."""
    if text.byte_length() % 2 != 0:
        raise Error("hex string has odd length " + String(text.byte_length()))
    var out = List[UInt8](capacity=text.byte_length() // 2)
    var i = 0
    while i < text.byte_length():
        var hi = _hex_nibble(text.as_bytes()[i])
        var lo = _hex_nibble(text.as_bytes()[i + 1])
        out.append(UInt8((hi << 4) | lo))
        i += 2
    return out^


def _hex_nibble(byte: UInt8) raises -> UInt8:
    if byte >= 48 and byte <= 57:
        return byte - 48
    if byte >= 97 and byte <= 102:
        return byte - 87
    if byte >= 65 and byte <= 70:
        return byte - 55
    raise Error("invalid hex character code " + String(Int(byte)))


def base64_encode_bytes(bytes: Span[UInt8, _]) raises -> String:
    """Standard Base64 (with padding) of raw bytes."""
    return b64encode(bytes)


def base64_decode_bytes(text: String) raises -> List[UInt8]:
    """Strict Base64 decode using the verified stdlib decoder.

    Enforces canonical form: only A-Z a-z 0-9 + / and trailing '=' padding,
    length a multiple of 4, padding only at the very end (0, 1 or 2 chars).
    Whitespace, missing padding and stray characters are rejected rather than
    silently tolerated by ``std.base64.b64decode``.
    """
    var n = text.byte_length()
    if n % 4 != 0:
        raise Error("Base64 length " + String(n) + " is not a multiple of 4")
    if n == 0:
        return List[UInt8]()
    var padding = 0
    var i = 0
    while i < n:
        var c = text.as_bytes()[i]
        if c == 61:  # '='
            padding += 1
        elif padding > 0:
            raise Error("Base64 padding '=' must appear only at the end")
        elif not (
            (c >= 65 and c <= 90)
            or (c >= 97 and c <= 122)
            or (c >= 48 and c <= 57)
            or c == 43
            or c == 47
        ):
            raise Error("invalid Base64 character at offset " + String(i))
        i += 1
    if padding > 2:
        raise Error("Base64 padding must be at most 2 '=' characters")
    if padding == 1 and text.as_bytes()[n - 2] == 61:
        raise Error("invalid Base64 padding placement")
    return b64decode(text)
