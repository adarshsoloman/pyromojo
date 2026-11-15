"""Phase 4 peak analysis and fragment matching.

Five public audioop operations on the Phase 1 sample layer. Semantics
match CPython 3.12.3 ``Modules/audioop.c``:

- ``avgpp``/``maxpp`` walk the sample sequence tracking the previous
  value and previous derivative direction. The first observed direction
  is the baseline; only when the derivative changes sign is the previous
  value remembered as an extreme, and only the *second* remembered
  extreme produces a peak-to-peak difference. Equal adjacent samples are
  ignored entirely. Differences are computed in 32-bit unsigned
  arithmetic, so the ``INT_MAX``/``INT_MIN`` pair yields ``4294967295``.
  ``avgpp`` truncates the mean of the unsigned differences; ``maxpp``
  keeps the maximum. A fragment of at most one sample returns 0.
- ``findmax`` treats the fragment as fixed 16-bit samples (there is no
  width argument); ``length`` is in samples. It slides an
  ``_sum2``-style energy window with the reference's incremental update
  ``result = result + last^2 - first^2`` and keeps the FIRST window on
  ties (strict ``>``). ``length`` 0 is valid and returns 0.
- ``findfactor`` is fixed 16-bit and requires equal even-sized
  fragments; it returns ``sum(a*r) / sum(r*r)`` as a double. A zero or
  empty reference divides 0 by 0 and returns ``nan``.
- ``findfit`` is fixed 16-bit; the fragment must have at least as many
  samples as the reference. It recomputes ``sum(a[j..]·r)`` fully for
  every window while updating ``sum(a[j..]²)`` incrementally, keeps the
  first strictly-better window, and returns the winning index plus
  ``sum(a[best..]·r) / sum(r²)`` recomputed at the winner.
"""

from std.collections import List

from mojo_audioop.samples import decode_fragment, validate_fragment


struct FindFit(RegisterPassable, ImplicitlyCopyable):
    """Result of ``findfit``: window index (16-bit samples) and factor."""

    var index: Int
    var factor: Float64

    def __init__(out self, index: Int, factor: Float64):
        self.index = index
        self.factor = factor


def _unsigned_diff(extreme: Int32, value: Int32) -> UInt32:
    """Reference ``extremediff``: unsigned subtraction of the two's-complement
    patterns, ordered by the signed comparison. The 32-bit wrap reproduces
    CPython exactly, including the 4294967295 result for the INT_MAX/INT_MIN
    pair.
    """
    if value < extreme:
        return UInt32(extreme) - UInt32(value)
    return UInt32(value) - UInt32(extreme)


def _sum_sq(values: Span[Int32, _], offset: Int, count: Int) -> Float64:
    """Reference ``_sum2(x, x, n)``: sequential ``sum += x[i] * x[i]``."""
    var sum: Float64 = 0.0
    for index in range(count):
        var value = Float64(values[offset + index])
        sum += value * value
    return sum


def _sum2(
    values: Span[Int32, _], offset: Int, reference: Span[Int32, _], count: Int
) -> Float64:
    """Reference ``_sum2``: sequential ``sum += a[i] * b[i]`` accumulation."""
    var sum: Float64 = 0.0
    for index in range(count):
        sum += Float64(values[offset + index]) * Float64(reference[index])
    return sum


def avgpp(fragment: Span[UInt8, _], width: Int) raises -> Int64:
    """Average peak-to-peak value (unsigned diffs, truncated mean)."""
    validate_fragment(fragment, width)
    if len(fragment) <= width:
        return 0
    var samples = decode_fragment(fragment, width)
    var prevval = samples[0]
    # ponytail: sentinel 17 mirrors the reference; any value > 1 works
    var prevdiff: Int = 17
    var prevextremevalid = False
    var prevextreme: Int32 = 0
    var nextreme: Int = 0
    var sum: Float64 = 0.0
    for index in range(1, len(samples)):
        var val = samples[index]
        if val != prevval:
            var diff: Int = 1 if val < prevval else 0
            if prevdiff == (1 - diff):
                if prevextremevalid:
                    sum += Float64(_unsigned_diff(prevextreme, prevval))
                    nextreme += 1
                prevextremevalid = True
                prevextreme = prevval
            prevval = val
            prevdiff = diff
    if nextreme == 0:
        return 0
    return Int64(sum / Float64(nextreme))


