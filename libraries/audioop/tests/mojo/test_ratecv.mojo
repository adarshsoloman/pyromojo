"""Phase 6 native tests: stateful sample-rate conversion.

Expectations come from the Phase 6 probes of CPython 3.12.3. Covers all
widths, mono/multichannel, equal/upsample/downsample rates, custom
weights, empty and short inputs, validation order, state initialization
and reuse, chunk equivalence, and the exact output byte sequences.
"""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_raises

from mojo_audioop import RatecvState, encode_fragment, ratecv, ratecv_continue


def list_of(*args: Int) -> List[Int]:
    var out = List[Int](capacity=len(args))
    for value in args:
        out.append(value)
    return out^


def _one_byte() -> List[UInt8]:
    var out = List[UInt8](capacity=1)
    out.append(1)
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


def copy_state(src: RatecvState, chans: Int) -> RatecvState:
    var prev = List[Int64](capacity=chans)
    var cur = List[Int64](capacity=chans)
    for i in range(chans):
        prev.append(src.prev_i[i])
        cur.append(src.cur_i[i])
    return RatecvState(src.d, prev^, cur^)


def test_ratecv_basics_match_reference() raises:
    # one sample 8k->8k: e803, state (-1, ((0, 65536000),))
    var one = frag(2, list_of(1000))
    var r = ratecv(Span(one), 2, 1, 8000, 8000)
    assert_equal(hexs_of(r.output), "e803")
    assert_equal(r.state.d, -1)
    assert_equal(r.state.prev_i[0], 0)
    assert_equal(r.state.cur_i[0], 65536000)

    var two = frag(2, list_of(1000, -1000))
    var r2 = ratecv(Span(two), 2, 1, 8000, 8000)
    assert_equal(hexs_of(r2.output), "e80318fc")
    assert_equal(r2.state.prev_i[0], 65536000)
    assert_equal(r2.state.cur_i[0], -65536000)

    # empty: (b"", (-1, zeros)) after gcd reduction of 8000/8000
    var empty = ratecv(Span(List[UInt8]()), 2, 1, 8000, 16000)
    assert_equal(len(empty.output), 0)
    assert_equal(empty.state.d, -2)
    assert_equal(empty.state.prev_i[0], 0)
    assert_equal(empty.state.cur_i[0], 0)


def test_ratecv_width_scaling() raises:
    # GETSAMPLE32 scaling: w1 sample 100 -> 100 * 2^24 = 1677721600
    var w1 = frag(1, list_of(100))
    var r1 = ratecv(Span(w1), 1, 1, 8000, 8000)
    assert_equal(hexs_of(r1.output), "64")
    assert_equal(r1.state.cur_i[0], 1677721600)
    # w4 is unshifted
    var w4 = frag(4, list_of(100000))
    var r4 = ratecv(Span(w4), 4, 1, 8000, 8000)
    assert_equal(hexs_of(r4.output), "a0860100")
    assert_equal(r4.state.cur_i[0], 100000)


def test_ratecv_all_widths_boundaries() raises:
    for width in range(1, 5):
        var lo = -1 << (width * 8 - 1)
        var hi = (1 << (width * 8 - 1)) - 1
        var data = frag(width, list_of(lo, hi))
        var result = ratecv(Span(data), width, 1, 8000, 8000)
        assert_equal(len(result.output), 2 * width)
        # equal rates store the filtered samples back through the same
        # top-aligned shift, so the first output byte is the lo sample
        if width == 1:
            assert_equal(result.output[0], UInt8(0x80))
        elif width == 2:
            assert_equal(result.output[0], UInt8(0x00))
            assert_equal(result.output[1], UInt8(0x80))


def test_ratecv_multichannel() raises:
    var stereo = frag(2, list_of(100, -100, 200, -200))
    var r = ratecv(Span(stereo), 2, 2, 8000, 8000)
    assert_equal(hexs_of(r.output), "64009cffc80038ff")
    assert_equal(len(r.state.prev_i), 2)
    assert_equal(len(r.state.cur_i), 2)
    assert_equal(r.state.prev_i[0], 6553600)
    assert_equal(r.state.cur_i[1], -13107200)


def test_ratecv_upsample_downsample() raises:
    var source = frag(2, list_of(-10, -9, -8, -7, -6))
    var up = ratecv(Span(source), 2, 1, 8000, 16000)
    # outputs per frame: 1 (from d=0) then 2 per remaining frame
    assert_equal(len(up.output), 18)

    var down_source = frag(2, list_of(-10, -9, -8, -7, -6))
    var down = ratecv(Span(down_source), 2, 1, 16000, 8000)
    # one output per two input frames, plus the boundary phase
    assert_equal(len(down.output), 6)


def test_ratecv_custom_weights() raises:
    var data = frag(2, list_of(1000, -1000))
    # gcd(5, 0) = 5 -> (1, 0): identical to the default filter
    var r50 = ratecv(Span(data), 2, 1, 8000, 8000, 5, 0)
    var r10 = ratecv(Span(data), 2, 1, 8000, 8000)
    assert_equal(hexs_of(r50.output), hexs_of(r10.output))

    # weights (2, 1): filtered value (2*cur + 1*prev) / 3
    var two = frag(2, list_of(1000, 1000))
    var r21 = ratecv(Span(two), 2, 1, 8000, 8000, 2, 1)
    # f2: prev=(2*65536000)/3=43690666, cur=65536000
    # -> (2*65536000 + 43690666)/3 = 58254222 (truncated toward zero)
    assert_equal(r21.state.cur_i[0], 58254222)


