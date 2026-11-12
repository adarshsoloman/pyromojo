"""Public Indel-based similarity ratio over Unicode strings.

``ratio`` is ``1 - indel_distance / (len1 + len2)`` where
``indel_distance = len1 + len2 - 2 * LCS``. This is the reference
definition (``rapidfuzz.distance.Indel.normalized_similarity``); it is
NOT the Levenshtein-distance normalization ``1 - lev / total`` — the
two differ (e.g. ``ratio("abc", "adc")`` is 2/3, not 5/6). Verified
bit-exact against the oracle on a 3000-pair corpus in Phase 0.
"""

from mojo_levenshtein.algorithms.lcs import lcs_bitparallel
from mojo_levenshtein.unicode import to_codepoints


def levenshtein_ratio(s1: String, s2: String) raises -> Float64:
    """Indel normalized similarity in ``[0.0, 1.0]``.

    Empty/empty is ``1.0``; a single empty input is ``0.0``. No cutoff
    support in v0.1: the reference converts similarity cutoffs through
    float32 and disagrees with exact comparison at boundaries.

    Marked ``raises`` for the ``Dict`` lookups in the bit-parallel LCS
    table (same convention as ``myers_distance``); all inputs have a
    defined result.
    """
    var a = to_codepoints(s1)
    var b = to_codepoints(s2)
    var total = len(a) + len(b)
    if total == 0:
        return 1.0
    # Shared affixes always belong to some LCS, so trimming is exact
    # (mirrors the distance path; kept inline to avoid touching it).
    var lo = 0
    var hi_a = len(a)
    var hi_b = len(b)
    while lo < hi_a and lo < hi_b and a[lo] == b[lo]:
        lo += 1
    while hi_a > lo and hi_b > lo and a[hi_a - 1] == b[hi_b - 1]:
        hi_a -= 1
        hi_b -= 1
    # Blocked bit-parallel LCS, shorter input as pattern; the result is
    # order-independent. dp_lcs_length remains the tested oracle.
    # Without trimming, run directly on the converted lists (no copies).
    var lcs: Int
    if lo == 0 and hi_a == len(a) and hi_b == len(b):
        if len(a) <= len(b):
            lcs = lcs_bitparallel(a, b)
        else:
            lcs = lcs_bitparallel(b, a)
    elif hi_a - lo <= hi_b - lo:
        lcs = _lcs_slice(a, lo, hi_a, b, lo, hi_b)
    else:
        lcs = _lcs_slice(b, lo, hi_b, a, lo, hi_a)
    # Every trimmed affix code point is matched in some optimal LCS, so
    # the full LCS is the trimmed LCS plus the trimmed lengths.
    var full_lcs = lcs + lo + (len(a) - hi_a)
    var indel = total - 2 * full_lcs
    return 1.0 - Float64(indel) / Float64(total)


def _lcs_slice(
    a: List[Int], alo: Int, ahi: Int, b: List[Int], blo: Int, bhi: Int
) raises -> Int:
    """Bit-parallel LCS over ``a[alo:ahi]`` vs ``b[blo:bhi]``."""
    var m = ahi - alo
    var n = bhi - blo
    if m == 0 or n == 0:
        return 0
    var pa = List[Int](capacity=m)
    for i in range(alo, ahi):
        pa.append(a[i])
    var pb = List[Int](capacity=n)
    for i in range(blo, bhi):
        pb.append(b[i])
    return lcs_bitparallel(pa, pb)
