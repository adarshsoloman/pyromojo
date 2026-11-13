"""Native in-process benchmark for the bitarray operations.

Usage: bench_bitarray <op> <warmup> <samples> < stdin-frame

The stdin frame reuses the canonical framed payloads (same layout as
the batch CLI, reused only to ferry bytes in; framing I/O, payload
validation, and BitArray construction happen once outside the timed
region and are never measured):

    framed(A) | framed(B) | u32be k

where framed(X) is ``uint32_be nbits | uint8 endian | packed bytes``.
``B`` is ignored by unary ops. ``k`` is used only by shifts.

Ops (all production entry points on packed storage):

- ``and``, ``or``, ``xor`` — ``a & b`` etc. (new array each call).
- ``count`` — ``a.count()``.
- ``shl``, ``shr`` — ``a << k`` / ``a >> k`` (new array each call).

Each timed loop calls exactly one operation plus an O(1) use of each
result (a running sink) to keep the work live. The final result is
reported as an FNV-1a checksum plus (for nbits <= 4096) full hex so the
driver can verify correctness outside the timed region. Results print
as one JSON object on stdout.
"""

from std.collections import List
from std.io import RawFileDescriptor
from std.sys import argv
from std.time import perf_counter_ns

from mojo_bitarray.protocol import (
    ENDIAN_BIG_ID,
    ENDIAN_LITTLE_ID,
    decode_payload_exact,
    decode_u32_be,
    read_frame,
)
from mojo_bitarray.storage import BitArray, bytes_for_bits


comptime FNV_OFFSET: UInt64 = 14695981039346656037
comptime FNV_PRIME: UInt64 = 1099511628217961
comptime HEX_DIGITS: String = "0123456789abcdef"


def _fnv1a(data: Span[UInt8, _]) -> UInt64:
    var h = FNV_OFFSET
    for byte in data:
        h = (h ^ UInt64(byte)) * FNV_PRIME
    return h


def _to_hex(data: Span[UInt8, _]) -> String:
    var out = String("")
    for byte in data:
        out += HEX_DIGITS[byte=(byte >> 4)]
        out += HEX_DIGITS[byte=(byte & 0x0F)]
    return out^


def _parse_frame(payload: Span[UInt8, _]) raises -> Tuple[Int, Int, Int]:
    """Validate one frame and return operand spans (untimed).

    Returns (len_a, len_b, k): ``payload[0:len_a]`` and
    ``payload[len_a:len_a + len_b]`` are the canonical operand payloads
    and the final 4 bytes are the shift count. Operands must match in
    logical length; endianness is checked at decode time.
    """
    if len(payload) < 9:
        raise Error("bench payload too short for two length prefixes")
    var na = Int(decode_u32_be(payload[0:4]))
    var la = 5 + bytes_for_bits(na)
    if len(payload) < la + 9:
        raise Error("bench payload truncated in first array")
    var rest = payload[la:]
    var nb = Int(decode_u32_be(rest[0:4]))
    var lb = 5 + bytes_for_bits(nb)
    if len(rest) != lb + 4:
        raise Error("bench payload has trailing bytes")
    var k = Int(decode_u32_be(rest[lb : lb + 4]))
    if na != nb:
        raise Error("bench operands must have equal length")
    return (la, lb, k)


def _checksum_bits(a: BitArray) -> UInt64:
    var raw = a.tobytes()
    var buf = List[UInt8](capacity=5 + len(raw))
    var n = UInt32(len(a))
    buf.append(UInt8((n >> 24) & 0xFF))
    buf.append(UInt8((n >> 16) & 0xFF))
    buf.append(UInt8((n >> 8) & 0xFF))
    buf.append(UInt8(n & 0xFF))
    buf.append(ENDIAN_BIG_ID if a.big_endian else ENDIAN_LITTLE_ID)
    for byte in raw:
        buf.append(byte)
    return _fnv1a(Span(buf))


def _checksum_count(c: Int) -> UInt64:
    var v = UInt64(c)
    var buf = List[UInt8](capacity=8)
    for i in range(8):
        buf.append(UInt8((v >> UInt64(8 * (7 - i))) & 0xFF))
    return _fnv1a(Span(buf))


