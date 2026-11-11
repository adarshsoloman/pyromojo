"""Batch CLI for the native MessagePack implementation.

Phase 3 implements integer, float, string, and binary DECODE and ENCODE.
Arrays, maps, extensions, timestamps, nil, and bool still report UNIMPLEMENTED;
malformed scalar models report ERROR.
"""

from std.collections import List
from std.io import RawFileDescriptor

from mojo_msgpack.scalar import (
    append_scalar_model,
    decode_scalar_exact,
    decode_scalar_model,
    encode_scalar_value,
)
from mojo_msgpack.protocol import (
    OP_DECODE,
    OP_ECHO,
    OP_ENCODE,
    OP_PING,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_UNIMPLEMENTED,
    ascii_bytes,
    read_frame,
    write_frame,
)


def _reply_error(mut stdout: RawFileDescriptor, message: String) raises:
    var payload = ascii_bytes(message)
    write_frame(stdout, STATUS_ERROR, Span(payload))


def _reply_unimplemented(mut stdout: RawFileDescriptor, opcode: UInt8) raises:
    var message = ascii_bytes(
        "opcode " + String(Int(opcode)) + " not implemented in Phase 1"
    )
    write_frame(stdout, STATUS_UNIMPLEMENTED, Span(message))


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
        var payload = view[1:]

        if opcode == OP_PING:
            write_frame(stdout, STATUS_OK, payload[0:0])
        elif opcode == OP_ECHO:
            write_frame(stdout, STATUS_OK, payload)
        elif opcode == OP_DECODE:
            try:
                var value = decode_scalar_exact(payload)
                var model = List[UInt8](capacity=1 + len(value.data))
                append_scalar_model(model, value)
                write_frame(stdout, STATUS_OK, Span(model))
            except error:
                var message = String(error)
                if message.startswith("unsupported-marker"):
                    _reply_unimplemented(stdout, opcode)
                else:
                    _reply_error(stdout, message)
        elif opcode == OP_ENCODE:
            # Preserve the Phase 1 stub behaviour for the nil sentinel while
            # reporting malformed scalar models as errors.
            if len(payload) == 1 and payload[0] == 0xC0:
                _reply_unimplemented(stdout, opcode)
                continue
            try:
                var value = decode_scalar_model(payload)
                var encoded = List[UInt8](capacity=1 + len(value.data))
                encode_scalar_value(encoded, value)
                write_frame(stdout, STATUS_OK, Span(encoded))
            except error:
                _reply_error(stdout, String(error))
        else:
            _reply_error(stdout, "unknown opcode " + String(Int(opcode)))
