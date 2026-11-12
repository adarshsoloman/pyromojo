"""Native in-process benchmark for the Levenshtein operations.

Usage: bench_levenshtein <op> <warmup> <samples> < stdin-frame

The stdin frame is ``u32be n1 | s1 bytes | u32be n2 | s2 bytes`` (raw
UTF-8, same framing as the batch CLI, reused only to ferry bytes in;
framing I/O, string validation, and code-point conversion happen once
outside the timed region and are never measured).

Ops:

- ``distance_dp`` — internal two-row DP on pre-converted code points.
- ``distance_myers`` — internal blocked Myers on pre-converted code
  points, shorter input as pattern (mirrors production dispatch).
- ``distance`` — production ``levenshtein_distance`` on Strings
  (includes one O(n+m) code-point materialization per call).
- ``ratio`` — production ``levenshtein_ratio`` on Strings.
- ``hamming`` — production ``levenshtein_hamming`` on Strings, padded.

Each timed loop calls exactly one algorithm (dispatch happens once,
outside the loop) plus an O(1) use of each result to keep the work
live. Result correctness is verified by the driver against the pinned
reference outside the timed region. Results print as one JSON object
on stdout.
"""

from std.collections import List
from std.io import RawFileDescriptor
from std.memory import bitcast
from std.sys import argv
from std.time import perf_counter_ns

from mojo_levenshtein.algorithms.dynamic_programming import dp_distance
from mojo_levenshtein.algorithms.myers import myers_distance
from mojo_levenshtein.distance import levenshtein_distance
from mojo_levenshtein.hamming import levenshtein_hamming
from mojo_levenshtein.protocol import decode_u32_be, read_frame
from mojo_levenshtein.ratio import levenshtein_ratio
from mojo_levenshtein.unicode import to_codepoints


def _parse_pair(payload: Span[UInt8, _]) raises -> Tuple[String, String]:
    """Split the frame into the two input strings (once, untimed)."""
    if len(payload) < 8:
        raise Error("bench payload too short for two length prefixes")
    var n1 = Int(decode_u32_be(payload[0:4]))
    var first = payload[4:]
    if len(first) < n1 + 4:
        raise Error("bench payload truncated in first string")
    var s1 = String(from_utf8=first[0:n1])
    var second = first[n1:]
    var n2 = Int(decode_u32_be(second[0:4]))
    if len(second) != 4 + n2:
        raise Error("bench payload has trailing bytes")
    var s2 = String(from_utf8=second[4 : 4 + n2])
    return (s1, s2)


def _print_json(
    op: String,
    samples: List[Int],
    result: Int,
    result_bits: UInt64,
    cp1: Int,
    cp2: Int,
    byte1: Int,
    byte2: Int,
):
    var line = String('{"op":"') + op + '","samples_ns":['
    for index in range(len(samples)):
        if index > 0:
            line += ","
        line += String(samples[index])
    line += '],"result":' + String(result)
    line += ',"result_bits":' + String(result_bits)
    line += ',"cp_len1":' + String(cp1) + ',"cp_len2":' + String(cp2)
    line += ',"byte_len1":' + String(byte1) + ',"byte_len2":' + String(byte2)
    line += "}"
    print(line)


def _finish_int(
    op: String,
    samples: List[Int],
    result: Int,
    sink: Int,
    a: List[Int],
    b: List[Int],
    s1: String,
    s2: String,
):
    if sink == -1 and result == -2:
        print("unreachable")
    _print_json(op, samples, result, 0, len(a), len(b), s1.byte_length(), s2.byte_length())


def _run_distance_dp(
    a: List[Int], b: List[Int], s1: String, s2: String, warmup: Int, sample_count: Int
) raises:
    var samples = List[Int]()
    var result = 0
    var sink = 0
    for _ in range(warmup):
        sink += dp_distance(a, b, 1, 1, 1)
    for _ in range(sample_count):
        var start = perf_counter_ns()
        var value = dp_distance(a, b, 1, 1, 1)
        sink += value
        result = value
        samples.append(perf_counter_ns() - start)
    _finish_int("distance_dp", samples, result, sink, a, b, s1, s2)