def _print_json(op: String, samples: List[Int], checksum: UInt64, extra: String):
    var line = String('{"op":"') + op + String('","samples_ns":[')
    for i in range(len(samples)):
        if i > 0:
            line += String(",")
        line += String(samples[i])
    line += String('],"checksum":"') + String(checksum) + String('"') + extra + String("}")
    print(line)


def _hex_field(a: BitArray) -> String:
    if len(a) > 4096:
        return String("")
    return String(',"hex":"') + _to_hex(Span(a.tobytes())) + String('"')


def _run_bitwise(op: String, a: BitArray, b: BitArray, warmup: Int, sample_count: Int) raises:
    var sink: UInt64 = 0
    for _ in range(warmup):
        if op == "and":
            _ = a & b
        elif op == "or":
            _ = a | b
        else:
            _ = a ^ b
    var samples = List[Int](capacity=sample_count)
    var last: BitArray
    if op == "and":
        last = a & b
    elif op == "or":
        last = a | b
    else:
        last = a ^ b
    for _ in range(sample_count):
        var start = Int(perf_counter_ns())
        if op == "and":
            last = a & b
        elif op == "or":
            last = a | b
        else:
            last = a ^ b
        samples.append(Int(perf_counter_ns()) - start)
        if len(last) > 0:
            sink = sink * 31 + UInt64(Int(last.read_bit(0))) + UInt64(len(last))
        else:
            sink = sink + UInt64(len(last))
    _print_json(op, samples, _checksum_bits(last), _hex_field(last) + String(',"sink":"') + String(sink) + String('"'))


def _run_count(a: BitArray, warmup: Int, sample_count: Int) raises:
    var sink: UInt64 = 0
    for _ in range(warmup):
        _ = a.count()
    var samples = List[Int](capacity=sample_count)
    var last = 0
    for _ in range(sample_count):
        var start = Int(perf_counter_ns())
        last = a.count()
        samples.append(Int(perf_counter_ns()) - start)
        sink = sink * 31 + UInt64(last)
    _print_json(
        String("count"),
        samples,
        _checksum_count(last),
        String(',"count":') + String(last) + String(',"sink":"') + String(sink) + String('"'),
    )


def _run_shift(op: String, a: BitArray, k: Int, warmup: Int, sample_count: Int) raises:
    var sink: UInt64 = 0
    for _ in range(warmup):
        if op == "shl":
            _ = a << k
        else:
            _ = a >> k
    var samples = List[Int](capacity=sample_count)
    var last: BitArray
    if op == "shl":
        last = a << k
    else:
        last = a >> k
    for _ in range(sample_count):
        var start = Int(perf_counter_ns())
        if op == "shl":
            last = a << k
        else:
            last = a >> k
        samples.append(Int(perf_counter_ns()) - start)
        if len(last) > 0:
            sink = sink * 31 + UInt64(Int(last.read_bit(0))) + UInt64(len(last))
        else:
            sink = sink + UInt64(len(last))
    _print_json(op, samples, _checksum_bits(last), _hex_field(last) + String(',"sink":"') + String(sink) + String('"'))


def main() raises:
    var args = argv()
    if len(args) != 4:
        raise Error("usage: bench_bitarray <op> <warmup> <samples>")
    var op = String(args[1])
    var warmup = Int(args[2])
    var sample_count = Int(args[3])
    if warmup < 0 or sample_count < 1:
        raise Error("warmup must be >= 0 and samples must be >= 1")
    if op != "and" and op != "or" and op != "xor" and op != "count" and op != "shl" and op != "shr":
        raise Error("op must be and, or, xor, count, shl, or shr")

    var stdin = RawFileDescriptor(0)
    var payload = List[UInt8]()
    if not read_frame(stdin, payload):
        raise Error("no payload frame on stdin")
    var parsed = _parse_frame(Span(payload))
    var la = parsed[0]
    var lb = parsed[1]
    var k = parsed[2]
    var view = Span(payload)
    var a = decode_payload_exact(view[0:la])
    var b = decode_payload_exact(view[la : la + lb])
    if a.big_endian != b.big_endian:
        raise Error("bench operands must have equal endianness")

    if op == "count":
        _run_count(a, warmup, sample_count)
    elif op == "shl" or op == "shr":
        _run_shift(op, a, k, warmup, sample_count)
    else:
        _run_bitwise(op, a, b, warmup, sample_count)
