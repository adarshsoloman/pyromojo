"""E05: overflow behaviour of integer types in Mojo 1.2.0.

Question: does arithmetic raise, trap, or wrap? The port must know this
because audioop relies on wrapping masks in some functions and clamping in
others.
"""


def main() raises:
    var i32: Int32 = 2147483647
    i32 += 1
    assert i32 == -2147483648

    var i32min: Int32 = -2147483648
    i32min -= 1
    assert i32min == 2147483647

    var i64: Int64 = 9223372036854775807
    i64 += 1
    assert i64 == -9223372036854775808

    var u32: UInt32 = 0
    u32 -= 1
    assert u32 == 4294967295

    var u8: UInt8 = 255
    u8 += 1
    assert u8 == 0

    print("E05 ok: signed and unsigned overflow wraps silently (no trap)")
