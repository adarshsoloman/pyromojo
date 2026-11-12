"""Length-prefixed request/response framing for the Levenshtein batch CLI.

Wire format (all integers big-endian), mirroring the MessagePack CLI
framing without depending on it:

    request  := uint32 length | body
    body     := uint8 opcode | payload
    response := uint32 length | body
    body     := uint8 status | payload

``length`` counts the body bytes only. A clean EOF between frames ends the
session with exit code 0. Framing errors produce one error frame on stdout
and a diagnostic plus non-zero exit on stderr.

Opcodes:

    PING     0x01  payload echoed back empty
    ECHO     0x02  payload echoed back verbatim
    DISTANCE 0x20  u64 ins | u64 del | u64 sub | u8 has_cutoff |
                   [u64 cutoff] | u32 n1 | s1 | u32 n2 | s2
                   -> u64 distance
    RATIO    0x21  u32 n1 | s1 | u32 n2 | s2 -> f64 bits
    HAMMING  0x22  u8 pad | u32 n1 | s1 | u32 n2 | s2 -> u64 distance

Strings are raw UTF-8 bytes; invalid UTF-8 is a request error, never
silent coercion. Weights and cutoffs arrive as u64 and are rejected when
they exceed the ``Int`` range the algorithms compute in.
"""

from std.collections import List
from std.io import RawFileDescriptor
from std.memory import bitcast


comptime MAX_FRAME_BYTES: Int = 64 * 1024 * 1024
comptime HEADER_BYTES: Int = 4

comptime OP_PING: UInt8 = 0x01
comptime OP_ECHO: UInt8 = 0x02
comptime OP_DISTANCE: UInt8 = 0x20
comptime OP_RATIO: UInt8 = 0x21
comptime OP_HAMMING: UInt8 = 0x22

comptime STATUS_OK: UInt8 = 0
comptime STATUS_ERROR: UInt8 = 1
comptime STATUS_UNIMPLEMENTED: UInt8 = 2


def read_exact(mut fd: RawFileDescriptor, mut buffer: List[UInt8]) raises -> Int:
    """Fill ``buffer`` from ``fd``; return bytes read, or 0 at clean EOF."""
    var filled = 0
    var total = len(buffer)
    while filled < total:
        var view = Span(buffer)
        var chunk = view[filled:]
        var count = fd.read_bytes(chunk)
        if count == 0:
            return filled
        filled += count
    return filled


def write_all(mut fd: RawFileDescriptor, payload: Span[UInt8, _]):
    """Write ``payload`` in small chunks to keep pipe writes bounded."""
    var offset = 0
    var total = len(payload)
    while offset < total:
        var end = offset + 4096
        if end > total:
            end = total
        fd.write_bytes(payload[offset:end])
        offset = end


def decode_u32_be(bytes: Span[UInt8, _]) raises -> UInt32:
    if len(bytes) < 4:
        raise Error("framing error: need 4 bytes for a length prefix")
    return (
        (UInt32(bytes[0]) << 24)
        | (UInt32(bytes[1]) << 16)
        | (UInt32(bytes[2]) << 8)
        | UInt32(bytes[3])
    )


def decode_u64_be(bytes: Span[UInt8, _]) raises -> UInt64:
    if len(bytes) < 8:
        raise Error("framing error: need 8 bytes for a u64 field")
    var value = UInt64(0)
    for i in range(8):
        value = (value << 8) | UInt64(bytes[i])
    return value


def decode_f64_be(bytes: Span[UInt8, _]) raises -> Float64:
    var bits = decode_u64_be(bytes)
    return bitcast[DType.float64, 1](SIMD[DType.uint64, 1](bits))[0]


def append_u32_be(mut out: List[UInt8], value: UInt32):
    out.append(UInt8((value >> 24) & 0xFF))
    out.append(UInt8((value >> 16) & 0xFF))
    out.append(UInt8((value >> 8) & 0xFF))
    out.append(UInt8(value & 0xFF))


def append_u64_be(mut out: List[UInt8], value: UInt64):
    for i in range(8):
        out.append(UInt8((value >> UInt64(56 - 8 * i)) & 0xFF))


def append_f64_be(mut out: List[UInt8], value: Float64):
    var bits = bitcast[DType.uint64, 1](value)[0]
    append_u64_be(out, bits)


def read_frame(mut fd: RawFileDescriptor, mut body: List[UInt8]) raises -> Bool:
    """Read one request body. Return False on clean EOF between frames."""
    var header = List[UInt8](capacity=HEADER_BYTES)
    for _ in range(HEADER_BYTES):
        header.append(0)
    var header_read = read_exact(fd, header)
    if header_read == 0:
        return False
    if header_read != HEADER_BYTES:
        raise Error("framing error: truncated frame header")

    var length = Int(decode_u32_be(Span(header)))
    if length > MAX_FRAME_BYTES:
        raise Error(
            "framing error: frame length "
            + String(length)
            + " exceeds limit "
            + String(MAX_FRAME_BYTES)
        )

    body = List[UInt8](capacity=length)
    for _ in range(length):
        body.append(0)
    if read_exact(fd, body) != length:
        raise Error("framing error: truncated frame body")
    return True


def write_frame(
    mut fd: RawFileDescriptor, status: UInt8, payload: Span[UInt8, _]
) raises:
    var frame = List[UInt8](capacity=HEADER_BYTES + 1 + len(payload))
    append_u32_be(frame, UInt32(1 + len(payload)))
    frame.append(status)
    for byte in payload:
        frame.append(byte)
    write_all(fd, Span(frame))


def ascii_bytes(text: String) -> List[UInt8]:
    """Copy a UTF-8 string into bytes for an error payload."""
    var out = List[UInt8](capacity=text.byte_length())
    for byte in text.as_bytes():
        out.append(byte)
    return out^
