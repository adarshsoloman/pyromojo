"""Phase 5 channel operations.

Two public audioop operations on the Phase 1 sample layer. Semantics
match CPython 3.12.3 ``Modules/audioop.c``:

- ``tomono`` combines interleaved stereo pairs:
  ``fbound(lfactor * left + rfactor * right)`` per pair, where ``fbound``
  clamps to the signed sample range, then floors. The sample count must
  be even; a single sample or an odd count raises ``not a whole number
  of frames`` (after the usual width/alignment validation). An empty
  fragment is valid.
- ``tostereo`` expands each mono sample to an interleaved
  ``(fbound(value * lfactor), fbound(value * rfactor))`` pair; the left
  sample is stored first. Any alignment is accepted; an empty fragment
  produces an empty result.

``fbound`` is the shared reference helper (clamp, floor, convert) with
the port's documented NaN policy: NaN results — from a NaN factor or
``0 * inf`` — are defined as zero, matching the reference's observed
behaviour at widths 1-3 and deviating from its undefined width-4
``(int)NaN`` result.
"""

from std.collections import List

from mojo_audioop.arithmetic import _fbound
from mojo_audioop.samples import (
    decode_fragment,
    encode_fragment,
    sample_max,
    sample_min,
    validate_fragment,
)


def tomono(
    fragment: Span[UInt8, _], width: Int, lfactor: Float64, rfactor: Float64
) raises -> List[UInt8]:
    """Mix interleaved stereo pairs to mono with saturation and floor."""
    validate_fragment(fragment, width)
    if (len(fragment) // width) % 2 != 0:
        raise Error("not a whole number of frames")
    var samples = decode_fragment(fragment, width)
    var minimum = Float64(Int(sample_min(width)))
    var maximum = Float64(Int(sample_max(width)))
    var out = List[Int64](capacity=len(samples) // 2)
    for index in range(0, len(samples), 2):
        var value = Float64(samples[index]) * lfactor + Float64(samples[index + 1]) * rfactor
        out.append(_fbound(value, minimum, maximum))
    return encode_fragment(Span(out), width)


def tostereo(
    fragment: Span[UInt8, _], width: Int, lfactor: Float64, rfactor: Float64
) raises -> List[UInt8]:
    """Expand mono samples to interleaved stereo pairs (left first)."""
    validate_fragment(fragment, width)
    var samples = decode_fragment(fragment, width)
    var minimum = Float64(Int(sample_min(width)))
    var maximum = Float64(Int(sample_max(width)))
    var out = List[Int64](capacity=2 * len(samples))
    for index in range(len(samples)):
        var value = Float64(samples[index])
        out.append(_fbound(value * lfactor, minimum, maximum))
        out.append(_fbound(value * rfactor, minimum, maximum))
    return encode_fragment(Span(out), width)
