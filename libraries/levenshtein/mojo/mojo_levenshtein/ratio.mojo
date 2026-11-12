"""Public Indel-based similarity ratio over Unicode strings.

``ratio`` is ``1 - indel_distance / (len1 + len2)`` where
``indel_distance = len1 + len2 - 2 * LCS``. This is the reference
definition (``rapidfuzz.distance.Indel.normalized_similarity``); it is
NOT the Levenshtein-distance normalization ``1 - lev / total`` — the
two differ (e.g. ``ratio("abc", "adc")`` is 2/3, not 5/6). Verified
bit-exact against the oracle on a 3000-pair corpus in Phase 0.
"""

from mojo_levenshtein.algorithms.dynamic_programming import dp_lcs_length
from mojo_levenshtein.unicode import to_codepoints


def levenshtein_ratio(s1: String, s2: String) -> Float64:
    """Indel normalized similarity in ``[0.0, 1.0]``.

    Empty/empty is ``1.0``; a single empty input is ``0.0``. No cutoff
    support in v0.1: the reference converts similarity cutoffs through
    float32 and disagrees with exact comparison at boundaries.
    """
    var a = to_codepoints(s1)
    var b = to_codepoints(s2)
    var total = len(a) + len(b)
    if total == 0:
        return 1.0
    var lcs = dp_lcs_length(a, b)
    var indel = total - 2 * lcs
    return 1.0 - Float64(indel) / Float64(total)
