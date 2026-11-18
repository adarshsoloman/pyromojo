"""Phase 3 / Component F: minimal framed CLI for the representation layer.

There is NO resampling opcode. Every operation exercises one Phase 3
component only. Malformed requests produce one STATUS_ERROR frame and the
session continues (no unexpected process crash). Framing errors follow the
established audioop convention (error frame + diagnostic + non-zero exit).

Build (see ``docs/representation-design.md`` §10)::

    .venv/bin/mojo build libraries/resampy/mojo/cli.mojo \
        -I libraries/resampy/mojo --fp-mode contract=off -o build/resampy_cli

Payload layouts (all integers big-endian, Float64 little-endian):
  OP_SIGNAL_INFO       : <f64 values>            -> "len=<n>;first_bits=<hex>;last_bits=<hex>"
  OP_OUTPUT_ALLOC      : <u32 length>           -> <f64 values, all zero>
  OP_OUTPUT_SET        : <u32 length> <u32 idx> <f64 value> -> <f64 values>
  OP_F64_ENCODE        : <f64 values>           -> Base64 ASCII
  OP_F64_DECODE        : <Base64 ASCII>         -> <f64 values>
  OP_SHA256            : <raw bytes>            -> 64-char lowercase hex ASCII
  OP_COMPARE           : <f64 atol> <f64 rtol> <u32 n_a> <a> <u32 n_b> <b> -> comparator record
  OP_GOLDEN_PARSE      : <JSON text>            -> summary record
  OP_GOLDEN_SERIALIZE  : <JSON text>            -> canonical JSON text
  OP_FILTER_LOAD       : <u32 meta_len> <meta JSON> <u32 bin_len> <bin> -> filter summary
"""

from std.collections import List
from std.io import RawFileDescriptor
from std.math import isnan, isinf

from mojo_resampy.protocol import (
    MAX_FRAME_BYTES,
    OP_COMPARE,
    OP_ECHO,
    OP_F64_DECODE,
    OP_F64_ENCODE,
    OP_FILTER_LOAD,
    OP_GOLDEN_PARSE,
    OP_GOLDEN_SERIALIZE,
    OP_OUTPUT_ALLOC,
    OP_OUTPUT_SET,
    OP_PING,
    OP_SHA256,
    OP_SIGNAL_INFO,
    STATUS_ERROR,
    STATUS_OK,
    ascii_bytes,
    decode_u32_be,
    read_frame,
    write_frame,
)
from mojo_resampy.float_codec import (
    base64_decode_bytes,
    base64_encode_bytes,
    bytes_to_hex,
    decode_f64le,
    encode_f64le,
    float64_to_bits,
)
from mojo_resampy.sha256 import sha256_hex
from mojo_resampy.signal import Signal
from mojo_resampy.output import OutputBuffer
from mojo_resampy.numerical_compare import compare_arrays
from mojo_resampy.golden_vector import parse_golden_vector, serialize_golden_vector
from mojo_resampy.coefficients import validate_filter_resource, describe_filter


def _reply_error(mut stdout: RawFileDescriptor, message: String) raises:
    write_frame(stdout, STATUS_ERROR, Span(ascii_bytes(message)))


def _need(payload: Span[UInt8, _], offset: Int, count: Int, label: String) raises:
    if offset < 0 or count < 0 or offset + count > len(payload):
        raise Error(label + ": payload too short (need " + String(offset + count)
                    + " bytes, have " + String(len(payload)) + ")")


def _u32(payload: Span[UInt8, _], offset: Int, label: String) raises -> Int:
    _need(payload, offset, 4, label)
    return Int(decode_u32_be(payload[offset : offset + 4]))


def _f64le(payload: Span[UInt8, _], offset: Int, label: String) raises -> Float64:
    _need(payload, offset, 8, label)
    var values = decode_f64le(payload[offset : offset + 8])
    return values[0]


def _text(payload: Span[UInt8, _]) raises -> String:
    return String(from_utf8=payload)


def _signal_info(payload: Span[UInt8, _]) raises -> List[UInt8]:
    var values = decode_f64le(payload)
    var signal = Signal(values^)
    var out = "len=" + String(len(signal))
    if len(signal) > 0:
        out += ";first_bits=" + _bits_hex(signal[0])
        out += ";last_bits=" + _bits_hex(signal[len(signal) - 1])
        var nonfinite = 0
        for i in range(len(signal)):
            if isnan(signal[i]) or isinf(signal[i]):
                nonfinite += 1
        out += ";nonfinite=" + String(nonfinite)
    else:
        out += ";first_bits=none;last_bits=none;nonfinite=0"
    return ascii_bytes(out)


def _bits_hex(value: Float64) raises -> String:
    var bits = float64_to_bits(value)
    var raw = List[UInt8](capacity=8)
    for j in range(8):
        raw.append(UInt8((bits >> UInt64(8 * j)) & 0xFF))
    return bytes_to_hex(Span(raw))


def _output_alloc(payload: Span[UInt8, _]) raises -> List[UInt8]:
    var length = _u32(payload, 0, "output_alloc")
    var buffer = OutputBuffer(length)
    return encode_f64le(buffer.view())