def test_ratecv_validation_order() raises:
    var empty = List[UInt8]()
    with assert_raises(contains="Size should be 1, 2, 3 or 4"):
        _ = ratecv(Span(empty), 0, 1, 1, 1)
    with assert_raises(contains="# of channels should be >= 1"):
        _ = ratecv(Span(empty), 2, 0, 1, 1)
    with assert_raises(contains="width * nchannels too big for a C int"):
        _ = ratecv(Span(empty), 4, 1073741824, 1, 1)
    with assert_raises(contains="weightA should be >= 1, weightB should be >= 0"):
        _ = ratecv(Span(empty), 2, 1, 1, 1, 0, 0)
    with assert_raises(contains="not a whole number of frames"):
        _ = ratecv(Span(_one_byte()), 2, 1, 1, 1)
    # alignment is checked before rates
    with assert_raises(contains="not a whole number of frames"):
        _ = ratecv(Span(_one_byte()), 2, 1, 0, 1)
    with assert_raises(contains="sampling rate not > 0"):
        _ = ratecv(Span(empty), 2, 1, 0, 1)
    with assert_raises(contains="sampling rate not > 0"):
        _ = ratecv(Span(empty), 2, 1, 1, 0)
    # argument conversion precedes body validation
    with assert_raises(contains="Python int too large to convert to C int"):
        _ = ratecv(Span(empty), 2, 1, 1099511627776, 1)
    with assert_raises(contains="Python int too large to convert to C int"):
        _ = ratecv(Span(empty), 2, 1099511627776, 1, 1)
    with assert_raises(contains="Python int too large to convert to C int"):
        _ = ratecv(Span(empty), 2, 1, 1, 1, 1099511627776, 0)


def test_ratecv_state_reuse() raises:
    # continue from a captured state; d and filter history carry over
    var first = frag(2, list_of(1000, -1000))
    var r1 = ratecv(Span(first), 2, 1, 8000, 8000)
    var state = copy_state(r1.state, 1)
    var second = frag(2, list_of(1000, -1000))
    var r2 = ratecv_continue(Span(second), 2, 1, 8000, 8000, state^)
    # after the second fragment: prev = 65536000, cur = -65536000
    assert_equal(r2.state.prev_i[0], 65536000)
    assert_equal(r2.state.cur_i[0], -65536000)
    assert_equal(r2.state.d, -1)


def test_ratecv_chunk_equivalence() raises:
    var values = list_of(
        -10, -9, -8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9
    )
    var full = frag(2, values)
    var whole = ratecv(Span(full), 2, 1, 8000, 16000)
    var whole_len = len(whole.output)
    var final_d = whole.state.d
    var final_prev = whole.state.prev_i[0]
    var final_cur = whole.state.cur_i[0]
    var final_state = copy_state(whole.state, 1)

    var c1 = ratecv(Span(frag(2, list_of(-10, -9, -8, -7))), 2, 1, 8000, 16000)
    var st2 = copy_state(c1.state, 1)
    var c2 = ratecv_continue(
        Span(frag(2, list_of(-6, -5, -4, -3, -2, -1, 0, 1))), 2, 1, 8000, 16000, st2^
    )
    var st3 = copy_state(c2.state, 1)
    var c3 = ratecv_continue(
        Span(frag(2, list_of(2, 3, 4, 5, 6, 7, 8, 9))), 2, 1, 8000, 16000, st3^
    )
    assert_equal(whole_len, len(c1.output) + len(c2.output) + len(c3.output))
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
    assert_equal(final_d, c3.state.d)
    assert_equal(final_prev, c3.state.prev_i[0])
    assert_equal(final_cur, c3.state.cur_i[0])
    _ = final_state


def test_ratecv_chunk_equivalence_multichannel() raises:
    var values = list_of(1, -2, 3, -4, 5, -6, 7, -8)
    var full = frag(2, values)
    var whole = ratecv(Span(full), 2, 2, 8000, 44100)
    var final_d = whole.state.d
    var final_prev0 = whole.state.prev_i[0]
    var final_cur1 = whole.state.cur_i[1]

    var c1 = ratecv(Span(frag(2, list_of(1, -2))), 2, 2, 8000, 44100)
    var st = copy_state(c1.state, 2)
    var c2 = ratecv_continue(Span(frag(2, list_of(3, -4, 5, -6))), 2, 2, 8000, 44100, st^)
    var st2 = copy_state(c2.state, 2)
    var c3 = ratecv_continue(Span(frag(2, list_of(7, -8))), 2, 2, 8000, 44100, st2^)
    var total = len(c1.output) + len(c2.output) + len(c3.output)
    assert_equal(len(whole.output), total)
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
    assert_equal(final_d, c3.state.d)
    assert_equal(final_prev0, c3.state.prev_i[0])
    assert_equal(final_cur1, c3.state.cur_i[1])


def test_ratecv_empty_chunks_compose() raises:
    var full = frag(2, list_of(1, 2, 3, 4))
    var whole = ratecv(Span(full), 2, 1, 8000, 16000)
    var final_d = whole.state.d

    var c1 = ratecv(Span(frag(2, list_of(1, 2))), 2, 1, 8000, 16000)
    var empty_result = ratecv_continue(Span(List[UInt8]()), 2, 1, 8000, 16000, copy_state(c1.state, 1)^)
    assert_equal(len(empty_result.output), 0)
    assert_equal(empty_result.state.d, c1.state.d)
    var st = copy_state(empty_result.state, 1)
    var c2 = ratecv_continue(Span(frag(2, list_of(3, 4))), 2, 1, 8000, 16000, st^)
    var idx = 0
    for i in range(len(c1.output)):
        assert_equal(whole.output[idx], c1.output[i])
        idx += 1
    for i in range(len(c2.output)):
        assert_equal(whole.output[idx], c2.output[i])
        idx += 1
    assert_equal(len(whole.output), idx)
    assert_equal(final_d, c2.state.d)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
