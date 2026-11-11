"""Batch CLI for the native MessagePack implementation.

Phase 1 implements the framing and control opcodes so Python compatibility
tests can drive the same process model the final decoder/encoder will use.
DECODE and ENCODE report UNIMPLEMENTED until Phase 2.
"""

from std.collections import List
from std.io import RawFileDescriptor

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
        elif opcode == OP_DECODE or opcode == OP_ENCODE:
            var message = ascii_bytes("opcode " + String(Int(opcode)) + " not implemented in Phase 1")
            write_frame(stdout, STATUS_UNIMPLEMENTED, Span(message))
        else:
            _reply_error(stdout, "unknown opcode " + String(Int(opcode)))
