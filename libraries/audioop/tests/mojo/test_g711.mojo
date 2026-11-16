"""Phase 7 native tests: G.711 A-law and mu-law codecs.

Expectations come from the Phase 7 probes of CPython 3.12.3. Covers all
four operations at every width, scaling shifts, segment boundaries,
clipping, empty fragments, encoder alignment errors, decoder
alignment-free behaviour, and exhaustive-style decoder spot checks
against the embedded reference tables.
"""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_audioop import alaw2lin, encode_fragment, lin2alaw, lin2ulaw, ulaw2lin


def list_of(*args: Int) -> List[Int]:
    var out = List[Int](capacity=len(args))
    for value in args:
        out.append(value)
    return out^


def frag(width: Int, values: List[Int]) raises -> List[UInt8]:
    var samples = List[Int64](capacity=len(values))
    for value in values:
        samples.append(Int64(value))
    return encode_fragment(Span(samples), width)


def hexs_of(bytes: List[UInt8]) raises -> String:
    var digits = List[UInt8](capacity=16)
    for i in range(16):
        if i < 10:
            digits.append(UInt8(48 + i))
        else:
            digits.append(UInt8(87 + i))
    var chars = List[UInt8](capacity=2 * len(bytes))
    for b in bytes:
        chars.append(digits[Int(b) >> 4])
        chars.append(digits[Int(b) & 15])
    return String(from_utf8=Span(chars))


def test_lin2ulaw_examples() raises:
    # [0,1,-1,4] w2 -> ff ff 7e fe
    var data = frag(2, list_of(0, 1, -1, 4))
    var result = lin2ulaw(Span(data), 2)
    assert_equal(hexs_of(result), "ffff7efe")
    # extrema at every width encode identically (scaling normalizes)
    for width in range(1, 5):
        var lo = -1 << (width * 8 - 1)
        var hi = (1 << (width * 8 - 1)) - 1
        var extrema = frag(width, list_of(hi, lo))
        assert_equal(hexs_of(lin2ulaw(Span(extrema), width)), "8000")


def test_lin2alaw_examples() raises:
    # [0,1,-1,4] w2 -> d5 d5 55 d5
    var data = frag(2, list_of(0, 1, -1, 4))
    var result = lin2alaw(Span(data), 2)
    assert_equal(hexs_of(result), "d5d555d5")
    for width in range(1, 5):
        var lo = -1 << (width * 8 - 1)
        var hi = (1 << (width * 8 - 1)) - 1
        var extrema = frag(width, list_of(hi, lo))
        assert_equal(hexs_of(lin2alaw(Span(extrema), width)), "aa2a")


def test_encoder_width_scaling() raises:
    # w1: sample * 64 (ulaw) / * 32 (alaw)
    var w1 = frag(1, list_of(127, -128))
    assert_equal(hexs_of(lin2ulaw(Span(w1), 1)), "8000")
    assert_equal(hexs_of(lin2alaw(Span(w1), 1)), "aa2a")
    # w2: sample >> 2 (ulaw) / >> 3 (alaw)
    var w2 = frag(2, list_of(8191, -8192))
    # 8191 >> 2 = 2047 -> segment 6 -> 0x9f; -8192 >> 2 -> 0x1f
    assert_equal(hexs_of(lin2ulaw(Span(w2), 2)), "9f1f")
    var w2a = frag(2, list_of(4095, -4096))
    # 4095 >> 3 = 511 -> segment 4 -> 0x9a; -4096 >> 3 -> 0x1a
    assert_equal(hexs_of(lin2alaw(Span(w2a), 2)), "9a1a")
    # w4: sample >> 18 (ulaw) / >> 19 (alaw)
    var w4u = frag(4, list_of(2147483647, -2147483648))
    assert_equal(hexs_of(lin2ulaw(Span(w4u), 4)), "8000")
    var w4a = frag(4, list_of(2147483647, -2147483648))
    assert_equal(hexs_of(lin2alaw(Span(w4a), 4)), "aa2a")


def test_ulaw_segment_boundaries() raises:
    # 14-bit values around seg_uend, encoded at w4 (sample >> 18)
    var values = list_of(30, 31, 32, 63, 64, 255, 256, 511, 512, 8191, 0, -1)
    var samples = List[Int64](capacity=12)
    for value in values:
        samples.append(Int64(value) << 18)
    var data = encode_fragment(Span(samples), 4)
    var expected = "f0efefe7e7cdcdbebe80ff7e"
    assert_equal(hexs_of(lin2ulaw(Span(data), 4)), expected)


def test_alaw_segment_boundaries() raises:
    # 13-bit values around seg_aend, encoded at w4 (sample >> 19)
    var values = list_of(30, 31, 32, 63, 64, 255, 256, 511, 512, 4095, 0, -1)
    var samples = List[Int64](capacity=12)
    for value in values:
        samples.append(Int64(value) << 19)
    var data = encode_fragment(Span(samples), 4)
    var expected = "dadac5caf5ea959a85aad555"
    assert_equal(hexs_of(lin2alaw(Span(data), 4)), expected)


