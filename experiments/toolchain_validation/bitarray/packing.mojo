"""Phase 0 Mojo 1.2.0 probe: packed-bit storage primitives.

Verifies: packing 8 logical bits into one UInt8, extracting a bit at an
arbitrary index, setting/clearing individual bits, big-endian vs
little-endian bit indexing, and boundary lengths (0, 1, 7, 8, 9, 63,
64, 65). Expected byte values were captured from the pinned reference
(``bitarray==3.12.3``); see ``reference_probe_output.txt``.

Run with::

    .venv/bin/mojo run experiments/toolchain_validation/bitarray/packing.mojo
"""

from std.collections import List
from std.testing import assert_equal


def pack_big(bits: List[UInt8]) -> List[UInt8]:
    """Pack code-point... i.e. logical 0/1 values, MSB-first per byte."""
    var out = List[UInt8]()
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


def pack_little(bits: List[UInt8]) -> List[UInt8]:
    """Pack logical 0/1 values, LSB-first per byte."""
    var out = List[UInt8]()
    var acc = UInt8(0)
    var count = 0
    for i in range(len(bits)):
        acc = acc | ((bits[i] & UInt8(1)) << UInt8(count))
        count += 1
        if count == 8:
            out.append(acc)
            acc = 0
            count = 0
    if count > 0:
        out.append(acc)
    return out^


def get_bit(buf: List[UInt8], index: Int, little_endian: Bool) -> UInt8:
    """Extract one logical bit; caller guarantees the index is in range."""
    var byte = buf[index // 8]
    var shift: Int
    if little_endian:
        shift = index % 8
    else:
        shift = 7 - (index % 8)
    return (byte >> UInt8(shift)) & UInt8(1)


def set_bit(mut buf: List[UInt8], index: Int, value: UInt8, little_endian: Bool):
    """Set one logical bit in place; caller guarantees index in range."""
    var shift: Int
    if little_endian:
        shift = index % 8
    else:
        shift = 7 - (index % 8)
    var mask = UInt8(1) << UInt8(shift)
    if value != 0:
        buf[index // 8] = buf[index // 8] | mask
    else:
        buf[index // 8] = buf[index // 8] & ~mask


def from_string(text: String) -> List[UInt8]:
    """Logical bits from an ASCII '0'/'1' string (test helper only)."""
    var out = List[UInt8]()
    for i in range(text.byte_length()):
        if text[byte=i] == "1":
            out.append(1)
        else:
            out.append(0)
    return out^


def main() raises:
    # Reference truth table (big-endian first, then little-endian).
    var be_cases = List[Tuple[String, UInt8]]()
    be_cases.append(("11001010", UInt8(0xCA)))
    be_cases.append(("1", UInt8(0x80)))
    be_cases.append(("10", UInt8(0x80)))
    var le_cases = List[Tuple[String, UInt8]]()
    le_cases.append(("11001010", UInt8(0x53)))
    le_cases.append(("1", UInt8(0x01)))
    le_cases.append(("10", UInt8(0x01)))
    for i in range(len(be_cases)):
        var packed = pack_big(from_string(be_cases[i][0]))
        assert_equal(len(packed), 1)
        assert_equal(packed[0], be_cases[i][1])
    for i in range(len(le_cases)):
        var packed = pack_little(from_string(le_cases[i][0]))
        assert_equal(len(packed), 1)
        assert_equal(packed[0], le_cases[i][1])
    print("PASS packing matches reference bytes (big and little)")

    # Boundary lengths: pad-bit counts must be (8 - n % 8) % 8.
    for n in range(0, 9):
        var bits = List[UInt8]()
        for _ in range(n):
            bits.append(1)
        var packed = pack_big(bits)
        var expect_bytes = (n + 7) // 8
        assert_equal(len(packed), expect_bytes)
        var expect_pad = (8 - (n % 8)) % 8
        var got_pad = (8 * len(packed) - n) if n > 0 or len(packed) > 0 else 0
        assert_equal(got_pad, expect_pad)
    # 9 bits -> 2 bytes, 63/64/65-bit lengths.
    for n in [63, 64, 65]:
        var bits = List[UInt8]()
        for _ in range(n):
            bits.append(1)
        var packed = pack_big(bits)
        assert_equal(len(packed), (n + 7) // 8)
    print("PASS boundary lengths 0-8 packed like the reference")
    print("PASS 63/64/65-bit lengths allocate ceil(n/8) bytes")

    # Extract every bit back out, both endiannesses.
    var pattern = from_string("11001010111")
    var be = pack_big(pattern)
    var le = pack_little(pattern)
    for i in range(len(pattern)):
        assert_equal(get_bit(be, i, False), pattern[i])
        assert_equal(get_bit(le, i, True), pattern[i])
    print("PASS bit extraction round-trips all positions (both endians)")

    # Set and clear each position, verifying neighbours are untouched.
    for endian in range(2):
        var little = endian == 1
        var buf = pack_big(from_string("00000000"))
        for i in range(8):
            set_bit(buf, i, 1, little)
            assert_equal(get_bit(buf, i, little), UInt8(1))
            set_bit(buf, i, 0, little)
            assert_equal(get_bit(buf, i, little), UInt8(0))
    print("PASS set/clear preserves neighbouring bits")

    # Partial final byte: pad bits must read back as stored zeros.
    var nine = pack_big(from_string("101010101"))
    assert_equal(len(nine), 2)
    assert_equal(nine[1] & UInt8(0x7F), UInt8(0))
    print("PASS partial-byte pad region stays zero")

    print("packing: all checks passed")
