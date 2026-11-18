"""Phase 3 native tests: Float64/Base64/Hex codec and SHA-256."""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_true, assert_raises

from mojo_resampy.float_codec import (
    base64_decode_bytes,
    base64_encode_bytes,
    bits_to_float64,
    bytes_to_hex,
    decode_f64le,
    encode_f64le,
    float64_to_bits,
    hex_to_bytes,
)
from mojo_resampy.sha256 import sha256_hex, sha256_hex_of_f64le
from test_support import assert_bits_equal, special_values, positive_inf, negative_inf, quiet_nan


def test_float64_bits_roundtrip() raises:
    var vals = special_values()
    for i in range(len(vals)):
        assert_bits_equal(bits_to_float64(float64_to_bits(vals[i])), vals[i])


def test_encode_decode_f64le_exact() raises:
    var vals = special_values()
    var raw = encode_f64le(Span(vals))
    assert_equal(len(raw), len(vals) * 8)
    var back = decode_f64le(Span(raw))
    assert_equal(len(back), len(vals))
    for i in range(len(vals)):
        assert_bits_equal(back[i], vals[i])


def test_signed_zero_bits_preserved() raises:
    var v = List[Float64]()
    v.append(-0.0)
    var raw = encode_f64le(Span(v))
    assert_equal(bytes_to_hex(Span(raw)), "0000000000000080")


def test_subnormal_bits_preserved() raises:
    var v = List[Float64]()
    v.append(5e-324)
    var raw = encode_f64le(Span(v))
    assert_equal(bytes_to_hex(Span(raw)), "0100000000000000")


def test_nan_payload_bits_preserved() raises:
    var nan_bits: UInt64 = 0x7FF8123456789ABC
    var v = List[Float64]()
    v.append(bits_to_float64(nan_bits))
    var raw = encode_f64le(Span(v))
    assert_equal(bytes_to_hex(Span(raw)), "bc9a78563412f87f")


def test_decode_rejects_misaligned_length() raises:
    var raw = List[UInt8]()
    raw.append(1)
    raw.append(2)
    raw.append(3)
    with assert_raises():
        _ = decode_f64le(Span(raw))


def test_bytes_hex_roundtrip() raises:
    var b = List[UInt8]()
    b.append(0)
    b.append(255)
    b.append(16)
    b.append(171)
    assert_equal(bytes_to_hex(Span(b)), "00ff10ab")
    var back = hex_to_bytes("00ff10ab")
    assert_equal(len(back), 4)
    assert_equal(back[0], 0)
    assert_equal(back[1], 255)


def test_hex_rejects_odd_length() raises:
    with assert_raises():
        _ = hex_to_bytes("abc")


def test_hex_rejects_bad_char() raises:
    with assert_raises():
        _ = hex_to_bytes("zz")


def test_base64_roundtrip() raises:
    var raw = encode_f64le(Span(special_values()))
    var text = base64_encode_bytes(Span(raw))
    var back = base64_decode_bytes(text)
    assert_equal(len(back), len(raw))
    for i in range(len(raw)):
        assert_equal(back[i], raw[i])


def test_base64_empty() raises:
    assert_equal(base64_encode_bytes(Span(List[UInt8]())), "")
    assert_equal(len(base64_decode_bytes("")), 0)


def test_base64_rejects_whitespace() raises:
    with assert_raises():
        _ = base64_decode_bytes("YQ==\n")


def test_base64_rejects_missing_padding() raises:
    with assert_raises():
        _ = base64_decode_bytes("YQ")


def test_base64_rejects_bad_char() raises:
    with assert_raises():
        _ = base64_decode_bytes("YQ!=")


def test_sha256_known_vectors() raises:
    var abc = List[UInt8]()
    abc.append(97)
    abc.append(98)
    abc.append(99)
    assert_equal(
        sha256_hex(Span(abc)),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    )
    assert_equal(
        sha256_hex(Span(List[UInt8]())),
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    var hello = List[UInt8]()
    for byte in String("hello").as_bytes():
        hello.append(byte)
    assert_equal(
        sha256_hex(Span(hello)),
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
    )


def test_sha256_multiblock() raises:
    var data = List[UInt8]()
    for i in range(200):
        data.append(UInt8(i & 0xFF))
    assert_equal(sha256_hex(Span(data)).byte_length(), 64)


def test_sha256_of_f64le() raises:
    var v = List[Float64]()
    v.append(1.5)
    assert_equal(sha256_hex_of_f64le(Span(v)), sha256_hex(Span(encode_f64le(Span(v)))))


def _bytes_pattern(n: Int) -> List[UInt8]:
    var out = List[UInt8](capacity=n)
    for i in range(n):
        out.append(UInt8((i * 37 + 11) & 0xFF))
    return out^


def test_sha256_padding_boundaries() raises:
    # Independently computed with Python hashlib; covers the 56/64-byte
    # padding thresholds and multi-block transitions.
    assert_equal(sha256_hex(Span(_bytes_pattern(55))), "2900465fcb533e05a158fd2b3be0e5e3b03740d83060aa3580e0d98a96bf2384")
    assert_equal(sha256_hex(Span(_bytes_pattern(56))), "31454ff48ef36af2f08fd511bdc37d9d5855ac23e992e5ff5445cb6b7674a674")
    assert_equal(sha256_hex(Span(_bytes_pattern(57))), "bcc0a5d3791b985b7550e04ca660a6c63a589ba1edd2283c8e110e5b515df124")
    assert_equal(sha256_hex(Span(_bytes_pattern(63))), "5f6401b96532c36de4e65beec0409b69b1d181864c8009b7a04f43e5d56350d1")
    assert_equal(sha256_hex(Span(_bytes_pattern(64))), "94eb5de4943613fd048dc93393ab06877405faa39c11f53e9386083339833e7e")
    assert_equal(sha256_hex(Span(_bytes_pattern(65))), "fc518669b6eb4b4dd91827ecacef86689c725bd5bab888fd3b26dbb196eec954")
    assert_equal(sha256_hex(Span(_bytes_pattern(119))), "b0dc41b1a384e2f1203f0351b38fbeaafceef577ce1191d5bfc25da39f721eae")
    assert_equal(sha256_hex(Span(_bytes_pattern(120))), "5df24dd802ac26132ce608dcb5f09841eef039ee0f152acf98d26d17fe4e88e6")
    assert_equal(sha256_hex(Span(_bytes_pattern(127))), "0fe729ff19257bd6fec853acc2ea355f6b34b58e6c0f684c3e188fcdfcd9baae")
    assert_equal(sha256_hex(Span(_bytes_pattern(128))), "0aedd4856f8eba0963627336ad5144a9a7dbe12498e6066f0165fc97d8ddee4c")
    assert_equal(sha256_hex(Span(_bytes_pattern(129))), "4f1757ae4bffbae86d775b831765b75af154d52f7deaa46dd378051a2d3ad57f")


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
