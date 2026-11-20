"""Native in-process benchmark for the Resampy kernel.

Usage: bench_resampy <metadata_path> <resource_path> <warmup> <samples>

Reads one framed payload from stdin:

    u32be sr_orig | u32be sr_new | u32be input_count | f64le input

The production ``kaiser_fast`` resource is loaded and validated before any
timing. Each timed iteration calls the public native ``resample`` entry point.
Filter loading, stdin framing, signal construction, and the output hash are
outside the timed region. Emits one JSON object on stdout with raw nanosecond
samples, output length, and the SHA-256 of the little-endian Float64 output.
"""

from std.collections import List
from std.io import RawFileDescriptor
from std.sys import argv
from std.time import perf_counter_ns

from mojo_resampy.coefficients import load_filter
from mojo_resampy.float_codec import decode_f64le, encode_f64le
from mojo_resampy.protocol import decode_u32_be, read_frame
from mojo_resampy.resample import resample
from mojo_resampy.sha256 import sha256_hex
from mojo_resampy.signal import Signal


def _parse_body(payload: Span[UInt8, _]) raises -> Tuple[Int, Int, Int]:
    if len(payload) < 12:
        raise Error("bench payload too short")
    var sr_orig = Int(decode_u32_be(payload[0:4]))
    var sr_new = Int(decode_u32_be(payload[4:8]))
    var count = Int(decode_u32_be(payload[8:12]))
    if len(payload) != 12 + count * 8:
        raise Error("bench payload length does not match input_count")
    return (sr_orig, sr_new, count)


def main() raises:
    var args = argv()
    if len(args) != 5:
        raise Error("usage: bench_resampy <metadata_path> <resource_path> <warmup> <samples>")
    var warmup = Int(args[3])
    var sample_count = Int(args[4])
    if warmup < 1 or sample_count < 1:
        raise Error("warmup and samples must be >= 1")

    var filter = load_filter(String(args[1]), String(args[2]))
    var stdin = RawFileDescriptor(0)
    var payload = List[UInt8]()
    if not read_frame(stdin, payload):
        raise Error("missing benchmark payload frame")
    var parsed = _parse_body(Span(payload))
    var sr_orig = parsed[0]
    var sr_new = parsed[1]
    var count = parsed[2]
    var values = decode_f64le(Span(payload)[12:])
    if len(values) != count:
        raise Error("decoded input count mismatch")
    var signal = Signal(values^)

    var last = resample(signal, sr_orig, sr_new, filter)
    for _ in range(warmup - 1):
        last = resample(signal, sr_orig, sr_new, filter)

    var samples = List[Int](capacity=sample_count)
    for _ in range(sample_count):
        var start = Int(perf_counter_ns())
        last = resample(signal, sr_orig, sr_new, filter)
        samples.append(Int(perf_counter_ns()) - start)

    var raw = encode_f64le(last.view())
    var digest = sha256_hex(Span(raw))
    var line = String('{"samples_ns":[')
    for i in range(len(samples)):
        if i > 0:
            line += String(",")
        line += String(samples[i])
    line += String('],"output_count":') + String(len(last))
    line += String(',"output_sha256":"') + digest + String('"}')
    print(line)