def maxpp(fragment: Span[UInt8, _], width: Int) raises -> Int64:
    """Maximum peak-to-peak value (unsigned diffs)."""
    validate_fragment(fragment, width)
    if len(fragment) <= width:
        return 0
    var samples = decode_fragment(fragment, width)
    var prevval = samples[0]
    var prevdiff: Int = 17
    var prevextremevalid = False
    var prevextreme: Int32 = 0
    var peak: UInt32 = 0
    for index in range(1, len(samples)):
        var val = samples[index]
        if val != prevval:
            var diff: Int = 1 if val < prevval else 0
            if prevdiff == (1 - diff):
                if prevextremevalid:
                    var extremediff = _unsigned_diff(prevextreme, prevval)
                    if extremediff > peak:
                        peak = extremediff
                prevextremevalid = True
                prevextreme = prevval
            prevval = val
            prevdiff = diff
    return Int64(peak)


def findmax(fragment: Span[UInt8, _], length: Int64) raises -> Int:
    """Index of the ``length``-sample 16-bit window with maximum energy."""
    if len(fragment) % 2 != 0:
        raise Error("Strings should be even-sized")
    var samples = decode_fragment(fragment, 2)
    var len1 = len(samples)
    if length < 0 or Int64(len1) < length:
        raise Error("Input sample should be longer")
    var count = Int(length)
    var result = _sum_sq(Span(samples), 0, count)
    var best_result = result
    var best_j: Int = 0
    for j in range(1, len1 - count + 1):
        var aj_m1 = Float64(samples[j - 1])
        var aj_lm1 = Float64(samples[j + count - 1])
        # reference order: ((result + last^2) - first^2)
        result = result + aj_lm1 * aj_lm1 - aj_m1 * aj_m1
        if result > best_result:
            best_result = result
            best_j = j
    return best_j


def findfactor(fragment: Span[UInt8, _], reference: Span[UInt8, _]) raises -> Float64:
    """Least-squares factor ``sum(a*r) / sum(r*r)`` over fixed 16-bit samples."""
    if len(fragment) % 2 != 0 or len(reference) % 2 != 0:
        raise Error("Strings should be even-sized")
    if len(fragment) != len(reference):
        raise Error("Samples should be same size")
    var frag_samples = decode_fragment(fragment, 2)
    var ref_samples = decode_fragment(reference, 2)
    var count = len(ref_samples)
    var sum_ri_2: Float64 = 0.0
    for index in range(count):
        var value = Float64(ref_samples[index])
        sum_ri_2 += value * value
    var sum_aij_ri: Float64 = 0.0
    for index in range(count):
        sum_aij_ri += Float64(frag_samples[index]) * Float64(ref_samples[index])
    return sum_aij_ri / sum_ri_2


def findfit(fragment: Span[UInt8, _], reference: Span[UInt8, _]) raises -> FindFit:
    """Best-aligning window of ``reference`` inside ``fragment`` (16-bit)."""
    if len(fragment) % 2 != 0 or len(reference) % 2 != 0:
        raise Error("Strings should be even-sized")
    var frag_samples = decode_fragment(fragment, 2)
    var ref_samples = decode_fragment(reference, 2)
    var len1 = len(frag_samples)
    var len2 = len(ref_samples)
    if len1 < len2:
        raise Error("First sample should be longer")

    var sum_ri_2 = _sum_sq(Span(ref_samples), 0, len2)
    var sum_aij_2 = _sum_sq(Span(frag_samples), 0, len2)
    var sum_aij_ri = _sum2(Span(frag_samples), 0, Span(ref_samples), len2)

    var result = (sum_ri_2 * sum_aij_2 - sum_aij_ri * sum_aij_ri) / sum_aij_2
    var best_result = result
    var best_j: Int = 0

    for j in range(1, len1 - len2 + 1):
        var aj_m1 = Float64(frag_samples[j - 1])
        var aj_lm1 = Float64(frag_samples[j + len2 - 1])
        # reference order: ((sum_aij_2 + last^2) - first^2)
        sum_aij_2 = sum_aij_2 + aj_lm1 * aj_lm1 - aj_m1 * aj_m1
        sum_aij_ri = _sum2(Span(frag_samples), j, Span(ref_samples), len2)
        result = (sum_ri_2 * sum_aij_2 - sum_aij_ri * sum_aij_ri) / sum_aij_2
        if result < best_result:
            best_result = result
            best_j = j

    var factor = _sum2(Span(frag_samples), best_j, Span(ref_samples), len2) / sum_ri_2
    return FindFit(best_j, factor)