def _run_distance_myers(
    a: List[Int], b: List[Int], s1: String, s2: String, warmup: Int, sample_count: Int
) raises:
    var samples = List[Int]()
    var result = 0
    var sink = 0
    var pattern_first = len(a) <= len(b)
    for _ in range(warmup):
        if pattern_first:
            sink += myers_distance(a, b)
        else:
            sink += myers_distance(b, a)
    for _ in range(sample_count):
        var start = perf_counter_ns()
        if pattern_first:
            result = myers_distance(a, b)
        else:
            result = myers_distance(b, a)
        sink += result
        samples.append(perf_counter_ns() - start)
    _finish_int("distance_myers", samples, result, sink, a, b, s1, s2)


def _run_distance(
    a: List[Int], b: List[Int], s1: String, s2: String, warmup: Int, sample_count: Int
) raises:
    var samples = List[Int]()
    var result = 0
    var sink = 0
    for _ in range(warmup):
        sink += levenshtein_distance(s1, s2)
    for _ in range(sample_count):
        var start = perf_counter_ns()
        var value = levenshtein_distance(s1, s2)
        sink += value
        result = value
        samples.append(perf_counter_ns() - start)
    _finish_int("distance", samples, result, sink, a, b, s1, s2)


def _run_hamming(
    a: List[Int], b: List[Int], s1: String, s2: String, warmup: Int, sample_count: Int
) raises:
    var samples = List[Int]()
    var result = 0
    var sink = 0
    for _ in range(warmup):
        sink += levenshtein_hamming(s1, s2)
    for _ in range(sample_count):
        var start = perf_counter_ns()
        var value = levenshtein_hamming(s1, s2)
        sink += value
        result = value
        samples.append(perf_counter_ns() - start)
    _finish_int("hamming", samples, result, sink, a, b, s1, s2)


def _run_ratio(
    a: List[Int], b: List[Int], s1: String, s2: String, warmup: Int, sample_count: Int
) raises:
    var samples = List[Int]()
    var bits = UInt64(0)
    var sink = UInt64(0)
    for _ in range(warmup):
        sink += _ratio_bits(s1, s2)
    for _ in range(sample_count):
        var start = perf_counter_ns()
        var value = _ratio_bits(s1, s2)
        sink += value
        bits = value
        samples.append(perf_counter_ns() - start)
    if sink == 0xFFFFFFFFFFFFFFFF and bits == 0xFFFFFFFFFFFFFFFE:
        print("unreachable")
    _print_json("ratio", samples, 0, bits, len(a), len(b), s1.byte_length(), s2.byte_length())


def _ratio_bits(s1: String, s2: String) raises -> UInt64:
    var value = levenshtein_ratio(s1, s2)
    return bitcast[DType.uint64, 1](SIMD[DType.float64, 1](value))[0]


def main() raises:
    var args = argv()
    if len(args) != 4:
        raise Error("usage: bench_levenshtein <op> <warmup> <samples>")
    var op = String(args[1])
    var warmup = Int(args[2])
    var sample_count = Int(args[3])
    if warmup < 0 or sample_count < 1:
        raise Error("warmup must be >= 0 and samples must be >= 1")

    var stdin = RawFileDescriptor(0)
    var payload = List[UInt8]()
    if not read_frame(stdin, payload):
        raise Error("no payload frame on stdin")
    var pair = _parse_pair(Span(payload))
    var s1 = pair[0]
    var s2 = pair[1]
    var a = to_codepoints(s1)
    var b = to_codepoints(s2)

    if op == "distance_dp":
        _run_distance_dp(a, b, s1, s2, warmup, sample_count)
    elif op == "distance_myers":
        _run_distance_myers(a, b, s1, s2, warmup, sample_count)
    elif op == "distance":
        _run_distance(a, b, s1, s2, warmup, sample_count)
    elif op == "ratio":
        _run_ratio(a, b, s1, s2, warmup, sample_count)
    elif op == "hamming":
        _run_hamming(a, b, s1, s2, warmup, sample_count)
    else:
        raise Error("op must be distance_dp, distance_myers, distance, ratio, or hamming")
