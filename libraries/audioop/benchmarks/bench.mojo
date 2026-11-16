"""Native in-process benchmark kernel for the audioop operations.

Reads workload lines from stdin, produces each result once (for the
driver's three-way correctness gate), then times each workload
in-process with ``perf_counter_ns`` (5 warmup + 25 measured samples)
and emits the raw timing samples. No process, framing, or IPC cost is
included in these numbers.

Line protocol (fields separated by ``|``; the workload driver in
``run_benchmarks.py`` is the reference client):

    ADD|width|frag_hex                 (the fragment is added to itself)
    MUL|width|factor_hex16|frag_hex    (factor: 16 hex chars, big-endian IEEE bits)
    BIAS|width|frag_hex
    BYTESWAP|width|frag_hex
    REVERSE|width|frag_hex
    LIN2LIN|width|newwidth|frag_hex
    GETSAMPLE|width|index|frag_hex
    MAX|width|frag_hex   MINMAX|width|frag_hex   AVG|width|frag_hex
    RMS|width|frag_hex   CROSS|width|frag_hex
    AVGPP|width|frag_hex MAXPP|width|frag_hex
    TOMONO|width|lfactor_hex16|rfactor_hex16|frag_hex
    TOSTEREO|width|lfactor_hex16|rfactor_hex16|frag_hex
    LIN2ALAW|width|frag_hex   LIN2ULAW|width|frag_hex
    ALAW2LIN|width|frag_hex   ULAW2LIN|width|frag_hex
    FINDFACTOR|ref_hex|frag_hex    FINDFIT|ref_hex|frag_hex
    FINDMAX|length|frag_hex
    LIN2ADPCM|width|valpred|index|frag_hex
    ADPCM2LIN|width|valpred|index|frag_hex
    RATECV|width|nch|inrate|outrate|wA|wB|d|prev0|cur0|...|frag_hex

A ``valpred``/``d`` of 2147483648 selects a fresh state (reference
``state=None``).

Output per workload: ``R <hex>`` (stateful: ``R <hex>|<state fields>``
with fields comma-separated) followed, after every gate result, by
``T <count> <ns>...`` lines with the raw in-process samples.
"""

from std.collections import List
from std.io import RawFileDescriptor
from std.memory import bitcast
from std.time import perf_counter_ns

from mojo_audioop import (
    AdpcmState,
    RatecvResult,
    RatecvState,
    add,
    adpcm2lin,
    alaw2lin,
    avg,
    avgpp,
    bias,
    byteswap,
    cross,
    findfactor,
    findfit,
    findmax,
    getsample,
    lin2adpcm,
    lin2alaw,
    lin2lin,
    lin2ulaw,
    max,
    maxpp,
    minmax,
    mul,
    ratecv,
    ratecv_continue,
    reverse,
    rms,
    tomono,
    tostereo,
    ulaw2lin,
)


comptime FRESH: Int64 = 2147483648


def read_all(mut fd: RawFileDescriptor) raises -> List[UInt8]:
    var data = List[UInt8]()
    var chunk = List[UInt8](capacity=65536)
    chunk.resize(65536, 0)
    while True:
        var view = Span(chunk)
        var count = fd.read_bytes(view)
        if count == 0:
            break
        for i in range(count):
            data.append(chunk[i])
    return data^


def hex_value(byte: UInt8) raises -> Int:
    if byte >= UInt8(48) and byte <= UInt8(57):
        return Int(byte) - 48
    if byte >= UInt8(97) and byte <= UInt8(102):
        return Int(byte) - 87
    return Int(byte) - 55


