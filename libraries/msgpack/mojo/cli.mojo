"""Batch CLI for the native MessagePack implementation.

Phase 6 supports the full v0.1 type set at the top level, including nil and
bool: the Phase 1 stub responses are retired and every MessagePack marker
decodes or reports a documented error.
"""

from std.collections import List
from std.io import RawFileDescriptor

from mojo_msgpack.container import (
    append_value_model,
    decode_value_exact,
    decode_value_model_exact,
    encode_value,
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
    # Retained as a safety net: no v0.1 marker reaches this path, since every
    # valid marker decodes and every other byte reports a documented error.
    var message = ascii_bytes(
        "opcode " + String(Int(opcode)) + " input is valid but not supported"
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
                var value = decode_value_exact(payload)
                var model = List[UInt8](capacity=1 + len(value.data))
                append_value_model(model, value)
                write_frame(stdout, STATUS_OK, Span(model))
            except error:
                var message = String(error)
                if message.startswith("unsupported-marker"):
                    _reply_unimplemented(stdout, opcode)
                else:
                    _reply_error(stdout, message)
        elif opcode == OP_ENCODE:
            try:
                var value = decode_value_model_exact(payload)
                var encoded = List[UInt8]()
                encode_value(encoded, value)
                write_frame(stdout, STATUS_OK, Span(encoded))
            except error:
                _reply_error(stdout, String(error))
        else:
            _reply_error(stdout, "unknown opcode " + String(Int(opcode)))
