"""Batch CLI for the Phase 1 audioop sample representation.

Operations (framed, see ``mojo_audioop/protocol.mojo``):

* ``0x01`` ping -> empty ``STATUS_OK``.
* ``0x02`` echo -> payload echoed with ``STATUS_OK``.
* ``0x20`` decode -> ``uint8 width | fragment bytes``; replies with
  space-separated ASCII signed samples (empty fragment -> empty payload).
* ``0x21`` encode -> ``uint8 width | space-separated ASCII samples``;
  replies with the native-order fragment bytes.

Malformed requests produce ``STATUS_ERROR`` frames; framing errors
produce one error frame plus a non-zero exit, like the other CLIs.
"""

from std.collections import List
from std.io import RawFileDescriptor

from mojo_audioop.protocol import (
    OP_DECODE_FRAGMENT,
    OP_ECHO,
    OP_ENCODE_FRAGMENT,
    OP_PING,
    STATUS_ERROR,
    STATUS_OK,
    ascii_bytes,
    read_frame,
    write_frame,
)
from mojo_audioop.samples import decode_fragment, encode_fragment


def _reply_error(mut stdout: RawFileDescriptor, message: String) raises:
    var payload = ascii_bytes(message)
    write_frame(stdout, STATUS_ERROR, Span(payload))


def _parse_values(text: Span[UInt8, _]) raises -> List[Int64]:
    """Parse space-separated decimal signed samples into Int32 values."""
    var values = List[Int64]()
    var i = 0
    var total = len(text)
    while i < total:
        while i < total and text[i] == UInt8(32):
            i += 1
        if i >= total:
            break

        var negative = False
        if text[i] == UInt8(45):
            negative = True
            i += 1
        if i >= total:
            raise Error("invalid sample value list")

        var acc: Int64 = 0
        var digits = 0
        while i < total and text[i] >= UInt8(48) and text[i] <= UInt8(57):
            acc = acc * 10 + (Int64(text[i]) - 48)
            if acc > 922337203685477580:
                raise Error("sample value out of range")
            digits += 1
            i += 1
        if digits == 0:
            raise Error("invalid sample value list")
        if negative:
            acc = -acc
        values.append(acc)

        if i < total and text[i] != UInt8(32):
            raise Error("invalid sample value list")
    return values^


def _format_values(samples: List[Int32]) -> List[UInt8]:
    """Render samples as space-separated ASCII decimals."""
    var out = List[UInt8]()
    for index in range(len(samples)):
        if index > 0:
            out.append(32)
        var text = String(Int(samples[index]))
        for byte in text.as_bytes():
            out.append(byte)
    return out^


def _decode_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    """Decode a fragment request into ASCII sample text."""
    if len(payload) < 1:
        raise Error("decode request too short: need a width byte")
    var width = Int(payload[0])
    var samples = decode_fragment(payload[1:], width)
    return _format_values(samples)


def _encode_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    """Encode ASCII sample text into a native-order fragment."""
    if len(payload) < 1:
        raise Error("encode request too short: need a width byte")
    var width = Int(payload[0])
    var samples = _parse_values(payload[1:])
    return encode_fragment(Span(samples), width)


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
        elif opcode == OP_DECODE_FRAGMENT:
            try:
                var text = _decode_request(payload)
                write_frame(stdout, STATUS_OK, Span(text))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_ENCODE_FRAGMENT:
            try:
                var encoded = _encode_request(payload)
                write_frame(stdout, STATUS_OK, Span(encoded))
            except error:
                _reply_error(stdout, String(error))
        else:
            _reply_error(stdout, "unknown opcode " + String(Int(opcode)))
