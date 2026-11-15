"""Phase 3 sample statistics operations.

Six public audioop statistics functions on the Phase 1 sample layer.
Semantics match CPython 3.12.3 ``Modules/audioop.c``:

- ``getsample`` returns one sample; any index outside ``0 .. count-1``
  raises ``Index out of range`` (negative indices are not Python-style).
- ``max`` returns the maximum absolute magnitude computed in unsigned
  arithmetic, so ``abs(-2147483648)`` is ``2147483648``.
- ``minmax`` returns the signed (minimum, maximum) pair; the empty
  sentinel is ``(2147483647, -2147483648)``.
- ``avg`` accumulates in ``Float64`` and applies ``floor`` to the mean:
  ``avg([-1, -2], 2)`` is ``-2``. Empty input returns ``0``.
- ``rms`` accumulates squares in ``Float64`` and truncates
  ``sqrt(mean)`` toward zero, matching the reference's unsigned cast;
  ``rms`` of the 32-bit minimum is ``2147483648``.
- ``cross`` counts sign-class transitions where the class of a sample is
  ``sample < 0`` (zero behaves like a positive sample); the counter
  starts at ``-1`` with a non-negative sentinel, so empty input returns
  ``-1`` and every non-empty fragment returns ``>= 0``.
"""

from std.collections import List
from std.math import floor, sqrt
from std.utils import StaticTuple

from mojo_audioop.samples import (
    decode_fragment,
    decode_sample,
    validate_fragment,
)


def getsample(fragment: Span[UInt8, _], width: Int, index: Int64) raises -> Int32:
    """Return sample ``index``; negative and out-of-range indices error."""
    validate_fragment(fragment, width)
    var count = len(fragment) // width
    if index < 0 or index >= Int64(count):
        raise Error("Index out of range")
    return decode_sample(fragment, width, Int(index))


def max(fragment: Span[UInt8, _], width: Int) raises -> Int64:
    """Maximum absolute sample magnitude (unsigned semantics)."""
    validate_fragment(fragment, width)
    var samples = decode_fragment(fragment, width)
    var result: Int64 = 0
    for index in range(len(samples)):
        var value = Int64(samples[index])
        if value < 0:
            value = -value
        if value > result:
            result = value
    return result


def minmax(fragment: Span[UInt8, _], width: Int) raises -> StaticTuple[Int32, 2]:
    """Signed (minimum, maximum) pair; empty sentinel (2147483647, -2147483648)."""
    validate_fragment(fragment, width)
    var samples = decode_fragment(fragment, width)
    var minimum: Int32 = 2147483647
    var maximum: Int32 = -2147483648
    for index in range(len(samples)):
        var value = samples[index]
        if value > maximum:
            maximum = value
        if value < minimum:
            minimum = value
    return StaticTuple[Int32, 2](minimum, maximum)


def avg(fragment: Span[UInt8, _], width: Int) raises -> Int64:
    """Floor of the mean, accumulated in Float64 like the reference."""
    validate_fragment(fragment, width)
    var samples = decode_fragment(fragment, width)
    if len(samples) == 0:
        return 0
    var sum: Float64 = 0.0
    for index in range(len(samples)):
        sum += Float64(samples[index])
    return Int64(floor(sum / Float64(len(samples))))


def rms(fragment: Span[UInt8, _], width: Int) raises -> Int64:
    """Truncated sqrt of the mean square, accumulated in Float64."""
    validate_fragment(fragment, width)
    var samples = decode_fragment(fragment, width)
    if len(samples) == 0:
        return 0
    var sum_squares: Float64 = 0.0
    for index in range(len(samples)):
        var value = Float64(samples[index])
        sum_squares += value * value
    return Int64(sqrt(sum_squares / Float64(len(samples))))


def cross(fragment: Span[UInt8, _], width: Int) raises -> Int64:
    """Zero-crossing count with the reference's -1 start and sign classes."""
    validate_fragment(fragment, width)
    var samples = decode_fragment(fragment, width)
    var ncross: Int = -1
    # ponytail: sentinel 17 mirrors the reference; any value > 1 works
    var prevval: Int = 17
    for index in range(len(samples)):
        var val: Int = 0
        if samples[index] < 0:
            val = 1
        if val != prevval:
            ncross += 1
        prevval = val
    return Int64(ncross)
