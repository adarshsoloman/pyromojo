"""Phase 8 native tests: Intel/DVI ADPCM encode and decode.

Expectations come from the Phase 8 probes of CPython 3.12.3. Covers
both operations at every width, the full nibble sweep, byte packing,
odd-sample nibble dropping, predictor/index clamping, empty inputs,
state continuity, and chunk composition (even encoder chunks; decoder
chunks of any size).
"""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_audioop import AdpcmState, adpcm2lin, encode_fragment, lin2adpcm


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


def test_lin2adpcm_matches_reference() raises:
    # [32767,-32768,0,-1,1] w2 -> 7f28, state (2, 13)
    var data = frag(2, list_of(32767, -32768, 0, -1, 1))
    var result = lin2adpcm(Span(data), 2, AdpcmState(0, 0)^)
    assert_equal(hexs_of(result.output), "7f28")
    assert_equal(result.state.valpred, 2)
    assert_equal(result.state.index, 13)
    # all widths produce the same bytes for this fragment
    for width in range(3, 5):
        var lo = -1 << (width * 8 - 1)
        var hi = (1 << (width * 8 - 1)) - 1
        var wide = frag(width, list_of(hi, lo, 0, -1, 1))
        var r = lin2adpcm(Span(wide), width, AdpcmState(0, 0)^)
        assert_equal(hexs_of(r.output), "7f28")
        assert_equal(r.state.valpred, 2)
    # width 1 scales samples up by 256: different quantization
    var w1 = frag(1, list_of(127, -128, 0, -1, 1))
    var r1 = lin2adpcm(Span(w1), 1, AdpcmState(0, 0)^)
    assert_equal(hexs_of(r1.output), "7f2f")
    assert_equal(r1.state.valpred, 69)


def test_lin2adpcm_odd_sample_count() raises:
    # one sample: no output bytes, state still updated
    var one = frag(2, list_of(1000))
    var r = lin2adpcm(Span(one), 2, AdpcmState(0, 0)^)
    assert_equal(len(r.output), 0)
    assert_equal(r.state.valpred, 11)
    assert_equal(r.state.index, 8)
    # three samples: one output byte, third nibble dropped, state updated
    var three = frag(2, list_of(1, 2, 3))
    var r3 = lin2adpcm(Span(three), 2, AdpcmState(0, 0)^)
    assert_equal(len(r3.output), 1)
    assert_equal(r3.state.valpred, 3)
    assert_equal(r3.state.index, 0)


def test_lin2adpcm_empty_keeps_state() raises:
    var state = AdpcmState(100, 50)
    var r = lin2adpcm(Span(List[UInt8]()), 2, state^)
    assert_equal(len(r.output), 0)
    assert_equal(r.state.valpred, 100)
    assert_equal(r.state.index, 50)


def test_lin2adpcm_validation() raises:
    var empty = List[UInt8]()
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = lin2adpcm(Span(empty), 0, AdpcmState(0, 0)^)
    with assert_raises(contains="not a whole number of frames"):
        var odd = List[UInt8]()
        odd.append(1)
        _ = lin2adpcm(Span(odd), 2, AdpcmState(0, 0)^)
    with assert_raises(contains="bad state"):
        _ = lin2adpcm(Span(empty), 2, AdpcmState(32768, 0)^)
    with assert_raises(contains="bad state"):
        _ = lin2adpcm(Span(empty), 2, AdpcmState(0, 89)^)
    with assert_raises(contains="bad state"):
        _ = lin2adpcm(Span(empty), 2, AdpcmState(0, -1)^)
    # boundary state values are valid
    _ = lin2adpcm(Span(empty), 2, AdpcmState(-32768, 88)^)


def test_adpcm2lin_matches_reference() raises:
    # 0x7f 0x28 from a fresh state -> 0b00edff0200ffff, state (-1, 14)
    var data = List[UInt8](capacity=2)
    data.append(0x7F)
    data.append(0x28)
    var r = adpcm2lin(Span(data), 2, AdpcmState(0, 0)^)
    assert_equal(hexs_of(r.output), "0b00edff0200ffff")
    assert_equal(r.state.valpred, -1)
    assert_equal(r.state.index, 14)


def test_adpcm2lin_nibble_sweep() raises:
    # high nibble 0..15 from a fresh state; two samples per byte
    var expected_outputs = [
        "00000000", "01000100", "03000300", "04000400",
        "07000800", "08000900", "0a000b00", "0b000d00",
        "00000000", "ffffffff", "fdfffdff", "fcfffcff",
        "f9fffaff", "f8fff9ff", "f6fff7ff", "f5fff7ff",
    ]
    var expected_valpreds = list_of(
        0, 1, 3, 4, 8, 9, 11, 13, 0, -1, -3, -4, -6, -7, -9, -9
    )
    var expected_indexes = list_of(0, 0, 0, 0, 1, 3, 5, 7, 0, 0, 0, 0, 1, 3, 5, 7)
    for nibble in range(16):
        var data = List[UInt8](capacity=1)
        data.append(UInt8(nibble << 4))
        var r = adpcm2lin(Span(data), 2, AdpcmState(0, 0)^)
        assert_equal(hexs_of(r.output), expected_outputs[nibble])
        assert_equal(r.state.valpred, Int64(expected_valpreds[nibble]))
        assert_equal(r.state.index, Int64(expected_indexes[nibble]))


