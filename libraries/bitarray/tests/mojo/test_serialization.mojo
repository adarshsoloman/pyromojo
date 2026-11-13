"""Phase 1E native tests: byte conversion, framed payloads, goldens.

Mirrors `tests/python_compat/test_serialization_oracle.py` and the
CLI protocol tests case-for-case; every expected byte sequence below
was captured from `bitarray==3.12.3` probe runs, and the bulk goldens
come from `tests/mojo/generated_vectors.mojo` (verified by
`generate_vectors.py --check`).
"""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises, assert_true

from generated_vectors import BitCase, bitarray_vectors
from mojo_bitarray import (
    BitArray,
    ENDIAN_BIG,
    ENDIAN_LITTLE,
    bytes_for_bits,
    decode_payload_exact,
    encode_payload,
)


def assert_padding_zero(a: BitArray) raises:
    var pad = a.padbits()
    if pad == 0 or len(a.buffer) == 0:
        return
    var last = a.buffer[len(a.buffer) - 1]
    if a.big_endian:
        assert_equal(last & ((UInt8(1) << UInt8(pad)) - UInt8(1)), UInt8(0))
    else:
        assert_equal(last >> UInt8(8 - pad), UInt8(0))


def assert_invariants(a: BitArray, big_endian: Bool) raises:
    assert_equal(a.big_endian, big_endian)
    assert_equal(len(a.buffer), a.nbytes())
    assert_equal(a.nbytes(), bytes_for_bits(len(a)))
    assert_equal(a.padbits(), (8 - len(a) % 8) % 8)
    assert_padding_zero(a)


def assert_bytes_equal(got: List[UInt8], want: List[UInt8]) raises:
    assert_equal(len(got), len(want))
    for i in range(len(want)):
        assert_equal(got[i], want[i])


def u8list1(a: UInt8) -> List[UInt8]:
    var out = List[UInt8](capacity=1)
    out.append(a)
    return out^


def u8list2(a: UInt8, b: UInt8) -> List[UInt8]:
    var out = List[UInt8](capacity=2)
    out.append(a)
    out.append(b)
    return out^


def test_tobytes() raises:
    for big in [True, False]:
        assert_equal(len(BitArray(String(""), big).tobytes()), 0)
        assert_invariants(BitArray(String(""), big), big)
    var be = BitArray(String("10110011"), ENDIAN_BIG)
    assert_bytes_equal(be.tobytes(), u8list1(UInt8(0xB3)))
    var le = BitArray(String("10110011"), ENDIAN_LITTLE)
    assert_bytes_equal(le.tobytes(), u8list1(UInt8(0xCD)))
    # Partial final bytes are zero-padded (probed reference outputs).
    assert_bytes_equal(BitArray(String("10110"), ENDIAN_BIG).tobytes(), u8list1(UInt8(0xB0)))
    assert_bytes_equal(BitArray(String("10110"), ENDIAN_LITTLE).tobytes(), u8list1(UInt8(0x0D)))
    # Result is an independent copy.
    var src = BitArray(String("10110"), ENDIAN_BIG)
    var raw = src.tobytes()
    raw[0] = UInt8(0xFF)
    assert_equal(src.to01(), String("10110"))
    assert_bytes_equal(src.tobytes(), u8list1(UInt8(0xB0)))


def test_frombytes() raises:
    for big in [True, False]:
        # Empty input is a no-op; empty target accepts whole bytes.
        var e = BitArray(String("101"), big)
        var before = len(e)
        e.frombytes(List[UInt8]())
        assert_equal(len(e), before)
        assert_equal(e.to01(), String("101"))
        var f = BitArray(String(""), big)
        f.frombytes(u8list1(UInt8(0xCA)))
        # 0xCA reads MSB-first (big) or LSB-first (little).
        assert_equal(f.to01(), String("11001010") if big else String("01010011"))
        assert_invariants(f, big)
    # Appends (never replaces), from any alignment, both endiannesses.
    var a = BitArray(String("1"), ENDIAN_BIG)
    a.frombytes(u8list1(UInt8(0xCA)))
    assert_equal(a.to01(), String("111001010"))
    assert_equal(a.endian(), String("big"))
    var b = BitArray(String("101"), ENDIAN_BIG)
    b.frombytes(u8list1(UInt8(0xCA)))
    assert_equal(b.to01(), String("10111001010"))
    var c = BitArray(String("101"), ENDIAN_LITTLE)
    c.frombytes(u8list1(UInt8(0xCA)))
    assert_equal(c.to01(), String("10101010011"))
    # Multiple consecutive calls accumulate.
    var d = BitArray(String(""), ENDIAN_BIG)
    d.frombytes(u8list1(UInt8(0xCA)))
    d.frombytes(u8list1(UInt8(0x53)))
    assert_equal(d.to01(), String("1100101001010011"))
    # Source bytes are only read, never mutated or aliased.
    var src = u8list2(UInt8(0xCA), UInt8(0x53))
    var e = BitArray(String("1"), ENDIAN_LITTLE)
    e.frombytes(src)
    assert_bytes_equal(src, u8list2(UInt8(0xCA), UInt8(0x53)))
    assert_equal(e.to01(), String("10101001111001010"))
    assert_invariants(a, ENDIAN_BIG)
    assert_invariants(b, ENDIAN_BIG)
    assert_invariants(c, ENDIAN_LITTLE)
    assert_invariants(d, ENDIAN_BIG)


