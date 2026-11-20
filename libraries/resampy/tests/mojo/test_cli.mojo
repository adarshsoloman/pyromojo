"""Phase 3 native tests: framed CLI operations.

All requests are sent in ONE batched subprocess call: on this host, a
Mojo-compiled binary launched from a Mojo parent via ``std.subprocess.run``
incurs a ~17 s runtime-startup delay (verified in Phase 3 diagnostics), so one
call keeps the suite fast. Python compatibility tests cover the CLI end-to-end
without that overhead.

The runner builds the CLI with ``--fp-mode contract=off`` and sets
``RESAMPY_CLI`` to its path.
"""

from std.collections import List
from std.io import FileHandle
from std.os import getenv
from std.subprocess import run
from std.testing import TestSuite, assert_equal, assert_true

from mojo_resampy.float_codec import decode_f64le, encode_f64le
from mojo_resampy.protocol import (
    OP_COMPARE,
    OP_ECHO,
    OP_F64_DECODE,
    OP_F64_ENCODE,
    OP_FILTER_LOAD,
    OP_GOLDEN_PARSE,
    OP_GOLDEN_SERIALIZE,
    OP_OUTPUT_ALLOC,
    OP_OUTPUT_SET,
    OP_PING,
    OP_SHA256,
    OP_SIGNAL_INFO,
    STATUS_ERROR,
    STATUS_OK,
    append_u32_be,
    decode_u32_be,
)
from test_support import assert_bits_equal, positive_inf, negative_inf, quiet_nan


comptime TMP: String = "/tmp/pyromojo_resampy_phase3"


def _cli_path() raises -> String:
    var path = getenv("RESAMPY_CLI")
    if path == "":
        raise Error("RESAMPY_CLI not set; use tests/run_phase3_tests.py")
    return path


def _bytes(text: String) -> List[UInt8]:
    var out = List[UInt8]()
    for byte in text.as_bytes():
        out.append(byte)
    return out^


def _u32_bytes(value: Int) -> List[UInt8]:
    var out = List[UInt8]()
    append_u32_be(out, UInt32(value))
    return out^


def _frame(body: List[UInt8]) -> List[UInt8]:
    var out = List[UInt8]()
    append_u32_be(out, UInt32(len(body)))
    for byte in body:
        out.append(byte)
    return out^


def _run_requests(requests: List[List[UInt8]]) raises -> List[List[UInt8]]:
    var wire = List[UInt8]()
    for body in requests:
        for byte in _frame(body):
            wire.append(byte)
    var req_path = TMP + "/cli_req.bin"
    var resp_path = TMP + "/cli_resp.bin"
    var w = FileHandle(req_path, "w")
    w.write_bytes(Span(wire))
    w.close()
    _ = run(
        "\"" + _cli_path() + "\" < \"" + req_path + "\" > \"" + resp_path
        + "\" 2> /dev/null; echo ok"
    )
    var f = FileHandle(resp_path, "r")
    var raw = f.read_bytes()
    f.close()
    var out = List[List[UInt8]]()
    var offset = 0
    while offset < len(raw):
        if offset + 4 > len(raw):
            raise Error("truncated response header")
        var length = Int(decode_u32_be(raw[offset : offset + 4]))
        offset += 4
        if offset + length > len(raw):
            raise Error("truncated response body")
        var frame = List[UInt8]()
        for j in range(length):
            frame.append(raw[offset + j])
        offset += length
        out.append(frame^)
    return out^


def _status(frame: List[UInt8]) raises -> UInt8:
    return frame[0]


def _payload(frame: List[UInt8]) raises -> List[UInt8]:
    var out = List[UInt8]()
    for i in range(1, len(frame)):
        out.append(frame[i])
    return out^


def _text(frame: List[UInt8]) raises -> String:
    return String(from_utf8=Span(_payload(frame)))


def _read_bytes(path: String) raises -> List[UInt8]:
    var f = FileHandle(path, "r")
    var raw = f.read_bytes()
    f.close()
    return raw^


def _read_text(path: String) raises -> String:
    return String(from_utf8=Span(_read_bytes(path)))


def _extract_first_case(text: String) raises -> String:
    var n = text.byte_length()
    var brace_count = 0
    var start = 0
    for j in range(n):
        if text.as_bytes()[j] == 123:
            brace_count += 1
            if brace_count == 2:
                start = j
                break
    if brace_count < 2:
        raise Error("no case object found")
    var depth = 0
    var in_string = False
    var end = start
    for j in range(start, n):
        var c = text.as_bytes()[j]
        if c == 34 and (j == 0 or text.as_bytes()[j - 1] != 92):
            in_string = not in_string
        elif not in_string:
            if c == 123:
                depth += 1
            elif c == 125:
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
    var out = List[UInt8]()
    for j in range(start, end):
        out.append(text.as_bytes()[j])
    return String(from_utf8=Span(out))


