"""Two-row dynamic programming: weighted distance and LCS length.

This module is the independent correctness oracle for the port. It stays
available and tested even after the bit-parallel implementation lands;
optimized paths must agree with it exactly.

Inputs are code-point sequences (see ``..unicode``). All accumulators
are ``Int``. Mojo integer arithmetic wraps silently, so the public entry
points validate up front that ``(len(a) + len(b)) * max_weight`` fits in
``Int``; no cell can then overflow. Lengths are memory-bounded, so the
check itself cannot overflow.
"""

from std.collections import List


def _check_bounds(
    a: List[Int],
    b: List[Int],
    insertion: Int,
    deletion: Int,
    substitution: Int,
) raises:
    """Reject weights whose true distance may not fit in ``Int``."""
    if insertion <= 0 or deletion <= 0 or substitution <= 0:
        raise Error(
            "invalid weights: insertion, deletion, and substitution"
            " costs must be positive integers"
        )
    var longest = insertion
    if deletion > longest:
        longest = deletion
    if substitution > longest:
        longest = substitution
    var total = len(a) + len(b)
    if total > Int.MAX // longest:
        raise Error(
            "weights too large for input lengths:"
            " distance would exceed the Int range"
        )


def dp_distance(
    a: List[Int],
    b: List[Int],
    insertion: Int = 1,
    deletion: Int = 1,
    substitution: Int = 1,
) raises -> Int:
    """Weighted Levenshtein distance with two rolling rows, O(len(a)*len(b)).

    Costs must be positive integers. Zero, negative, and non-integer
    weights are rejected: the reference is degenerate there (C++ raises
    on negatives while returning 0 for all-zero weights), so v0.1 does
    not promise parity outside positive integers.
    """
    _check_bounds(a, b, insertion, deletion, substitution)

    var n = len(a)
    var m = len(b)
    if n == 0:
        return m * insertion
    if m == 0:
        return n * deletion

    var prev = List[Int](capacity=m + 1)
    var curr = List[Int](capacity=m + 1)
    for j in range(m + 1):
        prev.append(j * insertion)
        curr.append(0)

    for i in range(1, n + 1):
        curr[0] = i * deletion
        for j in range(1, m + 1):
            var cost = substitution
            if a[i - 1] == b[j - 1]:
                cost = 0
            curr[j] = min(
                prev[j] + deletion,
                curr[j - 1] + insertion,
                prev[j - 1] + cost,
            )
        var swap = prev^
        prev = curr^
        curr = swap^

    return prev[m]


def dp_lcs_length(a: List[Int], b: List[Int]) -> Int:
    """Longest-common-subsequence length with two rolling rows.

    Used for the Indel distance behind ``ratio``. The result fits in
    ``min(len(a), len(b))`` and cannot overflow.
    """
    var n = len(a)
    var m = len(b)
    if n == 0 or m == 0:
        return 0

    var prev = List[Int](capacity=m + 1)
    var curr = List[Int](capacity=m + 1)
    for _ in range(m + 1):
        prev.append(0)
        curr.append(0)

    for i in range(1, n + 1):
        curr[0] = 0
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        var swap = prev^
        prev = curr^
        curr = swap^

    return prev[m]
