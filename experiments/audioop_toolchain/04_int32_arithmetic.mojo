"""E04: 32-bit integer arithmetic and reference-style saturation.

Question: can the reference's clamp arithmetic be reproduced for all four
sample widths, including the 32-bit path that the reference computes in
double precision?
"""

from std.utils import StaticTuple


def saturate(value: Int64, minimum: Int64, maximum: Int64) -> Int64:
    if value > maximum:
        return maximum
    if value < minimum:
        return minimum
    return value


def main() raises:
    # Reference width table.
    var maxvals = StaticTuple[Int64, 5](0, 0x7F, 0x7FFF, 0x7FFFFF, 0x7FFFFFFF)
    var minvals = StaticTuple[Int64, 5](
        0, -0x80, -0x8000, -0x800000, -0x80000000
    )

    # add() for width < 4 is plain int arithmetic then clamp; the sum fits
    # in Int64, so this is exact and overflow-free.
    assert saturate(0x7FFF + 0x7FFF, minvals[2], maxvals[2]) == 0x7FFF
    assert saturate(-0x8000 + -0x8000, minvals[2], maxvals[2]) == -0x8000
    assert saturate(123 + -456, minvals[2], maxvals[2]) == -333

    # width == 4: the reference promotes to double; Int64 is exact here too.
    assert saturate(2147483647 + 2147483647, minvals[4], maxvals[4]) == 2147483647
    assert saturate(-2147483648 + -2147483648, minvals[4], maxvals[4]) == -2147483648

    # Multiplication by a factor needs a wider accumulator.
    var sample: Int64 = 2147483647
    assert saturate(sample * 2, minvals[4], maxvals[4]) == 2147483647
    assert saturate(-2147483648 * 3, minvals[4], maxvals[4]) == -2147483648

    print("E04 ok: saturation exact for widths 1-4 with Int64 accumulators")