def test_protocol_helpers() raises:
    """Pure framing helpers need no subprocess."""
    var out = List[UInt8]()
    append_u32_be(out, UInt32(0x01020304))
    assert_equal(out[0], 1)
    assert_equal(out[3], 4)
    assert_equal(Int(decode_u32_be(Span(out))), 0x01020304)
    var frame = _frame(_bytes("abc"))
    assert_equal(Int(decode_u32_be(frame[0:4])), 3)


def test_cli_operations_batched() raises:
    var requests = List[List[UInt8]]()

    # 0: PING
    var b0 = List[UInt8](); b0.append(OP_PING); requests.append(b0^)
    # 1: ECHO
    var b1 = List[UInt8](); b1.append(OP_ECHO); b1.append(0xAA); b1.append(0); b1.append(0xFF)
    requests.append(b1^)
    # 2: unknown opcode -> error
    var b2 = List[UInt8](); b2.append(0x7F); requests.append(b2^)
    # 3: empty frame -> error
    var b3 = List[UInt8](); requests.append(b3^)
    # 4: SIGNAL_INFO
    var sv = List[Float64](); sv.append(1.5); sv.append(-0.0); sv.append(positive_inf())
    var b4 = List[UInt8](); b4.append(OP_SIGNAL_INFO)
    for byte in encode_f64le(Span(sv)): b4.append(byte)
    requests.append(b4^)
    # 5: OUTPUT_ALLOC(5)
    var b5 = List[UInt8](); b5.append(OP_OUTPUT_ALLOC)
    for byte in _u32_bytes(5): b5.append(byte)
    requests.append(b5^)
    # 6: OUTPUT_SET(4, idx2, -0.0)
    var one = List[Float64](); one.append(-0.0)
    var b6 = List[UInt8](); b6.append(OP_OUTPUT_SET)
    for byte in _u32_bytes(4): b6.append(byte)
    for byte in _u32_bytes(2): b6.append(byte)
    for byte in encode_f64le(Span(one)): b6.append(byte)
    requests.append(b6^)
    # 7: F64_ENCODE special values
    var sp = List[Float64]()
    sp.append(1.5); sp.append(-0.0); sp.append(5e-324); sp.append(quiet_nan())
    var b7 = List[UInt8](); b7.append(OP_F64_ENCODE)
    for byte in encode_f64le(Span(sp)): b7.append(byte)
    requests.append(b7^)
    # 8: SHA256("abc")
    var b8 = List[UInt8](); b8.append(OP_SHA256); b8.append(97); b8.append(98); b8.append(99)
    requests.append(b8^)
    # 9: COMPARE equal
    var av = List[Float64](); av.append(1.0); av.append(2.0)
    var bv = List[Float64](); bv.append(1.0); bv.append(2.0)
    var tol = List[Float64](); tol.append(1e-9); tol.append(1e-9)
    var b9 = List[UInt8](); b9.append(OP_COMPARE)
    for byte in encode_f64le(Span(tol)): b9.append(byte)
    for byte in _u32_bytes(2): b9.append(byte)
    for byte in encode_f64le(Span(av)): b9.append(byte)
    for byte in _u32_bytes(2): b9.append(byte)
    for byte in encode_f64le(Span(bv)): b9.append(byte)
    requests.append(b9^)
    # 10: COMPARE different lengths
    var cv = List[Float64](); cv.append(1.0); cv.append(2.0); cv.append(3.0)
    var dv = List[Float64](); dv.append(1.0)
    var b10 = List[UInt8](); b10.append(OP_COMPARE)
    for byte in encode_f64le(Span(tol)): b10.append(byte)
    for byte in _u32_bytes(3): b10.append(byte)
    for byte in encode_f64le(Span(cv)): b10.append(byte)
    for byte in _u32_bytes(1): b10.append(byte)
    for byte in encode_f64le(Span(dv)): b10.append(byte)
    requests.append(b10^)
    # 11: COMPARE malformed -> error
    var b11 = List[UInt8](); b11.append(OP_COMPARE); b11.append(1); b11.append(2)
    requests.append(b11^)
    # 12/13: GOLDEN_PARSE / GOLDEN_SERIALIZE
    var case_text = _extract_first_case(
        _read_text("libraries/resampy/tests/vectors/representation_vectors.json")
    )
    var b12 = List[UInt8](); b12.append(OP_GOLDEN_PARSE)
    for byte in _bytes(case_text): b12.append(byte)
    requests.append(b12^)
    var b13 = List[UInt8](); b13.append(OP_GOLDEN_SERIALIZE)
    for byte in _bytes(case_text): b13.append(byte)
    requests.append(b13^)
    # 14: FILTER_LOAD valid
    var meta = _read_text("libraries/resampy/resources/synthetic/synthetic_filter.json")
    var bin_data = _read_bytes("libraries/resampy/resources/synthetic/synthetic_filter.bin")
    var b14 = List[UInt8](); b14.append(OP_FILTER_LOAD)
    for byte in _u32_bytes(meta.byte_length()): b14.append(byte)
    for byte in _bytes(meta): b14.append(byte)
    for byte in _u32_bytes(len(bin_data)): b14.append(byte)
    for byte in bin_data: b14.append(byte)
    requests.append(b14^)
    # 15: FILTER_LOAD corrupt -> error
    var corrupt = List[UInt8]()
    for byte in bin_data: corrupt.append(byte)
    corrupt[0] = UInt8((Int(corrupt[0]) + 1) & 0xFF)
    var b15 = List[UInt8](); b15.append(OP_FILTER_LOAD)
    for byte in _u32_bytes(meta.byte_length()): b15.append(byte)
    for byte in _bytes(meta): b15.append(byte)
    for byte in _u32_bytes(len(corrupt)): b15.append(byte)
    for byte in corrupt: b15.append(byte)
    requests.append(b15^)
    # 16: F64_DECODE of the Base64 produced by request 7 (round trip)
    # (inserted after computing b64 below; placeholder filled by second call)

    var frames = _run_requests(requests)
    assert_equal(len(frames), 16)

    assert_equal(_status(frames[0]), STATUS_OK)
    assert_equal(len(_payload(frames[0])), 0)
    assert_equal(_status(frames[1]), STATUS_OK)
    assert_equal(_payload(frames[1])[1], 0)
    assert_equal(_status(frames[2]), STATUS_ERROR)
    assert_equal(_status(frames[3]), STATUS_ERROR)
    var info = _text(frames[4])
    assert_true("len=3" in info)
    assert_true("first_bits=000000000000f83f" in info)
    assert_true("last_bits=000000000000f07f" in info)
    assert_true("nonfinite=1" in info)
    var alloc = decode_f64le(Span(_payload(frames[5])))
    assert_equal(len(alloc), 5)
    for i in range(5): assert_bits_equal(alloc[i], 0.0)
    var set_buf = decode_f64le(Span(_payload(frames[6])))
    assert_equal(len(set_buf), 4)
    assert_bits_equal(set_buf[2], -0.0)
    var b64_text = _text(frames[7])
    assert_true(b64_text.byte_length() > 0)
    assert_equal(
        _text(frames[8]),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    )
    assert_true("passed=1" in _text(frames[9]))
    assert_true("lengths_match=0" in _text(frames[10]))
    assert_equal(_status(frames[11]), STATUS_ERROR)
    assert_true("case_id=empty_vector" in _text(frames[12]))
    assert_true("\"schema_version\": 1" in _text(frames[13]))
    assert_true("filter_id=synthetic_tiny_v1" in _text(frames[14]))
    assert_equal(_status(frames[15]), STATUS_ERROR)

    # F64_DECODE round trip (one extra subprocess call, unavoidable for data dep)
    var dec_req = List[List[UInt8]]()
    var bd = List[UInt8](); bd.append(OP_F64_DECODE)
    for byte in _bytes(b64_text): bd.append(byte)
    dec_req.append(bd^)
    var dec_frames = _run_requests(dec_req)
    assert_equal(len(dec_frames), 1)
    assert_equal(_status(dec_frames[0]), STATUS_OK)
    var back = decode_f64le(Span(_payload(dec_frames[0])))
    assert_equal(len(back), len(sp))
    for i in range(len(sp)):
        assert_bits_equal(back[i], sp[i])


