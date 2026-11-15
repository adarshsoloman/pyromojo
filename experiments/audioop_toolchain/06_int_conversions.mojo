"""E06: safe and unsafe integer conversions.

Question: which conversions are checked, and which silently truncate?
"""


def main() raises:
    # Widening is exact.
    var small: Int32 = -32768
    var wide: Int64 = Int64(small)
    assert wide == -32768

    # Narrowing silently truncates (no exception).
    var big: Int64 = 2147483648
    var narrowed: Int32 = Int32(big)
    assert narrowed == -2147483648

    var too_big: Int64 = 300
    var byte_value: UInt8 = UInt8(too_big)
    assert byte_value == 44

    # Signed/unsigned reinterpretation matches two's complement.
    var negative: Int32 = -1
    var as_unsigned: UInt32 = UInt32(negative)
    assert as_unsigned == 4294967295
    assert Int32(as_unsigned) == -1

    # Int32 to Int64 via unsigned preserves the bit pattern.
    var pattern: Int64 = Int64(UInt64(UInt32(negative)))
    assert pattern == 4294967295

    print("E06 ok: widening exact, narrowing truncates, two's complement holds")
