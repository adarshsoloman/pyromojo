"""Phase 0 Mojo 1.2.0 probe: dynamic byte-buffer storage for packed bits.

Verifies: List[UInt8] allocation with capacity, growth by appending,
copy semantics (independent buffers), element read/write, sub-range
copy (the primitive behind slicing), and packed-bytes <-> logical-bit
round-trips including partial final bytes and the empty case.

Run with::

    .venv/bin/mojo run experiments/toolchain_validation/bitarray/storage.mojo
"""

from std.collections import List
from std.testing import assert_equal


def bytes_for_bits(nbits: Int) -> Int:
    """Ceil(nbits / 8) without overflow risk for memory-bounded sizes."""
    return (nbits + 7) // 8


def pack_big(bits: List[UInt8]) -> List[UInt8]:
    var out = List[UInt8](capacity=bytes_for_bits(len(bits)))
    var acc = UInt8(0)
    var count = 0
    for i in range(len(bits)):
        acc = (acc << 1) | (bits[i] & UInt8(1))
        count += 1
        if count == 8:
            out.append(acc)
            acc = 0
            count = 0
    if count > 0:
        out.append(acc << UInt8(8 - count))
    return out^


def unpack_big(buf: List[UInt8], nbits: Int) -> List[UInt8]:
    """Logical bits from packed bytes (big-endian); ignores padding."""
    var out = List[UInt8](capacity=nbits)
    for i in range(nbits):
        var byte = buf[i // 8]
        var bit = (byte >> UInt8(7 - (i % 8))) & UInt8(1)
        out.append(bit)
    return out^


def copy_range(src: List[UInt8], lo: Int, hi: Int) -> List[UInt8]:
    """Independent copy of src[lo:hi] (slicing primitive)."""
    var out = List[UInt8](capacity=hi - lo)
    for i in range(lo, hi):
        out.append(src[i])
    return out^


def main() raises:
    # Allocation: capacity is a hint; length tracks appends exactly.
    var buf = List[UInt8](capacity=4)
    assert_equal(len(buf), 0)
    for i in range(10):
        buf.append(UInt8(i))
    assert_equal(len(buf), 10)
    for i in range(10):
        assert_equal(buf[i], UInt8(i))
    print("PASS List grows past initial capacity, indexing is exact")

    # Copy is independent (no aliasing).
    var original = List[UInt8]()
    original.append(0xAA)
    original.append(0x0F)
    var dup = copy_range(original, 0, len(original))
    dup[0] = UInt8(0)
    assert_equal(original[0], UInt8(0xAA))
    assert_equal(dup[0], UInt8(0))
    assert_equal(len(dup), len(original))
    print("PASS copied buffer is independent of the original")

    # Sub-range copy behaves like a slice.
    var mid = copy_range(original, 1, 2)
    assert_equal(len(mid), 1)
    assert_equal(mid[0], UInt8(0x0F))
    var empty = copy_range(original, 1, 1)
    assert_equal(len(empty), 0)
    print("PASS sub-range copy matches slice semantics")

    # Round-trip packed bytes <-> logical bits, incl. partial tails.
    var cases = List[Int]()
    cases.append(0)
    cases.append(1)
    cases.append(7)
    cases.append(8)
    cases.append(9)
    cases.append(63)
    cases.append(64)
    cases.append(65)
    cases.append(200)
    for ci in range(len(cases)):
        var n = cases[ci]
        var bits = List[UInt8]()
        for i in range(n):
            bits.append(UInt8(i % 2))
        var packed = pack_big(bits)
        assert_equal(len(packed), bytes_for_bits(n))
        var back = unpack_big(packed, n)
        assert_equal(len(back), n)
        for i in range(n):
            assert_equal(back[i], bits[i])
    print("PASS pack/unpack round-trips lengths 0..200 incl. partial bytes")

    # Simulated frombytes/to-bytes: whole-byte append, then trim to length.
    var stream = List[UInt8]()
    stream.append(UInt8(0xAA))
    stream.append(UInt8(0x80))
    var imported = List[UInt8]()
    for i in range(len(stream)):
        imported.append(stream[i])
    assert_equal(len(imported), 2)
    imported[1] = UInt8(0x00)
    assert_equal(stream[1], UInt8(0x80))
    print("PASS imported bytes are owned (mutating copy is safe)")

    # Zeros are the safe default fill; capacity never leaks length.
    var fresh = List[UInt8](capacity=1000)
    assert_equal(len(fresh), 0)
    print("PASS capacity does not affect length")

    print("storage: all checks passed")