def test_cli_allocation_limits_batched() raises:
    # P2-06: semantic allocation requests are bounded and rejected cleanly.
    var requests = List[List[UInt8]]()

    # 0: zero-length allocation -> OK, empty payload
    var b0 = List[UInt8](); b0.append(OP_OUTPUT_ALLOC)
    for byte in _u32_bytes(0): b0.append(byte)
    requests.append(b0^)

    # 1: one-element allocation -> OK, 8 zero bytes
    var b1 = List[UInt8](); b1.append(OP_OUTPUT_ALLOC)
    for byte in _u32_bytes(1): b1.append(byte)
    requests.append(b1^)

    # 2: one above the maximum (1_000_001) -> ERROR frame
    var b2 = List[UInt8](); b2.append(OP_OUTPUT_ALLOC)
    for byte in _u32_bytes(1_000_001): b2.append(byte)
    requests.append(b2^)

    # 3: extremely large u32 (20_000_000) -> ERROR frame (the reported repro)
    var b3 = List[UInt8](); b3.append(OP_OUTPUT_ALLOC)
    for byte in _u32_bytes(20_000_000): b3.append(byte)
    requests.append(b3^)

    # 4: PING after rejected requests -> session continues, OK
    var b4 = List[UInt8](); b4.append(OP_PING)
    requests.append(b4^)

    var frames = _run_requests(requests)
    assert_equal(len(frames), 5)
    assert_equal(_status(frames[0]), STATUS_OK)
    assert_equal(len(_payload(frames[0])), 0)
    assert_equal(_status(frames[1]), STATUS_OK)
    assert_equal(len(_payload(frames[1])), 8)
    assert_equal(_status(frames[2]), STATUS_ERROR)
    assert_true("exceeds limit" in _text(frames[2]))
    assert_equal(_status(frames[3]), STATUS_ERROR)
    assert_true("exceeds limit" in _text(frames[3]))
    assert_equal(_status(frames[4]), STATUS_OK)  # session survived rejection


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
