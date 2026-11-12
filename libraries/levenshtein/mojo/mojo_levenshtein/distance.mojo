"""Public Levenshtein distance over Unicode strings.

Unit and positive-integer weighted costs. Unit costs dispatch to the
blocked Myers bit-parallel implementation; weighted costs use the
two-row DP oracle. Both paths count Unicode code points and agree
exactly (parity is tested, not assumed).
"""

from std.collections import List

from mojo_levenshtein.algorithms.dynamic_programming import dp_distance
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
    """Dispatch code-point sequences to Myers (unit) or DP (weighted)."""
    if insertion == 1 and deletion == 1 and substitution == 1:
        if len(a) <= len(b):
            return myers_distance(a, b)
        return myers_distance(b, a)
    return dp_distance(a, b, insertion, deletion, substitution)