def hex_to_bytes(text: String) raises -> List[UInt8]:
    var out = List[UInt8](capacity=text.byte_length() // 2)
    var raw = text.as_bytes()
    var i = 0
    while i + 1 < len(raw):
        out.append(UInt8(hex_value(raw[i]) * 16 + hex_value(raw[i + 1])))
        i += 2
    return out^


def parse_i64(text: String) raises -> Int64:
    var negative = False
    var start = 0
    if text.byte_length() > 0 and text.as_bytes()[0] == UInt8(45):
        negative = True
        start = 1
    var value: Int64 = 0
    var raw = text.as_bytes()
    for i in range(start, len(raw)):
        value = value * 10 + Int64(raw[i]) - 48
    if negative:
        value = -value
    return value


def parse_double(text: String) raises -> Float64:
    """16 hex chars: big-endian IEEE-754 double bits (bit-exact factors)."""
    var bits: UInt64 = 0
    var raw = text.as_bytes()
    for i in range(16):
        bits = (bits << 4) | UInt64(hex_value(raw[i]))
    return bitcast[DType.float64, 1](bits)


def bytes_to_hex(data: List[UInt8]) raises -> String:
    var digits = List[UInt8](capacity=16)
    for i in range(16):
        if i < 10:
            digits.append(UInt8(48 + i))
        else:
            digits.append(UInt8(87 + i))
    var chars = List[UInt8](capacity=2 * len(data))
    for b in data:
        chars.append(digits[Int(b) >> 4])
        chars.append(digits[Int(b) & 15])
    return String(from_utf8=Span(chars))


def u64_hex(bits: UInt64) raises -> String:
    var bytes = List[UInt8](capacity=8)
    for shift in range(56, -8, -8):
        bytes.append(UInt8((bits >> UInt64(shift)) & 0xFF))
    return bytes_to_hex(bytes^)


def format_i64(value: Int64) raises -> String:
    if value == 0:
        return String("0")
    var negative = value < 0
    var v = value if not negative else -value
    var reversed_digits = List[UInt8]()
    while v > 0:
        reversed_digits.append(UInt8(48 + v % 10))
        v = v // 10
    var chars = List[UInt8]()
    if negative:
        chars.append(UInt8(45))
    for i in range(len(reversed_digits)):
        chars.append(reversed_digits[len(reversed_digits) - 1 - i])
    return String(from_utf8=Span(chars))


def split_fields(line: String) raises -> List[String]:
    var fields = List[String]()
    var raw = line.as_bytes()
    var start = 0
    for i in range(len(raw)):
        if raw[i] == UInt8(124):
            var span = Span(raw)[start:i]
            fields.append(String(from_utf8=span))
            start = i + 1
    var tail = Span(raw)[start:len(raw)]
    fields.append(String(from_utf8=tail))
    return fields^


def adpcm_state_of(valpred: Int64, index: Int64) raises -> AdpcmState:
    if valpred == FRESH:
        return AdpcmState(0, 0)
    return AdpcmState(valpred, index)


def _mix_bytes(data: List[UInt8]) -> Int64:
    """One data-dependent word per output; keeps the timed call live."""
    var acc: UInt64 = 0
    for i in range(len(data)):
        acc = acc * UInt64(31) + UInt64(data[i])
    return Int64(acc & 0xFFFFFFFF)


def _run_ratecv_gate(
    frag: Span[UInt8, _], width: Int, nchannels: Int64, inrate: Int64,
    outrate: Int64, weight_a: Int64, weight_b: Int64, d: Int64,
    var prev: List[Int64],
    var cur: List[Int64],
) raises -> RatecvResult:
    if d == FRESH:
        return ratecv(frag, width, nchannels, inrate, outrate, weight_a, weight_b)
    var state = RatecvState(d, prev^, cur^)
    return ratecv_continue(
        frag, width, nchannels, inrate, outrate, state^, weight_a, weight_b,
    )


def main() raises:
    var stdin = RawFileDescriptor(0)
    var data = read_all(stdin)
    var lines = List[String]()
    var start = 0
    var view = Span(data)
    for i in range(len(data)):
        if data[i] == UInt8(10):
            if i > start:
                lines.append(String(from_utf8=view[start:i]))
            start = i + 1
    if len(data) > start:
        lines.append(String(from_utf8=view[start:len(data)]))

    var count = Int(parse_i64(lines[0]))

    # ---- gate pass: one untimed call per workload, result printed ----
    for w in range(count):
        var fields = split_fields(lines[1 + w])
        var op = fields[0]
        var width = Int(parse_i64(fields[1]))
        var result_hex = String("")
        var state_text = String("")

        if op == String("ADD"):
            var frag = hex_to_bytes(fields[2])
            var copy = List[UInt8](capacity=len(frag))
            for b in frag:
                copy.append(b)
            result_hex = bytes_to_hex(add(Span(frag), Span(copy), width))
        elif op == String("MUL"):
            var factor = parse_double(fields[2])
            var frag = hex_to_bytes(fields[3])
            result_hex = bytes_to_hex(mul(Span(frag), width, factor))
        elif op == String("BIAS"):
            var frag = hex_to_bytes(fields[2])
            result_hex = bytes_to_hex(bias(Span(frag), width, 37))
        elif op == String("BYTESWAP"):
            var frag = hex_to_bytes(fields[2])
            result_hex = bytes_to_hex(byteswap(Span(frag), width))
        elif op == String("REVERSE"):
            var frag = hex_to_bytes(fields[2])
            result_hex = bytes_to_hex(reverse(Span(frag), width))
        elif op == String("LIN2LIN"):
            var new_width = Int(parse_i64(fields[2]))
            var frag = hex_to_bytes(fields[3])
            result_hex = bytes_to_hex(lin2lin(Span(frag), width, new_width))
        elif op == String("GETSAMPLE"):
            var index = parse_i64(fields[2])
            var frag = hex_to_bytes(fields[3])
            result_hex = format_i64(Int64(getsample(Span(frag), width, index)))
        elif op == String("MAX"):
            var frag = hex_to_bytes(fields[2])
            result_hex = format_i64(max(Span(frag), width))
        elif op == String("MINMAX"):
            var frag = hex_to_bytes(fields[2])
            var pair = minmax(Span(frag), width)
            result_hex = (
                format_i64(Int64(pair[0])) + String(",") + format_i64(Int64(pair[1]))
            )
        elif op == String("AVG"):
            var frag = hex_to_bytes(fields[2])
            result_hex = format_i64(avg(Span(frag), width))
        elif op == String("RMS"):
            var frag = hex_to_bytes(fields[2])
            result_hex = format_i64(rms(Span(frag), width))
        elif op == String("CROSS"):
            var frag = hex_to_bytes(fields[2])
            result_hex = format_i64(cross(Span(frag), width))
        elif op == String("AVGPP"):
            var frag = hex_to_bytes(fields[2])
            result_hex = format_i64(avgpp(Span(frag), width))
        elif op == String("MAXPP"):
            var frag = hex_to_bytes(fields[2])
            result_hex = format_i64(maxpp(Span(frag), width))
        elif op == String("TOMONO"):
            var left = parse_double(fields[2])
            var right = parse_double(fields[3])
            var frag = hex_to_bytes(fields[4])
            result_hex = bytes_to_hex(tomono(Span(frag), width, left, right))
        elif op == String("TOSTEREO"):
            var left = parse_double(fields[2])
            var right = parse_double(fields[3])
            var frag = hex_to_bytes(fields[4])
            result_hex = bytes_to_hex(tostereo(Span(frag), width, left, right))
        elif op == String("LIN2ALAW"):
            var frag = hex_to_bytes(fields[2])
            result_hex = bytes_to_hex(lin2alaw(Span(frag), width))
        elif op == String("LIN2ULAW"):
            var frag = hex_to_bytes(fields[2])
            result_hex = bytes_to_hex(lin2ulaw(Span(frag), width))
        elif op == String("ALAW2LIN"):
            var frag = hex_to_bytes(fields[2])
            result_hex = bytes_to_hex(alaw2lin(Span(frag), width))
        elif op == String("ULAW2LIN"):
            var frag = hex_to_bytes(fields[2])
            result_hex = bytes_to_hex(ulaw2lin(Span(frag), width))
        elif op == String("FINDFACTOR"):
            var reference = hex_to_bytes(fields[1])
            var frag = hex_to_bytes(fields[2])
            var factor = findfactor(Span(frag), Span(reference))
            result_hex = u64_hex(bitcast[DType.uint64, 1](factor))
        elif op == String("FINDFIT"):
            var reference = hex_to_bytes(fields[1])
            var frag = hex_to_bytes(fields[2])
            var fit = findfit(Span(frag), Span(reference))
            result_hex = (
                format_i64(Int64(fit.index)) + String(",")
                + u64_hex(bitcast[DType.uint64, 1](fit.factor))
            )
        elif op == String("FINDMAX"):
            var length = parse_i64(fields[1])
            var frag = hex_to_bytes(fields[2])
            result_hex = format_i64(Int64(findmax(Span(frag), length)))
        elif op == String("LIN2ADPCM"):
            var frag = hex_to_bytes(fields[4])
            var result = lin2adpcm(
                Span(frag), width,
                adpcm_state_of(parse_i64(fields[2]), parse_i64(fields[3])),
            )
            result_hex = bytes_to_hex(result.output)
            state_text = (
                format_i64(result.state.valpred) + String(",")
                + format_i64(result.state.index)
            )
        elif op == String("ADPCM2LIN"):
            var frag = hex_to_bytes(fields[4])
            var result = adpcm2lin(
                Span(frag), width,
                adpcm_state_of(parse_i64(fields[2]), parse_i64(fields[3])),
            )
            result_hex = bytes_to_hex(result.output)
            state_text = (
                format_i64(result.state.valpred) + String(",")
                + format_i64(result.state.index)
            )
        elif op == String("RATECV"):
            var nchannels = Int(parse_i64(fields[2]))
            var inrate = parse_i64(fields[3])
            var outrate = parse_i64(fields[4])
            var weight_a = parse_i64(fields[5])
            var weight_b = parse_i64(fields[6])
            var d = parse_i64(fields[7])
            var prev = List[Int64](capacity=nchannels)
            var cur = List[Int64](capacity=nchannels)
            var frag_offset = 8
            if d != FRESH:
                for c in range(nchannels):
                    prev.append(parse_i64(fields[8 + c * 2]))
                    cur.append(parse_i64(fields[9 + c * 2]))
                frag_offset = 8 + 2 * nchannels
            var frag = hex_to_bytes(fields[frag_offset])
            var result = _run_ratecv_gate(
                Span(frag), width, Int64(nchannels), inrate, outrate,
                weight_a, weight_b, d, prev^, cur^,
            )
            result_hex = bytes_to_hex(result.output)
            state_text = format_i64(result.state.d)
            for c in range(nchannels):
                state_text += String(",") + format_i64(result.state.prev_i[c])
                state_text += String(",") + format_i64(result.state.cur_i[c])
        else:
            raise Error("bench: unknown op " + op)

        if state_text.byte_length() > 0:
            print("R " + result_hex + String("|") + state_text, flush=True)
        else:
            print("R " + result_hex, flush=True)

    # ---- timed pass: prebuilt inputs; 5 warmup + 25 measured ----
    for w in range(count):
        var fields = split_fields(lines[1 + w])
        var op = fields[0]
        var width = Int(parse_i64(fields[1]))
        var samples = List[Int64](capacity=25)
        # prebuilt holders (parsed once, outside the timed region)
        var frag = List[UInt8]()
        var frag2 = List[UInt8]()
        var int_a: Int64 = 0
        var int_b: Int64 = 0
        var int_c: Int64 = 0
        var int_d: Int64 = 0
        var int_e: Int64 = 0
        var int_f: Int64 = 0
        var dbl_a: Float64 = 0.0
        var dbl_b: Float64 = 0.0
        if op == String("ADD"):
            frag = hex_to_bytes(fields[2])
            for b in frag:
                frag2.append(b)
        elif op == String("MUL"):
            dbl_a = parse_double(fields[2])
            frag = hex_to_bytes(fields[3])
        elif op == String("BIAS") or op == String("BYTESWAP") or op == String("REVERSE") \
                or op == String("MAX") or op == String("MINMAX") or op == String("AVG") \
                or op == String("RMS") or op == String("CROSS") or op == String("AVGPP") \
                or op == String("MAXPP") or op == String("LIN2ALAW") \
                or op == String("LIN2ULAW") or op == String("ALAW2LIN") \
                or op == String("ULAW2LIN"):
            frag = hex_to_bytes(fields[2])
        elif op == String("LIN2LIN"):
            int_a = parse_i64(fields[2])
            frag = hex_to_bytes(fields[3])
        elif op == String("GETSAMPLE"):
            int_a = parse_i64(fields[2])
            frag = hex_to_bytes(fields[3])
        elif op == String("TOMONO") or op == String("TOSTEREO"):
            dbl_a = parse_double(fields[2])
            dbl_b = parse_double(fields[3])
            frag = hex_to_bytes(fields[4])
        elif op == String("FINDFACTOR") or op == String("FINDFIT"):
            frag2 = hex_to_bytes(fields[1])
            frag = hex_to_bytes(fields[2])
        elif op == String("FINDMAX"):
            int_a = parse_i64(fields[1])
            frag = hex_to_bytes(fields[2])
        elif op == String("LIN2ADPCM") or op == String("ADPCM2LIN"):
            int_a = parse_i64(fields[2])
            int_b = parse_i64(fields[3])
            frag = hex_to_bytes(fields[4])
        elif op == String("RATECV"):
            int_a = parse_i64(fields[2])  # nchannels
            int_b = parse_i64(fields[3])  # inrate
            int_c = parse_i64(fields[4])  # outrate
            int_d = parse_i64(fields[5])  # weightA
            int_e = parse_i64(fields[6])  # weightB
            int_f = parse_i64(fields[7])  # d (FRESH or state)
            var nchannels = Int(int_a)
            var prev = List[Int64](capacity=nchannels)
            var cur = List[Int64](capacity=nchannels)
            var frag_offset = 8
            if int_f != FRESH:
                for c in range(nchannels):
                    prev.append(parse_i64(fields[8 + c * 2]))
                    cur.append(parse_i64(fields[9 + c * 2]))
                frag_offset = 8 + 2 * nchannels
            frag = hex_to_bytes(fields[frag_offset])

        for _ in range(5):
            if op == String("ADD"):
                _ = add(Span(frag), Span(frag2), width)
            elif op == String("MUL"):
                _ = mul(Span(frag), width, dbl_a)
            elif op == String("BIAS"):
                _ = bias(Span(frag), width, 37)
            elif op == String("BYTESWAP"):
                _ = byteswap(Span(frag), width)
            elif op == String("REVERSE"):
                _ = reverse(Span(frag), width)
            elif op == String("LIN2LIN"):
                _ = lin2lin(Span(frag), width, Int(int_a))
            elif op == String("GETSAMPLE"):
                _ = getsample(Span(frag), width, int_a)
            elif op == String("MAX"):
                _ = max(Span(frag), width)
            elif op == String("MINMAX"):
                _ = minmax(Span(frag), width)
            elif op == String("AVG"):
                _ = avg(Span(frag), width)
            elif op == String("RMS"):
                _ = rms(Span(frag), width)
            elif op == String("CROSS"):
                _ = cross(Span(frag), width)
            elif op == String("AVGPP"):
                _ = avgpp(Span(frag), width)
            elif op == String("MAXPP"):
                _ = maxpp(Span(frag), width)
            elif op == String("TOMONO"):
                _ = tomono(Span(frag), width, dbl_a, dbl_b)
            elif op == String("TOSTEREO"):
                _ = tostereo(Span(frag), width, dbl_a, dbl_b)
            elif op == String("LIN2ALAW"):
                _ = lin2alaw(Span(frag), width)
            elif op == String("LIN2ULAW"):
                _ = lin2ulaw(Span(frag), width)
            elif op == String("ALAW2LIN"):
                _ = alaw2lin(Span(frag), width)
            elif op == String("ULAW2LIN"):
                _ = ulaw2lin(Span(frag), width)
            elif op == String("FINDFACTOR"):
                _ = findfactor(Span(frag), Span(frag2))
            elif op == String("FINDFIT"):
                _ = findfit(Span(frag), Span(frag2))
            elif op == String("FINDMAX"):
                _ = findmax(Span(frag), int_a)
            elif op == String("LIN2ADPCM"):
                var state = adpcm_state_of(int_a, int_b)
                var result = lin2adpcm(Span(frag), width, state^)
                _ = result
            elif op == String("ADPCM2LIN"):
                var state = adpcm_state_of(int_a, int_b)
                var result = adpcm2lin(Span(frag), width, state^)
                _ = result
            elif op == String("RATECV"):
                var nchannels = Int(int_a)
                var prev = List[Int64](capacity=nchannels)
                var cur = List[Int64](capacity=nchannels)
                var frag_offset = 8
                if int_f != FRESH:
                    for c in range(nchannels):
                        prev.append(parse_i64(fields[8 + c * 2]))
                        cur.append(parse_i64(fields[9 + c * 2]))
                    frag_offset = 8 + 2 * nchannels
                var warm_frag = hex_to_bytes(fields[frag_offset])
                if int_f == FRESH:
                    var result = ratecv(
                        Span(warm_frag), width, int_a, int_b, int_c, int_d, int_e,
                    )
                    _ = result
                else:
                    var state = RatecvState(int_f, prev^, cur^)
                    var result = ratecv_continue(
                        Span(warm_frag), width, int_a, int_b, int_c,
                        state^, int_d, int_e,
                    )
                    _ = result
        var sink: Int64 = 0
        for _ in range(25):
            var start = Int64(perf_counter_ns())
            if op == String("ADD"):
                sink = sink &+ _mix_bytes(add(Span(frag), Span(frag2), width)^)
            elif op == String("MUL"):
                sink = sink &+ _mix_bytes(mul(Span(frag), width, dbl_a)^)
            elif op == String("BIAS"):
                sink = sink &+ _mix_bytes(bias(Span(frag), width, 37)^)
            elif op == String("BYTESWAP"):
                sink = sink &+ _mix_bytes(byteswap(Span(frag), width)^)
            elif op == String("REVERSE"):
                sink = sink &+ _mix_bytes(reverse(Span(frag), width)^)
            elif op == String("LIN2LIN"):
                sink = sink &+ _mix_bytes(lin2lin(Span(frag), width, Int(int_a))^)
            elif op == String("GETSAMPLE"):
                sink = sink &+ Int64(getsample(Span(frag), width, int_a))
            elif op == String("MAX"):
                sink = sink &+ max(Span(frag), width)
            elif op == String("MINMAX"):
                var pair = minmax(Span(frag), width)
                sink = sink &+ Int64(pair[0]) &+ Int64(pair[1])
            elif op == String("AVG"):
                sink = sink &+ avg(Span(frag), width)
            elif op == String("RMS"):
                sink = sink &+ rms(Span(frag), width)
            elif op == String("CROSS"):
                sink = sink &+ cross(Span(frag), width)
            elif op == String("AVGPP"):
                sink = sink &+ avgpp(Span(frag), width)
            elif op == String("MAXPP"):
                sink = sink &+ maxpp(Span(frag), width)
            elif op == String("TOMONO"):
                sink = sink &+ _mix_bytes(tomono(Span(frag), width, dbl_a, dbl_b)^)
            elif op == String("TOSTEREO"):
                sink = sink &+ _mix_bytes(tostereo(Span(frag), width, dbl_a, dbl_b)^)
            elif op == String("LIN2ALAW"):
                sink = sink &+ _mix_bytes(lin2alaw(Span(frag), width)^)
            elif op == String("LIN2ULAW"):
                sink = sink &+ _mix_bytes(lin2ulaw(Span(frag), width)^)
            elif op == String("ALAW2LIN"):
                sink = sink &+ _mix_bytes(alaw2lin(Span(frag), width)^)
            elif op == String("ULAW2LIN"):
                sink = sink &+ _mix_bytes(ulaw2lin(Span(frag), width)^)
            elif op == String("FINDFACTOR"):
                var ff = findfactor(Span(frag), Span(frag2))
                sink = sink &+ Int64(bitcast[DType.uint64, 1](ff) & 0xFFFFFFFF)
            elif op == String("FINDFIT"):
                var ffit = findfit(Span(frag), Span(frag2))
                sink = sink &+ Int64(ffit.index)
                sink = sink &+ Int64(bitcast[DType.uint64, 1](ffit.factor) & 0xFF)
            elif op == String("FINDMAX"):
                sink = sink &+ Int64(findmax(Span(frag), int_a))
            elif op == String("LIN2ADPCM"):
                var state = adpcm_state_of(int_a, int_b)
                var result = lin2adpcm(Span(frag), width, state^)
                sink = sink &+ _mix_bytes(result.output^)
                sink = sink &+ result.state.valpred
            elif op == String("ADPCM2LIN"):
                var state = adpcm_state_of(int_a, int_b)
                var result = adpcm2lin(Span(frag), width, state^)
                sink = sink &+ _mix_bytes(result.output^)
                sink = sink &+ result.state.valpred
            elif op == String("RATECV"):
                var nchannels = Int(int_a)
                var prev = List[Int64](capacity=nchannels)
                var cur = List[Int64](capacity=nchannels)
                if int_f != FRESH:
                    for c in range(nchannels):
                        prev.append(parse_i64(fields[8 + c * 2]))
                        cur.append(parse_i64(fields[9 + c * 2]))
                if int_f == FRESH:
                    var result = ratecv(
                        Span(frag), width, int_a, int_b, int_c, int_d, int_e,
                    )
                    sink = sink &+ _mix_bytes(result.output^)
                else:
                    var state = RatecvState(int_f, prev^, cur^)
                    var result = ratecv_continue(
                        Span(frag), width, int_a, int_b, int_c,
                        state^, int_d, int_e,
                    )
                    sink = sink &+ _mix_bytes(result.output^)
            samples.append(Int64(perf_counter_ns()) - start)
        var line = String("T ") + format_i64(Int64(len(samples)))
        for s in samples:
            line += String(" ") + format_i64(s)
        print(line, flush=True)
        print(String("S ") + format_i64(sink), flush=True)
