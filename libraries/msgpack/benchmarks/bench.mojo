"""Native in-process benchmark for the MessagePack codec.

Usage: bench_msgpack <encode|decode> <warmup> <samples> < payload_frame

The payload frame on stdin is ``uint32_be length | MessagePack bytes`` (the
same framing as the batch CLI, reused only to ferry bytes in; framing I/O
happens once outside the timed region and is never measured).

The timed region contains only codec calls plus an O(1) use of each result
to keep the work live. Full-output checksums and the decoded-value
fingerprint are computed outside the timed region so verification does not
pollute the measurement. Results print as one JSON object on stdout.
"""

from std.collections import List
from std.io import RawFileDescriptor
from std.sys import argv
from std.time import perf_counter_ns

from mojo_msgpack.container import decode_value_exact, encode_value
from mojo_msgpack.protocol import read_frame
from mojo_msgpack.value import (
    VALUE_ARRAY,
    VALUE_BIN,
    VALUE_BOOL,
    VALUE_EXT,
    VALUE_FLOAT32,
    VALUE_FLOAT64,
    VALUE_INT,
    VALUE_MAP,
    VALUE_NIL,
    VALUE_STR,
    VALUE_TIMESTAMP,
    VALUE_UINT,
    Value,
)


def _fnv_update(mut acc: UInt64, byte: UInt8):
    acc = (acc ^ UInt64(byte)) * UInt64(1099511628211)


def _fnv_bytes(mut acc: UInt64, data: Span[UInt8, _]):
    for byte in data:
        _fnv_update(acc, byte)


def _fnv_u64be(mut acc: UInt64, value: UInt64):
    for index in range(8):
        var shift = UInt64((7 - index) * 8)
        _fnv_update(acc, UInt8((value >> shift) & 0xFF))


def _fnv_u32be(mut acc: UInt64, value: UInt32):
    for index in range(4):
        var shift = UInt32((3 - index) * 8)
        _fnv_update(acc, UInt8((UInt32(value) >> shift) & 0xFF))


def fingerprint(mut acc: UInt64, value: Value):
    """Fold a decoded value into FNV-1a; mirrors the Python driver's fold."""
    _fnv_update(acc, value.kind)
    if value.kind == VALUE_NIL:
        pass
    elif value.kind == VALUE_BOOL:
        _fnv_update(acc, UInt8(1) if value.as_bool() else UInt8(0))
    elif value.kind == VALUE_INT or value.kind == VALUE_UINT:
        _fnv_u64be(acc, value.int_bits)
    elif value.kind == VALUE_FLOAT32:
        _fnv_u32be(acc, value.as_float32_bits())
    elif value.kind == VALUE_FLOAT64:
        _fnv_u64be(acc, value.as_float64_bits())
    elif value.kind == VALUE_STR or value.kind == VALUE_BIN:
        _fnv_bytes(acc, Span(value.data))
    elif value.kind == VALUE_ARRAY or value.kind == VALUE_MAP:
        for index in range(len(value.kids)):
            fingerprint(acc, value.kids[index])
    elif value.kind == VALUE_EXT:
        _fnv_update(acc, UInt8(UInt64(value.ext_code.to_bits()) & 0xFF))
        _fnv_bytes(acc, Span(value.data))
    elif value.kind == VALUE_TIMESTAMP:
        _fnv_u64be(acc, UInt64(value.as_int64().to_bits()))
        _fnv_u32be(acc, value.nsec)


def _time_decode(
    payload: Span[UInt8, _], warmup: Int, samples: Int, mut out: List[Int]
) raises -> UInt64:
    var sink: UInt64 = 0
    for _ in range(warmup):
        var value = decode_value_exact(payload)
        sink += UInt64(len(value.kids)) ^ UInt64(value.kind)
    var acc: UInt64 = 14695981039346656037
    for _ in range(samples):
        var start = perf_counter_ns()
        var value = decode_value_exact(payload)
        sink += UInt64(len(value.kids)) ^ UInt64(value.kind)
        var elapsed = perf_counter_ns() - start
        out.append(elapsed)
        fingerprint(acc, value)
    if sink == 0xFFFFFFFFFFFFFFFF:
        print("unreachable")
    return acc


def _time_encode(
    value: Value, warmup: Int, samples: Int, mut out: List[Int]
) raises -> UInt64:
    var sink: UInt64 = 0
    for _ in range(warmup):
        var encoded = List[UInt8]()
        encode_value(encoded, value)
        sink += UInt64(len(encoded))
    var acc: UInt64 = 14695981039346656037
    for _ in range(samples):
        var encoded = List[UInt8]()
        var start = perf_counter_ns()
        encode_value(encoded, value)
        sink += UInt64(len(encoded))
        var elapsed = perf_counter_ns() - start
        out.append(elapsed)
        _fnv_bytes(acc, Span(encoded))
    if sink == 0xFFFFFFFFFFFFFFFF:
        print("unreachable")
    return acc


def _print_json(op: String, samples: List[Int], checksum: UInt64, extra: String):
    var line = String('{"op":"') + op + '","samples_ns":['
    for index in range(len(samples)):
        if index > 0:
            line += ","
        line += String(samples[index])
    line += '],"checksum":' + String(checksum) + extra + "}"
    print(line)


def main() raises:
    var args = argv()
    if len(args) != 4:
        raise Error("usage: bench_msgpack <encode|decode> <warmup> <samples>")
    var op = String(args[1])
    var warmup = Int(args[2])
    var sample_count = Int(args[3])
    if warmup < 0 or sample_count < 1:
        raise Error("warmup must be >= 0 and samples must be >= 1")

    var stdin = RawFileDescriptor(0)
    var payload = List[UInt8]()
    if not read_frame(stdin, payload):
        raise Error("no payload frame on stdin")
    var view = Span(payload)

    var samples = List[Int]()
    if op == "decode":
        var hash = _time_decode(view, warmup, sample_count, samples)
        var fp_value = decode_value_exact(view)
        var fp: UInt64 = 14695981039346656037
        fingerprint(fp, fp_value)
        _print_json(
            op,
            samples,
            hash,
            ',"payload_bytes":'
            + String(len(view))
            + ',"fingerprint":'
            + String(fp),
        )
    elif op == "encode":
        var value = decode_value_exact(view)
        var hash = _time_encode(value, warmup, sample_count, samples)
        var probe = List[UInt8]()
        encode_value(probe, value)
        var verify: UInt64 = 14695981039346656037
        _fnv_bytes(verify, Span(probe))
        var fp: UInt64 = 14695981039346656037
        fingerprint(fp, value)
        _print_json(
            op,
            samples,
            hash,
            ',"payload_bytes":'
            + String(len(view))
            + ',"verify_checksum":'
            + String(verify)
            + ',"fingerprint":'
            + String(fp),
        )
    else:
        raise Error("op must be encode or decode")
