"""Signed sample representation for the native audioop port (Phase 1).

Fragments are raw native-endian bytes, exactly as the CPython 3.12
reference reads them: width 1/2/3/4 bytes per sample, signed two's
complement. This module owns width and length validation, single-sample
decode/encode, and whole-fragment decode/encode. It implements no
public audioop operation.

Native byte order is detected at runtime with
``bitcast[DType.uint8, 2]`` on ``UInt16(1)`` — no pointers, no
assumption about the host. The reference reads samples through the same
native word order, so no explicit endianness argument is exposed.

Sentinel behaviour is intentional: an empty fragment is valid (zero
samples) and is never treated as malformed. Width is validated before
fragment length, matching the reference's ``audioop_check_size`` then
``audioop_check_parameters`` order.
"""

from std.collections import List
from std.memory import bitcast


comptime MIN_WIDTH: Int = 1
comptime MAX_WIDTH: Int = 4


def native_is_little_endian() -> Bool:
    """True when the host stores the low byte of a word first."""
    var one: UInt16 = 1
    var bytes = bitcast[DType.uint8, 2](one)
    return bytes[0] == UInt8(1)


def validate_width(width: Int) raises:
    """Reject widths other than 1, 2, 3 or 4 (reference message)."""
    if width < MIN_WIDTH or width > MAX_WIDTH:
        raise Error("Size should be 1, 2, 3 or 4")


def validate_fragment(fragment: Span[UInt8, _], width: Int) raises:
    """Validate width first, then require whole samples (reference order)."""
    validate_width(width)
    if len(fragment) % width != 0:
        raise Error("not a whole number of frames")


def sample_min(width: Int) raises -> Int32:
    """Smallest signed value representable at ``width``."""
    validate_width(width)
    if width == 1:
        return Int32(-128)
    if width == 2:
        return Int32(-32768)
    if width == 3:
        return Int32(-8388608)
    return Int32(-2147483648)


def sample_max(width: Int) raises -> Int32:
    """Largest signed value representable at ``width``."""
    validate_width(width)
    if width == 1:
        return Int32(127)
    if width == 2:
        return Int32(32767)
    if width == 3:
        return Int32(8388607)
    return Int32(2147483647)


def in_sample_range(width: Int, value: Int64) raises -> Bool:
    """Whether ``value`` fits the signed range of ``width``."""
    return value >= Int64(sample_min(width)) and value <= Int64(sample_max(width))


def validate_value(width: Int, value: Int64) raises:
    """Reject values outside the signed range instead of truncating."""
    if not in_sample_range(width, value):
        raise Error(
            "sample value "
            + String(value)
            + " out of range for width "
            + String(width)
        )


def _load_sample(
    fragment: Span[UInt8, _], width: Int, byte_offset: Int, little: Bool
) -> Int32:
    """Decode one native-order sample at ``byte_offset`` (already validated)."""
    var raw: UInt32 = 0
    for i in range(width):
        var at = byte_offset + (i if little else width - 1 - i)
        raw |= UInt32(fragment[at]) << UInt32(i * 8)
    var bits = width * 8
    if (raw & (UInt32(1) << UInt32(bits - 1))) != 0:
        return Int32(Int64(raw) - (Int64(1) << Int64(bits)))
    return Int32(raw)


def _store_sample(
    mut out: List[UInt8], offset: Int, width: Int, value: Int64, little: Bool
):
    """Write one native-order sample at ``offset`` (range already validated)."""
    var mask = (UInt64(1) << UInt64(width * 8)) - 1
    var raw = UInt64(value) & mask
    for i in range(width):
        var at = offset + (i if little else width - 1 - i)
        out[at] = UInt8((raw >> UInt64(i * 8)) & 0xFF)


def decode_sample(fragment: Span[UInt8, _], width: Int, index: Int) raises -> Int32:
    """Decode sample ``index`` from a validated-width fragment.

    Raises the reference message ``Index out of range`` when ``index`` is
    outside ``0 .. sample_count - 1``.
    """
    validate_fragment(fragment, width)
    var count = len(fragment) // width
    if index < 0 or index >= count:
        raise Error("Index out of range")
    return _load_sample(fragment, width, index * width, native_is_little_endian())


def decode_fragment(fragment: Span[UInt8, _], width: Int) raises -> List[Int32]:
    """Decode every sample of a fragment; an empty fragment yields ``[]``."""
    validate_fragment(fragment, width)
    var count = len(fragment) // width
    var little = native_is_little_endian()
    var samples = List[Int32](capacity=count)
    for index in range(count):
        samples.append(_load_sample(fragment, width, index * width, little))
    return samples^


def encode_sample(width: Int, value: Int64) raises -> List[UInt8]:
    """Encode one value as ``width`` native-order bytes.

    Out-of-range values raise; they are never truncated or wrapped.
    """
    validate_width(width)
    validate_value(width, value)
    var out = List[UInt8](capacity=width)
    out.resize(width, 0)
    _store_sample(out, 0, width, value, native_is_little_endian())
    return out^


def encode_fragment(samples: Span[Int64, _], width: Int) raises -> List[UInt8]:
    """Encode signed samples into one native-order fragment.

    Every value is validated before any output is produced, so a failure
    never returns a partially encoded fragment.
    """
    validate_width(width)
    for value in samples:
        validate_value(width, value)
    var out = List[UInt8](capacity=len(samples) * width)
    out.resize(len(samples) * width, 0)
    var little = native_is_little_endian()
    for index in range(len(samples)):
        _store_sample(out, index * width, width, samples[index], little)
    return out^


def sample_count(fragment: Span[UInt8, _], width: Int) raises -> Int:
    """Number of whole samples in a fragment after validation."""
    validate_fragment(fragment, width)
    return len(fragment) // width
