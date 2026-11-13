"""Batch CLI for the native bitarray implementation.

Framed request/response workflow reusing the PyroMojo convention
(``mojo_bitarray/protocol.mojo``):

* ``0x01`` ping → empty ``STATUS_OK``.
* ``0x02`` echo → payload echoed with ``STATUS_OK``.
* ``0x10`` decode → canonical payload (nbits, endian, packed bytes)
  decoded to an ASCII ``'0'``/``'1'`` string with ``STATUS_OK``.
* ``0x11`` encode → endian id plus ASCII bits packed into the canonical
  payload with ``STATUS_OK``.

Malformed requests produce ``STATUS_ERROR`` frames; framing errors
produce one error frame plus a non-zero exit, like the other CLIs.
"""

from std.collections import List
from std.io import RawFileDescriptor

from mojo_bitarray.protocol import (
    ENDIAN_BIG_ID,
    ENDIAN_LITTLE_ID,
    OP_DECODE,
    OP_ECHO,
    OP_ENCODE,
    OP_PING,
    STATUS_ERROR,
    STATUS_OK,
    ascii_bytes,
    decode_payload_exact,
    encode_payload,
    read_frame,
    write_frame,
)
from mojo_bitarray.storage import BitArray


def _reply_error(mut stdout: RawFileDescriptor, message: String) raises:
    var payload = ascii_bytes(message)
    write_frame(stdout, STATUS_ERROR, Span(payload))


def _parse_encode_request(payload: Span[UInt8, _]) raises -> BitArray:
    """Build a BitArray from an encode request (endian id + ASCII bits)."""
    if len(payload) < 1:
        raise Error("encode request too short: need 1-byte endian and ASCII bits")
    var endian_id = payload[0]
    var big_endian: Bool
    if endian_id == ENDIAN_BIG_ID:
        big_endian = True
    elif endian_id == ENDIAN_LITTLE_ID:
        big_endian = False
    else:
        raise Error(
            "invalid endian identifier "
            + String(Int(endian_id))
            + ": want 0 (big) or 1 (little)"
        )
    var bits = List[Int](capacity=len(payload) - 1)
    for i in range(1, len(payload)):
        var byte = payload[i]
        if byte == UInt8(48):
            bits.append(0)
        elif byte == UInt8(49):
            bits.append(1)
        else:
            raise Error("expected '0' or '1' in encode request")
    return BitArray(bits, big_endian)


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
                var bits = decode_payload_exact(payload)
                var text = ascii_bytes(bits.to01())
                write_frame(stdout, STATUS_OK, Span(text))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_ENCODE:
            try:
                var bits = _parse_encode_request(payload)
                var packed = encode_payload(bits)
                write_frame(stdout, STATUS_OK, Span(packed))
            except error:
                _reply_error(stdout, String(error))
        else:
            _reply_error(stdout, "unknown opcode " + String(Int(opcode)))
