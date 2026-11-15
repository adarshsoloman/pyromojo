"""Batch CLI for the Phase 1 audioop sample representation.

Operations (framed, see ``mojo_audioop/protocol.mojo``):

* ``0x01`` ping -> empty ``STATUS_OK``.
* ``0x02`` echo -> payload echoed with ``STATUS_OK``.
* ``0x20`` decode -> ``uint8 width | fragment bytes``; replies with
  space-separated ASCII signed samples (empty fragment -> empty payload).
* ``0x21`` encode -> ``uint8 width | space-separated ASCII samples``;
  replies with the native-order fragment bytes.
* ``0x22`` add -> ``uint8 width | uint32_be len1 | fragment1 | fragment2``.
* ``0x23`` bias -> ``uint8 width | int64_be bias | fragment``.
* ``0x24`` mul -> ``uint8 width | 8-byte IEEE-754 big-endian factor | fragment``.
* ``0x25`` reverse -> ``uint8 width | fragment``.
* ``0x26`` byteswap -> ``uint8 width | fragment``.
* ``0x27`` lin2lin -> ``uint8 width | uint8 newwidth | fragment``.
* ``0x28`` getsample -> ``uint8 width | int64_be index | fragment``;
  replies with one ASCII decimal sample.
* ``0x29`` max -> ``uint8 width | fragment``; replies with one ASCII
  decimal (the absolute maximum; may exceed the signed range).
* ``0x2A`` minmax -> ``uint8 width | fragment``; replies with two
  space-separated ASCII decimals (minimum, maximum).
* ``0x2B`` avg -> ``uint8 width | fragment``; replies with one ASCII
  decimal (floor of the mean).
* ``0x2C`` rms -> ``uint8 width | fragment``; replies with one ASCII
  decimal (truncated sqrt of the mean square).
* ``0x2D`` cross -> ``uint8 width | fragment``; replies with one ASCII
  decimal (zero-class transition count).
* ``0x2E`` avgpp -> ``uint8 width | fragment``; replies with one ASCII
  decimal (truncated mean of unsigned peak differences).
* ``0x2F`` maxpp -> ``uint8 width | fragment``; replies with one ASCII
  decimal (maximum unsigned peak difference).
* ``0x30`` findmax -> ``int64_be length | fragment``; replies with the
  winning 16-bit sample index as one ASCII decimal (the reference has
  no width argument; the fragment is read as native int16 pairs).
* ``0x31`` findfactor -> ``uint32_be len1 | frag1 | frag2``; replies
  with 8 big-endian IEEE-754 bytes of the factor (bit-exact, nan too).
* ``0x32`` findfit -> ``uint32_be len1 | frag1 | frag2``; replies with
  the ASCII decimal window index, a space, then 8 big-endian IEEE-754
  bytes of the factor.
* ``0x33`` tomono -> ``uint8 width | 8-byte IEEE-754 BE lfactor |
  8-byte IEEE-754 BE rfactor | fragment``; replies with the mono
  fragment bytes.
* ``0x34`` tostereo -> same payload as tomono; replies with the stereo
  fragment bytes (left sample first per input sample).

Malformed requests produce ``STATUS_ERROR`` frames; framing errors
produce one error frame plus a non-zero exit, like the other CLIs.
"""

from std.collections import List
from std.io import RawFileDescriptor

from mojo_audioop.arithmetic import (
    add,
    bias,
    byteswap,
    lin2lin,
    mul,
    reverse,
)
from mojo_audioop.protocol import (
    OP_ADD,
    OP_AVG,
    OP_BIAS,
    OP_BYTESWAP,
    OP_AVGPP,
    OP_CROSS,
    OP_DECODE_FRAGMENT,
    OP_FINDFACTOR,
    OP_FINDFIT,
    OP_FINDMAX,
    OP_ECHO,
    OP_ENCODE_FRAGMENT,
    OP_GETSAMPLE,
    OP_LIN2LIN,
    OP_MAX,
    OP_MAXPP,
    OP_MINMAX,
    OP_MUL,
    OP_PING,
    OP_REVERSE,
    OP_RMS,
    OP_TOMONO,
    OP_TOSTEREO,
    STATUS_ERROR,
    STATUS_OK,
    ascii_bytes,
    decode_u32_be,
    read_frame,
    write_frame,
)
from mojo_audioop.samples import decode_fragment, encode_fragment
from mojo_audioop.channels import tomono, tostereo
from mojo_audioop.peak_analysis import avgpp, findfactor, findfit, findmax, maxpp
from mojo_audioop.statistics import avg, cross, getsample, max, minmax, rms
from std.memory import bitcast


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


