"""E09: encode/decode all four sample widths in both byte orders.

Question: can a get/set sample pair cover widths 1/2/3/4 and both byte
orders without unsafe pointer casts?
"""

from std.collections import List
from std.utils import StaticTuple


def bounds(width: Int) -> StaticTuple[Int64, 2]:
    if width == 1:
        return StaticTuple[Int64, 2](-128, 127)
    if width == 2:
        return StaticTuple[Int64, 2](-32768, 32767)
    if width == 3:
        return StaticTuple[Int64, 2](-8388608, 8388607)
    return StaticTuple[Int64, 2](-2147483648, 2147483647)


def get_sample(fragment: List[UInt8], width: Int, le: Bool) -> Int64:
    var raw: UInt64 = 0
    for i in range(width):
        var byte_index = i if le else (width - 1 - i)
        raw |= UInt64(fragment[byte_index]) << (UInt64(i) * 8)
    var bits = UInt64(width * 8)
    var sign_bit = UInt64(1) << (bits - 1)
    if (raw & sign_bit) != 0:
        return Int64(raw) - Int64(UInt64(1) << bits)
    return Int64(raw)


def set_sample(mut fragment: List[UInt8], width: Int, le: Bool, value: Int64):
    var raw = UInt64(value) & ((UInt64(1) << (UInt64(width) * 8)) - 1)
    for i in range(width):
        var byte_index = i if le else (width - 1 - i)
        fragment[byte_index] = UInt8((raw >> (UInt64(i) * 8)) & 0xFF)


def main() raises:
    for width in range(1, 5):
        var limits = bounds(width)
        var values = StaticTuple[Int64, 4](
            limits[0], limits[1], 0, -1
        )
        for index in range(4):
            for little in range(2):
                var le = little == 0
                var fragment = List[UInt8](capacity=width)
                fragment.resize(width, 0)
                set_sample(fragment, width, le, values[index])
                var result = get_sample(fragment, width, le)
                assert result == values[index]
    print("E09 ok: get/set sample exact for widths 1-4, LE and BE")