def test_encoder_empty_and_validation() raises:
    assert_equal(len(lin2ulaw(Span(List[UInt8]()), 2)), 0)
    assert_equal(len(lin2alaw(Span(List[UInt8]()), 2)), 0)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = lin2ulaw(Span(List[UInt8]()), 0)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = lin2alaw(Span(List[UInt8]()), 5)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        _ = lin2ulaw(Span(odd), 2)
    with assert_raises(contains="not a whole number of frames"):
        var odd3 = List[UInt8]()
        odd3.append(1)
        odd3.append(2)
        odd3.append(3)
        _ = lin2alaw(Span(odd3), 2)


def test_ulaw2lin_table_spot_checks() raises:
    # reference table values: 0x00 -> -32124, 0x80 -> 32124, 0xff -> 0
    var codes = List[UInt8](capacity=6)
    codes.append(0x00)
    codes.append(0x7F)
    codes.append(0x80)
    codes.append(0xFF)
    codes.append(0x55)
    codes.append(0xAA)
    var result = ulaw2lin(Span(codes), 2)
    assert_equal(hexs_of(result), "848200007c7d000034fdfc14")


def test_alaw2lin_table_spot_checks() raises:
    # reference table: 0x00 -> -5504, 0xd5 -> 5504, 0x2a -> 2688, 0xff -> -8032
    var codes = List[UInt8](capacity=5)
    codes.append(0x00)
    codes.append(0xD5)
    codes.append(0x2A)
    codes.append(0xFF)
    codes.append(0x55)
    var result = alaw2lin(Span(codes), 2)
    # 0x00 -> -5504 (80ea LE); 0xd5 -> 5504; 0x2a -> 2688; 0xff -> -8032; 0x55 -> -8
    assert_equal(hexs_of(result), "80ea080000825003f8ff")


def test_decoder_widths() raises:
    # 0x00 decodes to -32124 at 16 bits; narrower widths truncate the
    # top-aligned store: w1 = -32124 >> 8 = -126, w3 = -32124 << 8,
    # w4 = -32124 << 16
    var code = List[UInt8](capacity=1)
    code.append(0x00)
    var w1 = ulaw2lin(Span(code), 1)
    assert_equal(w1[0], UInt8(0x82))
    var w2 = ulaw2lin(Span(code), 2)
    assert_equal(w2[0], UInt8(0x84))
    assert_equal(w2[1], UInt8(0x82))
    var w3 = ulaw2lin(Span(code), 3)
    assert_equal(hexs_of(w3), "008482")
    var w4 = ulaw2lin(Span(code), 4)
    assert_equal(hexs_of(w4), "00008482")
    var a_w1 = alaw2lin(Span(code), 1)
    # -5504 >> 8 = -22 (floor -21.5 -> -22)
    assert_equal(a_w1[0], UInt8(0xEA))
    var a_w2 = alaw2lin(Span(code), 2)
    assert_equal(hexs_of(a_w2), "80ea")


def test_decoder_no_alignment_required() raises:
    # decoders accept any byte length (check_size only)
    var three = List[UInt8](capacity=3)
    three.append(0x00)
    three.append(0xD5)
    three.append(0x55)
    var result = alaw2lin(Span(three), 2)
    assert_equal(len(result), 6)
    var u_three = ulaw2lin(Span(three), 2)
    assert_equal(len(u_three), 6)
    assert_equal(len(ulaw2lin(Span(List[UInt8]()), 2)), 0)
    assert_equal(len(alaw2lin(Span(List[UInt8]()), 2)), 0)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = ulaw2lin(Span(List[UInt8]()), 0)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = alaw2lin(Span(List[UInt8]()), 7)


def test_roundtrips() raises:
    var source = frag(2, list_of(0, 1, -1, 100, -100, 32767, -32768))
    var ulaw_code = lin2ulaw(Span(source), 2)
    var back = ulaw2lin(Span(ulaw_code), 2)
    assert_equal(hexs_of(back), "00000000f8ff680098ff7c7d8482")
    var alaw_code = lin2alaw(Span(source), 2)
    var a_back = alaw2lin(Span(alaw_code), 2)
    assert_equal(hexs_of(a_back), "08000800f8ff680098ff007e0082")


def test_repeated_and_alternating() raises:
    var repeated = frag(2, list_of(1000, 1000, 1000))
    var u = lin2ulaw(Span(repeated), 2)
    assert_equal(u[0], u[1])
    assert_equal(u[1], u[2])
    var alternating = frag(2, list_of(1, -1, 1, -1))
    var a = lin2alaw(Span(alternating), 2)
    assert_equal(hexs_of(a), "d555d555")


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