def test_adpcm2lin_widths_and_no_alignment() raises:
    var data = List[UInt8](capacity=3)
    data.append(0x01)
    data.append(0x02)
    data.append(0x03)
    var r2 = adpcm2lin(Span(data), 2, AdpcmState(0, 0)^)
    assert_equal(hexs_of(r2.output), "000001000100040004000800")
    var single = List[UInt8](capacity=1)
    single.append(0x01)
    var w1 = adpcm2lin(Span(single), 1, AdpcmState(0, 0)^)
    assert_equal(len(w1.output), 2)
    assert_equal(len(adpcm2lin(Span(List[UInt8]()), 2, AdpcmState(0, 0)^).output), 0)
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = adpcm2lin(Span(List[UInt8]()), 0, AdpcmState(0, 0)^)
    with assert_raises(contains="bad state"):
        _ = adpcm2lin(Span(List[UInt8]()), 2, AdpcmState(0, 100)^)


def test_state_reuse_encoder_decoder() raises:
    # continued encoder state changes the output
    var first = frag(2, list_of(-10, -9, -8, -7))
    var r1 = lin2adpcm(Span(first), 2, AdpcmState(0, 0)^)
    var st = AdpcmState(r1.state.valpred, r1.state.index)
    var second = frag(2, list_of(-6, -5, -4, -3))
    var r2 = lin2adpcm(Span(second), 2, st^)
    var fresh = lin2adpcm(Span(second), 2, AdpcmState(0, 0)^)
    var r2_hex = hexs_of(r2.output)
    var fresh_hex = hexs_of(fresh.output)
    _ = r2
    _ = fresh
    assert_equal(r2_hex != fresh_hex, True)

    # continued decoder state differs from a fresh decode
    # nibble 2 leaves state (3, 0), which differs from a fresh (0, 0)
    var codes = List[UInt8](capacity=1)
    codes.append(0x20)
    var d1 = adpcm2lin(Span(codes), 2, AdpcmState(0, 0)^)
    var dst = AdpcmState(d1.state.valpred, d1.state.index)
    var d2 = adpcm2lin(Span(codes), 2, dst^)
    var dfresh = adpcm2lin(Span(codes), 2, AdpcmState(0, 0)^)
    var d2_hex = hexs_of(d2.output)
    var dfresh_hex = hexs_of(dfresh.output)
    _ = d2
    _ = dfresh
    assert_equal(d2_hex != dfresh_hex, True)


def test_encoder_even_chunk_composition() raises:
    var values = list_of(
        -10, -9, -8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9
    )
    var full = frag(2, values)
    var whole = lin2adpcm(Span(full), 2, AdpcmState(0, 0)^)
    var c1 = lin2adpcm(Span(frag(2, list_of(-10, -9, -8, -7))), 2, AdpcmState(0, 0)^)
    var st = AdpcmState(c1.state.valpred, c1.state.index)
    var c2 = lin2adpcm(
        Span(frag(2, list_of(-6, -5, -4, -3, -2, -1, 0, 1))), 2, st^
    )
    var st2 = AdpcmState(c2.state.valpred, c2.state.index)
    var c3 = lin2adpcm(
        Span(frag(2, list_of(2, 3, 4, 5, 6, 7, 8, 9))), 2, st2^
    )
    var idx = 0
    for i in range(len(c1.output)):
        assert_equal(whole.output[idx], c1.output[i])
        idx += 1
    for i in range(len(c2.output)):
        assert_equal(whole.output[idx], c2.output[i])
        idx += 1
    for i in range(len(c3.output)):
        assert_equal(whole.output[idx], c3.output[i])
        idx += 1
    assert_equal(len(whole.output), idx)
    assert_equal(whole.state.valpred, c3.state.valpred)
    assert_equal(whole.state.index, c3.state.index)


def test_encoder_odd_chunk_boundaries_differ() raises:
    # an odd chunk drops its trailing nibble entirely and the next chunk
    # starts a fresh buffer, so odd-chunk concatenation is NOT byte-equal
    # to the whole encoding (documented CPython behaviour): [1,2,3,4]
    # encodes to 2 bytes whole, but 3+1 splits give 1 byte + 0 bytes
    var whole = lin2adpcm(Span(frag(2, list_of(1, 2, 3, 4))), 2, AdpcmState(0, 0)^)
    assert_equal(hexs_of(whole.output), "1111")
    var c1 = lin2adpcm(Span(frag(2, list_of(1, 2, 3))), 2, AdpcmState(0, 0)^)
    assert_equal(hexs_of(c1.output), "11")
    assert_equal(c1.state.valpred, 3)
    var st = AdpcmState(c1.state.valpred, c1.state.index)
    var c2 = lin2adpcm(Span(frag(2, list_of(4))), 2, st^)
    assert_equal(len(c2.output), 0)


def test_decoder_chunk_composition() raises:
    var values = list_of(
        -10, -9, -8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9
    )
    var full = frag(2, values)
    var encoded = lin2adpcm(Span(full), 2, AdpcmState(0, 0)^)
    var dec_whole = adpcm2lin(Span(encoded.output), 2, AdpcmState(0, 0)^)
    var st = AdpcmState(0, 0)
    var chunk_parts = List[UInt8]()
    for start in range(0, len(encoded.output), 2):
        var end = start + 2
        if end > len(encoded.output):
            end = len(encoded.output)
        var chunk = List[UInt8]()
        for i in range(start, end):
            chunk.append(encoded.output[i])
        var part = adpcm2lin(Span(chunk), 2, st^)
        for b in part.output:
            chunk_parts.append(b)
        st = AdpcmState(part.state.valpred, part.state.index)
    assert_equal(len(chunk_parts), len(dec_whole.output))
    for i in range(len(chunk_parts)):
        assert_equal(chunk_parts[i], dec_whole.output[i])
    assert_equal(st.valpred, dec_whole.state.valpred)
    assert_equal(st.index, dec_whole.state.index)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