def test_bytes_roundtrip() raises:
    var sizes = List[Int]()
    for n in [0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65]:
        sizes.append(n)
    for i in range(len(sizes)):
        var n = sizes[i]
        for big in [True, False]:
            var text = String("")
            for j in range(n):
                text += String("1") if (j * 7 + 3) % 5 < 2 else String("0")
            var a = BitArray(text, big)
            var raw = a.tobytes()
            assert_equal(len(raw), (n + 7) // 8)
            var back = BitArray(String(""), big)
            back.frombytes(raw)
            # frombytes appends whole bytes (pad zeros included); the
            # caller trims to the logical length, which the framed
            # protocol carries explicitly.
            assert_equal(len(back), 8 * ((n + 7) // 8))
            assert_equal(back[:n].to01(), text)
            assert_equal(back.endian(), a.endian())
            assert_invariants(back, big)


def test_framed_roundtrip() raises:
    var cases = bitarray_vectors()
    assert_true(len(cases) > 200)
    for i in range(len(cases)):
        # Borrowed field access: BitCase owns Lists and is not copied.
        var a = BitArray(cases[i].bits, cases[i].big_endian)
        assert_equal(len(a), cases[i].nbits)
        # Packed bytes match the reference goldens exactly.
        assert_bytes_equal(a.tobytes(), cases[i].packed)
        # Canonical payload matches the golden framed bytes.
        var payload = encode_payload(a)
        assert_bytes_equal(payload, cases[i].framed)
        # Decode round-trips to the identical logical array.
        var back = decode_payload_exact(Span(cases[i].framed))
        assert_equal(back.to01(), cases[i].bits)
        assert_equal(back.big_endian, cases[i].big_endian)
        assert_equal(len(back), cases[i].nbits)
        assert_invariants(back, cases[i].big_endian)


def _payload(nbits: Int, endian_id: UInt8, data: List[UInt8]) -> List[UInt8]:
    var out = List[UInt8](capacity=5 + len(data))
    var n = UInt32(nbits)
    out.append(UInt8((n >> 24) & 0xFF))
    out.append(UInt8((n >> 16) & 0xFF))
    out.append(UInt8((n >> 8) & 0xFF))
    out.append(UInt8(n & 0xFF))
    out.append(endian_id)
    for i in range(len(data)):
        out.append(data[i])
    return out^


def test_framed_validation() raises:
    # Too short for nbits + endian id.
    with assert_raises(contains="too short"):
        _ = decode_payload_exact(Span(u8list2(UInt8(0), UInt8(1))))
    # Bad endian identifier.
    with assert_raises(contains="invalid endian"):
        _ = decode_payload_exact(Span(_payload(5, UInt8(2), u8list1(UInt8(0xB0)))))
    # Byte count mismatches in both directions.
    with assert_raises(contains="byte count"):
        _ = decode_payload_exact(Span(_payload(5, UInt8(0), List[UInt8]())))
    with assert_raises(contains="byte count"):
        _ = decode_payload_exact(Span(_payload(5, UInt8(0), u8list2(UInt8(0xB0), UInt8(0xFF)))))
    # Nonzero padding is rejected, never exposed (big: low pad bits).
    with assert_raises(contains="nonzero padding"):
        _ = decode_payload_exact(Span(_payload(5, UInt8(0), u8list1(UInt8(0xB1)))))
    # Nonzero padding is rejected for little-endian (top pad bits).
    with assert_raises(contains="nonzero padding"):
        _ = decode_payload_exact(Span(_payload(5, UInt8(1), u8list1(UInt8(0x8D)))))
    # Empty array payload decodes.
    var empty = decode_payload_exact(Span(_payload(0, UInt8(0), List[UInt8]())))
    assert_equal(len(empty), 0)
    assert_equal(empty.big_endian, True)
    # Zeroed padding decodes to the right logical bits.
    var ok = decode_payload_exact(Span(_payload(5, UInt8(0), u8list1(UInt8(0xB0)))))
    assert_equal(ok.to01(), String("10110"))
    var okl = decode_payload_exact(Span(_payload(5, UInt8(1), u8list1(UInt8(0x0D)))))
    assert_equal(okl.to01(), String("10110"))
    assert_invariants(ok, True)
    assert_invariants(okl, False)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
