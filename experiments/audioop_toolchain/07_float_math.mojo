"""E07: floating-point arithmetic used by reference algorithms.

Question: are floor/sqrt exact enough to reproduce the reference's double
arithmetic (rms truncation, ratecv interpolation, findfit)?
"""

from std.math import floor, sqrt, trunc


def main() raises:
    assert floor(2.5) == 2.0
    assert floor(-1.5) == -2.0
    assert floor(7.0) == 7.0

    assert sqrt(9.0) == 3.0
    assert sqrt(0.0) == 0.0

    # Integer-valued doubles are exact up to 2^53, which covers all sums of
    # squared 32-bit samples in practical fragment sizes.
    var big: Float64 = 9007199254740992.0
    assert big + 1.0 == big

    # 0.1 + 0.2 is not 0.3, exactly like CPython's C doubles.
    var tenth: Float64 = 0.1
    var fifth: Float64 = 0.2
    assert tenth + fifth != 0.3
    assert trunc(-1.9) == -1.0

    # Reference rms truncates: sqrt((9+0)/2)=2.1213 -> 2
    var sum_squares: Float64 = 9.0
    var mean = sum_squares / 2.0
    var root = sqrt(mean)
    var truncated = Int64(floor(root))
    assert truncated == 2

    print("E07 ok: floor/sqrt/trunc available; IEEE-754 double semantics match")
