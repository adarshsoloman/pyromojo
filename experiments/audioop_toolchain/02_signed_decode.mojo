"""E02: decode signed 8/16/32-bit samples from unsigned bytes, both byte orders.

Question: can every width's sign extension be expressed exactly, with no
reliance on the reference's native-endian memory tricks?
"""


def decode_u8(b0: UInt8) -> Int32:
    var v = UInt32(b0)
    if (v & 0x80) != 0:
        return Int32(Int64(v) - 256)
    return Int32(v)


def decode_i16(b0: UInt8, b1: UInt8, le: Bool) -> Int32:
    var raw: UInt32
    if le:
        raw = UInt32(b0) | (UInt32(b1) << 8)
    else:
        raw = UInt32(b1) | (UInt32(b0) << 8)
    if (raw & 0x8000) != 0:
        return Int32(Int64(raw) - 65536)
    return Int32(raw)


def decode_i32(b0: UInt8, b1: UInt8, b2: UInt8, b3: UInt8, le: Bool) -> Int64:
    var raw: UInt64
    if le:
        raw = (
            UInt64(b0)
            | (UInt64(b1) << 8)
            | (UInt64(b2) << 16)
            | (UInt64(b3) << 24)
        )
    else:
        raw = (
            UInt64(b3)
            | (UInt64(b2) << 8)
            | (UInt64(b1) << 16)
            | (UInt64(b0) << 24)
        )
    if (raw & 0x80000000) != 0:
        return Int64(raw) - 4294967296
    return Int64(raw)


def main() raises:
    assert decode_u8(0) == 0
    assert decode_u8(127) == 127
    assert decode_u8(128) == -128
    assert decode_u8(255) == -1

    assert decode_i16(0x00, 0x80, True) == -32768
    assert decode_i16(0xFF, 0x7F, True) == 32767
    assert decode_i16(0x80, 0x00, False) == -32768
    assert decode_i16(0x80, 0xFF, True) == -256

    assert decode_i32(0x00, 0x00, 0x00, 0x80, True) == -2147483648
    assert decode_i32(0xFF, 0xFF, 0xFF, 0x7F, True) == 2147483647
    assert decode_i32(0x80, 0x00, 0x00, 0x00, False) == -2147483648
    assert decode_i32(0xFE, 0xFF, 0xFF, 0xFF, True) == -2

    print("E02 ok: u8/i16/i32 sign extension exact in both byte orders")
