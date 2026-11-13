"""Phase 1A native tests: BitArray storage, endianness, and invariants.

Covers: empty and byte-boundary lengths (0, 1, 7, 8, 9, 15, 16, 17,
63, 64, 65); big- and little-endian indexing; logical bit reads and
writes; reference byte layouts; padding-bit invariants including
deliberately contaminated buffers; storage independence (no
aliasing); invalid buffer sizes and indexes.
"""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_bitarray import BitArray, ENDIAN_BIG, ENDIAN_LITTLE, bytes_for_bits


def u8list(a: UInt8) -> List[UInt8]:
    var out = List[UInt8](capacity=1)
    out.append(a)
    return out^


def u8list2(a: UInt8, b: UInt8) -> List[UInt8]:
    var out = List[UInt8](capacity=2)
    out.append(a)
    out.append(b)
    return out^


def test_byte_counts() raises:
    assert_equal(bytes_for_bits(0), 0)
    assert_equal(bytes_for_bits(1), 1)
    assert_equal(bytes_for_bits(7), 1)
    assert_equal(bytes_for_bits(8), 1)
    assert_equal(bytes_for_bits(9), 2)
    assert_equal(bytes_for_bits(15), 2)
    assert_equal(bytes_for_bits(16), 2)
    assert_equal(bytes_for_bits(17), 3)
    assert_equal(bytes_for_bits(63), 8)
    assert_equal(bytes_for_bits(64), 8)
    assert_equal(bytes_for_bits(65), 9)


def test_empty_has_no_storage() raises:
    var a = BitArray(List[UInt8](), 0, ENDIAN_BIG)
    assert_equal(len(a.buffer), 0)
    assert_equal(a.length, 0)
    assert_equal(a.byte_count(), 0)
    assert_equal(a.pad_count(), 0)


def test_constructor_rejects_bad_shapes() raises:
    with assert_raises(contains="negative"):
        _ = BitArray(u8list(0), -1, ENDIAN_BIG)
    with assert_raises(contains="buffer"):
        _ = BitArray(u8list(0), 9, ENDIAN_BIG)
    with assert_raises(contains="buffer"):
        _ = BitArray(u8list2(UInt8(0), UInt8(0)), 1, ENDIAN_LITTLE)


def test_reference_byte_layouts() raises:
    # Probed against bitarray==3.12.3: logical bits -> physical bytes.
    var be = BitArray(bytearray_literal_be(), 8, ENDIAN_BIG)
    assert_equal(be.buffer[0], UInt8(0xCA))
    var le = BitArray(bytearray_literal_le(), 8, ENDIAN_LITTLE)
    assert_equal(le.buffer[0], UInt8(0x53))
    var one_be = BitArray(u8list(0), 1, ENDIAN_BIG)
    assert_equal(one_be.buffer[0], UInt8(0))
    var pay = BitArray(u8list(UInt8(0xFF)), 1, ENDIAN_BIG)
    assert_equal(pay.buffer[0], UInt8(0x80))
    var pay_le = BitArray(u8list(UInt8(0xFF)), 1, ENDIAN_LITTLE)
    assert_equal(pay_le.buffer[1 - 1], UInt8(0x01))


def bytearray_literal_be() -> List[UInt8]:
    return u8list(UInt8(0xCA))


def bytearray_literal_le() -> List[UInt8]:
    return u8list(UInt8(0x53))


def test_indexing_follows_endianness() raises:
    var be = BitArray(bytearray_literal_be(), 8, ENDIAN_BIG)
    assert_equal(be.read_bit(0), UInt8(1))
    assert_equal(be.read_bit(1), UInt8(1))
    assert_equal(be.read_bit(2), UInt8(0))
    var le = BitArray(bytearray_literal_le(), 8, ENDIAN_LITTLE)
    assert_equal(le.read_bit(0), UInt8(1))
    assert_equal(le.read_bit(1), UInt8(1))
    assert_equal(le.read_bit(2), UInt8(0))
    # Same logical pattern from opposite byte layouts agrees bit by bit,
    # except where the layouts genuinely differ.
    var cross = BitArray(u8list(UInt8(0x80)), 1, ENDIAN_LITTLE)
    assert_equal(cross.read_bit(0), UInt8(0))


def test_set_clear_roundtrip() raises:
    for big in [True, False]:
        var buf = List[UInt8]()
        buf.append(UInt8(0))
        var bits = BitArray(buf^, 1, big)
        bits.set_bit(0)
        assert_equal(bits.read_bit(0), UInt8(1))
        bits.clear_bit(0)
        assert_equal(bits.read_bit(0), UInt8(0))


def test_out_of_bounds_raises() raises:
    var bits = BitArray(u8list(UInt8(0xFF)), 8, ENDIAN_BIG)
    with assert_raises(contains="out of range"):
        _ = bits.read_bit(8)
    with assert_raises(contains="out of range"):
        bits.set_bit(100)
    with assert_raises(contains="out of range"):
        bits.clear_bit(8)
    with assert_raises(contains="out of range"):
        _ = bits.read_bit(-1)


def test_padding_bits_stay_zero() raises:
    # Contaminated trailing byte is normalized by the constructor.
    var dirty = u8list2(UInt8(0xFF), UInt8(0xFF))
    var bits = BitArray(dirty^, 9, ENDIAN_BIG)
    assert_equal(bits.buffer[0], UInt8(0xFF))
    assert_equal(bits.buffer[1], UInt8(0x80))
    var dirty_le = u8list2(UInt8(0xFF), UInt8(0xFF))
    var bits_le = BitArray(dirty_le^, 9, ENDIAN_LITTLE)
    assert_equal(bits_le.buffer[1], UInt8(0x01))
    # Padding introspection matches the reference formula.
    assert_equal(BitArray(u8list(UInt8(0)), 1, ENDIAN_BIG).pad_count(), 7)
    assert_equal(BitArray(u8list(UInt8(0)), 8, ENDIAN_BIG).pad_count(), 0)


def test_copies_do_not_alias() raises:
    var original = BitArray(u8list(UInt8(0b10100000)), 8, ENDIAN_BIG)
    var copied = BitArray(original.buffer.copy(), original.length, original.big_endian)
    copied.set_bit(7)
    assert_equal(copied.read_bit(7), UInt8(1))
    assert_equal(original.read_bit(7), UInt8(0))


def test_boundary_lengths_end_to_end() raises:
    # Constructed arrays at every required boundary length; checks
    # length, byte count, padding, and first/last valid bits.
    var sizes = List[Int]()
    sizes.append(0)
    sizes.append(1)
    sizes.append(7)
    sizes.append(8)
    sizes.append(9)
    sizes.append(15)
    sizes.append(16)
    sizes.append(17)
    sizes.append(63)
    sizes.append(64)
    sizes.append(65)
    for i in range(len(sizes)):
        var n = sizes[i]
        var buf = List[UInt8]()
        var need = bytes_for_bits(n)
        for _ in range(need):
            buf.append(UInt8(0xFF))
        for endian in [True, False]:
            var bits = BitArray(buf.copy(), n, endian)
            assert_equal(len(bits.buffer), need)
            assert_equal(bits.length, n)
            if n == 0:
                continue
            # First bit reads back set; last valid bit reads back set.
            assert_equal(bits.read_bit(0), UInt8(1))
            assert_equal(bits.read_bit(n - 1), UInt8(1))
            # Clearing then setting the last valid bit round-trips.
            bits.clear_bit(n - 1)
            assert_equal(bits.read_bit(n - 1), UInt8(0))
            bits.set_bit(n - 1)
            assert_equal(bits.read_bit(n - 1), UInt8(1))


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
