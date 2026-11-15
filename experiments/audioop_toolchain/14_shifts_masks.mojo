"""E14: shifts, masks and bit packing at 8/16/24/32 bits.

Question: are arithmetic right shifts and width masks exact, so the port can
replace the reference's signed-char pointer tricks?
"""


def main() raises:
    # Arithmetic right shift preserves sign.
    var negative: Int32 = -32768
    assert (negative >> 8) == -128
    assert (negative >> 16) == -1
    var positive: Int32 = 32767
    assert (positive >> 8) == 127

    # Left shift then mask truncates to width.
    var wide: Int32 = 0x12345678
    assert (UInt32(wide) & 0xFF) == 0x78
    assert ((UInt32(wide) >> 8) & 0xFFFF) == 0x3456
    assert ((UInt32(wide) >> 16) & 0xFFFF) == 0x1234

    # 32-bit masks are exact; ~ on UInt32 is a 32-bit complement.
    var full: UInt32 = 0xFFFFFFFF
    assert (~full & 0xFFFFFFFF) == 0
    assert (0xFFFFFFFF >> 31) == 1

    # Pack/unpack a 32-bit sample from four bytes (little-endian).
    var b0: UInt8 = 0x78
    var b1: UInt8 = 0x56
    var b2: UInt8 = 0x34
    var b3: UInt8 = 0x12
    var packed =
        UInt32(b0)
        | (UInt32(b1) << 8)
        | (UInt32(b2) << 16)
        | (UInt32(b3) << 24)
    assert packed == 0x12345678

    # Converting a 16-bit signed value to unsigned for masking is lossless.
    var sample: Int32 = -1
    var mask16: UInt32 = 0xFFFF
    assert (UInt32(UInt64(Int64(sample))) & mask16) == 0xFFFF

    print("E14 ok: arithmetic shifts and width masks exact for 8/16/24/32 bits")
