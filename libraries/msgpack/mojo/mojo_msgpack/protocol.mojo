"""Length-prefixed request/response framing for the MessagePack batch CLI.

Wire format (all integers big-endian):

    request  := uint32 length | body
    body     := uint8 opcode | payload
    response := uint32 length | body
    body     := uint8 status | payload

``length`` counts the body bytes only. A clean EOF between frames ends the
session with exit code 0. Framing errors produce one error frame on stdout and
a diagnostic plus non-zero exit on stderr.
"""

from std.collections import List
from std.io import RawFileDescriptor


comptime MAX_FRAME_BYTES: Int = 64 * 1024 * 1024
comptime HEADER_BYTES: Int = 4

comptime OP_PING: UInt8 = 0x01
comptime OP_ECHO: UInt8 = 0x02
comptime OP_DECODE: UInt8 = 0x10
comptime OP_ENCODE: UInt8 = 0x11

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


def write_all(mut fd: RawFileDescriptor, payload: Span[UInt8, _]) raises:
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


def append_u32_be(mut out: List[UInt8], value: UInt32):
    out.append(UInt8((value >> 24) & 0xFF))
    out.append(UInt8((value >> 16) & 0xFF))
    out.append(UInt8((value >> 8) & 0xFF))
    out.append(UInt8(value & 0xFF))


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
