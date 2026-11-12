"""Batch CLI for the native Levenshtein implementation.

One process answers many framed requests over stdin/stdout (see
``mojo_levenshtein/protocol.mojo``). The CLI only parses, validates, and
frames; all string algorithms live in ``mojo_levenshtein`` and never see
transport bytes.
"""

from std.collections import List
from std.io import RawFileDescriptor

from mojo_levenshtein.distance import (
    levenshtein_distance,
    levenshtein_distance_cutoff,
)
from mojo_levenshtein.hamming import levenshtein_hamming
from mojo_levenshtein.protocol import (
    OP_DISTANCE,
    OP_ECHO,
    OP_HAMMING,
    OP_PING,
    OP_RATIO,
    STATUS_ERROR,
    STATUS_OK,
    append_f64_be,
    append_u64_be,
    ascii_bytes,
    decode_u32_be,
    decode_u64_be,
    read_frame,
    write_frame,
)
from mojo_levenshtein.ratio import levenshtein_ratio


struct RequestReader[origin: Origin]:
    """Cursor over a request payload with bounds-checked field reads."""

    var data: Span[UInt8, Self.origin]
    var pos: Int

    def __init__(out self, data: Span[UInt8, Self.origin]):
        self.data = data
        self.pos = 0

    def remaining(self) -> Int:
        return len(self.data) - self.pos

    def read_bytes(mut self, count: Int) raises -> Span[UInt8, Self.origin]:
        if count < 0 or count > self.remaining():
            raise Error("malformed request: field length exceeds payload")
        var start = self.pos
        self.pos += count
        return self.data[start : start + count]

    def read_u8(mut self) raises -> UInt8:
        return self.read_bytes(1)[0]

    def read_u32(mut self) raises -> UInt32:
        return decode_u32_be(self.read_bytes(4))

    def read_u64(mut self) raises -> UInt64:
        return decode_u64_be(self.read_bytes(8))

    def read_string(mut self) raises -> String:
        var length = Int(self.read_u32())
        var raw = self.read_bytes(length)
        return String(from_utf8=raw)

    def read_int_field(mut self, name: String) raises -> Int:
        var value = self.read_u64()
        if value > UInt64(Int.MAX):
            raise Error("malformed request: " + name + " exceeds Int range")
        return Int(value)

    def check_end(self) raises:
        if self.remaining() != 0:
            raise Error("malformed request: trailing bytes after fields")


def _reply_error(mut stdout: RawFileDescriptor, message: String) raises:
    var payload = ascii_bytes(message)
    write_frame(stdout, STATUS_ERROR, Span(payload))


def _handle_distance(
    mut reader: RequestReader, mut out: List[UInt8]
) raises:
    var insertion = reader.read_int_field("insertion weight")
    var deletion = reader.read_int_field("deletion weight")
    var substitution = reader.read_int_field("substitution weight")
    var has_cutoff = reader.read_u8()
    var cutoff = 0
    var cutoff_active = False
    if has_cutoff == 1:
        var raw_cutoff = reader.read_u64()
        # A cutoff above Int range can never truncate: every distance
        # fits in Int (guarded by _check_bounds), so min(d, cutoff + 1)
        # is just d. Treat it as no cutoff rather than rejecting it.
        if raw_cutoff <= UInt64(Int.MAX):
            cutoff = Int(raw_cutoff)
            cutoff_active = True
    elif has_cutoff != 0:
        raise Error("malformed request: cutoff flag must be 0 or 1")
    var left = reader.read_string()
    var right = reader.read_string()
    reader.check_end()
    var distance: Int
    if cutoff_active:
        distance = levenshtein_distance_cutoff(
            left, right, cutoff, insertion, deletion, substitution
        )
    else:
        distance = levenshtein_distance(
            left, right, insertion, deletion, substitution
        )
    append_u64_be(out, UInt64(distance))


def _handle_ratio(mut reader: RequestReader, mut out: List[UInt8]) raises:
    var left = reader.read_string()
    var right = reader.read_string()
    reader.check_end()
    append_f64_be(out, levenshtein_ratio(left, right))


def _handle_hamming(mut reader: RequestReader, mut out: List[UInt8]) raises:
    var pad = reader.read_u8()
    if pad != 0 and pad != 1:
        raise Error("malformed request: pad flag must be 0 or 1")
    var left = reader.read_string()
    var right = reader.read_string()
    reader.check_end()
    append_u64_be(out, UInt64(levenshtein_hamming(left, right, pad == 1)))


def main() raises:
    var stdin = RawFileDescriptor(0)
    var stdout = RawFileDescriptor(1)

    while True:
        var body = List[UInt8]()
        try:
            if not read_frame(stdin, body):
                return
        except error:
            _reply_error(stdout, String(error))
            raise error

        if len(body) == 0:
            _reply_error(stdout, "empty request frame")
            continue

        var opcode = body[0]
        var view = Span(body)
        var reader = RequestReader(view[1:])
        var payload = List[UInt8]()

        if opcode == OP_PING:
            try:
                reader.check_end()
            except error:
                _reply_error(stdout, String(error))
                continue
            write_frame(stdout, STATUS_OK, Span(payload))
        elif opcode == OP_ECHO:
            var rest = reader.remaining()
            var echo = reader.read_bytes(rest)
            for byte in echo:
                payload.append(byte)
            write_frame(stdout, STATUS_OK, Span(payload))
        elif opcode == OP_DISTANCE:
            try:
                _handle_distance(reader, payload)
            except error:
                _reply_error(stdout, String(error))
                continue
            write_frame(stdout, STATUS_OK, Span(payload))
        elif opcode == OP_RATIO:
            try:
                _handle_ratio(reader, payload)
            except error:
                _reply_error(stdout, String(error))
                continue
            write_frame(stdout, STATUS_OK, Span(payload))
        elif opcode == OP_HAMMING:
            try:
                _handle_hamming(reader, payload)
            except error:
                _reply_error(stdout, String(error))
                continue
            write_frame(stdout, STATUS_OK, Span(payload))
        else:
            _reply_error(stdout, "unknown opcode " + String(Int(opcode)))
