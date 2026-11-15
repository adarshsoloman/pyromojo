"""Phase 2 arithmetic and fragment operations.

All six operations reuse the Phase 1 sample representation layer. Numeric
behaviour matches CPython 3.12.3's ``audioop``: ``add`` clamps, ``bias``
wraps, ``mul`` clamps then floors, ``reverse`` reverses sample order,
``byteswap`` reverses bytes inside each sample, and ``lin2lin`` widens by
left shift or narrows by arithmetic right shift.
"""

from std.collections import List
from std.math import floor

from mojo_audioop.samples import (
    decode_fragment,
    encode_fragment,
    sample_max,
    sample_min,
    validate_fragment,
    validate_width,
)


def _fbound(value: Float64, minimum: Float64, maximum: Float64) -> Int64:
    """Reference ``fbound``: clamp, floor, convert toward zero.

    The reference leaves NaN results undefined (``(int)NaN``). The port
    defines NaN results as zero so behaviour is deterministic on every
    host; this is a documented deviation from undefined behaviour.
    """
    if value != value:
        return 0
    var clamped = value
    if value > maximum:
        clamped = maximum
    elif value < minimum + 1.0:
        clamped = minimum
    return Int64(floor(clamped))


def add(
    fragment1: Span[UInt8, _], fragment2: Span[UInt8, _], width: Int
) raises -> List[UInt8]:
    """Per-sample addition with saturation; never wraps."""
    validate_fragment(fragment1, width)
    if len(fragment1) != len(fragment2):
        raise Error("Lengths should be the same")
    var left = decode_fragment(fragment1, width)
    var right = decode_fragment(fragment2, width)
    var minimum = Int64(sample_min(width))
    var maximum = Int64(sample_max(width))
    var out = List[Int64](capacity=len(left))
    for index in range(len(left)):
        var value = Int64(left[index]) + Int64(right[index])
        if value > maximum:
            value = maximum
        elif value < minimum:
            value = minimum
        out.append(value)
    return encode_fragment(Span(out), width)


def bias(fragment: Span[UInt8, _], width: Int, offset: Int64) raises -> List[UInt8]:
    """Per-sample bias with unsigned wrap-around, matching ``masks[width]``."""
    if offset < -2147483648 or offset > 2147483647:
        raise Error("Python int too large to convert to C int")
    validate_fragment(fragment, width)
    var mask: UInt32 = 0xFFFFFFFF
    if width < 4:
        mask = (UInt32(1) << UInt32(width * 8)) - 1
    var bits = width * 8
    var samples = decode_fragment(fragment, width)
    var out = List[Int64](capacity=len(samples))
    for index in range(len(samples)):
        var raw = (UInt32(samples[index]) + UInt32(Int32(offset))) & mask
        var value: Int64
        if (raw & (UInt32(1) << UInt32(bits - 1))) != 0:
            value = Int64(raw) - (Int64(1) << Int64(bits))
        else:
            value = Int64(raw)
        out.append(value)
    return encode_fragment(Span(out), width)


def mul(fragment: Span[UInt8, _], width: Int, factor: Float64) raises -> List[UInt8]:
    """Multiply samples by a floating-point factor: clamp, then floor."""
    validate_fragment(fragment, width)
    var samples = decode_fragment(fragment, width)
    var minimum = Float64(Int(sample_min(width)))
    var maximum = Float64(Int(sample_max(width)))
    var out = List[Int64](capacity=len(samples))
    for index in range(len(samples)):
        out.append(_fbound(Float64(samples[index]) * factor, minimum, maximum))
    return encode_fragment(Span(out), width)


def reverse(fragment: Span[UInt8, _], width: Int) raises -> List[UInt8]:
    """Reverse sample order; each sample's internal byte order is unchanged."""
    validate_fragment(fragment, width)
    var count = len(fragment) // width
    var out = List[UInt8](capacity=len(fragment))
    out.resize(len(fragment), 0)
    for index in range(count):
        var source = index * width
        var destination = (count - 1 - index) * width
        for byte in range(width):
            out[destination + byte] = fragment[source + byte]
    return out^


def byteswap(fragment: Span[UInt8, _], width: Int) raises -> List[UInt8]:
    """Reverse the bytes inside each sample; sample order is unchanged."""
    validate_fragment(fragment, width)
    var out = List[UInt8](capacity=len(fragment))
    out.resize(len(fragment), 0)
    var count = len(fragment) // width
    for index in range(count):
        var base = index * width
        for byte in range(width):
            out[base + width - 1 - byte] = fragment[base + byte]
    return out^


def lin2lin(
    fragment: Span[UInt8, _], width: Int, new_width: Int
) raises -> List[UInt8]:
    """Widen by left shift; narrow by arithmetic shift (floor toward -inf)."""
    validate_fragment(fragment, width)
    validate_width(new_width)
    var samples = decode_fragment(fragment, width)
    var shift = (new_width - width) * 8
    var out = List[Int64](capacity=len(samples))
    for index in range(len(samples)):
        if shift > 0:
            out.append(Int64(samples[index]) << Int64(shift))
        elif shift < 0:
            out.append(Int64(samples[index]) >> Int64(-shift))
        else:
            out.append(Int64(samples[index]))
    return encode_fragment(Span(out), new_width)