def _decode_u64_be(data: Span[UInt8, _]) -> UInt64:
    """Big-endian 8-byte unsigned integer (IEEE-754 factor transport)."""
    var value: UInt64 = 0
    for index in range(8):
        value = (value << 8) | UInt64(data[index])
    return value


def _decode_double_be(data: Span[UInt8, _]) -> Float64:
    """Big-endian IEEE-754 double, bit-exact for nan/inf too."""
    return bitcast[DType.float64, 1](_decode_u64_be(data))


def _add_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 5:
        raise Error("add request too short: need width and first length")
    var width = Int(payload[0])
    var length1 = Int(decode_u32_be(payload[1:5]))
    var rest = payload[5:]
    if length1 > len(rest):
        raise Error("add request too short: first fragment is missing")
    var second = List[UInt8](capacity=len(rest) - length1)
    for index in range(length1, len(rest)):
        second.append(rest[index])
    return add(rest[:length1], Span(second), width)


def _bias_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 9:
        raise Error("bias request too short: need width and bias")
    var width = Int(payload[0])
    var value = _decode_i64_be(payload[1:9])
    return bias(payload[9:], width, value)


def _decode_i64_be(data: Span[UInt8, _]) -> Int64:
    """Big-endian 8-byte two's-complement integer."""
    var value: Int64 = 0
    for index in range(8):
        value = (value << 8) | Int64(data[index])
    return value


def _mul_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 9:
        raise Error("mul request too short: need width and factor")
    var width = Int(payload[0])
    var factor = _decode_double_be(payload[1:9])
    return mul(payload[9:], width, factor)


def _reverse_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 1:
        raise Error("reverse request too short: need a width byte")
    return reverse(payload[1:], Int(payload[0]))


def _byteswap_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 1:
        raise Error("byteswap request too short: need a width byte")
    return byteswap(payload[1:], Int(payload[0]))


def _lin2lin_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 2:
        raise Error("lin2lin request too short: need width and new width")
    return lin2lin(payload[2:], Int(payload[0]), Int(payload[1]))


def _format_scalar(value: Int64) -> List[UInt8]:
    var text = String(value)
    var out = List[UInt8](capacity=text.byte_length())
    for byte in text.as_bytes():
        out.append(byte)
    return out^


def _format_pair(first: Int64, second: Int64) -> List[UInt8]:
    var out = _format_scalar(first)
    out.append(32)
    var second_text = _format_scalar(second)
    for byte in second_text:
        out.append(byte)
    return out^


def _getsample_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 9:
        raise Error("getsample request too short: need width and index")
    var width = Int(payload[0])
    var index = _decode_i64_be(payload[1:9])
    var value = getsample(payload[9:], width, index)
    return _format_scalar(Int64(value))


def _max_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 1:
        raise Error("max request too short: need a width byte")
    return _format_scalar(max(payload[1:], Int(payload[0])))


def _minmax_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 1:
        raise Error("minmax request too short: need a width byte")
    var pair = minmax(payload[1:], Int(payload[0]))
    return _format_pair(Int64(pair[0]), Int64(pair[1]))


def _avg_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 1:
        raise Error("avg request too short: need a width byte")
    return _format_scalar(avg(payload[1:], Int(payload[0])))


def _rms_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 1:
        raise Error("rms request too short: need a width byte")
    return _format_scalar(rms(payload[1:], Int(payload[0])))


def _cross_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 1:
        raise Error("cross request too short: need a width byte")
    return _format_scalar(cross(payload[1:], Int(payload[0])))


def _encode_double_be(value: Float64) -> List[UInt8]:
    """Big-endian IEEE-754 bytes, bit-exact for nan and infinities."""
    var bits = bitcast[DType.uint64, 1](value)
    var out = List[UInt8](capacity=8)
    for shift in range(56, -8, -8):
        out.append(UInt8((bits >> UInt64(shift)) & 0xFF))
    return out^


def _avgpp_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 1:
        raise Error("avgpp request too short: need a width byte")
    return _format_scalar(avgpp(payload[1:], Int(payload[0])))


def _maxpp_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 1:
        raise Error("maxpp request too short: need a width byte")
    return _format_scalar(maxpp(payload[1:], Int(payload[0])))


def _findmax_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 8:
        raise Error("findmax request too short: need a length")
    var length = _decode_i64_be(payload[0:8])
    return _format_scalar(Int64(findmax(payload[8:], length)))


