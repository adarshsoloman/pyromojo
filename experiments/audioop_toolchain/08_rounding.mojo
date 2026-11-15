"""E08: reproduce the reference's fbound() rounding and clamp rules.

Question: can floor-then-clamp be reproduced exactly, and what happens with
NaN/Inf inputs where the C reference has undefined behaviour?
"""

from std.math import floor


def fbound(value: Float64, minimum: Float64, maximum: Float64) -> Int64:
    """Reference rule: clamp, then floor, then convert toward zero."""
    var clamped = value
    if value > maximum:
        clamped = maximum
    elif value < minimum + 1.0:
        clamped = minimum
    return Int64(floor(clamped))


def main() raises:
    # floor, not round-to-nearest
    assert fbound(2.5, -32768.0, 32767.0) == 2
    assert fbound(-1.5, -32768.0, 32767.0) == -2
    assert fbound(0.5, -32768.0, 32767.0) == 0
    assert fbound(-0.5, -32768.0, 32767.0) == -1

    # saturation at both ends
    assert fbound(40000.0, -32768.0, 32767.0) == 32767
    assert fbound(-40000.0, -32768.0, 32767.0) == -32768
    assert fbound(-32767.5, -32768.0, 32767.0) == -32768

    # Infinities clamp because comparisons are well defined.
    var inf: Float64 = 1.0 / 0.0
    assert fbound(inf, -32768.0, 32767.0) == 32767
    assert fbound(-inf, -32768.0, 32767.0) == -32768

    # NaN compares false, so the C reference falls through to (int)NaN,
    # which is undefined; Mojo's float->int for NaN is also undefined.
    var nan: Float64 = 0.0 / 0.0
    assert nan != nan
    print("E08 ok: floor+clamp exact; NaN is undefined in the reference too")
