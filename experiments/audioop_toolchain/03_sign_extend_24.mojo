"""E03: 24-bit sign extension and re-encoding.

Question: can 3-byte samples be decoded/encoded exactly, including the
most negative value, without an Int24 type?
"""

from std.utils import StaticTuple


def decode24(b0: UInt8, b1: UInt8, b2: UInt8, le: Bool) -> Int32:
    var raw: UInt32
    if le:
        raw = UInt32(b0) | (UInt32(b1) << 8) | (UInt32(b2) << 16)
    else:
        raw = UInt32(b2) | (UInt32(b1) << 8) | (UInt32(b0) << 16)
    if raw >= 0x800000:
        return Int32(Int64(raw) - 16777216)
    return Int32(raw)


def encode24(value: Int32, le: Bool) -> StaticTuple[UInt8, 3]:
    var raw = UInt32(UInt64(Int64(value)) & 0xFFFFFF)
    var lo = UInt8(raw & 0xFF)
    var mid = UInt8((raw >> 8) & 0xFF)
    var hi = UInt8((raw >> 16) & 0xFF)
    if le:
        return StaticTuple[UInt8, 3](lo, mid, hi)
    return StaticTuple[UInt8, 3](hi, mid, lo)



def main() raises:
    assert decode24(0xFF, 0xFF, 0xFF, True) == -1
    assert decode24(0x00, 0x00, 0x80, True) == -8388608
    assert decode24(0xFF, 0xFF, 0x7F, True) == 8388607
    assert decode24(0x80, 0x00, 0x00, False) == -8388608
    assert decode24(0x7F, 0xFF, 0xFF, False) == 8388607

    var packed = encode24(-8388608, True)
    assert packed[0] == 0x00 and packed[1] == 0x00 and packed[2] == 0x80
    var packed_be = encode24(-1, False)
    assert packed_be[0] == 0xFF and packed_be[2] == 0xFF

    # Round-trip every boundary value in both orders.
    var values = StaticTuple[Int32, 4](-8388608, 8388607, 0, -1)
    for index in range(4):
        var value = values[index]
        var le_packed = encode24(value, True)
        assert decode24(le_packed[0], le_packed[1], le_packed[2], True) == value
        var be_packed = encode24(value, False)
        assert decode24(be_packed[0], be_packed[1], be_packed[2], False) == value

    print("E03 ok: 24-bit round-trips exactly at both extremes, both orders")