def _findfactor_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 4:
        raise Error("findfactor request too short: need the first length")
    var length1 = Int(decode_u32_be(payload[0:4]))
    var rest = payload[4:]
    if length1 > len(rest):
        raise Error("findfactor request too short: first fragment is missing")
    var first = List[UInt8](capacity=length1)
    for index in range(length1):
        first.append(rest[index])
    var second = List[UInt8](capacity=len(rest) - length1)
    for index in range(length1, len(rest)):
        second.append(rest[index])
    return _encode_double_be(findfactor(Span(first), Span(second)))


def _findfit_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 4:
        raise Error("findfit request too short: need the first length")
    var length1 = Int(decode_u32_be(payload[0:4]))
    var rest = payload[4:]
    if length1 > len(rest):
        raise Error("findfit request too short: first fragment is missing")
    var first = List[UInt8](capacity=length1)
    for index in range(length1):
        first.append(rest[index])
    var second = List[UInt8](capacity=len(rest) - length1)
    for index in range(length1, len(rest)):
        second.append(rest[index])
    var fit = findfit(Span(first), Span(second))
    var out = _format_scalar(Int64(fit.index))
    out.append(32)
    var bits = _encode_double_be(fit.factor)
    for byte in bits:
        out.append(byte)
    return out^


def _tomono_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 17:
        raise Error("tomono request too short: need width and two factors")
    var width = Int(payload[0])
    var left = _decode_double_be(payload[1:9])
    var right = _decode_double_be(payload[9:17])
    return tomono(payload[17:], width, left, right)


def _tostereo_request(payload: Span[UInt8, _]) raises -> List[UInt8]:
    if len(payload) < 17:
        raise Error("tostereo request too short: need width and two factors")
    var width = Int(payload[0])
    var left = _decode_double_be(payload[1:9])
    var right = _decode_double_be(payload[9:17])
    return tostereo(payload[17:], width, left, right)


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
        elif opcode == OP_ADD:
            try:
                var added = _add_request(payload)
                write_frame(stdout, STATUS_OK, Span(added))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_BIAS:
            try:
                var biased = _bias_request(payload)
                write_frame(stdout, STATUS_OK, Span(biased))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_MUL:
            try:
                var scaled = _mul_request(payload)
                write_frame(stdout, STATUS_OK, Span(scaled))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_REVERSE:
            try:
                var reversed_fragment = _reverse_request(payload)
                write_frame(stdout, STATUS_OK, Span(reversed_fragment))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_BYTESWAP:
            try:
                var swapped = _byteswap_request(payload)
                write_frame(stdout, STATUS_OK, Span(swapped))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_LIN2LIN:
            try:
                var converted = _lin2lin_request(payload)
                write_frame(stdout, STATUS_OK, Span(converted))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_GETSAMPLE:
            try:
                var sampled = _getsample_request(payload)
                write_frame(stdout, STATUS_OK, Span(sampled))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_MAX:
            try:
                var peak = _max_request(payload)
                write_frame(stdout, STATUS_OK, Span(peak))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_MINMAX:
            try:
                var pair = _minmax_request(payload)
                write_frame(stdout, STATUS_OK, Span(pair))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_AVG:
            try:
                var mean = _avg_request(payload)
                write_frame(stdout, STATUS_OK, Span(mean))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_RMS:
            try:
                var square_mean = _rms_request(payload)
                write_frame(stdout, STATUS_OK, Span(square_mean))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_CROSS:
            try:
                var crossings = _cross_request(payload)
                write_frame(stdout, STATUS_OK, Span(crossings))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_AVGPP:
            try:
                var avg_peak = _avgpp_request(payload)
                write_frame(stdout, STATUS_OK, Span(avg_peak))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_MAXPP:
            try:
                var max_peak = _maxpp_request(payload)
                write_frame(stdout, STATUS_OK, Span(max_peak))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_FINDMAX:
            try:
                var window = _findmax_request(payload)
                write_frame(stdout, STATUS_OK, Span(window))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_FINDFACTOR:
            try:
                var factor_bits = _findfactor_request(payload)
                write_frame(stdout, STATUS_OK, Span(factor_bits))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_FINDFIT:
            try:
                var fit_result = _findfit_request(payload)
                write_frame(stdout, STATUS_OK, Span(fit_result))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_TOMONO:
            try:
                var mono_fragment = _tomono_request(payload)
                write_frame(stdout, STATUS_OK, Span(mono_fragment))
            except error:
                _reply_error(stdout, String(error))
        elif opcode == OP_TOSTEREO:
            try:
                var stereo_fragment = _tostereo_request(payload)
                write_frame(stdout, STATUS_OK, Span(stereo_fragment))
            except error:
                _reply_error(stdout, String(error))
        else:
            _reply_error(stdout, "unknown opcode " + String(Int(opcode)))