def _output_set(payload: Span[UInt8, _]) raises -> List[UInt8]:
    var length = _u32(payload, 0, "output_set")
    var index = _u32(payload, 4, "output_set")
    var value = _f64le(payload, 8, "output_set")
    if len(payload) != 16:
        raise Error("output_set: payload must be exactly 16 bytes")
    var buffer = OutputBuffer(length)
    buffer.set(index, value)
    return encode_f64le(buffer.view())


def _f64_encode(payload: Span[UInt8, _]) raises -> List[UInt8]:
    var values = decode_f64le(payload)
    var raw = encode_f64le(Span(values))
    return ascii_bytes(base64_encode_bytes(Span(raw)))


def _f64_decode(payload: Span[UInt8, _]) raises -> List[UInt8]:
    var text = _text(payload)
    var raw = base64_decode_bytes(text)
    var values = decode_f64le(Span(raw))
    return encode_f64le(Span(values))


def _compare(payload: Span[UInt8, _]) raises -> List[UInt8]:
    var atol = _f64le(payload, 0, "compare")
    var rtol = _f64le(payload, 8, "compare")
    var n_a = _u32(payload, 16, "compare")
    _need(payload, 20, n_a * 8, "compare actual")
    var a = decode_f64le(payload[20 : 20 + n_a * 8])
    var off_b = 20 + n_a * 8
    var n_b = _u32(payload, off_b, "compare reference")
    _need(payload, off_b + 4, n_b * 8, "compare reference")
    var b = decode_f64le(payload[off_b + 4 : off_b + 4 + n_b * 8])
    if len(payload) != off_b + 4 + n_b * 8:
        raise Error("compare: trailing bytes after reference vector")
    var result = compare_arrays(Span(a), Span(b), atol, rtol)
    return ascii_bytes(result.serialize())


def _golden_parse(payload: Span[UInt8, _]) raises -> List[UInt8]:
    var gv = parse_golden_vector(_text(payload))
    var out = "case_id=" + gv.case_id
    out += ";schema_version=" + String(gv.schema_version)
    out += ";input_count=" + String(gv.input_count)
    out += ";expected_count=" + String(gv.expected_count)
    out += ";payload_element_count=" + String(gv.payload_element_count)
    out += ";payload_sha256=" + gv.payload_sha256
    out += ";atol=" + String(gv.atol)
    out += ";rtol=" + String(gv.rtol)
    if len(gv.input_values) > 0:
        out += ";first_input_bits=" + _bits_hex(gv.input_values[0])
    else:
        out += ";first_input_bits=none"
    return ascii_bytes(out)


def _golden_serialize(payload: Span[UInt8, _]) raises -> List[UInt8]:
    var gv = parse_golden_vector(_text(payload))
    return ascii_bytes(serialize_golden_vector(gv))


def _filter_load(payload: Span[UInt8, _]) raises -> List[UInt8]:
    var meta_len = _u32(payload, 0, "filter_load")
    _need(payload, 4, meta_len, "filter_load metadata")
    var meta_text = _text(payload[4 : 4 + meta_len])
    var bin_offset = 4 + meta_len
    var bin_len = _u32(payload, bin_offset, "filter_load")
    _need(payload, bin_offset + 4, bin_len, "filter_load resource")
    if len(payload) != bin_offset + 4 + bin_len:
        raise Error("filter_load: trailing bytes after resource")
    var resource = validate_filter_resource(meta_text, payload[bin_offset + 4 : bin_offset + 4 + bin_len])
    return ascii_bytes(describe_filter(resource))


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
        var payload = Span(body)[1:]
        try:
            if opcode == OP_PING:
                write_frame(stdout, STATUS_OK, payload[0:0])
            elif opcode == OP_ECHO:
                write_frame(stdout, STATUS_OK, payload)
            elif opcode == OP_SIGNAL_INFO:
                var out = _signal_info(payload)
                write_frame(stdout, STATUS_OK, Span(out))
            elif opcode == OP_OUTPUT_ALLOC:
                var out = _output_alloc(payload)
                write_frame(stdout, STATUS_OK, Span(out))
            elif opcode == OP_OUTPUT_SET:
                var out = _output_set(payload)
                write_frame(stdout, STATUS_OK, Span(out))
            elif opcode == OP_F64_ENCODE:
                var out = _f64_encode(payload)
                write_frame(stdout, STATUS_OK, Span(out))
            elif opcode == OP_F64_DECODE:
                var out = _f64_decode(payload)
                write_frame(stdout, STATUS_OK, Span(out))
            elif opcode == OP_SHA256:
                write_frame(stdout, STATUS_OK, Span(ascii_bytes(sha256_hex(payload))))
            elif opcode == OP_COMPARE:
                var out = _compare(payload)
                write_frame(stdout, STATUS_OK, Span(out))
            elif opcode == OP_GOLDEN_PARSE:
                var out = _golden_parse(payload)
                write_frame(stdout, STATUS_OK, Span(out))
            elif opcode == OP_GOLDEN_SERIALIZE:
                var out = _golden_serialize(payload)
                write_frame(stdout, STATUS_OK, Span(out))
            elif opcode == OP_FILTER_LOAD:
                var out = _filter_load(payload)
                write_frame(stdout, STATUS_OK, Span(out))
            else:
                _reply_error(stdout, "unknown opcode " + String(Int(opcode)))
        except error:
            _reply_error(stdout, String(error))
