"""Public Levenshtein distance over Unicode strings.

Unit and positive-integer weighted costs. Unit costs dispatch to the
blocked Myers bit-parallel implementation; weighted costs use the
two-row DP oracle. Both paths count Unicode code points and agree
exactly (parity is tested, not assumed).
"""

from std.collections import List

from mojo_levenshtein.algorithms.dynamic_programming import _check_bounds, dp_distance
from mojo_levenshtein.algorithms.myers import myers_distance
from mojo_levenshtein.unicode import to_codepoints


def levenshtein_distance(
    s1: String,
    s2: String,
    insertion: Int = 1,
    deletion: Int = 1,
    substitution: Int = 1,
) raises -> Int:
    """Levenshtein edit distance between two strings.

    Costs must be positive integers; anything else raises, because the
    reference is degenerate outside that domain (Phase 0 audit). The
    shorter string is used as the Myers pattern; the result does not
    depend on argument order.
    """
    var a = to_codepoints(s1)
    var b = to_codepoints(s2)
    return _distance_codepoints(a, b, insertion, deletion, substitution)


def levenshtein_distance_cutoff(
    s1: String,
    s2: String,
    score_cutoff: Int,
    insertion: Int = 1,
    deletion: Int = 1,
    substitution: Int = 1,
) raises -> Int:
    """Edit distance truncated to ``score_cutoff + 1``.

    Matches the reference exactly: returns ``score_cutoff + 1`` when the
    true distance exceeds the cutoff, else the true distance. Negative
    cutoffs raise. The ``+ 1`` cannot overflow: it is only computed when
    the true distance (which fits in ``Int``) exceeds the cutoff.
    """
    if score_cutoff < 0:
        raise Error("invalid score_cutoff: must be a non-negative integer")
    var distance = levenshtein_distance(s1, s2, insertion, deletion, substitution)
    if distance > score_cutoff:
        return score_cutoff + 1
    return distance


def _distance_codepoints(
    a: List[Int],
    b: List[Int],
    insertion: Int,
    deletion: Int,
    substitution: Int,
) raises -> Int:
    """Dispatch code-point sequences to Myers (unit) or DP (weighted).

    Common affixes are stripped first: for positive costs an optimal
    alignment always matches a shared prefix/suffix at zero cost, so
    trimming is exact (matches what the reference does internally).
    When nothing trims, the original lists are used with no copy.

    The overflow/weight contract is validated on the *untrimmed* inputs
    before trimming, so the guard keeps its documented meaning (and its
    tested behavior) regardless of how much the affix scan removes.
    """
    _check_bounds(a, b, insertion, deletion, substitution)
    var lo = 0
    var hi_a = len(a)
    var hi_b = len(b)
    while lo < hi_a and lo < hi_b and a[lo] == b[lo]:
        lo += 1
    while hi_a > lo and hi_b > lo and a[hi_a - 1] == b[hi_b - 1]:
        hi_a -= 1
        hi_b -= 1
    if lo == 0 and hi_a == len(a) and hi_b == len(b):
        return _dispatch(a, b, insertion, deletion, substitution)
    var ta = List[Int](capacity=hi_a - lo)
    for i in range(lo, hi_a):
        ta.append(a[i])
    var tb = List[Int](capacity=hi_b - lo)
    for i in range(lo, hi_b):
        tb.append(b[i])
    return _dispatch(ta, tb, insertion, deletion, substitution)


def _dispatch(
    a: List[Int],
    b: List[Int],
    insertion: Int,
    deletion: Int,
    substitution: Int,
) raises -> Int:
    """Dispatch code-point sequences to Myers (unit) or DP (weighted)."""
    if insertion == 1 and deletion == 1 and substitution == 1:
        if len(a) <= len(b):
            return myers_distance(a, b)
        return myers_distance(b, a)
    return dp_distance(a, b, insertion, deletion, substitution)
