"""E15: width dispatch without duplicating every algorithm four times.

Question: can width 1/2/3/4 be dispatched compactly (overloads or a
parameter), with per-width specialisation where it matters?
"""

from std.collections import List
from std.utils import StaticTuple


def max_value(width: Int) -> Int64:
    var values = StaticTuple[Int64, 5](
        0, 0x7F, 0x7FFF, 0x7FFFFF, 0x7FFFFFFF
    )
    return values[width]


def clamp_sample(value: Int64, width: Int) -> Int64:
    var maximum = max_value(width)
    var minimum = -maximum - 1
    if value > maximum:
        return maximum
    if value < minimum:
        return minimum
    return value


def bias16(fragment: List[UInt8], bias: Int32) -> List[UInt8]:
    var result = List[UInt8](capacity=len(fragment))
    result.resize(len(fragment), 0)
    for i in range(0, len(fragment), 2):
        var raw = UInt16(fragment[i]) | (UInt16(fragment[i + 1]) << 8)
        var sample = Int32(Int16(raw))
        var biased = Int32(
            clamp_sample(Int64(sample) + Int64(bias), 2)
        )
        var encoded = UInt16(UInt32(Int64(biased)) & 0xFFFF)
        result[i] = UInt8(encoded & 0xFF)
        result[i + 1] = UInt8(encoded >> 8)
    return result^


# Overloads let the compiler pick a fixed-width implementation.
def describe(value: Int8) -> String:
    return "8-bit"


def describe(value: Int16) -> String:
    return "16-bit"


def describe(value: Int32) -> String:
    return "32-bit"


def main() raises:
    assert clamp_sample(2000000000, 2) == 32767
    assert clamp_sample(-2000000000, 2) == -32768
    assert clamp_sample(0, 1) == 0
    assert clamp_sample(300, 1) == 127

    var fragment = List[UInt8](capacity=4)
    fragment.append(0x00)
    fragment.append(0x80)  # -32768 LE
    fragment.append(0xFF)
    fragment.append(0x7F)  # 32767 LE
    var biased = bias16(fragment, 1000)
    assert biased[0] == 0xE8
    assert biased[1] == 0x83  # -31768
    assert biased[2] == 0xFF and biased[3] == 0x7F  # saturated

    assert describe(Int8(1)) == "8-bit"
    assert describe(Int16(1)) == "16-bit"
    assert describe(Int32(1)) == "32-bit"

    print("E15 ok: runtime width table, clamp helper and static overloads")
